"""交互模式：Ask / Agent / Yolo。"""

from __future__ import annotations

from friday.storage import UserSettings

MODE_ASK = "ask"
MODE_AGENT = "agent"
MODE_YOLO = "yolo"

VALID_MODES = frozenset({MODE_ASK, MODE_AGENT, MODE_YOLO})

MODE_LABELS = {
    MODE_ASK: "Ask · 只读",
    MODE_AGENT: "Agent · 确认后执行",
    MODE_YOLO: "Yolo · 工作区自动",
}

MODE_HINTS = {
    MODE_ASK: "仅查阅与分析，不会修改文件或执行命令",
    MODE_AGENT: "每次写入、执行、下载等操作都会弹出确认",
    MODE_YOLO: "开启时确认一次，之后工作区内自动执行（不再反复确认）",
}

ASK_BLOCK_REASON = (
    "当前为 Ask 模式：仅回答与只读查看，不会修改文件或执行命令。"
    "请切换到 Agent 或 Yolo 模式后再试。"
)

# Yolo 下仍须人工确认的高风险 EXEC
YOLO_EXEC_REQUIRES_APPROVAL = frozenset({
    "run_powershell",
    "run_python",
    "run_python_script",
    "install_friday_plugin",
    "uninstall_friday_plugin",
})


def normalize_mode(value: str | None) -> str:
    mode = (value or MODE_AGENT).strip().lower()
    if mode not in VALID_MODES:
        return MODE_AGENT
    return mode


def mode_prompt_block(mode: str, *, yolo_unlocked: bool = False) -> str:
    m = normalize_mode(mode)
    if m == MODE_ASK:
        return (
            "\n【当前交互模式：Ask】"
            "你只能使用只读工具查阅信息并给出建议，禁止调用任何会修改文件、"
            "下载安装、执行命令或写入剪贴板的工具。"
            "统计文件夹大小时用 get_disk_usage、list_directory、get_file_info、search_files，"
            "不要调用 run_powershell / run_python。"
        )
    if m == MODE_YOLO:
        if yolo_unlocked:
            return (
                "\n【当前交互模式：Yolo · 已授权】"
                "用户已在开启 Yolo 时完成一次性确认。"
                "在默认操作文件夹内的允许操作请直接执行，不要反复请求用户确认。"
                "路径不得超出工作区（联网下载到用户指定盘符除外）。"
                "仍被安全策略禁止的操作（如 PowerShell 下载链接）不要尝试。"
            )
        return (
            "\n【当前交互模式：Yolo · 未授权】"
            "用户选择了 Yolo 但尚未完成开启确认，写入与执行仍需按 Agent 模式请求用户确认。"
        )
    return (
        "\n【当前交互模式：Agent】"
        "修改文件、执行命令、下载等操作每次都需要用户确认后再执行。"
    )


def effective_settings(settings: UserSettings, *, yolo_unlocked: bool = False) -> UserSettings:
    """按模式得到本次工具评估用的设置（不修改磁盘上的 settings）。"""
    mode = normalize_mode(getattr(settings, "interaction_mode", MODE_AGENT))
    if mode == MODE_YOLO:
        patch: dict[str, object] = {"restrict_to_workspace": True}
        if yolo_unlocked:
            patch["require_approval_writes"] = False
            patch["require_approval_exec"] = False
        return settings.merge(patch)
    return settings


def tool_allowed_in_mode(tool_name: str, mode: str) -> bool:
    if normalize_mode(mode) != MODE_ASK:
        return True
    from friday.safety import RiskLevel, classify_tool

    return classify_tool(tool_name) == RiskLevel.READ


def yolo_exec_needs_approval(tool_name: str) -> bool:
    return tool_name in YOLO_EXEC_REQUIRES_APPROVAL
