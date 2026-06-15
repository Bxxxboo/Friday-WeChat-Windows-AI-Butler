"""记忆变更审计链 —— 追加写入 memory_events.jsonl。"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from friday.paths import get_appdata_dir

_MAX_DETAIL_LEN = 500


def events_path() -> Path:
    return get_appdata_dir() / "memory_events.jsonl"


def log_memory_event(
    action: str,
    target: str,
    *,
    detail: str = "",
    session_id: str = "",
    extra: dict[str, Any] | None = None,
) -> None:
    """记录记忆相关操作。action 示例：remember / forget / workspace_save / promote / dream."""
    path = events_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    row: dict[str, Any] = {
        "ts": time.time(),
        "action": str(action or "").strip()[:40],
        "target": str(target or "").strip()[:80],
        "detail": str(detail or "").strip()[:_MAX_DETAIL_LEN],
    }
    if session_id:
        row["session_id"] = session_id.strip()[:64]
    if extra:
        row.update(extra)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
