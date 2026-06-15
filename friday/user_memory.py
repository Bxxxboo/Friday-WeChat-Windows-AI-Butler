"""跨会话用户记忆（偏好、常用路径、习惯）。"""

from __future__ import annotations

import time
import uuid
from typing import Any

from friday.io_utils import atomic_write_json, load_json
from friday.paths import get_appdata_dir

MAX_FACTS = 25
MAX_FACT_LEN = 240


def _memory_path():
    return get_appdata_dir() / "user_memory.json"


def load_facts() -> list[dict[str, Any]]:
    data = load_json(_memory_path()) or {}
    facts = data.get("facts") or []
    if not isinstance(facts, list):
        return []
    out: list[dict[str, Any]] = []
    for item in facts:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        out.append({
            "id": str(item.get("id") or uuid.uuid4().hex[:10]),
            "text": text[:MAX_FACT_LEN],
            "updated_at": float(item.get("updated_at") or 0),
        })
    return out[:MAX_FACTS]


def _save_facts(facts: list[dict[str, Any]]) -> None:
    atomic_write_json(
        _memory_path(),
        {"facts": facts[:MAX_FACTS], "version": 1},
    )


def _normalize_key(text: str) -> str:
    return " ".join(str(text or "").strip().casefold().split())


def remember_fact(text: str) -> dict[str, Any]:
    cleaned = str(text or "").strip()
    if not cleaned:
        return {"ok": False, "message": "记忆内容不能为空"}
    if len(cleaned) > MAX_FACT_LEN:
        cleaned = cleaned[:MAX_FACT_LEN]
    facts = load_facts()
    key = _normalize_key(cleaned)
    now = time.time()
    for item in facts:
        if _normalize_key(item["text"]) == key:
            item["text"] = cleaned
            item["updated_at"] = now
            _save_facts(facts)
            _log_event("remember", item["id"], cleaned, updated=True)
            return {"ok": True, "message": "已更新已有记忆", "id": item["id"]}
    entry = {"id": uuid.uuid4().hex[:10], "text": cleaned, "updated_at": now}
    facts.insert(0, entry)
    _save_facts(facts)
    _log_event("remember", entry["id"], cleaned)
    return {"ok": True, "message": "已记住", "id": entry["id"]}


def forget_fact(query: str) -> dict[str, Any]:
    needle = str(query or "").strip().casefold()
    if not needle:
        return {"ok": False, "message": "请提供要删除的记忆关键词"}
    facts = load_facts()
    kept = [f for f in facts if needle not in f["text"].casefold()]
    removed = len(facts) - len(kept)
    if removed <= 0:
        return {"ok": False, "message": "未找到匹配的记忆"}
    removed_texts = [f["text"] for f in facts if f not in kept]
    _save_facts(kept)
    for piece in removed_texts[:5]:
        _log_event("forget", query, piece)
    return {"ok": True, "message": f"已删除 {removed} 条记忆"}


def update_fact_by_id(fact_id: str, text: str) -> dict[str, Any]:
    fid = str(fact_id or "").strip()
    cleaned = str(text or "").strip()
    if not fid:
        return {"ok": False, "message": "缺少记忆 ID"}
    if not cleaned:
        return {"ok": False, "message": "记忆内容不能为空"}
    if len(cleaned) > MAX_FACT_LEN:
        cleaned = cleaned[:MAX_FACT_LEN]
    facts = load_facts()
    for item in facts:
        if item["id"] == fid:
            item["text"] = cleaned
            item["updated_at"] = time.time()
            _save_facts(facts)
            _log_event("remember", fid, cleaned, updated=True, via="settings")
            return {"ok": True, "message": "已更新", "id": fid}
    return {"ok": False, "message": "未找到该记忆"}


def delete_fact_by_id(fact_id: str) -> dict[str, Any]:
    fid = str(fact_id or "").strip()
    if not fid:
        return {"ok": False, "message": "缺少记忆 ID"}
    facts = load_facts()
    kept = [f for f in facts if f["id"] != fid]
    if len(kept) == len(facts):
        return {"ok": False, "message": "未找到该记忆"}
    removed = next(f for f in facts if f["id"] == fid)
    _save_facts(kept)
    _log_event("forget", fid, removed["text"], via="settings")
    return {"ok": True, "message": "已删除"}


def _log_event(
    action: str,
    target: str,
    detail: str,
    *,
    updated: bool = False,
    via: str = "agent",
) -> None:
    try:
        from friday.memory_events import log_memory_event

        log_memory_event(
            action,
            target,
            detail=detail,
            extra={"updated": updated, "via": via},
        )
    except Exception:
        pass


def format_for_prompt() -> str:
    facts = load_facts()
    if not facts:
        return ""
    lines = ["【用户长期偏好与记忆（跨会话，请主动参考）】"]
    for item in facts:
        lines.append(f"- {item['text']}")
    lines.append("用户明确表达的稳定偏好可用 remember_user_fact 记录；过时信息用 forget_user_fact 删除。")
    return "\n".join(lines) + "\n"
