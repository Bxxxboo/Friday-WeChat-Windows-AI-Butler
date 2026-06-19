"""有限多 Agent：并发池、工具限制、固定 eval。"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import MagicMock

import pytest

from friday.storage import UserSettings
from friday.sub_agents import (
    SubAgentPool,
    multi_agent_enabled,
    maybe_inject_planner_hint,
    orchestrate_bounded_sub_agents,
    parse_planner_json,
    planner_output_to_markdown,
    prepare_multi_agent_turn,
    sub_agent_tool_allowed,
)

# 固定 eval case（TODOS P1-6）
FIXED_EVAL_USER_TEXT = (
    "帮我整理桌面，然后排查下载文件夹里的重复文件，最后写个汇总脚本"
)
FIXED_EVAL_PLANNER_JSON = (
    '{"steps":["扫描桌面并列出大文件","搜索下载目录中的重复文件","编写汇总脚本并保存到工作区"],'
    '"research_topics":["Downloads"]}'
)


def test_multi_agent_enabled_by_default():
    settings = UserSettings()
    assert multi_agent_enabled(settings) is True
    assert settings.max_sub_agents == 3


def test_multi_agent_skips_hint_when_disabled():
    settings = UserSettings(multi_agent_enabled=False)
    text = "整理桌面并压缩备份"
    assert maybe_inject_planner_hint(text, settings, brain=None) == text


def test_multi_agent_injects_hint_when_enabled():
    settings = UserSettings()
    text = "整理桌面并压缩备份"
    out = maybe_inject_planner_hint(text, settings, brain=None)
    assert out != text
    assert "多 Agent 试点" in out


def test_sub_agent_blocks_dangerous_tools():
    assert sub_agent_tool_allowed("list_directory") is True
    assert sub_agent_tool_allowed("read_text_file") is True
    assert sub_agent_tool_allowed("delete_file") is False
    assert sub_agent_tool_allowed("run_powershell") is False
    assert sub_agent_tool_allowed("send_weixin_contact_message") is False
    assert sub_agent_tool_allowed("write_text_file") is False


def test_fixed_eval_planner_parse_quality():
    parsed = parse_planner_json(FIXED_EVAL_PLANNER_JSON)
    assert len(parsed.steps) >= 3
    assert all(len(step) >= 4 for step in parsed.steps)
    md = planner_output_to_markdown(parsed)
    assert "任务计划" in md
    assert "1." in md


def test_sub_agent_pool_queues_beyond_max():
    pool = SubAgentPool(2)
    lock = threading.Lock()
    current = {"v": 0}
    peak = {"v": 0}

    def slow_task() -> str:
        with lock:
            current["v"] += 1
            peak["v"] = max(peak["v"], current["v"])
        time.sleep(0.08)
        with lock:
            current["v"] -= 1
        return "done"

    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = [ex.submit(pool.run, "research", slow_task) for _ in range(4)]
        results = [f.result(timeout=5) for f in futs]
    assert results == ["done"] * 4
    assert peak["v"] <= 2


def test_prepare_multi_agent_skipped_when_disabled(tmp_appdata, monkeypatch):
    monkeypatch.setattr("friday.sessions.get_appdata_dir", lambda: tmp_appdata)
    settings = UserSettings(multi_agent_enabled=False)
    text, plan_md = prepare_multi_agent_turn(
        FIXED_EVAL_USER_TEXT,
        settings,
        brain=MagicMock(),
        session_id="",
    )
    assert plan_md == ""
    assert text == FIXED_EVAL_USER_TEXT


def test_prepare_multi_agent_persists_plan(tmp_appdata, monkeypatch):
    monkeypatch.setattr("friday.sessions.get_appdata_dir", lambda: tmp_appdata)
    from friday.sessions import create_session, get_session

    session = create_session("multi-agent")
    settings = UserSettings(multi_agent_enabled=True, max_sub_agents=2)

    planner_resp = MagicMock()
    planner_resp.choices = [MagicMock(message=MagicMock(content=FIXED_EVAL_PLANNER_JSON))]
    research_resp = MagicMock()
    research_resp.choices = [
        MagicMock(message=MagicMock(content="- 列出 Downloads 下 >100MB 文件\n- 记录重复文件名"))
    ]
    brain = MagicMock()
    brain.chat = MagicMock(side_effect=[planner_resp, research_resp])

    text, plan_md = prepare_multi_agent_turn(
        FIXED_EVAL_USER_TEXT,
        settings,
        brain,
        session_id=session.id,
    )
    assert plan_md
    assert text == FIXED_EVAL_USER_TEXT
    saved = get_session(session.id)
    assert saved is not None
    assert "任务计划" in saved.plan_markdown
    assert brain.chat.call_count >= 1


def test_operations_log_sub_agent_trigger(tmp_appdata, monkeypatch):
    monkeypatch.setattr("friday.operations.get_appdata_dir", lambda: tmp_appdata)
    from friday.operations import list_operations
    from friday.sub_agents import _log_sub_agent

    _log_sub_agent("planner", "3 步", session_id="sess-1", ok=True)
    entries = list_operations(limit=5)
    assert entries
    assert entries[-1]["trigger"] == "sub_agent:planner"
