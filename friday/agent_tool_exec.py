"""Agent 工具执行 mixin —— 从 agent.py 拆分。"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from friday.agent_events import (
    EVENT_APPROVAL_AUTO,
    EVENT_FILE_CHANGE,
    EVENT_FILE_GENERATED,
    EVENT_IMAGE_GENERATED,
    EVENT_OPERATION_LOGGED,
    EVENT_PLAN_UPDATED,
    EVENT_PROGRESS,
    EVENT_TOOL_START,
    EVENT_ASK_BLOCKED,
)
from friday.brain import ChatCompletionResult
from friday.config import MAX_TOOL_RESULT_CHARS
from friday.logging_config import get_logger
from friday.operations import log_operation_from_meta
from friday.ppt_task import (
    block_draft_document_during_ppt_message,
    block_plugin_list_during_ppt_message,
    block_powershell_read_during_ppt_message,
)
from friday.safety import (
    PendingAction,
    RiskLevel,
    TurnApprovalState,
    classify_tool,
    describe_approval_plain,
    evaluate_tool,
    mark_turn_approved,
    should_request_approval,
    summarize_action,
    summarize_preview,
)
from friday.tools.registry import CANCELLED_TOOL_MESSAGE, execute_tool, is_download_task_context, parse_tool_arguments

EventCallback = Callable[[str, dict[str, Any]], None]

_log = get_logger("agent.tool_exec")

CANCELLED_MESSAGE = "⏹ 已停止生成。"


class AgentToolExecMixin:
    """工具调用执行、审批与操作日志（混入 FridayAgent）。"""

    def _execute_single_tool(
        self,
        name: str,
        args: dict[str, Any],
        tool_count: int,
        idx: int,
        on_event: EventCallback | None,
    ) -> str:
        from friday.interaction_modes import ASK_BLOCK_REASON, normalize_mode, tool_allowed_in_mode

        if name == "python_env_info" and self._python_env_info_used:
            return (
                "本任务已调用过 python_env_info，请根据已有环境信息编写完整脚本，"
                "一次 run_python 或 run_python_script 执行。"
            )
        if name == "python_env_info":
            self._python_env_info_used = True

        mode = normalize_mode(getattr(self.settings, "interaction_mode", "agent"))
        if not tool_allowed_in_mode(name, mode):
            result = ASK_BLOCK_REASON
            self._emit(on_event, EVENT_ASK_BLOCKED, {"tool_name": name, "message": result})
            log_operation_from_meta(self.operation_meta, name, args, result)
            return result

        if name in {"run_powershell", "run_python", "run_python_script", "open_url"} and is_download_task_context(self._latest_user_text()):
            result = (
                f"工具 {name} 在下载任务中不可用。"
                f"请改用 download_software(软件名, 保存路径) 一次完成下载。"
            )
            log_operation_from_meta(self.operation_meta, name, args, result)
            return result

        if name in {"list_friday_plugins", "list_plugin_catalog", "install_friday_plugin"} and self._ppt_session_active():
            result = block_plugin_list_during_ppt_message()
            log_operation_from_meta(self.operation_meta, name, args, result)
            return result

        if name in {"create_pptx", "create_docx"} and self._ppt_session_active():
            result = block_draft_document_during_ppt_message()
            log_operation_from_meta(self.operation_meta, name, args, result)
            return result

        if name == "run_powershell" and self._ppt_session_active():
            cmd = str(args.get("command", "")).lower()
            if "get-content" in cmd or "skill.md" in cmd or "ppt-master" in cmd:
                result = block_powershell_read_during_ppt_message()
                log_operation_from_meta(self.operation_meta, name, args, result)
                return result

        decision = evaluate_tool(
            self.settings,
            name,
            args,
            yolo_unlocked=getattr(self, "yolo_unlocked", False),
        )

        if not decision.allowed:
            result = decision.reason or "该操作已被安全策略阻止。"
            log_operation_from_meta(self.operation_meta, name, args, result)
            return result

        approved: bool | None = None
        exec_args = dict(args)
        preview = summarize_preview(name, args)
        needs_approval = should_request_approval(self.settings, decision, self._turn_approval)
        if needs_approval:
            pending = PendingAction(
                tool_name=name,
                arguments=args,
                summary=summarize_action(name, args),
                risk=classify_tool(name),
                large_download=decision.large_download,
                download_size_bytes=decision.download_size_bytes,
                untrusted_download=decision.untrusted_download,
                trust_label=decision.trust_label,
                user_goal=self._approval_user_goal(),
                assistant_note=self._latest_assistant_text(),
            )
            if self._cancel_event.is_set():
                return CANCELLED_MESSAGE
            approved = self.request_approval(pending)
            if self._cancel_event.is_set():
                return CANCELLED_MESSAGE
            if not approved:
                self._turn_approval = TurnApprovalState()
                result = "用户拒绝了该操作。"
                log_operation_from_meta(self.operation_meta, name, args, result, approved=False)
                return result

            mark_turn_approved(self._turn_approval, decision)
            if decision.large_download:
                exec_args["_allow_large"] = True
            if decision.untrusted_download:
                exec_args["confirm_untrusted_source"] = True
                exec_args["_untrusted_approved"] = True

            recheck = evaluate_tool(self.settings, name, exec_args)
            if not recheck.allowed:
                result = recheck.reason or "该操作已被安全策略阻止。"
                log_operation_from_meta(self.operation_meta, name, args, result, approved=True)
                return result
        elif decision.needs_approval:
            approved = True
            mark_turn_approved(self._turn_approval, decision)
            if decision.large_download:
                exec_args["_allow_large"] = True
            if decision.untrusted_download:
                exec_args["confirm_untrusted_source"] = True
                exec_args["_untrusted_approved"] = True
            self._emit(on_event, EVENT_APPROVAL_AUTO, {
                "summary": describe_approval_plain(name, args),
                "tool_name": name,
            })

        self._emit(on_event, EVENT_TOOL_START, {
            "tool": name,
            "preview": preview,
            "step": idx,
            "tool_count": tool_count,
            "round": self._round_count + 1,
        })
        if self._cancel_event.is_set():
            return CANCELLED_MESSAGE

        pending_old_text = ""
        if name == "write_text_file":
            from friday.file_diff import read_text_if_exists

            pending_old_text = read_text_if_exists(str(args.get("path", "")))

        meta = self.operation_meta or {}
        shell_deliver_snapshot: set[str] | None = None
        if (
            str(meta.get("trigger", "")) == "weixin"
            and name in {"run_powershell", "run_python", "run_python_script"}
        ):
            from friday.weixin.deliverables import snapshot_deliverable_path_keys as _snap_keys

            shell_deliver_snapshot = _snap_keys(self.settings)

        on_heartbeat = None
        if on_event and name in ("generate_image", "describe_image"):
            def on_heartbeat() -> None:
                self._emit(on_event, EVENT_PROGRESS, {
                    "tools": [name],
                    "heartbeat": True,
                    "step": idx,
                    "tool_count": tool_count,
                    "round": self._round_count + 1,
                })

        result = execute_tool(
            name,
            exec_args,
            cancel_event=self._cancel_event,
            on_heartbeat=on_heartbeat,
        )
        if self._cancel_event.is_set() or result == CANCELLED_TOOL_MESSAGE:
            return CANCELLED_MESSAGE

        self._maybe_update_plan_from_tool(name, args, result, on_event)

        if name == "write_text_file" and result.startswith("已写入"):
            from friday.file_diff import build_file_change_payload

            path_arg = str(args.get("path", ""))
            payload = build_file_change_payload(
                path_arg,
                pending_old_text,
                str(args.get("content", "")),
            )
            self._emit(on_event, EVENT_FILE_CHANGE, payload)

        entry = log_operation_from_meta(
            self.operation_meta,
            name,
            args,
            result,
            approved=approved,
        )
        self._emit(on_event, EVENT_OPERATION_LOGGED, entry)
        from friday.weixin.deliverables import (
            extract_copy_file_destination,
            extract_deliverable_path,
            extract_move_file_destination,
            file_generated_kind_for_path,
            is_text_file_deliverable,
            list_deliverables_since_path_snapshot,
            should_emit_weixin_copy_deliverable,
        )

        def _emit_weixin_file_generated(path: str) -> None:
            if not should_emit_weixin_copy_deliverable(path, settings=self.settings):
                return
            kind = file_generated_kind_for_path(path)
            if kind:
                self._emit(on_event, EVENT_FILE_GENERATED, {"path": path, "kind": kind})

        if name == "generate_image":
            img_path = extract_deliverable_path(name, result)
            if img_path:
                self._emit(on_event, EVENT_IMAGE_GENERATED, {"path": img_path})
        elif name == "screenshot":
            shot_path = extract_deliverable_path(name, result)
            if shot_path:
                self._emit(on_event, EVENT_IMAGE_GENERATED, {"path": shot_path})
        elif name in {"create_docx", "create_pptx"}:
            doc_path = extract_deliverable_path(name, result)
            if doc_path:
                self._emit(on_event, EVENT_FILE_GENERATED, {"path": doc_path, "kind": "document"})
        elif name == "write_text_file" and result.startswith("已写入"):
            text_path = extract_deliverable_path(name, result)
            if text_path and is_text_file_deliverable(text_path):
                self._emit(on_event, EVENT_FILE_GENERATED, {"path": text_path, "kind": "text"})
        elif name == "copy_file" and str(meta.get("trigger", "")) == "weixin":
            dest = extract_copy_file_destination(result)
            if dest:
                _emit_weixin_file_generated(dest)
        elif name == "move_file" and str(meta.get("trigger", "")) == "weixin":
            dest = extract_move_file_destination(result)
            if dest:
                _emit_weixin_file_generated(dest)
        elif (
            name in {"run_powershell", "run_python", "run_python_script"}
            and str(meta.get("trigger", "")) == "weixin"
            and shell_deliver_snapshot is not None
            and (result or "").strip().startswith("exit=0")
        ):
            for delivered_path in list_deliverables_since_path_snapshot(
                self.settings,
                before_keys=shell_deliver_snapshot,
            ):
                _emit_weixin_file_generated(str(delivered_path))
        return result

    def _emit_plan_update(self, on_event: EventCallback | None) -> None:
        session_id = str((self.operation_meta or {}).get("session_id", ""))
        if not session_id:
            return
        from friday.plan import get_session_plan

        plan = get_session_plan(session_id)
        if plan.get("ok"):
            self._emit(on_event, EVENT_PLAN_UPDATED, plan)

    def _maybe_update_plan_from_tool(
        self,
        name: str,
        args: dict[str, Any],
        result: str,
        on_event: EventCallback | None,
    ) -> None:
        session_id = str((self.operation_meta or {}).get("session_id", ""))
        if not session_id:
            return
        from friday.plan import PLAN_TOOL_NAMES, auto_complete_todos_from_tool, sync_todos_from_plan

        if name in PLAN_TOOL_NAMES:
            if name == "update_session_plan":
                sync_todos_from_plan(session_id)
            self._emit_plan_update(on_event)
            return
        changed = auto_complete_todos_from_tool(session_id, name, args, result)
        if changed.get("changed"):
            self._emit_plan_update(on_event)

    def _append_tool_result(self, call_id: str, name: str, result: str) -> None:
        from friday.context import compress_tool_result

        original_len = len(result)
        compressed = compress_tool_result(name, result, max_chars=MAX_TOOL_RESULT_CHARS)
        if len(compressed) < original_len:
            _log.info(
                "工具 %s 输出压缩 (%d -> %d 字符)",
                name,
                original_len,
                len(compressed),
            )
        self.messages.append({
            "role": "tool",
            "tool_call_id": call_id,
            "content": compressed,
        })
        session_id = str((self.operation_meta or {}).get("session_id", ""))
        if session_id and len(result) > 120:
            try:
                from friday.checkpoint_writer import append_session_note

                snippet = result[:400].replace("\n", " ")
                append_session_note(session_id, f"工具 {name}: {snippet}")
            except Exception:
                _log.debug("append_session_note 跳过", exc_info=True)

    def _parse_tool_call(self, call: dict[str, Any]) -> tuple[str, dict[str, Any], str]:
        function = call.get("function") or {}
        name = str(function.get("name", ""))
        raw_args = str(function.get("arguments", ""))
        args = parse_tool_arguments(raw_args)
        call_id = str(call.get("id", ""))
        return name, args, call_id

    def _execute_round(self, finish: ChatCompletionResult, on_event: EventCallback | None) -> None:
        tool_count = len(finish.tool_calls)
        tool_names = [
            (c.get("function") or {}).get("name", "unknown") for c in finish.tool_calls
        ]
        max_rounds = self._max_tool_rounds()
        self._emit(on_event, EVENT_PROGRESS, {
            "round": self._round_count + 1,
            "max_rounds": max_rounds,
            "tool_count": tool_count,
            "tools": tool_names,
        })

        parsed: list[tuple[str, dict[str, Any], str]] = []
        for call in finish.tool_calls:
            name, args, call_id = self._parse_tool_call(call)
            if "__parse_error__" in args:
                self._append_tool_result(
                    call_id,
                    name,
                    f"工具参数无效（JSON 解析失败）: {args['__parse_error__']}",
                )
                continue
            parsed.append((name, args, call_id))

        if not parsed:
            return

        if self._can_parallelize_round([name for name, _, _ in parsed]):
            results: dict[str, str] = {}
            with ThreadPoolExecutor(max_workers=min(4, len(parsed))) as pool:
                futures = {
                    pool.submit(
                        self._execute_single_tool,
                        name,
                        args,
                        tool_count,
                        idx,
                        on_event,
                    ): call_id
                    for idx, (name, args, call_id) in enumerate(parsed, 1)
                }
                for future in as_completed(futures):
                    if self._cancel_event.is_set():
                        break
                    call_id = futures[future]
                    try:
                        results[call_id] = future.result()
                    except Exception as exc:
                        _log.exception("并行工具执行失败")
                        results[call_id] = f"工具执行异常: {exc}"
            if self._cancel_event.is_set():
                return
            for name, args, call_id in parsed:
                result = results.get(call_id, "工具未返回结果")
                if result == CANCELLED_MESSAGE:
                    break
                self._append_tool_result(call_id, name, result)
            return

        for idx, (name, args, call_id) in enumerate(parsed, 1):
            if self._cancel_event.is_set():
                break
            result = self._execute_single_tool(name, args, tool_count, idx, on_event)
            if result == CANCELLED_MESSAGE:
                break
            self._append_tool_result(call_id, name, result)
