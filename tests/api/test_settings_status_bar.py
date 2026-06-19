"""设置保存后 /api/status-bar 与 vision_enabled 等开关一致。"""

from __future__ import annotations

from fastapi.testclient import TestClient

import friday.server as server_mod
from friday.auth import ensure_api_token
from friday.storage import UserSettings, save_settings


def _client_and_headers():
    server_mod._backend_ready = True
    client = TestClient(server_mod.app)
    token = ensure_api_token()
    return client, {"X-Friday-Token": token, "Content-Type": "application/json"}


def _base_settings(ws) -> UserSettings:
    return UserSettings(
        api_key="sk-fake-key-for-testing1234567890",
        model="deepseek-chat",
        workspace=str(ws),
    )


def test_status_bar_reflects_vision_disabled_after_settings_put(tmp_appdata):
    from friday.api_connect import record_service_status

    ws = tmp_appdata / "ws-vision-off"
    ws.mkdir()
    settings = _base_settings(ws).merge(
        {
            "vision_enabled": True,
            "vision_api_key": "ark-test-key-12345678",
            "vision_model": "ep-test-vision",
        }
    )
    save_settings(settings)
    record_service_status("llm", settings, True, "API 可用")
    record_service_status("vision", settings, True, "视觉 API 可用")

    client, headers = _client_and_headers()

    bar = client.get("/api/status-bar", headers=headers).json()
    assert bar["vision_enabled"] is True

    put = client.put("/api/settings", headers=headers, json={"vision_enabled": False})
    assert put.status_code == 200
    assert put.json()["vision_enabled"] is False

    bar2 = client.get("/api/status-bar", headers=headers).json()
    assert bar2["vision_enabled"] is False
    assert bar2["vision_online"] is False
    assert "未启用" in str(bar2["vision_reach_detail"])


def test_status_bar_reflects_vision_enabled_after_settings_put(tmp_appdata):
    from friday.api_connect import record_service_status

    ws = tmp_appdata / "ws-vision-on"
    ws.mkdir()
    settings = _base_settings(ws).merge(
        {
            "vision_enabled": False,
            "vision_api_key": "ark-test-key-12345678",
            "vision_model": "ep-test-vision",
        }
    )
    save_settings(settings)
    record_service_status("llm", settings, True, "API 可用")

    client, headers = _client_and_headers()

    bar = client.get("/api/status-bar", headers=headers).json()
    assert bar["vision_enabled"] is False

    put = client.put("/api/settings", headers=headers, json={"vision_enabled": True})
    assert put.status_code == 200
    assert put.json()["vision_enabled"] is True

    bar2 = client.get("/api/status-bar", headers=headers).json()
    assert bar2["vision_enabled"] is True
    assert bar2["vision_configured"] is True


def test_settings_put_response_matches_status_bar_enabled_flags(tmp_appdata):
    ws = tmp_appdata / "ws-flags"
    ws.mkdir()
    save_settings(
        _base_settings(ws).merge(
            {
                "vision_enabled": True,
                "vision_api_key": "ark-test-key-12345678",
                "vision_model": "ep-test",
                "image_gen_enabled": False,
            }
        )
    )

    client, headers = _client_and_headers()

    saved = client.put(
        "/api/settings",
        headers=headers,
        json={"vision_enabled": False, "image_gen_enabled": True, "image_gen_model": "gpt-image-2"},
    ).json()

    bar = client.get("/api/status-bar", headers=headers).json()
    assert bar["vision_enabled"] == saved["vision_enabled"]
    assert bar["image_gen_enabled"] == saved["image_gen_enabled"]
