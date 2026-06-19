"""有限多 Agent 设置（默认关闭）。"""

from __future__ import annotations

from friday.storage import UserSettings
from friday.sub_agents import maybe_inject_planner_hint, multi_agent_enabled


def test_multi_agent_disabled_by_default():
    settings = UserSettings()
    assert multi_agent_enabled(settings) is False
    text = "整理桌面并压缩备份"
    assert maybe_inject_planner_hint(text, settings, brain=None) == text


def test_multi_agent_injects_hint_when_enabled():
    settings = UserSettings(multi_agent_enabled=True)
    text = "整理桌面并压缩备份"
    out = maybe_inject_planner_hint(text, settings, brain=None)
    assert out != text
    assert "多 Agent 试点" in out
