from __future__ import annotations

import pytest

from friday.error_hints import classify_error, format_user_message


def test_classify_backend_starting():
    hint = classify_error("", context="backend_starting")
    assert hint.code == "backend_starting"
    assert "启动" in hint.detail
    assert hint.hint


def test_classify_pythonnet():
    hint = classify_error("ImportError: Python.Runtime")
    assert hint.code == "runtime_lib"
    assert "VC++" in hint.detail or "运行库" in hint.detail


def test_classify_multipart():
    hint = classify_error("No module named 'multipart'")
    assert hint.code == "missing_multipart"


def test_classify_api_network():
    hint = classify_error("Connection timed out", context="api_test")
    assert hint.code == "api_network"


def test_classify_auth_401():
    hint = classify_error("Unauthorized", context="auth_401")
    assert hint.code == "auth_401"


def test_classify_api_key_missing():
    hint = classify_error("", context="api_key_missing")
    assert hint.code == "api_key_missing"


def test_format_user_message_includes_hint():
    hint = classify_error("", context="backend_starting")
    text = format_user_message(hint)
    assert hint.detail in text
    assert hint.hint in text
