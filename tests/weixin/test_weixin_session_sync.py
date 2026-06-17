from __future__ import annotations

import asyncio

from friday.sessions import create_session, save_agent_state
from friday.ws_broadcast import notify_session_updated, register_ws_client, unregister_ws_client


def test_save_agent_state_without_promote_active(tmp_appdata):
    a = create_session("会话 A")
    b = create_session("会话 B")
    save_agent_state(b.id, [{"role": "user", "content": "B"}], promote_active=True)

    save_agent_state(
        a.id,
        [{"role": "user", "content": "微信消息"}],
        promote_active=False,
    )

    from friday.sessions import list_sessions

    _, active = list_sessions()
    assert active == b.id


def test_notify_session_updated_calls_ws_clients():
    loop = asyncio.new_event_loop()
    events: list[tuple[str, dict]] = []

    async def send(event_type: str, payload: dict | None = None) -> None:
        events.append((event_type, payload or {}))

    register_ws_client(loop, send)
    notify_session_updated("sess-1", source="weixin")
    loop.run_until_complete(asyncio.sleep(0.05))
    unregister_ws_client(loop, send)
    loop.close()

    assert events
    assert events[0][0] == "session_updated"
    assert events[0][1]["session_id"] == "sess-1"
    assert events[0][1]["source"] == "weixin"


def test_build_display_messages_shows_tool_pending_placeholder():
    from friday.sessions import build_display_messages

    display = build_display_messages([
        {"role": "user", "content": "你好"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"id": "c1", "function": {"name": "run_python"}}],
        },
    ])
    assert display[-1]["content"] == "（正在处理…）"
