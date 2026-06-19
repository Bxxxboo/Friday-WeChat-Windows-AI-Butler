"""Goal 完成校验 —— 有 plan/复杂任务时拦截过早收尾。"""

from __future__ import annotations

import json
import re
from typing import Any

from friday.logging_config import get_logger
from friday.storage import UserSettings, load_settings

_log = get_logger("goal_verifier")

_FINISH_RE = re.compile(
    r"(已完成|全部完成|搞定了|做完了|任务完成|current task is done)",
    re.IGNORECASE,
)
_STRONG_FINISH_RE = re.compile(
    r"(全部|任务|当前).*?(已完成|做完了|搞定了)",
    re.IGNORECASE,
)


def _parse_llm_json(raw: str) -> dict[str, Any]:
    text = str(raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```\s*$", "", text)
    data = json.loads(text)
    return data if isinstance(data, dict) else {}


def _open_todos(session_id: str) -> list[str]:
    from friday.plan import get_session_plan

    plan = get_session_plan(session_id)
    todos = plan.get("todos") or []
    open_items: list[str] = []
    for item in todos:
        if not isinstance(item, dict):
            continue
        if not item.get("done"):
            text = str(item.get("text", "")).strip()
            if text:
                open_items.append(text)
    return open_items


def should_verify(session_id: str, reply: str, *, settings: UserSettings | None = None) -> bool:
    cfg = settings or load_settings()
    if not getattr(cfg, "goal_verifier_enabled", True):
        return False
    if not getattr(cfg, "context_smart_enabled", True):
        return False
    if not session_id or not reply.strip():
        return False
    if not _FINISH_RE.search(reply):
        return False
    open_items = _open_todos(session_id)
    if open_items:
        return True
    from friday.plan import get_session_plan

    plan = get_session_plan(session_id)
    plan_md = str(plan.get("plan_markdown", "") or "").strip()
    if plan_md and len(plan_md) > 80:
        return _STRONG_FINISH_RE.search(reply) is not None
    return False


def verify_goal_complete(
    session_id: str,
    reply: str,
    *,
    settings: UserSettings | None = None,
    brain: Any | None = None,
    evidence: list[dict[str, Any]] | None = None,
    evidence_since: float | None = None,
) -> dict[str, Any]:
    """校验助手是否过早宣告完成。返回 ok/block/reason。"""
    cfg = settings or load_settings()
    if not getattr(cfg, "goal_verifier_enabled", True):
        return {"ok": True, "block": False}

    from friday.goal_evidence import (
        check_evidence_gates,
        collect_session_evidence,
        format_evidence_for_llm,
    )

    bundle = evidence
    if bundle is None:
        bundle = collect_session_evidence(session_id, since=evidence_since)
    evidence_required = getattr(cfg, "goal_verifier_evidence_required", True)
    gate = check_evidence_gates(reply, bundle, evidence_required=evidence_required)
    if gate:
        return gate

    if not should_verify(session_id, reply, settings=cfg):
        return {"ok": True, "block": False}

    open_items = _open_todos(session_id)
    if open_items:
        reason = "计划中仍有未完成待办：" + "；".join(open_items[:5])
        return {"ok": False, "block": True, "reason": reason, "open_todos": open_items}

    if brain is None:
        from friday.brain import DeepSeekBrain

        brain = DeepSeekBrain(cfg)

    from friday.checkpoint_writer import read_checkpoint

    ck = read_checkpoint(session_id)
    pending = ""
    if ck.get("exists"):
        fields = ck.get("fields") or {}
        pending = str(fields.get("pending", "") or "").strip()

    if pending and pending != "（暂无）":
        return {
            "ok": False,
            "block": True,
            "reason": f"工作记忆仍记录未完成项：{pending[:240]}",
        }

    if not cfg.api_ready:
        return {"ok": True, "block": False}

    try:
        brain.record_api_call()
        evidence_text = format_evidence_for_llm(bundle)
        response = brain.client.chat.completions.create(
            model=cfg.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是任务完成审核员。根据助手回复与会话内工具证据，判断任务是否真的可以收尾。"
                        "若回复声称已发送微信/已写入文件，但证据中无对应成功工具，必须 complete=false。"
                        "仅回答 JSON：{\"complete\": true/false, \"reason\": \"简短中文\"}"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"助手回复：\n{reply[:2000]}\n\n"
                        f"工具证据（新→旧）：\n{evidence_text}\n\n"
                        "请判断是否真的完成。"
                    ),
                },
            ],
            max_tokens=200,
            temperature=0.0,
        )
        raw = (response.choices[0].message.content or "").strip()
        data = _parse_llm_json(raw)
        if not data.get("complete"):
            return {
                "ok": False,
                "block": True,
                "reason": str(data.get("reason") or "审核认为任务尚未完成"),
            }
    except Exception as exc:  # noqa: BLE001
        _log.warning("Goal verifier API 失败，放行 | %s", exc)

    return {"ok": True, "block": False}
