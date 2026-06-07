"""操作历史 —— 持久化 Agent 工具调用记录，供时间线展示。"""

from __future__ import annotations

import csv
import io
import json
import time
import uuid
from pathlib import Path
from typing import Any

from friday.io_utils import atomic_write_json, load_json
from friday.logging_config import get_logger
from friday.paths import get_appdata_dir
from friday.safety import RiskLevel, WRITE_TOOLS, classify_tool, summarize_action

_log = get_logger("operations")

_MAX_ENTRIES = 300


def _store_path() -> Path:
    return get_appdata_dir() / "operations.json"


def _load_all() -> list[dict[str, Any]]:
    data = load_json(_store_path())
    if isinstance(data, list):
        return data
    return []


def _save_all(entries: list[dict[str, Any]]) -> None:
    atomic_write_json(_store_path(), entries[-_MAX_ENTRIES:])


def _infer_success(result: str) -> bool:
    blocked = (
        "用户拒绝了该操作",
        "该操作已被安全策略阻止",
        "已在安全设置中禁用",
        "路径超出默认操作文件夹范围",
    )
    return not any(marker in result for marker in blocked)


def log_operation(
    tool_name: str,
    args: dict[str, Any],
    result: str,
    *,
    session_id: str = "",
    trigger: str = "chat",
    schedule_id: str = "",
    approved: bool | None = None,
) -> dict[str, Any]:
    """记录一次工具调用并持久化。"""
    risk = classify_tool(tool_name)
    entry: dict[str, Any] = {
        "id": uuid.uuid4().hex[:12],
        "ts": time.time(),
        "tool": tool_name,
        "risk": risk.value,
        "summary": summarize_action(tool_name, args),
        "args": args,
        "result": result[:400],
        "success": _infer_success(result),
        "session_id": session_id,
        "trigger": trigger,
        "schedule_id": schedule_id,
    }
    if approved is not None:
        entry["approved"] = approved

    entries = _load_all()
    entries.append(entry)
    _save_all(entries)
    return entry


def list_operations(
    *,
    limit: int = 50,
    session_id: str = "",
    schedule_id: str = "",
    writes_only: bool = False,
    tool: str = "",
    risk: str = "",
    trigger: str = "",
    since: float | None = None,
) -> list[dict[str, Any]]:
    """返回最新操作记录（时间倒序）。"""
    entries = _load_all()
    if session_id:
        entries = [e for e in entries if e.get("session_id") == session_id]
    if schedule_id:
        entries = [e for e in entries if e.get("schedule_id") == schedule_id]
    if writes_only:
        entries = [e for e in entries if e.get("tool") in WRITE_TOOLS]
    if tool:
        entries = [e for e in entries if e.get("tool") == tool]
    if risk:
        entries = [e for e in entries if e.get("risk") == risk]
    if trigger:
        entries = [e for e in entries if e.get("trigger") == trigger]
    if since is not None:
        entries = [e for e in entries if float(e.get("ts", 0)) >= since]
    entries.sort(key=lambda e: float(e.get("ts", 0)), reverse=True)
    return entries[: max(1, min(limit, 500))]


def get_operation(operation_id: str) -> dict[str, Any] | None:
    for entry in _load_all():
        if entry.get("id") == operation_id:
            return entry
    return None


def replay_prompt(operation_id: str) -> str | None:
    """根据历史操作生成可重放的自然语言指令。"""
    entry = get_operation(operation_id)
    if not entry:
        return None
    tool = entry.get("tool", "")
    summary = entry.get("summary") or tool
    args = entry.get("args") or {}
    if args:
        args_text = json.dumps(args, ensure_ascii=False)
        if len(args_text) > 200:
            args_text = args_text[:200] + "…"
        return f"请再次帮我执行：{summary}（工具 {tool}，参数 {args_text}）"
    return f"请再次帮我执行：{summary}"


def export_operations(
    *,
    format: str = "json",
    writes_only: bool = False,
    tool: str = "",
    risk: str = "",
    trigger: str = "",
    limit: int = 500,
) -> tuple[str, str, str]:
    """返回 (content, media_type, filename)。"""
    items = list_operations(
        limit=limit,
        writes_only=writes_only,
        tool=tool,
        risk=risk,
        trigger=trigger,
    )
    if format == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["id", "ts", "tool", "risk", "summary", "success", "trigger", "session_id"])
        for item in items:
            writer.writerow([
                item.get("id", ""),
                item.get("ts", ""),
                item.get("tool", ""),
                item.get("risk", ""),
                item.get("summary", ""),
                item.get("success", ""),
                item.get("trigger", ""),
                item.get("session_id", ""),
            ])
        return buf.getvalue(), "text/csv; charset=utf-8", "friday-operations.csv"
    body = json.dumps(items, ensure_ascii=False, indent=2)
    return body, "application/json; charset=utf-8", "friday-operations.json"


def clear_operations() -> int:
    """清空操作历史，返回删除条数。"""
    count = len(_load_all())
    _save_all([])
    return count


def is_write_tool(tool_name: str) -> bool:
    return tool_name in WRITE_TOOLS


def risk_label(risk: str) -> str:
    mapping = {
        RiskLevel.READ.value: "只读",
        RiskLevel.WRITE.value: "文件",
        RiskLevel.EXEC.value: "执行",
    }
    return mapping.get(risk, risk)
