"""有限多 Agent 编排（默认关闭，v1.5 试点）。"""

from __future__ import annotations

from typing import Any

from friday.storage import UserSettings


def multi_agent_enabled(settings: UserSettings | None) -> bool:
    return bool(getattr(settings, "multi_agent_enabled", False))


def max_sub_agents(settings: UserSettings | None) -> int:
    raw = int(getattr(settings, "max_sub_agents", 2) or 2)
    return max(1, min(raw, 3))


def maybe_inject_planner_hint(user_text: str, settings: UserSettings, brain: Any) -> str:
    """multi_agent_enabled 时注入规划提示；关闭时原样返回。"""
    if not multi_agent_enabled(settings):
        return user_text
    if not str(user_text or "").strip():
        return user_text
    # 试点：仅追加系统侧提示，不 spawn 子进程；完整 planner 见 TODOS P1-6
    hint = (
        "\n\n【多 Agent 试点】请先列出 3～6 个可核对步骤再执行；"
        "只读调研可并行思考，写文件/Shell/微信仍须主 Agent 单次审批。"
    )
    if hint.strip() in user_text:
        return user_text
    return user_text + hint


def run_bounded_sub_agents(*, settings: UserSettings, **_kwargs: Any) -> None:
    """占位：并发池尚未启用；确保关闭时无操作。"""
    if not multi_agent_enabled(settings):
        return
