"""POST /api/settings/startup-tests 与设置页测试对齐。"""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

import friday.server as server_mod
from friday.auth import ensure_api_token
from friday.storage import UserSettings, save_settings


def test_startup_tests_uses_settings_test_logic(tmp_appdata):
    server_mod._backend_ready = True
    client = TestClient(server_mod.app)
    token = ensure_api_token()
    headers = {"X-Friday-Token": token}

    ws = tmp_appdata / "ws"
    ws.mkdir()
    save_settings(
        UserSettings(
            api_key="sk-fake-key-for-testing1234567890",
            model="deepseek-chat",
            workspace=str(ws),
            vision_enabled=False,
            image_gen_enabled=False,
        )
    )

    calls: list[str] = []

    def fake_llm(_cfg):
        calls.append("llm")
        return True, "API 可用"

    def fake_vision(_cfg):
        calls.append("vision")
        return None

    def fake_image(_cfg):
        calls.append("image_gen")
        return None

    with (
        patch("friday.api_connect.test_llm_service", side_effect=fake_llm),
        patch("friday.api_connect.test_vision_service", side_effect=fake_vision),
        patch("friday.api_connect.test_image_gen_service", side_effect=fake_image),
    ):
        res = client.post("/api/settings/startup-tests", headers=headers)

    assert res.status_code == 200
    data = res.json()
    assert data["llm"]["ok"] is True
    assert data["vision"] is None
    assert data["image_gen"] is None
    assert calls == ["llm", "vision", "image_gen"]
