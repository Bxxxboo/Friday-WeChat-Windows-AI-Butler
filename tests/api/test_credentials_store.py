from __future__ import annotations

import json

from friday.credentials_store import (
    credentials_dir,
    load_api_secrets,
    migrate_secrets_from_settings_json_if_needed,
    secrets_path,
)
from friday.io_utils import load_json
from friday.storage import UserSettings, load_settings, save_settings


def test_api_secrets_saved_in_credentials_dir(tmp_appdata):
    original = UserSettings(api_key="sk-test-credentials-store-key")
    save_settings(original)
    assert secrets_path().is_file()
    assert (credentials_dir() / ".fernet_key").is_file()
    loaded = load_settings()
    assert loaded.api_key == "sk-test-credentials-store-key"


def test_empty_save_does_not_wipe_existing_key(tmp_appdata):
    save_settings(UserSettings(api_key="sk-preserve-me-please"))
    save_settings(UserSettings(api_key=""))
    loaded = load_settings()
    assert loaded.api_key == "sk-preserve-me-please"


def test_migrate_secrets_from_legacy_settings_json(tmp_appdata):
    from friday.storage import _encrypt_key

    settings_path = tmp_appdata / "settings.json"
    settings_path.write_text(
        json.dumps({"api_key": _encrypt_key("sk-migrated-from-settings"), "model": "deepseek-chat"}),
        encoding="utf-8",
    )
    assert migrate_secrets_from_settings_json_if_needed()
    assert secrets_path().is_file()
    secrets = load_api_secrets()
    assert secrets.get("api_key") == "sk-migrated-from-settings"
    loaded = load_settings()
    assert loaded.api_key == "sk-migrated-from-settings"


def test_save_replaces_existing_key_when_credentials_present(tmp_appdata):
    save_settings(UserSettings(api_key="sk-old-key-12345678"))
    save_settings(UserSettings(api_key="sk-new-mimo-key-12345678901234567890"))
    loaded = load_settings()
    assert loaded.api_key == "sk-new-mimo-key-12345678901234567890"


def test_credentials_preferred_when_settings_decrypt_fails(tmp_appdata):
    save_settings(UserSettings(api_key="sk-authoritative-key"))
    raw = load_json(tmp_appdata / "settings.json")
    raw["api_key"] = "fernet:invalid-token"
    (tmp_appdata / "settings.json").write_text(json.dumps(raw), encoding="utf-8")
    loaded = load_settings()
    assert loaded.api_key == "sk-authoritative-key"
