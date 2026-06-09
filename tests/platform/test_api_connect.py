from __future__ import annotations

from friday.api_connect import (
    _auth_status_key,
    _read_auth_status,
    apply_network_environment,
    diagnose_llm,
    format_api_error,
    parse_host_port,
    probe_llm_status,
    quick_reachability,
    record_service_status,
)
from friday.error_hints import classify_error
from friday.storage import UserSettings


def test_parse_host_port_https_default():
    host, port, scheme = parse_host_port("https://api.deepseek.com")
    assert host == "api.deepseek.com"
    assert port == 443
    assert scheme == "https"


def test_format_api_error_connection():
    msg = format_api_error("Connection error", context="api_test")
    assert "连接" in msg or "API" in msg
    assert classify_error("Connection error", context="api_test").code == "api_network"


def test_diagnose_llm_missing_key():
    settings = UserSettings(api_key="", base_url="https://api.deepseek.com")
    steps = diagnose_llm(settings, include_api=False)
    assert steps[0].ok
    assert any(s.name == "DNS 解析" for s in steps)


def test_apply_network_proxy(monkeypatch):
    import os

    monkeypatch.delenv("HTTPS_PROXY", raising=False)
    settings = UserSettings(api_proxy="http://127.0.0.1:7890")
    apply_network_environment(settings)
    assert os.environ.get("HTTPS_PROXY") == "http://127.0.0.1:7890"


def test_quick_reachability_invalid_url():
    ok, detail = quick_reachability("", None)
    assert ok is False
    assert detail


def test_probe_llm_status_not_configured():
    settings = UserSettings(api_key="")
    ok, detail = probe_llm_status(settings)
    assert ok is False
    assert "未配置" in detail


def test_probe_image_gen_status_not_enabled():
    from friday.api_connect import probe_image_gen_status

    settings = UserSettings(image_gen_enabled=False)
    ok, detail = probe_image_gen_status(settings)
    assert ok is False
    assert "未启用" in detail


def test_probe_image_gen_status_uses_lightweight_verify(monkeypatch):
    from friday.api_connect import probe_image_gen_status

    settings = UserSettings(
        image_gen_enabled=True,
        image_gen_api_key="sk-test-key-12345678",
        image_gen_model="image2",
        image_gen_base_url="https://next.zhima.world",
    )

    monkeypatch.setattr(
        "friday.api_connect.quick_reachability",
        lambda *_a, **_k: (True, "next.zhima.world 网络可达"),
    )
    monkeypatch.setattr(
        "friday.image_gen.verify_image_gen_api",
        lambda *_a, **_k: (True, "API 认证通过"),
    )

    ok, detail = probe_image_gen_status(settings, force=True)
    assert ok is True
    assert "认证通过" in detail


def test_record_service_status_cached():
    settings = UserSettings(api_key="sk-test-key-123456", base_url="https://api.deepseek.com")
    record_service_status("llm", settings, False, "连接失败")
    cached = _read_auth_status(_auth_status_key("llm", settings), service="llm")
    assert cached is not None
    assert cached[0] is False


def test_image_gen_auth_status_key_uses_default_base_url():
    settings = UserSettings(
        image_gen_enabled=True,
        image_gen_api_key="sk-test-key-12345678",
        image_gen_model="image2",
        image_gen_base_url="",
        image_gen_provider="openai_compat",
    )
    key = _auth_status_key("image_gen", settings)
    assert "https://next.zhima.world" in key
    assert "openai_compat" not in key


def test_probe_image_gen_status_uses_test_cache(monkeypatch):
    from friday.api_connect import probe_image_gen_status

    settings = UserSettings(
        image_gen_enabled=True,
        image_gen_api_key="sk-test-key-12345678",
        image_gen_model="image2",
        image_gen_base_url="",
        image_gen_provider="openai_compat",
    )
    record_service_status("image_gen", settings, True, "生图测试通过")

    monkeypatch.setattr(
        "friday.api_connect.quick_reachability",
        lambda *_a, **_k: (False, "should not be called"),
    )

    ok, detail = probe_image_gen_status(settings)
    assert ok is True
    assert "生图测试通过" in detail
