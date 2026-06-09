"""本地 API 访问令牌 —— 防止本机其他进程未授权调用。"""

from __future__ import annotations

import os
import secrets

from friday.io_utils import atomic_write_text
from friday.paths import get_appdata_dir

_TOKEN: str = ""
_TOKEN_FILENAME = "api_token.txt"


def _token_path():
    return get_appdata_dir() / _TOKEN_FILENAME


def load_persisted_api_token() -> str:
    path = _token_path()
    if not path.is_file():
        return ""
    try:
        token = path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    return token if len(token) >= 32 else ""


def persist_api_token(token: str) -> None:
    value = token.strip()
    if len(value) < 32:
        return
    atomic_write_text(_token_path(), value + "\n")


def ensure_api_token() -> str:
    global _TOKEN
    env = os.environ.get("FRIDAY_API_TOKEN", "").strip()
    if env:
        _TOKEN = env
        persist_api_token(_TOKEN)
        return _TOKEN
    if _TOKEN:
        return _TOKEN
    persisted = load_persisted_api_token()
    if persisted:
        _TOKEN = persisted
        return _TOKEN
    _TOKEN = secrets.token_hex(32)
    persist_api_token(_TOKEN)
    return _TOKEN


def get_api_token() -> str:
    return ensure_api_token()


def set_api_token(token: str) -> None:
    global _TOKEN
    _TOKEN = token.strip()
    persist_api_token(_TOKEN)


def verify_api_token(provided: str | None) -> bool:
    if not provided:
        return False
    return secrets.compare_digest(provided, ensure_api_token())
