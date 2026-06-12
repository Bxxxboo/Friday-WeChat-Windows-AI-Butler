from __future__ import annotations

from friday.weixin.approval import format_approval_prompt_weixin, parse_approval_text


def test_parse_approval_approve():
    assert parse_approval_text("同意") is True
    assert parse_approval_text("OK") is True
    assert parse_approval_text("  可以  ") is True


def test_parse_approval_reject():
    assert parse_approval_text("拒绝") is False
    assert parse_approval_text("no") is False
    assert parse_approval_text("不要") is False


def test_parse_approval_unknown():
    assert parse_approval_text("帮我整理桌面") is None
    assert parse_approval_text("") is None


def test_format_approval_prompt_weixin_compact():
    text = format_approval_prompt_weixin("创建 Word 文档：文档")
    assert "【需你确认】" in text
    assert "同意" in text
    assert "拒绝" in text
    assert "▸" not in text
