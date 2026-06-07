"""本地 API 访问令牌 —— 防止本机其他进程未授权调用。"""

from __future__ import annotations

import os
import secrets

_TOKEN: str = ""


def ensure_api_token() -> str:
    global _TOKEN
    env = os.environ.get("FRIDAY_API_TOKEN", "").strip()
    if env:
        _TOKEN = env
        return _TOKEN
    if not _TOKEN:
        _TOKEN = secrets.token_hex(32)
    return _TOKEN


def get_api_token() -> str:
    return ensure_api_token()


def set_api_token(token: str) -> None:
    global _TOKEN
    _TOKEN = token.strip()


def verify_api_token(provided: str | None) -> bool:
    if not provided:
        return False
    return secrets.compare_digest(provided, ensure_api_token())
