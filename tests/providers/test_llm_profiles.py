"""大模型服务商配置记忆测试。"""

from friday.llm_profiles import (
    persist_active_profile,
    profiles_summary,
    seed_profiles_from_active,
    switch_llm_provider,
)
from friday.storage import UserSettings, merge_settings


def test_switch_llm_provider_restores_saved_profile():
    current = UserSettings(
        llm_provider="mimo",
        api_key="mimo-key-123456",
        base_url="https://api.xiaomimimo.com/v1",
        model="mimo-v2.5-pro",
        llm_profiles={
            "deepseek": {
                "api_key": "ds-key-abcdefgh",
                "base_url": "https://api.deepseek.com",
                "model": "deepseek-v4-flash",
            }
        },
    )
    switched = switch_llm_provider(current, "deepseek")
    assert switched.llm_provider == "deepseek"
    assert switched.api_key == "ds-key-abcdefgh"
    assert switched.model == "deepseek-v4-flash"
    assert switched.llm_profiles["mimo"]["api_key"] == "mimo-key-123456"


def test_merge_settings_switch_flag():
    current = UserSettings(
        llm_provider="mimo",
        api_key="mimo-key",
        base_url="https://api.xiaomimimo.com/v1",
        model="mimo-v2-flash",
        llm_profiles={
            "deepseek": {
                "api_key": "ds-key",
                "base_url": "https://api.deepseek.com",
                "model": "deepseek-chat",
            }
        },
    )
    merged = merge_settings(current, {"llm_provider": "deepseek", "switch_llm_profile": True})
    assert merged.api_key == "ds-key"
    assert merged.llm_provider == "deepseek"


def test_persist_active_profile_on_save():
    current = UserSettings(
        llm_provider="deepseek",
        api_key="old-key",
        base_url="https://api.deepseek.com",
        model="deepseek-chat",
    )
    merged = merge_settings(
        current,
        {"api_key": "new-key-123456", "base_url": "https://api.deepseek.com", "model": "deepseek-v4-pro"},
    )
    assert merged.llm_profiles["deepseek"]["api_key"] == "new-key-123456"
    assert merged.llm_profiles["deepseek"]["model"] == "deepseek-v4-pro"


def test_seed_profiles_from_active():
    settings = UserSettings(
        api_key="sk-test",
        base_url="https://api.deepseek.com",
        model="deepseek-chat",
        llm_provider="deepseek",
    )
    seeded = seed_profiles_from_active(settings)
    assert seeded.llm_profiles["deepseek"]["api_key"] == "sk-test"


def test_switch_llm_to_mimo_syncs_vision():
    current = UserSettings(
        llm_provider="deepseek",
        api_key="ds-key",
        base_url="https://api.deepseek.com",
        model="deepseek-v4-flash",
        vision_provider="ark",
        vision_base_url="https://ark.cn-beijing.volces.com/api/v3",
        vision_model="mimo-v2.5",
        vision_api_key="ark-old",
        llm_profiles={
            "mimo": {
                "api_key": "mimo-key-123456",
                "base_url": "https://api.xiaomimimo.com/v1",
                "model": "mimo-v2.5-pro",
            }
        },
    )
    switched = switch_llm_provider(current, "mimo")
    assert switched.llm_provider == "mimo"
    assert switched.model == "mimo-v2.5-pro"
    assert switched.vision_provider == "mimo"
    assert switched.vision_base_url == "https://api.xiaomimimo.com/v1"
    assert switched.vision_model == "mimo-v2.5"
    assert switched.vision_api_key == "mimo-key-123456"


def test_profiles_summary_masks_key():
    settings = UserSettings(
        llm_provider="mimo",
        llm_profiles={
            "mimo": {"api_key": "abcdefghijklmnop", "base_url": "https://api.xiaomimimo.com/v1", "model": "mimo-v2-flash"}
        },
    )
    summary = profiles_summary(settings)
    assert summary["mimo"]["configured"] is True
    assert "abcd" in str(summary["mimo"]["api_key_masked"])
