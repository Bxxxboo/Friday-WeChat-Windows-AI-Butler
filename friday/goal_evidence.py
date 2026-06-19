"""Goal 完成校验 —— 会话内工具证据链。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_WEIXIN_SENT_CLAIM = re.compile(
    r"(已发送给|已成功发送|消息已发|已经发(给|送)|发送成功)",
)
_HISTORICAL_WEIXIN = re.compile(r"(之前|上次|先前|刚才我们|Earlier)")
_DELIVERY_HANDOFF = re.compile(r"(请查收|请查看|发给你|发您了?)")
_COMPLETION_CLAIM_RE = re.compile(
    r"(已完成|全部完成|搞定了|做完了|任务完成|current task is done)",
    re.IGNORECASE,
)
_PATH_IN_REPLY = re.compile(r"[A-Za-z]:\\|/[\w./-]+|\.docx|\.pptx|\.png|\.jpg")
_WRITE_TOOLS = frozenset({
    "write_text_file",
    "create_docx",
    "create_pptx",
    "copy_file",
    "move_file",
    "generate_image",
})


def reply_claims_completion(text: str) -> bool:
    return bool(_COMPLETION_CLAIM_RE.search(str(text or "")))


def collect_session_evidence(
    session_id: str,
    *,
    limit: int = 60,
    since: float | None = None,
) -> list[dict[str, Any]]:
    if not session_id:
        return []
    from friday.operations import list_operations

    return list_operations(session_id=session_id, limit=limit, since=since)


def format_evidence_for_llm(evidence: list[dict[str, Any]]) -> str:
    if not evidence:
        return "（本轮暂无工具调用记录）"
    lines: list[str] = []
    for item in evidence[:40]:
        tool = str(item.get("tool", ""))
        ok = bool(item.get("success"))
        summary = str(item.get("summary") or "")[:100]
        result = str(item.get("result") or "")[:120]
        status = "成功" if ok else "失败"
        lines.append(f"- {tool} [{status}] {summary} | {result}")
    return "\n".join(lines)


def _weixin_sent_claim_is_actionable(text: str) -> bool:
    """当前轮交付宣称（非历史回顾）才校验微信回执。"""
    if not _WEIXIN_SENT_CLAIM.search(text):
        return False
    if _HISTORICAL_WEIXIN.search(text):
        return False
    return reply_claims_completion(text) or bool(_DELIVERY_HANDOFF.search(text))


def check_evidence_gates(
    reply: str,
    evidence: list[dict[str, Any]],
    *,
    evidence_required: bool = True,
) -> dict[str, Any] | None:
    """确定性证据拦截；返回 block dict 或 None。"""
    if not evidence_required:
        return None
    text = (reply or "").strip()
    if not text:
        return None

    if _weixin_sent_claim_is_actionable(text):
        sent_ok = any(
            item.get("tool") == "send_weixin_contact_message"
            and item.get("success")
            and "已发送给" in str(item.get("result", ""))
            for item in evidence
        )
        if not sent_ok:
            return {
                "ok": False,
                "block": True,
                "reason": "回复声称已通过微信发送，但本轮无 send_weixin_contact_message 成功回执",
            }

    claims_done = reply_claims_completion(text)
    if claims_done:
        mentions_path = bool(_PATH_IN_REPLY.search(text))
        wrote_ok = any(
            item.get("tool") in _WRITE_TOOLS and item.get("success")
            for item in evidence
        )
        if mentions_path and not wrote_ok:
            return {
                "ok": False,
                "block": True,
                "reason": "回复提到文件/路径并宣称完成，但本轮无成功的写入或生成工具记录",
            }

        for item in evidence:
            if not item.get("success"):
                continue
            tool = str(item.get("tool", ""))
            if tool not in _WRITE_TOOLS:
                continue
            args = item.get("args") or {}
            path = str(args.get("path") or args.get("destination") or "").strip()
            if path and not Path(path).expanduser().exists():
                return {
                    "ok": False,
                    "block": True,
                    "reason": f"回复宣称完成，但工具 {tool} 记录的路径不存在：{path}",
                }
    return None
