"""log_operation_from_meta 与 agent 事件常量。"""

from __future__ import annotations

from friday import agent_events
from friday.operations import log_operation_from_meta


def test_log_operation_from_meta_uses_agent_meta(tmp_appdata):
    meta = {
        "session_id": "sess-abc",
        "trigger": "weixin",
        "schedule_id": "sched-1",
    }
    entry = log_operation_from_meta(meta, "list_directory", {"path": "C:\\"}, "ok")
    assert entry["session_id"] == "sess-abc"
    assert entry["trigger"] == "weixin"
    assert entry["schedule_id"] == "sched-1"
    assert entry["tool"] == "list_directory"


def test_log_operation_from_meta_empty_meta(tmp_appdata):
    entry = log_operation_from_meta(None, "read_text_file", {"path": "x"}, "done")
    assert entry["session_id"] == ""
    assert entry["trigger"] == "chat"


def test_agent_event_constants_are_stable_strings():
    assert agent_events.EVENT_TOOL_START == "tool_start"
    assert agent_events.EVENT_OPERATION_LOGGED == "operation_logged"
    assert agent_events.EVENT_ASK_BLOCKED == "ask_blocked"
