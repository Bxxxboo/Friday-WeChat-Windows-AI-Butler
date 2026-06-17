"""制作演示文稿任务检测与 Agent 路由提示。"""

from __future__ import annotations

import re

_PPT_TASK_RE = re.compile(
    r"pptx?|ppt-master|演示文稿|幻灯片|"
    r"做汇报|生成演示|导出\s*pptx|"
    r"design_spec|做\s*svg|svg\s*并|"
    r"制作.{0,12}(?:ppt|幻灯片|演示)|"
    r"做.{0,8}(?:ppt|幻灯片|演示)|"
    r"复习\s*ppt|继续生成\s*ppt",
    re.I,
)

_PLUGIN_LIST_GOAL_RE = re.compile(
    r"插件|技能|规则|扩展|catalog|github.*rule|rules|skill",
    re.I,
)

_PLUGIN_LIST_TOOLS = frozenset({
    "list_friday_plugins",
    "list_plugin_catalog",
    "install_friday_plugin",
})

_DRAFT_PPT_TOOLS = frozenset({"create_pptx", "create_docx"})

_CONFIRMATION_ONLY_RE = re.compile(
    r"^(确认生成|确认|继续|好的|同意|ok|okay|行|可以)[\s!。，,~！？]*$",
    re.I,
)


def is_ppt_task_context(text: str) -> bool:
    return bool(_PPT_TASK_RE.search(text or ""))


def is_plugin_list_goal(text: str) -> bool:
    goal = (text or "").strip()
    if not goal:
        return False
    if is_ppt_task_context(goal):
        return False
    return bool(_PLUGIN_LIST_GOAL_RE.search(goal))


def is_short_confirmation(text: str) -> bool:
    return bool(_CONFIRMATION_ONLY_RE.match((text or "").strip()))


def is_ppt_project_artifact_path(path: str) -> bool:
    lowered = (path or "").replace("\\", "/").lower()
    return (
        "ppt_project" in lowered
        or "design_spec.md" in lowered
        or "spec_lock.md" in lowered
        or "/sources/" in lowered
        or "/slides/" in lowered
        or lowered.endswith(".svg")
        or lowered.endswith(".pptx")
    )


def conversation_in_ppt_task(messages: list[dict]) -> bool:
    """会话是否处于 ppt-master 多步流水线（含确认/继续类短句）。"""
    for msg in reversed(messages or []):
        role = msg.get("role")
        if role == "user":
            text = str(msg.get("content", "")).strip()
            if not text or text.startswith("【系统提示】"):
                continue
            if "\n\n【当前任务：" in text:
                text = text.split("\n\n【当前任务：", 1)[0].strip()
            if is_ppt_task_context(text):
                return True
            if is_short_confirmation(text):
                continue
        elif role == "assistant":
            content = str(msg.get("content", "")).strip()
            if not content:
                continue
            if "BLOCKING" in content or "八项确认" in content:
                return True
            if "ppt_project" in content.lower() or "design_spec" in content.lower():
                return True
    return False


def block_draft_document_during_ppt_message() -> str:
    return (
        "当前为 ppt-master 专业演示文稿任务，禁止 create_pptx / create_docx 草稿工具。"
        "请按 SKILL.md 走 SVG 流水线，最后用 scripts/svg_to_pptx.py 导出 .pptx。"
    )


def block_powershell_read_during_ppt_message() -> str:
    return (
        "制作 PPT 时不要用 PowerShell 读文件。请用 read_text_file 读取 SKILL.md、"
        "design_spec.md 等文本；docx 用 ppt-master/scripts/source_to_md/ 转换。"
    )


def append_ppt_task_hint(user_text: str, *, session_active: bool = False) -> str:
    if not is_ppt_task_context(user_text) and not session_active:
        return user_text
    from friday.bundled import bundled_resource_dir

    plugin_dir = str(bundled_resource_dir("ppt-master")).replace("\\", "/")
    hint = (
        "\n\n【当前任务：制作演示文稿】"
        "内置 ppt-master 已可用，禁止 list_friday_plugins / list_plugin_catalog / install_friday_plugin。"
        "禁止 create_pptx / create_docx；禁止用 PowerShell Get-Content 读 SKILL.md，须 read_text_file。"
        f"第一步：read_text_file 读取 {plugin_dir}/SKILL.md，严格按工作流串行执行。"
        f"源材料非 Markdown 时先用 {plugin_dir}/scripts/source_to_md/ 下脚本转换。"
        f"完成后用 python {plugin_dir}/scripts/svg_to_pptx.py 导出 .pptx；Windows 用 python 不用 python3。"
        "禁止 create_pptx（除非用户明确只要极简一页草稿）。"
    )
    return user_text + hint


def block_plugin_list_during_ppt_message() -> str:
    from friday.bundled import bundled_resource_dir

    plugin_dir = str(bundled_resource_dir("ppt-master")).replace("\\", "/")
    return (
        "制作 PPT 无需安装或列举插件（ppt-master 已内置）。"
        f"请 read_text_file 读取 {plugin_dir}/SKILL.md 并按工作流执行。"
    )
