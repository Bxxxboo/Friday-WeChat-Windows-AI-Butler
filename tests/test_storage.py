from __future__ import annotations

from friday.storage import UserSettings, load_settings, save_settings


def test_settings_api_key_encryption_roundtrip(tmp_appdata):
    original = UserSettings(api_key="sk-test-secret-key-123456")
    save_settings(original)
    loaded = load_settings()
    assert loaded.api_key == "sk-test-secret-key-123456"
    assert loaded.masked_key().startswith("sk-t")


def test_settings_persist_fields(tmp_appdata):
    original = UserSettings(
        model="deepseek-chat",
        theme="light",
        restrict_to_workspace=False,
        auto_approve_scheduled_writes=False,
    )
    save_settings(original)
    loaded = load_settings()
    assert loaded.model == "deepseek-chat"
    assert loaded.theme == "light"
    assert loaded.restrict_to_workspace is False
    assert loaded.auto_approve_scheduled_writes is False


def test_settings_default_auto_approve_scheduled_writes():
    assert UserSettings().auto_approve_scheduled_writes is False
