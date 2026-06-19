"""有限多 Agent 编排（默认开启，max_sub_agents=3，v1.5 试点）。"""

from __future__ import annotations

import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable, TypeVar

from friday.logging_config import get_logger
from friday.storage import UserSettings

_log = get_logger("sub_agents")

T = TypeVar("T")

# 子 Agent 禁止调用的工具（写盘 / Shell / 微信等）
SUB_AGENT_BLOCKED_TOOLS = frozenset({
    "delete_file",
    "delete_directory",
    "run_powershell",
    "run_python",
    "run_python_script",
    "send_weixin_contact_message",
    "write_text_file",
    "move_file",
    "organize_directory",
    "batch_rename",
    "install_friday_plugin",
    "uninstall_friday_plugin",
})

# 调研子 Agent 若未来启用工具，仅允许只读类
SUB_AGENT_READ_TOOLS = frozenset({
    "list_directory",
    "search_files",
    "read_text_file",
    "read_pdf",
    "read_excel",
    "get_file_info",
    "get_system_status",
    "get_disk_usage",
    "browse_webpage",
    "python_env_info",
})

_PLANNER_SYSTEM = (
    "你是 Friday 的规划子 Agent。只输出 JSON，不要 markdown 围栏或解释。\n"
    '格式：{"steps":["可核对步骤1","步骤2",...],"research_topics":["可选调研主题"]}\n'
    "要求：steps 3～6 条，每条可验收、用简体中文；research_topics 0～2 条。"
)

_RESEARCH_SYSTEM = (
    "你是 Friday 的调研子 Agent。根据用户任务与主题，输出 3～5 条只读调研要点（纯文本），"
    "不要调用工具、不要建议删除/Shell/微信操作。"
)

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


@dataclass
class PlannerOutput:
    steps: list[str] = field(default_factory=list)
    research_topics: list[str] = field(default_factory=list)
    raw: str = ""


@dataclass
class MultiAgentTurnResult:
    plan_markdown: str = ""
    research_notes: list[str] = field(default_factory=list)
    roles_run: list[str] = field(default_factory=list)


class SubAgentPool:
    """有上限的并发池；超出 max_active 时排队等待。"""

    def __init__(self, max_active: int) -> None:
        self.max_active = max(1, min(int(max_active), 3))
        self._active = 0
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)

    @property
    def active_count(self) -> int:
        with self._lock:
            return self._active

    def run(self, role: str, fn: Callable[[], T]) -> T:
        with self._cond:
            while self._active >= self.max_active:
                _log.debug("子 Agent 排队 | role=%s active=%d max=%d", role, self._active, self.max_active)
                self._cond.wait(timeout=120.0)
            self._active += 1
        try:
            return fn()
        finally:
            with self._cond:
                self._active -= 1
                self._cond.notify()


def multi_agent_enabled(settings: UserSettings | None) -> bool:
    return bool(getattr(settings, "multi_agent_enabled", True))


def max_sub_agents(settings: UserSettings | None) -> int:
    raw = int(getattr(settings, "max_sub_agents", 3) or 3)
    return max(1, min(raw, 3))


def sub_agent_tool_allowed(tool_name: str) -> bool:
    name = (tool_name or "").strip()
    if not name or name.startswith("mcp_"):
        return False
    if name in SUB_AGENT_BLOCKED_TOOLS:
        return False
    return name in SUB_AGENT_READ_TOOLS


def parse_planner_json(raw: str) -> PlannerOutput:
    text = _JSON_FENCE_RE.sub("", str(raw or "").strip())
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("planner JSON 须为 object")
    steps_raw = data.get("steps") or []
    topics_raw = data.get("research_topics") or []
    steps = [str(s).strip() for s in steps_raw if str(s).strip()]
    topics = [str(t).strip() for t in topics_raw if str(t).strip()]
    if len(steps) < 3:
        raise ValueError("planner steps 少于 3 条")
    return PlannerOutput(steps=steps[:8], research_topics=topics[:2], raw=text)


def planner_output_to_markdown(planner: PlannerOutput, research_notes: list[str] | None = None) -> str:
    lines = ["## 任务计划（多 Agent 规划）", ""]
    for idx, step in enumerate(planner.steps, start=1):
        lines.append(f"{idx}. {step}")
    if research_notes:
        lines.extend(["", "## 调研摘要", ""])
        for note in research_notes:
            for part in str(note).strip().splitlines():
                part = part.strip()
                if part:
                    lines.append(f"- {part.lstrip('- ')}")
    lines.append("")
    lines.append(
        "长任务请严格按上述计划推进；完成项用 update_session_todos 标记。"
        "写文件/Shell/微信仍须主 Agent 审批。"
    )
    return "\n".join(lines)


def _log_sub_agent(role: str, summary: str, *, session_id: str = "", ok: bool = True) -> None:
    try:
        from friday.operations import log_operation

        log_operation(
            "sub_agent",
            {"role": role, "summary": summary[:200]},
            "ok" if ok else "failed",
            session_id=session_id,
            trigger=f"sub_agent:{role}",
        )
    except Exception:
        _log.exception("记录 sub_agent 操作失败 | role=%s", role)


def _call_llm_text(brain: Any, system: str, user: str, *, tools: bool = False) -> str:
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    response = brain.chat(messages, tools=tools)
    choice = response.choices[0]
    return str(getattr(choice.message, "content", "") or "").strip()


