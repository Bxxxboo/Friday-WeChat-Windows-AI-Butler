"""单工具成功后的快速收尾 —— 跳过一次大模型总结轮。"""

from __future__ import annotations

import re
from typing import Any

_MULTI_STEP_HINTS = re.compile(
    r"多个|全部|批量|重构|所有文件|逐个|每个文件|一系列|分步|多文件|整个项目",
    re.I,
)

_READ_LIST_TOOLS = frozenset({"list_friday_plugins", "list_plugin_catalog"})


def looks_like_multi_step_task(user_goal: str, *, pending_todos: int = 0) -> bool:
    if pending_todos > 2:
        return True
    goal = (user_goal or "").strip()
    if not goal:
        return False
    return bool(_MULTI_STEP_HINTS.search(goal))


def looks_like_plugin_list_goal(user_goal: str) -> bool:
    from friday.ppt_task import is_plugin_list_goal

    return is_plugin_list_goal(user_goal)


def _format_plugin_list_reply(
    tool_results: list[tuple[str, dict[str, Any], str]],
) -> str:
    installed = ""
    catalog = ""
    for name, _args, result in tool_results:
        text = (result or "").strip()
        if not text:
            continue
        if name == "list_friday_plugins":
            installed = text
        elif name == "list_plugin_catalog":
            catalog = text
    parts = ["根据当前环境整理的插件与扩展信息：", ""]
    if installed:
        parts.extend(["**已安装**", installed, ""])
    if catalog:
        parts.extend(["**推荐 / 安装来源**", catalog, ""])
    parts.append(
        "可在「设置 → 扩展 → 插件」一键安装；GitHub Agent Skill 用 "
        "`skill:owner/repo/目录` 格式（整仓 Skill 可用 `skill:Haojae/scipilot-figure-skill/.`）。"
    )
    return "\n".join(parts).strip()


def try_fast_finish_reply(
    tool_results: list[tuple[str, dict[str, Any], str]],
    *,
    user_goal: str = "",
    pending_todos: int = 0,
    ppt_session_active: bool = False,
) -> str | None:
    """工具成功后返回模板回复以跳过总结轮 LLM（单工具或插件双列表）。"""
    if not tool_results:
        return None

    from friday.ppt_task import is_ppt_project_artifact_path, is_ppt_task_context

    if is_ppt_task_context(user_goal) or pending_todos > 0 or ppt_session_active:
        return None

    names = {name for name, _, _ in tool_results}
    if names <= _READ_LIST_TOOLS and len(tool_results) == len(names):
        if not looks_like_plugin_list_goal(user_goal):
            return None
        if len(tool_results) == 2 and names == _READ_LIST_TOOLS:
            return _format_plugin_list_reply(tool_results)
        if len(tool_results) == 1:
            name, _args, result = tool_results[0]
            text = (result or "").strip()
            if not text:
                return None
            if name == "list_plugin_catalog":
                return f"{text}\n\n可在「设置 → 扩展 → 插件」安装；Skill 用 skill:owner/repo/目录。"
            if name == "list_friday_plugins":
                return f"{text}\n\n需要推荐来源时可说「看看插件目录」或打开设置 → 扩展。"

    if len(tool_results) != 1:
        return None
    if looks_like_multi_step_task(user_goal, pending_todos=pending_todos):
        return None

    name, _args, result = tool_results[0]
    text = (result or "").strip()
    if not text:
        return None

    if name == "write_text_file" and text.startswith("已写入:"):
        path = text.split(":", 1)[1].strip()
        if is_ppt_project_artifact_path(path):
            return None
        return f"已保存修改到 `{path}`。"

    if name == "generate_image" and text.startswith("已生成图片并保存："):
        first = text.split("\n", 1)[0].strip()
        path = first.replace("已生成图片并保存：", "", 1).strip()
        size_line = next((ln for ln in text.splitlines() if ln.startswith("实际尺寸：")), "")
        detail = f" {size_line.rstrip('。')}" if size_line else ""
        return f"图片已生成并保存到 `{path}`。{detail}".strip()

    if name == "move_file" and text.startswith("已移动:"):
        if is_ppt_project_artifact_path(text.split(":", 1)[-1]):
            return None
        return f"{text.rstrip('。')}。"

    if name == "copy_file" and text.startswith("已复制:"):
        if is_ppt_project_artifact_path(text):
            return None
        return f"{text.rstrip('。')}。"

    if name == "create_docx" and text.startswith("已创建 Word"):
        return f"{text.rstrip('。')}。"

    if name == "create_pptx" and text.startswith("已创建 PPT"):
        return f"{text.rstrip('。')}。"

    return None
