from __future__ import annotations

import secrets

import friday.auth as auth


def test_api_token_prefers_env_after_module_import():
    auth._TOKEN = ""
    token = secrets.token_hex(32)

    import os

    os.environ.pop("FRIDAY_API_TOKEN", None)
    from friday.server import app  # noqa: F401 — import 时不应固定 token

    os.environ["FRIDAY_API_TOKEN"] = token

    assert auth.ensure_api_token() == token
    assert auth.verify_api_token(token)


def test_api_token_persists_to_appdata(tmp_appdata, monkeypatch):
    import os

    monkeypatch.delenv("FRIDAY_API_TOKEN", raising=False)
    auth._TOKEN = ""

    first = auth.ensure_api_token()
    second = auth.load_persisted_api_token()

    assert first == second
    assert (tmp_appdata / "api_token.txt").is_file()


def test_auth_token_endpoint_localhost():
    import os

    from fastapi.testclient import TestClient

    from friday.server import app

    token = secrets.token_hex(32)
    os.environ["FRIDAY_API_TOKEN"] = token
    auth.set_api_token(token)

    with TestClient(app) as client:
        res = client.get("/api/auth/token")
        assert res.status_code == 200
        assert res.json()["token"] == token
