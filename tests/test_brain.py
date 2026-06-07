from __future__ import annotations

from unittest.mock import patch

from friday.brain import DeepSeekBrain, resolve_max_context
from friday.storage import UserSettings


def test_brain_lazy_encoder():
    brain = DeepSeekBrain(UserSettings(api_key="sk-test", model="deepseek-chat"))
    assert brain._encoder_initialized is False
    with patch.object(DeepSeekBrain, "_init_encoder", return_value=None) as init:
        brain.count_tokens([{"role": "user", "content": "hello"}])
        init.assert_called_once()
    assert brain._encoder_initialized is True


def test_resolve_max_context_fallback():
    settings = UserSettings(model="deepseek-chat")
    assert resolve_max_context(settings) == 64_000


def test_resolve_max_context_from_api():
    settings = UserSettings(model="deepseek-chat", api_key="sk-test")

    class FakeModel:
        max_context_tokens = 120_000

    class FakeClient:
        class models:
            @staticmethod
            def retrieve(_model: str):
                return FakeModel()

    assert resolve_max_context(settings, client=FakeClient()) == 120_000
