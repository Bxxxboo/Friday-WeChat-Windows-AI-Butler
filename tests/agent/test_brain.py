from __future__ import annotations

from unittest.mock import patch

from friday.brain import DeepSeekBrain, build_system_prompt, resolve_max_context, _CONTEXT_MARKER
from friday.storage import UserSettings


def test_init_encoder_returns_none_when_encoding_unavailable():
    brain = DeepSeekBrain(UserSettings(api_key="sk-test", model="deepseek-chat"))
    with patch("tiktoken.get_encoding", side_effect=ValueError("Unknown encoding")):
        assert brain._init_encoder() is None
    tokens = brain.count_tokens([{"role": "user", "content": "hello world"}])
    assert tokens > 0
    brain = DeepSeekBrain(UserSettings(api_key="sk-test", model="deepseek-chat"))
    assert brain._encoder_initialized is False
    with patch.object(DeepSeekBrain, "_init_encoder", return_value=None) as init:
        brain.count_tokens([{"role": "user", "content": "hello"}])
        init.assert_called_once()
    assert brain._encoder_initialized is True


def test_resolve_max_context_fallback():
    settings = UserSettings(model="deepseek-chat")
    assert resolve_max_context(settings) == 64_000


def test_build_system_prompt_cache_marker():
    prompt = build_system_prompt(UserSettings(api_key="sk-test"))
    marker_idx = prompt.index(_CONTEXT_MARKER)
    assert prompt.index("你是「星期五」") < marker_idx
    assert "本机常用文件夹路径" in prompt[marker_idx:]


def test_usage_summary_includes_api_call_count():
    brain = DeepSeekBrain(UserSettings(api_key="sk-test", model="deepseek-chat"))
    brain.reset_turn_api_calls()
    brain.record_api_call()
    brain.record_api_call()
    brain.usage_stats.prompt_tokens = 100
    brain.usage_stats.completion_tokens = 50
    summary = brain.usage_summary()
    assert "本次共调用 2 次 API" in summary
    assert "100" in summary


def test_call_with_transient_retry_counts_each_attempt():
    brain = DeepSeekBrain(UserSettings(api_key="sk-test", model="deepseek-chat"))
    brain.reset_turn_api_calls()
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("429 Too many requests")
        return "ok"

    with patch("friday.api_connect.is_transient_api_error", return_value=True):
        with patch("time.sleep"):
            result = brain._call_with_transient_retry(flaky)

    assert result == "ok"
    assert brain._turn_api_calls == 2


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
