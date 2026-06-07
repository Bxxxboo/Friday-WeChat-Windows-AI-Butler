from __future__ import annotations

import json
from pathlib import Path

from friday.config import MAX_PERSISTED_TOOL_CHARS, SESSION_FORMAT_VERSION
from friday.sessions import (
    get_session,
    migrate_session_files,
    save_agent_state,
    create_session,
)


def test_session_save_compresses_tool_messages(tmp_appdata):
    session = create_session()
    long_result = "x" * 5000
    messages = [
        {"role": "user", "content": "查文件"},
        {"role": "assistant", "content": "好的"},
        {"role": "tool", "tool_call_id": "1", "content": long_result},
    ]
    save_agent_state(session.id, messages, user_text="查文件")

    raw = json.loads((tmp_appdata / "sessions" / f"{session.id}.json").read_text(encoding="utf-8"))
    assert raw["format_version"] == SESSION_FORMAT_VERSION
    assert len(raw["display_messages"]) == 2
    tool_content = raw["agent_messages"][-1]["content"]
    assert len(tool_content) < len(long_result)
    assert "已压缩" in tool_content
    assert len(tool_content) <= MAX_PERSISTED_TOOL_CHARS + 40


def test_migrate_old_session_format(tmp_appdata):
    session = create_session(title="旧格式")
    path = tmp_appdata / "sessions" / f"{session.id}.json"
    path.write_text(
        json.dumps(
            {
                "id": session.id,
                "title": "旧格式",
                "created_at": session.created_at,
                "updated_at": session.updated_at,
                "agent_messages": [
                    {"role": "user", "content": "你好"},
                    {"role": "assistant", "content": "你好！"},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    assert migrate_session_files() >= 1
    loaded = get_session(session.id)
    assert loaded is not None
    assert loaded.display_messages
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data.get("format_version") == SESSION_FORMAT_VERSION
