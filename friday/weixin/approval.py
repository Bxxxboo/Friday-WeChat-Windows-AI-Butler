from __future__ import annotations

_APPROVE = frozenset(
    {
        "同意",
        "批准",
        "确认",
        "ok",
        "okay",
        "yes",
        "y",
        "是",
        "好",
        "可以",
        "行",
        "通过",
    }
)
_REJECT = frozenset(
    {
        "拒绝",
        "不同意",
        "否",
        "no",
        "n",
        "不要",
        "取消",
        "算了",
        "不行",
    }
)


def parse_approval_text(text: str) -> bool | None:
    """解析微信审批回复。无法识别时返回 None。"""
    normalized = (text or "").strip().lower()
    if not normalized:
        return None
    compact = normalized.replace(" ", "")
    if compact in _APPROVE or normalized in _APPROVE:
        return True
    if compact in _REJECT or normalized in _REJECT:
        return False
    if compact.startswith("同意") or compact.endswith("同意"):
        return True
    if compact.startswith("拒绝") or compact.endswith("拒绝"):
        return False
    return None


def format_approval_prompt_weixin(summary: str, *, preview: str = "") -> str:
    """微信端精简审批卡，避免长列表刷屏。"""
    summary = summary.strip()
    detail = (preview or "").strip()
    if detail and detail != summary:
        body = f"{summary}（{detail[:100]}）"
    else:
        body = summary
    return f"【需你确认】{body}\n回复「同意」执行，「拒绝」取消（5 分钟内有效）"


def format_approval_prompt(summary: str, *, preview: str = "") -> str:
    summary = summary.strip()
    detail = (preview or "").strip()
    if detail == summary:
        detail = ""

    lines = [
        "【星期五 · 需要你的许可】",
        "",
        "▸ 准备做什么",
        summary,
    ]
    if detail:
        lines.extend(["", "▸ 补充说明", detail[:280]])
    lines.extend(
        [
            "",
            "▸ 请你决定",
            "回复「同意」= 允许在这台电脑上执行",
            "回复「拒绝」= 取消，不做任何改动",
            "",
            "（5 分钟内有效）",
        ]
    )
    return "\n".join(lines)
