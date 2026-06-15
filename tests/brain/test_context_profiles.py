from __future__ import annotations

from friday.context_assembler import (
    layer_caps_for_profile,
    resolve_memory_profile,
)


def test_resolve_memory_profile_weixin(monkeypatch):
    monkeypatch.setattr("friday.weixin.sessions.is_weixin_session", lambda sid: sid == "wx1")
    assert resolve_memory_profile("wx1", []) == "weixin"
    assert resolve_memory_profile("desktop1", [{"role": "user", "content": "hi"}] * 5) == "chat"


def test_resolve_memory_profile_long_task(monkeypatch):
    class FakeSession:
        plan_markdown = "- [ ] step"
        todos = [{"text": "a", "done": False}]

    monkeypatch.setattr("friday.weixin.sessions.is_weixin_session", lambda _sid: False)
    monkeypatch.setattr("friday.sessions.get_session", lambda _sid: FakeSession())
    assert resolve_memory_profile("s1", []) == "long_task"


def test_layer_caps_weixin_higher_user_memory():
    caps = layer_caps_for_profile("weixin")
    desktop = layer_caps_for_profile("desktop")
    assert caps["user_memory"] > desktop["user_memory"]
    assert caps["checkpoint"] < desktop["checkpoint"]
