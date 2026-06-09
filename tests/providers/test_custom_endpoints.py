"""自定义 OpenAI 兼容接入测试。"""

from friday.custom_endpoints import (
    add_blank_endpoint,
    delete_custom_endpoint,
    endpoint_id_from_provider,
    is_custom_provider_id,
    provider_id_for_endpoint,
    switch_custom_endpoint,
    upsert_endpoint,
)
from friday.storage import UserSettings, merge_settings


def test_upsert_and_switch_custom_llm():
    settings = UserSettings()
    settings = upsert_endpoint(
        settings,
        "llm",
        name="本地 Ollama",
        api_key="sk-test-123456",
        base_url="http://127.0.0.1:11434/v1",
        model="llama3",
        preserve_key_if_empty=False,
    )
    pid = settings.llm_provider
    assert is_custom_provider_id(pid)
    assert settings.model == "llama3"

    settings = add_blank_endpoint(settings, "llm", name="中转 B")
    first_id = endpoint_id_from_provider(pid)
    switched = switch_custom_endpoint(settings, "llm", first_id or "")
    assert switched.model == "llama3"


def test_delete_custom_endpoint():
    settings = upsert_endpoint(
        UserSettings(),
        "llm",
        name="A",
        api_key="key-a",
        base_url="https://a.example/v1",
        model="a",
        preserve_key_if_empty=False,
    )
    eid = endpoint_id_from_provider(settings.llm_provider)
    settings = add_blank_endpoint(settings, "llm", name="B")
    settings = delete_custom_endpoint(settings, "llm", eid or "")
    assert len(settings.llm_custom_endpoints) == 1
    assert settings.llm_custom_endpoints[0]["name"] == "B"
    assert is_custom_provider_id(settings.llm_provider)


def test_merge_settings_switch_custom():
    settings = upsert_endpoint(
        UserSettings(),
        "llm",
        name="A",
        api_key="key-a",
        base_url="https://a.example/v1",
        model="model-a",
        preserve_key_if_empty=False,
    )
    settings = add_blank_endpoint(settings, "llm", name="B")
    first_pid = provider_id_for_endpoint(settings.llm_custom_endpoints[0]["id"])
    merged = merge_settings(settings, {"llm_provider": first_pid, "switch_llm_profile": True})
    assert merged.model == "model-a"


def test_persist_custom_on_save_vision():
    pid = provider_id_for_endpoint("test123")
    settings = UserSettings(vision_provider=pid, vision_model="gpt-4o")
    merged = merge_settings(
        settings,
        {
            "vision_provider": pid,
            "vision_api_key": "vision-key-123456",
            "vision_base_url": "https://api.example/v1",
            "vision_model": "gpt-4o-mini",
            "custom_endpoint_name": "GPT Relay",
        },
    )
    assert len(merged.vision_custom_endpoints) == 1
    assert merged.vision_custom_endpoints[0]["name"] == "GPT Relay"
    assert merged.vision_model == "gpt-4o-mini"
