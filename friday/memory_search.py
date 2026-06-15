"""无向量记忆检索 —— 关键词匹配 user_memory 与 MEMORY.md。"""

from __future__ import annotations

import re
from typing import Any

from friday.storage import load_settings, resolved_workspace
from friday.user_memory import load_facts
from friday.workspace_memory import load_memory


def _normalize_query(query: str) -> str:
    return " ".join(str(query or "").strip().casefold().split())


def _snippet(text: str, needle: str, *, max_len: int = 160) -> str:
    body = re.sub(r"\s+", " ", str(text or "").strip())
    if len(body) <= max_len:
        return body
    idx = body.casefold().find(needle.casefold()) if needle else -1
    if idx < 0:
        return body[: max_len - 3] + "..."
    start = max(0, idx - 40)
    piece = body[start : start + max_len]
    prefix = "..." if start > 0 else ""
    suffix = "..." if start + max_len < len(body) else ""
    return f"{prefix}{piece}{suffix}"


def search_saved_memory(query: str, *, limit: int = 10) -> list[dict[str, Any]]:
    """搜索 user_memory.json 与当前工作区 MEMORY.md。"""
    raw = str(query or "").strip()
    if not raw:
        return []
    needle = _normalize_query(raw)
    if not needle:
        return []

    hits: list[dict[str, Any]] = []
    for item in load_facts():
        text = str(item.get("text", "")).strip()
        if needle not in _normalize_query(text):
            continue
        hits.append({
            "source": "user_memory",
            "id": item.get("id", ""),
            "text": text,
            "snippet": _snippet(text, raw),
        })

    workspace = resolved_workspace(load_settings())
    memory_text = load_memory(workspace)
    for line in memory_text.splitlines():
        piece = line.strip().lstrip("-•* ").strip()
        if len(piece) < 4:
            continue
        if needle not in _normalize_query(piece):
            continue
        hits.append({
            "source": "workspace_memory",
            "workspace": workspace,
            "text": piece[:240],
            "snippet": _snippet(piece, raw),
        })

    return hits[: max(1, min(limit, 30))]
