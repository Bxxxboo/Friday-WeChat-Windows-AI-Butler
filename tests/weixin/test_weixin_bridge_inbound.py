from __future__ import annotations

import pytest

from friday.storage import UserSettings
from friday.weixin.bridge import InboundRequest, handle_inbound
from friday.weixin.client import WeixinAccount


def _account() -> WeixinAccount:
    return WeixinAccount(
        account_id="bot-1",
        token="token-abc",
        base_url="https://ilinkai.weixin.qq.com",
        user_id="user-1",
    )


@pytest.fixture(autouse=True)
def _reset_weixin_bridge_caches():
    import friday.weixin.bridge as bridge

    bridge._recent_inbound.clear()
    bridge._recent_busy_notice.clear()
    bridge._processing_keys.clear()
    bridge._peer_processing_text.clear()
    bridge._approval_waiters.clear()
    bridge._approval_meta.clear()
    yield


def test_handle_inbound_returns_agent_reply_via_openclaw(tmp_appdata, monkeypatch):
    monkeypatch.setattr(
        "friday.weixin.bridge.load_settings",
        lambda: UserSettings(
            api_key="sk-test-key-12345678",
            weixin_bridge_enabled=True,
        ),
    )
    monkeypatch.setattr("friday.weixin.bridge.resolve_account", lambda _aid: _account())
    monkeypatch.setattr("friday.weixin.bridge.resolve_session_id", lambda *_a, **_k: "wx-session-1")
    monkeypatch.setattr("friday.weixin.bridge._run_agent", lambda **_k: "你好，我是星期五。")
    sent: list[str] = []
    monkeypatch.setattr(
        "friday.weixin.bridge.send_peer_text",
        lambda *_a, text, **_k: sent.append(text),
    )

    result = handle_inbound(
        InboundRequest(
            text="帮我看一下 CPU",
            sender_id="peer-123",
            account_id="bot-1",
            context_token="ctx-token",
        )
    )

    assert result.handled is True
    assert result.reply == ""
    assert sent == ["你好，我是星期五。"]


def test_handle_inbound_greeting_fast_path_skips_agent(tmp_appdata, monkeypatch):
    monkeypatch.setattr(
        "friday.weixin.bridge.load_settings",
        lambda: UserSettings(
            api_key="sk-live-key-1234567890",
            weixin_bridge_enabled=True,
        ),
    )
    monkeypatch.setattr("friday.weixin.bridge.resolve_account", lambda _aid: _account())
    monkeypatch.setattr("friday.weixin.bridge.resolve_session_id", lambda *_a, **_k: "wx-session-1")

    def fail_agent(**_kwargs):
        raise AssertionError("_run_agent should not be called for greetings")

    monkeypatch.setattr("friday.weixin.bridge._run_agent", fail_agent)
    sent: list[str] = []
    monkeypatch.setattr(
        "friday.weixin.bridge.send_peer_text",
        lambda *_a, text, **_k: sent.append(text),
    )

    result = handle_inbound(
        InboundRequest(text="你好", sender_id="peer-123", account_id="bot-1"),
    )

    assert result.handled is True
    assert result.reply == ""
    assert len(sent) == 1
    assert "星期五" in sent[0]


def test_handle_inbound_falls_back_to_openclaw_when_ilink_fails(tmp_appdata, monkeypatch):
    monkeypatch.setattr(
        "friday.weixin.bridge.load_settings",
        lambda: UserSettings(
            api_key="sk-test-key-12345678",
            weixin_bridge_enabled=True,
        ),
    )
    monkeypatch.setattr("friday.weixin.bridge.resolve_account", lambda _aid: _account())
    monkeypatch.setattr("friday.weixin.bridge.resolve_session_id", lambda *_a, **_k: "wx-session-1")
    monkeypatch.setattr("friday.weixin.bridge._run_agent", lambda **_k: "备用通道回复")

    def fail_send(*_args, **_kwargs):
        raise RuntimeError("微信发送失败 (401)")

    monkeypatch.setattr("friday.weixin.bridge.send_peer_text", fail_send)

    result = handle_inbound(
        InboundRequest(
            text="你好",
            sender_id="peer-123",
            account_id="bot-1",
            context_token="ctx-token",
        )
    )

    assert result.handled is True
    assert result.reply == "备用通道回复"


def test_handle_inbound_reports_missing_api(tmp_appdata, monkeypatch):
    monkeypatch.setattr(
        "friday.weixin.bridge.load_settings",
        lambda: UserSettings(weixin_bridge_enabled=True),
    )
    monkeypatch.setattr("friday.weixin.bridge.resolve_account", lambda _aid: _account())
    monkeypatch.setattr("friday.weixin.bridge.resolve_session_id", lambda *_a, **_k: "wx-session-1")
    sent: list[str] = []
    monkeypatch.setattr(
        "friday.weixin.bridge.send_peer_text",
        lambda *_a, text, **_k: sent.append(text),
    )

    result = handle_inbound(
        InboundRequest(text="你好", sender_id="peer-123", account_id="bot-1"),
    )

    assert result.reply == ""
    assert sent == ["请先在星期五桌面版「设置 → API 连接」中配置并保存大模型 API Key。"]


def test_format_weixin_agent_error_api_message():
    from friday.weixin.bridge import _format_weixin_agent_error

    class _FakeApiError(Exception):
        pass

    msg = _format_weixin_agent_error(_FakeApiError("Error code: 401 - Invalid API key"))
    assert "执行出错" in msg
    assert msg != "执行出错，请稍后重试，或在星期五桌面版查看日志。"


