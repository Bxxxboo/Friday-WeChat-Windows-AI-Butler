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


@register_tool(
    name="remember_pain_point",
    description=(
        "记录结构化踩坑经验（跨会话保留）：场景 tag + 现象 + 原因 + 修复。"
        "如微信发送失败、API Key 无效、PPT 路径错误等。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "tag": {
                "type": "string",
                "description": "场景标签，如 weixin_send、api_key、ppt、path",
            },
            "symptom": {
                "type": "string",
                "description": "用户看到的现象或错误，简短明确",
            },
            "cause": {
                "type": "string",
                "description": "根因（可选）",
            },
            "fix": {
                "type": "string",
                "description": "已验证的修复动作（可选）",
            },
        },
        "required": ["tag", "symptom"],
    },
)
def remember_pain_point(
    tag: str,
    symptom: str,
    cause: str = "",
    fix: str = "",
) -> str:
    from friday.pain_points import remember_pain_point as _remember

    result = _remember(tag, symptom, cause=cause, fix=fix)
    if not result.get("ok"):
        return str(result.get("message") or "记录失败")
    return str(result.get("message") or "已记录踩坑")


@register_tool(
    name="append_work_note",
    description="向当前会话工作笔记追加一条要点（会并入下次检查点）。用于记录路径、决策、中间结论。",
    parameters={
        "type": "object",
        "properties": {
            "note": {
                "type": "string",
                "description": "要记录的要点，简短明确",
            },
        },
        "required": ["note"],
    },
)
def append_work_note(note: str) -> str:
    from friday.agent_context import current_session_id
    from friday.checkpoint_writer import append_session_note

    session_id = str(current_session_id.get() or "").strip()
    if not session_id:
        return "当前无活动会话，无法写入工作笔记。"
    cleaned = str(note or "").strip()
    if not cleaned:
        return "笔记内容不能为空。"
    append_session_note(session_id, cleaned)
    return "已写入工作笔记，将在下次检查点归档。"


@register_tool(
    name="search_past_conversations",
    description="按关键词搜索历史对话（跨会话 FTS）。用户问「之前说过/做过什么」时使用。",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索关键词，如项目名、文件名、操作主题",
            },
            "limit": {
                "type": "integer",
                "description": "最多返回条数，默认 5",
            },
        },
        "required": ["query"],
    },
)
def search_past_conversations(query: str, limit: int = 5) -> str:
    from friday.history_index import search_messages

    cleaned = str(query or "").strip()
    if not cleaned:
        return "请提供搜索关键词。"
    cap = max(1, min(int(limit or 5), 20))
    hits = search_messages(cleaned, limit=cap)
    if not hits:
        return f"未找到与「{cleaned}」相关的历史对话。"
    lines = [f"共 {len(hits)} 条与「{cleaned}」相关的历史片段："]
    for idx, hit in enumerate(hits, 1):
        role = str(hit.get("role", ""))
        sid = str(hit.get("session_id", ""))[:12]
        content = str(hit.get("content", "")).strip().replace("\n", " ")
        if len(content) > 200:
            content = content[:197] + "..."
        lines.append(f"{idx}. [{role}] 会话 {sid}… — {content}")
    return "\n".join(lines)


@register_tool(
    name="search_saved_memory",
    description="搜索已保存的长期记忆（用户偏好 + 工作区 MEMORY.md）。",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索关键词",
            },
            "limit": {
                "type": "integer",
                "description": "最多返回条数，默认 10",
            },
        },
        "required": ["query"],
    },
)
def search_saved_memory(query: str, limit: int = 10) -> str:
    from friday.memory_search import search_saved_memory as _search

    cleaned = str(query or "").strip()
    if not cleaned:
        return "请提供搜索关键词。"
    cap = max(1, min(int(limit or 10), 30))
    hits = _search(cleaned, limit=cap)
    if not hits:
        return f"未找到与「{cleaned}」相关的已保存记忆。"
    lines = [f"共 {len(hits)} 条与「{cleaned}」相关的记忆："]
    for idx, hit in enumerate(hits, 1):
        source = hit.get("source", "")
        if source == "user_memory":
            label = "用户偏好"
        elif source == "pain_point":
            label = "踩坑"
        else:
            label = "工作区 MEMORY"
        text = str(hit.get("text", "")).strip()
        lines.append(f"{idx}. [{label}] {text}")
    return "\n".join(lines)
