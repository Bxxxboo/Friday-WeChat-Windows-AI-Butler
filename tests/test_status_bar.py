from __future__ import annotations

import asyncio

from friday.agent import FridayAgent
from friday.server import _agent_cache, get_status_bar
from friday.storage import save_settings, UserSettings


def test_status_bar_payload(tmp_appdata):
    ws = tmp_appdata / "ws"
    ws.mkdir()
    save_settings(
        UserSettings(
            api_key="sk-test-key-1234567890",
            model="deepseek-chat",
            workspace=str(ws),
            vision_enabled=False,
        )
    )

    data = asyncio.run(get_status_bar())
    assert data["api_online"] is True
    assert data["vision_enabled"] is False
    assert data["model"] == "deepseek-chat"
    assert isinstance(data["tokens_total"], int)
    assert isinstance(data["tasks"], int)


def test_status_bar_session_tokens(tmp_appdata):
    ws = tmp_appdata / "ws2"
    ws.mkdir()
    settings = UserSettings(
        api_key="sk-test-key-1234567890",
        model="deepseek-chat",
        workspace=str(ws),
    )
    save_settings(settings)

    agent = FridayAgent(settings, lambda _action: True)
    agent.brain.total_prompt_tokens = 120
    agent.brain.total_completion_tokens = 30
    agent._finalize_usage()

    session_id = "test-session-tokens"
    _agent_cache[session_id] = agent
    try:
        data = asyncio.run(get_status_bar(session_id=session_id))
        assert data["tokens_prompt"] == 120
        assert data["tokens_completion"] == 30
        assert data["tokens_total"] == 150
    finally:
        _agent_cache.pop(session_id, None)