def test_handle_inbound_surfaces_agent_error(tmp_appdata, monkeypatch):
    monkeypatch.setattr(
        "friday.weixin.bridge.load_settings",
        lambda: UserSettings(
            api_key="sk-test-key-12345678",
            weixin_bridge_enabled=True,
        ),
    )
    monkeypatch.setattr("friday.weixin.bridge.resolve_account", lambda _aid: _account())
    monkeypatch.setattr("friday.weixin.bridge.resolve_session_id", lambda *_a, **_k: "wx-session-1")

    def boom(**_k):
        raise RuntimeError("Connection error: timed out")

    monkeypatch.setattr("friday.weixin.bridge._run_agent", boom)
    sent: list[str] = []
    monkeypatch.setattr(
        "friday.weixin.bridge.send_peer_text",
        lambda *_a, text, **_k: sent.append(text),
    )

    result = handle_inbound(
        InboundRequest(text="你好", sender_id="peer-123", account_id="bot-1"),
    )

    assert result.handled is True
    assert result.reply == ""
    assert len(sent) == 1
    assert sent[0].startswith("执行出错")
    assert "timed out" in sent[0] or "连接" in sent[0]


def test_handle_inbound_ignores_duplicate_text(tmp_appdata, monkeypatch):
    monkeypatch.setattr(
        "friday.weixin.bridge.load_settings",
        lambda: UserSettings(
            api_key="sk-test-key-12345678",
            weixin_bridge_enabled=True,
        ),
    )
    monkeypatch.setattr("friday.weixin.bridge.resolve_account", lambda _aid: _account())
    monkeypatch.setattr("friday.weixin.bridge.resolve_session_id", lambda *_a, **_k: "wx-session-1")
    monkeypatch.setattr("friday.weixin.bridge._run_agent", lambda **_k: "完成")
    monkeypatch.setattr("friday.weixin.bridge.send_peer_text", lambda *_a, **_k: None)

    req = InboundRequest(text="你好", sender_id="peer-dup", account_id="bot-1")
    first = handle_inbound(req)
    second = handle_inbound(req)

    assert first.reply == ""
    assert second.handled is True
    assert second.reply == ""


def test_handle_inbound_ignores_concurrent_duplicate_text(tmp_appdata, monkeypatch):
    import threading

    monkeypatch.setattr(
        "friday.weixin.bridge.load_settings",
        lambda: UserSettings(
            api_key="sk-test-key-12345678",
            weixin_bridge_enabled=True,
        ),
    )
    monkeypatch.setattr("friday.weixin.bridge.resolve_account", lambda _aid: _account())
    monkeypatch.setattr("friday.weixin.bridge.resolve_session_id", lambda *_a, **_k: "wx-session-1")

    gate = threading.Event()
    started = threading.Event()

    def slow_agent(**_k):
        started.set()
        gate.wait(timeout=2)
        return "额度查询结果"

    monkeypatch.setattr("friday.weixin.bridge._run_agent", slow_agent)
    sent: list[str] = []
    monkeypatch.setattr(
        "friday.weixin.bridge.send_peer_text",
        lambda *_a, text, **_k: sent.append(text),
    )

    req = InboundRequest(text="我的deepseekapi额度还有多少", sender_id="peer-same", account_id="bot-1")
    worker = threading.Thread(target=lambda: handle_inbound(req))
    worker.start()
    assert started.wait(timeout=2)

    duplicate = handle_inbound(req)
    gate.set()
    worker.join(timeout=3)

    assert duplicate.reply == ""
    assert not any("处理中" in msg for msg in sent)
    assert any("额度查询结果" in msg for msg in sent)


def test_handle_inbound_busy_while_processing(tmp_appdata, monkeypatch):
    import threading

    monkeypatch.setattr(
        "friday.weixin.bridge.load_settings",
        lambda: UserSettings(
            api_key="sk-test-key-12345678",
            weixin_bridge_enabled=True,
        ),
    )
    monkeypatch.setattr("friday.weixin.bridge.resolve_account", lambda _aid: _account())
    monkeypatch.setattr("friday.weixin.bridge.resolve_session_id", lambda *_a, **_k: "wx-session-1")

    gate = threading.Event()
    started = threading.Event()

    def slow_agent(**_k):
        started.set()
        gate.wait(timeout=2)
        return "done"

    monkeypatch.setattr("friday.weixin.bridge._run_agent", slow_agent)
    sent: list[str] = []
    monkeypatch.setattr(
        "friday.weixin.bridge.send_peer_text",
        lambda *_a, text, **_k: sent.append(text),
    )

    worker = threading.Thread(
        target=lambda: handle_inbound(
            InboundRequest(text="第一个问题", sender_id="peer-busy", account_id="bot-1"),
        ),
    )
    worker.start()
    assert started.wait(timeout=2)

    result = handle_inbound(
        InboundRequest(text="第二个问题", sender_id="peer-busy", account_id="bot-1"),
    )
    gate.set()
    worker.join(timeout=3)

    assert result.reply == ""
    assert any("处理中" in msg for msg in sent)


def test_handle_inbound_bridge_disabled_replies(tmp_appdata, monkeypatch):
    monkeypatch.setattr(
        "friday.weixin.bridge.load_settings",
        lambda: UserSettings(weixin_bridge_enabled=False),
    )

    result = handle_inbound(
        InboundRequest(text="你好", sender_id="peer-123", account_id="bot-1"),
    )

    assert result.handled is True
    assert "桥接已关闭" in result.reply
