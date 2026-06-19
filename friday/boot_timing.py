"""启动分段计时 — splash → 后端 → health → 内置技能。"""

from __future__ import annotations

import time
from typing import Any

from friday.logging_config import get_logger

_log = get_logger("boot")

_ORIGIN = time.perf_counter()
_MARKS: list[tuple[str, float]] = []


def reset() -> None:
    """测试用：清空已有标记。"""
    global _ORIGIN, _MARKS
    _ORIGIN = time.perf_counter()
    _MARKS.clear()


def mark(phase: str) -> None:
    """记录阶段时间点（可重复调用同名 phase，保留最后一次）。"""
    now = time.perf_counter()
    for idx, (name, _) in enumerate(_MARKS):
        if name == phase:
            _MARKS[idx] = (phase, now)
            return
    _MARKS.append((phase, now))


def _ms_since_origin(at: float) -> int:
    return int(round((at - _ORIGIN) * 1000))


def _ms_delta(prev: float, at: float) -> int:
    return int(round((at - prev) * 1000))


def summary() -> list[dict[str, Any]]:
    """返回各阶段相对启动原点的毫秒与段间增量。"""
    if not _MARKS:
        return []
    rows: list[dict[str, Any]] = []
    prev = _ORIGIN
    for name, at in _MARKS:
        rows.append(
            {
                "phase": name,
                "ms_total": _ms_since_origin(at),
                "ms_step": _ms_delta(prev, at),
            }
        )
        prev = at
    return rows


def log_summary(*, trigger: str = "") -> None:
    rows = summary()
    if not rows:
        return
    parts = [f"{row['phase']}={row['ms_total']}ms(+{row['ms_step']}ms)" for row in rows]
    suffix = f" | trigger={trigger}" if trigger else ""
    _log.info("启动分段%s | %s", suffix, " → ".join(parts))
