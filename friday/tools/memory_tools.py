"""用户长期记忆工具。"""

from __future__ import annotations

from friday.tools._decorators import register_tool
from friday.user_memory import forget_fact, load_facts, remember_fact


@register_tool(
    name="remember_user_fact",
    description="记住用户的长期偏好或习惯（跨会话保留），如常用保存路径、喜欢的软件、命名习惯。",
    parameters={
        "type": "object",
        "properties": {
            "fact": {
                "type": "string",
                "description": "要记住的事实，简短明确，如「下载软件默认保存到 E:\\软件」",
            },
        },
        "required": ["fact"],
    },
)
def remember_user_fact(fact: str) -> str:
    result = remember_fact(fact)
    if not result.get("ok"):
        return str(result.get("message") or "记住失败")
    return str(result.get("message") or "已记住")


@register_tool(
    name="forget_user_fact",
    description="删除一条过时的用户长期记忆（按关键词匹配）。",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "要删除的记忆中包含的关键词",
            },
        },
        "required": ["query"],
    },
)
def forget_user_fact(query: str) -> str:
    result = forget_fact(query)
    if not result.get("ok"):
        return str(result.get("message") or "删除失败")
    return str(result.get("message") or "已删除")


@register_tool(
    name="list_user_memory",
    description="查看已记住的用户长期偏好与习惯。",
    parameters={"type": "object", "properties": {}},
)
def list_user_memory() -> str:
    facts = load_facts()
    if not facts:
        return "暂无长期记忆。用户表达稳定偏好时可用 remember_user_fact 记录。"
    lines = [f"{idx}. {item['text']}" for idx, item in enumerate(facts, 1)]
    return "\n".join(lines)
