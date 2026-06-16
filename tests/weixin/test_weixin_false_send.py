from __future__ import annotations

from friday.weixin.bridge import (
    _agent_claims_contact_sent,
    _contact_send_text_only,
    _strip_false_send_claims,
    _user_requests_contact_send,
    _verified_contact_send_in_messages,
    _weixin_contact_send_miss_hint,
)
from friday.weixin.ui_send import SEND_SUCCESS_MARKER, format_send_success


def test_user_contact_send_intent():
    assert _user_requests_contact_send("给白霄发消息，内容是：可以着了")
    assert _user_requests_contact_send("发给张三一条微信")
    assert _user_requests_contact_send("发这句话到我微信沈哥：可以着了")
    assert not _user_requests_contact_send("今天天气怎么样")


def test_contact_send_text_only():
    assert _contact_send_text_only("给沈哥发消息：可以着了")
    assert _contact_send_text_only("发这句话到我微信沈哥：可以着了")
    assert not _contact_send_text_only("把第一节辅导课.docx 发给沈哥")


def test_agent_contact_send_claim():
    assert _agent_claims_contact_sent("已经给白霄发过去了 ✅")
    assert _agent_claims_contact_sent("发给张三了，请查收")
    assert not _agent_claims_contact_sent("我会尝试发送，请稍等")


def test_strip_contact_send_claims():
    body = "已经给白霄发过去了 ✅\n\n还有其他事吗？"
    stripped = _strip_false_send_claims(body)
    assert "白霄" not in stripped
    assert "还有其他事吗" in stripped


def test_verified_contact_send_in_messages():
    ok = format_send_success("白霄", "可以着了")
    assert ok.startswith(SEND_SUCCESS_MARKER)
    messages = [
        {"role": "assistant", "content": "好的"},
        {"role": "tool", "content": ok, "tool_call_id": "1"},
    ]
    assert _verified_contact_send_in_messages(messages)
    assert not _verified_contact_send_in_messages(
        [{"role": "tool", "content": "已启动: 微信"}]
    )


def test_miss_hint_non_empty():
    assert "核对" in _weixin_contact_send_miss_hint()