def run_planner_sub_agent(brain: Any, user_text: str, *, session_id: str = "") -> PlannerOutput:
    started = time.time()
    try:
        raw = _call_llm_text(
            brain,
            _PLANNER_SYSTEM,
            f"用户任务：\n{_strip_task_suffixes(user_text)}",
            tools=False,
        )
        parsed = parse_planner_json(raw)
        _log_sub_agent(
            "planner",
            f"{len(parsed.steps)} 步 | {int((time.time() - started) * 1000)}ms",
            session_id=session_id,
            ok=True,
        )
        return parsed
    except Exception as exc:
        _log.warning("规划子 Agent 失败 | %s", exc)
        _log_sub_agent("planner", str(exc)[:200], session_id=session_id, ok=False)
        raise


def run_research_sub_agent(
    brain: Any,
    user_text: str,
    topic: str,
    *,
    session_id: str = "",
) -> str:
    started = time.time()
    prompt = (
        f"用户总任务：\n{_strip_task_suffixes(user_text)}\n\n"
        f"调研主题：{topic}\n"
        "列出需要只读确认的路径/文件/网页要点。"
    )
    try:
        note = _call_llm_text(brain, _RESEARCH_SYSTEM, prompt, tools=False)
        _log_sub_agent(
            "research",
            f"{topic[:40]} | {int((time.time() - started) * 1000)}ms",
            session_id=session_id,
            ok=bool(note.strip()),
        )
        return note.strip()
    except Exception as exc:
        _log.warning("调研子 Agent 失败 | topic=%s | %s", topic, exc)
        _log_sub_agent("research", str(exc)[:200], session_id=session_id, ok=False)
        return ""


def orchestrate_bounded_sub_agents(
    user_text: str,
    settings: UserSettings,
    brain: Any,
    *,
    session_id: str = "",
) -> MultiAgentTurnResult | None:
    """复杂任务：Planner + 可选并行 Research（有并发上限与排队）。"""
    if not multi_agent_enabled(settings):
        return None
    from friday.plan import is_complex_task, session_has_actionable_plan

    if not is_complex_task(user_text) or session_has_actionable_plan(session_id):
        return None

    pool = SubAgentPool(max_sub_agents(settings))
    result = MultiAgentTurnResult()

    try:
        planner = pool.run("planner", lambda: run_planner_sub_agent(brain, user_text, session_id=session_id))
    except Exception:
        return None

    result.roles_run.append("planner")
    research_slots = max(0, pool.max_active - 1)
    topics = planner.research_topics[:research_slots]

    if topics:
        notes: list[str] = []

        def _research_job(topic: str) -> str:
            return pool.run(
                "research",
                lambda t=topic: run_research_sub_agent(brain, user_text, t, session_id=session_id),
            )

        with ThreadPoolExecutor(max_workers=len(topics)) as executor:
            futures = {executor.submit(_research_job, topic): topic for topic in topics}
            for fut in as_completed(futures):
                note = fut.result()
                if note:
                    notes.append(f"**{futures[fut]}**：\n{note}")
                    result.roles_run.append("research")
        result.research_notes = notes

    result.plan_markdown = planner_output_to_markdown(planner, result.research_notes)
    return result


def _strip_task_suffixes(user_text: str) -> str:
    from friday.plan import _strip_agent_task_suffixes

    return _strip_agent_task_suffixes(user_text)


def maybe_inject_planner_hint(user_text: str, settings: UserSettings, brain: Any) -> str:
    """multi_agent_enabled 且未走完整编排时的轻量提示；关闭时原样返回。"""
    if not multi_agent_enabled(settings):
        return user_text
    if not str(user_text or "").strip():
        return user_text
    hint = (
        "\n\n【多 Agent 试点】请先列出 3～6 个可核对步骤再执行；"
        "只读调研可并行思考，写文件/Shell/微信仍须主 Agent 单次审批。"
    )
    if hint.strip() in user_text:
        return user_text
    return user_text + hint


def prepare_multi_agent_turn(
    user_text: str,
    settings: UserSettings,
    brain: Any,
    *,
    session_id: str = "",
) -> tuple[str, str]:
    """返回 (user_text, plan_markdown)。plan_markdown 非空时应写入 session / plan anchor。"""
    orchestrated = orchestrate_bounded_sub_agents(
        user_text,
        settings,
        brain,
        session_id=session_id,
    )
    if orchestrated and orchestrated.plan_markdown.strip():
        from friday.sessions import get_session, save_session_fields
        from friday.plan import merge_todos_from_plan

        session = get_session(session_id) if session_id else None
        existing_todos = getattr(session, "todos", None) if session else None
        merged, _added = merge_todos_from_plan(existing_todos, orchestrated.plan_markdown)
        if session_id:
            save_session_fields(
                session_id,
                plan_markdown=orchestrated.plan_markdown,
                todos=merged,
            )
        return user_text, orchestrated.plan_markdown

    return maybe_inject_planner_hint(user_text, settings, brain), ""


def run_bounded_sub_agents(*, settings: UserSettings, **_kwargs: Any) -> None:
    """兼容占位：关闭时无操作。"""
    if not multi_agent_enabled(settings):
        return
