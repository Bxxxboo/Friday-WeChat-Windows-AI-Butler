from __future__ import annotations

from friday.tools._decorators import register_tool
from friday.weixin.ui_send import format_send_success, send_text_to_contact


@register_tool(
    name="send_weixin_contact_message",
    description=(
        "在微信桌面版向指定联系人发送文字消息（侧边栏搜索联系人后发送）。"
        "用户要求给某人发微信/发消息时必须用此工具，不要用 PowerShell 操作微信界面。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "contact": {"type": "string", "description": "联系人昵称（与微信侧边栏显示一致）"},
            "message": {"type": "string", "description": "要发送的文字内容"},
        },
        "required": ["contact", "message"],
    },
)
def send_weixin_contact_message(contact: str, message: str) -> str:
    try:
        send_text_to_contact(contact, message)
        return format_send_success(contact.strip(), message.strip())
    except Exception as exc:  # noqa: BLE001 - surface to model
        return f"发送失败: {exc}"
