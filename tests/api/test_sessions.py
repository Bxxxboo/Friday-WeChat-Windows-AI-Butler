from __future__ import annotations

import json
from pathlib import Path

from friday.sessions import (
    create_session,
    delete_session,
    get_session,
    list_sessions,
    save_agent_state,
    session_exists,
)


def test_session_crud(tmp_appdata):
    session = create_session(title="测试对话")
    assert session_exists(session.id)
    assert get_session(session.id) is not None

    summaries, active = list_sessions()
    assert any(s.id == session.id for s in summaries)
    assert active == session.id

    save_agent_state(
        session.id,
        [{"role": "user", "content": "你好"}],
        user_text="你好",
    )
    updated = get_session(session.id)
    assert updated is not None
    assert updated.title != "新对话"
    assert len(updated.agent_messages) == 1

    _, next_id = delete_session(session.id)
    assert not session_exists(session.id)
    assert next_id


def test_session_corrupt_json_returns_none(tmp_appdata):
    session = create_session()
    path = tmp_appdata / "sessions" / f"{session.id}.json"
    path.write_text("{broken", encoding="utf-8")
    assert get_session(session.id) is None
