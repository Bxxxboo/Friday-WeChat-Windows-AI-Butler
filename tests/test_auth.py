from __future__ import annotations

import secrets

import friday.auth as auth


def test_api_token_prefers_env_after_module_import():
    auth._TOKEN = ""
    token = secrets.token_hex(32)

    import os

    os.environ.pop("FRIDAY_API_TOKEN", None)
    from friday.server import app  # noqa: F401 — triggers ensure_api_token at import

    wrong = auth.get_api_token()
    os.environ["FRIDAY_API_TOKEN"] = token

    assert auth.ensure_api_token() == token
    assert auth.verify_api_token(token)
    assert wrong != token
