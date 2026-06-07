from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from friday.interaction_modes import (
    ASK_BLOCK_REASON,
    effective_settings,
    normalize_mode,
    tool_allowed_in_mode,
)
from friday.storage import UserSettings, resolved_workspace


class RiskLevel(str, Enum):
    READ = "read"
    WRITE = "write"
    EXEC = "exec"


@dataclass
class PendingAction:
    tool_name: str
    arguments: dict
    summary: str
    risk: RiskLevel
    large_download: bool = False
    download_size_bytes: int | None = None
    untrusted_download: bool = False
    trust_label: str = ""


@dataclass
class ToolDecision:
    allowed: bool
    needs_approval: bool
    reason: str = ""
    large_download: bool = False
    download_size_bytes: int | None = None
    untrusted_download: bool = False
    trust_label: str = ""


@dataclass
class TurnApprovalState:
    """当前对话中已获得的审批授权（跨多条用户消息保留，直到新建对话或拒绝操作）。"""

    general: bool = False
    large_download: bool = False
    untrusted_download: bool = False


def should_request_approval(
    settings: UserSettings,
    decision: ToolDecision,
    state: TurnApprovalState,
) -> bool:
    """判断本次工具调用是否仍需弹出审批。"""
    if not decision.needs_approval:
        return False
    if not settings.approve_once_per_turn:
        return True
    if decision.large_download and not state.large_download:
        return True
    if decision.untrusted_download and not state.untrusted_download:
        return True
    return not state.general


def mark_turn_approved(state: TurnApprovalState, decision: ToolDecision) -> None:
    state.general = True
    if decision.large_download:
        state.large_download = True
    if decision.untrusted_download:
        state.untrusted_download = True


WRITE_TOOLS = {
    "write_text_file",
    "move_file",
    "organize_directory",
    "create_docx",
    "create_pptx",
    "batch_rename",
    "zip_files",
    "unzip_file",
    "delete_file",
    "delete_directory",
    "copy_file",
    "clipboard_write",
    "download_file",
    "download_software",
}

READ_ONLY_TOOLS = {
    "list_directory",
    "search_files",
    "read_text_file",
    "read_pdf",
    "read_excel",
    "find_duplicates",
    "get_system_status",
    "get_disk_usage",
    "get_top_processes",
    "get_file_info",
    "screenshot",
    "clipboard_read",
    "get_network_info",
    "browse_webpage",
    "verify_download_source",
    "list_friday_plugins",
    "list_plugin_catalog",
    "describe_image",
    "vision_status",
    "python_env_info",
}

# 所有接受路径参数的工具（读 + 写），用于工作区限制
PATH_TOOLS = WRITE_TOOLS | {
    "list_directory",
    "search_files",
    "read_text_file",
    "read_pdf",
    "read_excel",
    "find_duplicates",
    "get_file_info",
    "screenshot",
    "download_file",
    "describe_image",
}

PYTHON_PATH_TOOLS = {
    "run_python",
    "run_python_script",
}


def classify_tool(tool_name: str) -> RiskLevel:
    exec_tools = {
        "run_powershell",
        "run_python",
        "run_python_script",
        "open_url",
        "open_app",
        "install_friday_plugin",
        "uninstall_friday_plugin",
    }
    if tool_name in READ_ONLY_TOOLS:
        return RiskLevel.READ
    if tool_name in exec_tools:
        return RiskLevel.EXEC
    return RiskLevel.WRITE


def _resolve_path(path: str) -> Path:
    return Path(path).expanduser().resolve()


def path_in_workspace(path: str, workspace: str) -> bool:
    try:
        target = _resolve_path(path)
        root = _resolve_path(workspace)
        target.relative_to(root)
        return True
    except (ValueError, OSError, RuntimeError):
        return False


def _extract_paths(tool_name: str, arguments: dict) -> list[str]:
    if tool_name in {"list_directory", "read_text_file", "write_text_file", "organize_directory",
                      "read_pdf", "read_excel", "find_duplicates", "batch_rename",
                      "delete_file", "delete_directory", "get_file_info"}:
        path = arguments.get("path")
        return [str(path)] if path else []
    if tool_name in {"search_files"}:
        root = arguments.get("root")
        return [str(root)] if root else []
    if tool_name in {"move_file", "copy_file"}:
        paths = []
        if arguments.get("source"):
            paths.append(str(arguments["source"]))
        if arguments.get("destination"):
            paths.append(str(arguments["destination"]))
        return paths
    if tool_name in {"create_docx", "create_pptx", "zip_files", "screenshot"}:
        output = arguments.get("output_path") or arguments.get("output")
        paths = [str(output)] if output else []
        sources = arguments.get("sources")
        if isinstance(sources, list):
            paths.extend(str(s) for s in sources)
        return paths
    if tool_name == "unzip_file":
        return [str(arguments.get(k)) for k in ("source", "output_dir") if arguments.get(k)]
    if tool_name == "download_file":
        dest = arguments.get("destination")
        return [str(dest)] if dest else []
    if tool_name == "download_software":
        dest = arguments.get("destination")
        return [str(dest)] if dest else []
    if tool_name == "run_python_script":
        path = arguments.get("path")
        paths = [str(path)] if path else []
        if arguments.get("cwd"):
            paths.append(str(arguments["cwd"]))
        return paths
    if tool_name == "run_python":
        cwd = arguments.get("cwd")
        return [str(cwd)] if cwd else []
    return []


def _tool_enabled(settings: UserSettings, tool_name: str) -> tuple[bool, str]:
    if tool_name == "write_text_file" and not settings.allow_write_files:
        return False, "已在安全设置中禁用「写入文件」"
    if tool_name == "move_file" and not settings.allow_move_files:
        return False, "已在安全设置中禁用「移动/重命名文件」"
    if tool_name == "organize_directory" and not settings.allow_organize:
        return False, "已在安全设置中禁用「整理目录」"
    if tool_name in {"create_docx", "create_pptx"} and not settings.allow_create_documents:
        return False, "已在安全设置中禁用「创建 Word/PPT 文档」"
    if tool_name == "run_powershell" and not settings.allow_powershell:
        return False, "已在安全设置中禁用「PowerShell 命令」"
    if tool_name in {"run_python", "run_python_script"} and not settings.allow_python:
        return False, "已在安全设置中禁用「Python 代码执行」"
    if tool_name == "browse_webpage" and not settings.allow_web_browse:
        return False, "已在安全设置中禁用「浏览网页」"
    if tool_name == "download_file" and not settings.allow_downloads:
        return False, "已在安全设置中禁用「联网下载」"
    return True, ""


def evaluate_tool(
    settings: UserSettings,
    tool_name: str,
    arguments: dict,
    *,
    yolo_unlocked: bool = False,
) -> ToolDecision:
    mode = normalize_mode(getattr(settings, "interaction_mode", "agent"))
    if not tool_allowed_in_mode(tool_name, mode):
        return ToolDecision(False, False, ASK_BLOCK_REASON)

    cfg = effective_settings(settings, yolo_unlocked=yolo_unlocked)
    enabled, reason = _tool_enabled(cfg, tool_name)
    if not enabled:
        return ToolDecision(False, False, reason)

    risk = classify_tool(tool_name)

    if cfg.restrict_to_workspace and tool_name in (PATH_TOOLS | PYTHON_PATH_TOOLS):
        # 用户指定路径的联网下载不受工作区限制（如保存到 E 盘）
        if tool_name != "download_file":
            root = resolved_workspace(cfg)
            for path in _extract_paths(tool_name, arguments):
                if path and not path_in_workspace(path, root):
                    return ToolDecision(
                        False,
                        False,
                        f"路径超出默认操作文件夹范围（{root}）: {path}",
                    )

    if tool_name == "download_file":
        return _evaluate_download(cfg, arguments, yolo_unlocked=yolo_unlocked)

    if tool_name == "download_software":
        enabled, reason = _tool_enabled(cfg, "download_file")
        if not enabled:
            return ToolDecision(False, False, reason)
        return ToolDecision(True, cfg.require_approval_writes)

    if tool_name == "run_powershell":
        blocked = _powershell_download_block_reason(str(arguments.get("command", "")))
        if blocked:
            return ToolDecision(False, False, blocked)

    if risk == RiskLevel.READ:
        return ToolDecision(True, False)

    if risk == RiskLevel.EXEC:
        return ToolDecision(True, cfg.require_approval_exec)

    return ToolDecision(True, cfg.require_approval_writes)


def _powershell_download_block_reason(command: str) -> str:
    """禁止用 PowerShell 下载/探测 URL，引导使用专用下载工具。"""
    normalized = re.sub(r"\s+", " ", command.replace("`", "")).strip().lower()
    if not normalized:
        return ""

    if re.search(r"https?://", normalized):
        return (
            "禁止用 PowerShell 访问或下载 URL。请改用 download_software（推荐）或 browse_webpage + download_file。"
        )

    download_hints = (
        r"\b(iwr|invoke-webrequest|invoke-restmethod|wget|curl|start-bitstransfer)\b",
        r"\b(webclient|downloadfile|downloadstring)\b",
        r"\b-uri\b",
        r"\bout-file\b",
        r"\busebasicparsing\b",
    )
    for pattern in download_hints:
        if re.search(pattern, normalized):
            return (
                "禁止用 PowerShell 下载文件。请改用 download_software 或 download_file 工具，"
                "它们会验证官方来源且不会反复弹窗。"
            )
    return ""


def _format_bytes(num: int) -> str:
    if num >= 1024 ** 3:
        return f"{num / (1024 ** 3):.2f} GB"
    if num >= 1024 ** 2:
        return f"{num / (1024 ** 2):.1f} MB"
    if num >= 1024:
        return f"{num / 1024:.1f} KB"
    return f"{num} B"


def _evaluate_download(
    settings: UserSettings,
    arguments: dict,
    *,
    yolo_unlocked: bool = False,
) -> ToolDecision:
    from friday.config import (
        DOWNLOAD_LARGE_MAX_BYTES,
        DOWNLOAD_LARGE_THRESHOLD_BYTES,
    )
    from friday.tools.web import probe_download
    from friday.tools.web_trust import assess_download_trust

    url = str(arguments.get("url", "")).strip()
    expected = str(arguments.get("expected_software", "")).strip()
    confirm_large = bool(arguments.get("confirm_large_download"))
    confirm_untrusted = bool(arguments.get("confirm_untrusted_source"))
    allow_large = bool(arguments.get("_allow_large"))
    approved_untrusted = bool(arguments.get("_untrusted_approved"))

    trust = assess_download_trust(url, expected_software=expected)
    if trust.is_blocked:
        return ToolDecision(
            False,
            False,
            f"下载源不安全（{trust.label}）：{' '.join(trust.reasons[:2])}",
            trust_label=trust.label,
        )

    if (
        trust.needs_untrusted_confirm
        and settings.require_trusted_downloads
        and not confirm_untrusted
        and not approved_untrusted
        and not yolo_unlocked
    ):
        hint = "；若用户仍同意非官方来源，请先 verify_download_source 并设置 confirm_untrusted_source=true"
        return ToolDecision(
            False,
            False,
            f"下载源未通过安全验证（{trust.label}）：{' '.join(trust.reasons[:2])}{hint}",
            trust_label=trust.label,
        )

    probe = probe_download(url)
    size = probe.content_length

    if size is not None and size > DOWNLOAD_LARGE_MAX_BYTES:
        return ToolDecision(
            False,
            False,
            f"文件过大（{_format_bytes(size)}），超过系统上限 {_format_bytes(DOWNLOAD_LARGE_MAX_BYTES)}",
            trust_label=trust.label,
        )

    large = allow_large or confirm_large
    if size is not None and size > DOWNLOAD_LARGE_THRESHOLD_BYTES:
        large = True

    untrusted = trust.needs_untrusted_confirm and not approved_untrusted and not yolo_unlocked
    if yolo_unlocked:
        needs = False
    else:
        needs = settings.require_approval_writes or large or untrusted
        if large and not allow_large:
            needs = True

    return ToolDecision(
        True,
        needs,
        large_download=large and not allow_large,
        download_size_bytes=size,
        untrusted_download=untrusted,
        trust_label=trust.label,
    )


def needs_approval(tool_name: str) -> bool:
    return classify_tool(tool_name) != RiskLevel.READ


def summarize_action(tool_name: str, arguments: dict) -> str:
    if tool_name == "move_file":
        return f"移动文件: {arguments.get('source')} -> {arguments.get('destination')}"
    if tool_name == "organize_directory":
        return f"整理目录: {arguments.get('path')} (按 {arguments.get('by', 'extension')})"
    if tool_name == "create_docx":
        return f"创建 Word: {arguments.get('output_path')}"
    if tool_name == "create_pptx":
        return f"创建 PPT: {arguments.get('output_path')}"
    if tool_name == "run_powershell":
        cmd = str(arguments.get("command", ""))[:120]
        return f"执行 PowerShell: {cmd}"
    if tool_name == "run_python":
        preview = str(arguments.get("code", "")).replace("\n", " ")[:120]
        return f"执行 Python: {preview}"
    if tool_name == "run_python_script":
        return f"运行 Python 脚本: {arguments.get('path')}"
    if tool_name == "write_text_file":
        return f"写入文件: {arguments.get('path')}"
    if tool_name == "clipboard_write":
        preview = str(arguments.get("text", ""))[:80]
        return f"写入剪贴板: {preview}{'…' if len(str(arguments.get('text', ''))) > 80 else ''}"
    if tool_name == "batch_rename":
        return f"批量重命名: {arguments.get('path')} (模式: {arguments.get('mode')})"
    if tool_name == "zip_files":
        return f"压缩文件: {len(arguments.get('sources', []))} 个 -> {arguments.get('output')}"
    if tool_name == "unzip_file":
        return f"解压文件: {arguments.get('source')} -> {arguments.get('output_dir')}"
    if tool_name == "download_file":
        return f"下载文件: {arguments.get('url')} -> {arguments.get('destination')}"
    if tool_name == "download_software":
        return f"下载软件: {arguments.get('software_name')} -> {arguments.get('destination')}"
    if tool_name == "browse_webpage":
        return f"浏览网页: {arguments.get('url')}"
    if tool_name == "install_friday_plugin":
        return f"安装扩展插件: {arguments.get('source')}"
    if tool_name == "uninstall_friday_plugin":
        return f"卸载扩展插件: {arguments.get('plugin_id')}"
    if tool_name == "find_duplicates":
        return f"查找重复文件: {arguments.get('path')}"
    return f"{tool_name}({arguments})"

def summarize_preview(tool_name: str, arguments: dict) -> str:
    """为审批界面生成更详细的预览说明"""
    if tool_name == "batch_rename":
        pattern = arguments.get("pattern", "*")
        mode = arguments.get("mode", "prefix")
        value = arguments.get("value", "")
        return f"在 {arguments.get('path')} 中将匹配 {pattern} 的文件按 {mode} 模式重命名 (参数: {value})"
    if tool_name == "organize_directory":
        return f"将对 {arguments.get('path')} 按 {arguments.get('by', 'extension')} 分类整理"
    if tool_name == "zip_files":
        sources = arguments.get("sources", [])
        return f"将 {len(sources)} 个项目压缩到 {arguments.get('output')}"
    if tool_name == "unzip_file":
        return f"将 {arguments.get('source')} 解压到 {arguments.get('output_dir')}"
    if tool_name == "download_file":
        return _summarize_download(arguments)
    return summarize_action(tool_name, arguments)


def _summarize_download(arguments: dict) -> str:
    from friday.config import DOWNLOAD_LARGE_MAX_BYTES, DOWNLOAD_LARGE_THRESHOLD_BYTES
    from friday.tools.web import probe_download
    from friday.tools.web_trust import assess_download_trust, format_trust_report

    url = str(arguments.get("url", ""))
    dest = arguments.get("destination", "")
    expected = str(arguments.get("expected_software", "")).strip()
    trust = assess_download_trust(url, expected_software=expected)
    trust_block = format_trust_report(trust).split("\n")
    trust_summary = "\n".join(trust_block[:6])

    if trust.is_blocked:
        return f"下载被拒绝\n来源: {trust.label}\n链接: {url}\n保存至: {dest}\n{trust_summary}"

    probe = probe_download(url)
    size = probe.content_length
    header = f"来源: {trust.label}"
    if size is not None:
        size_text = _format_bytes(size)
        if size > DOWNLOAD_LARGE_THRESHOLD_BYTES or arguments.get("confirm_large_download"):
            return (
                f"大文件下载（约 {size_text}）\n"
                f"{header}\n"
                f"链接: {url}\n"
                f"保存至: {dest}\n"
                f"{trust_summary}\n"
                f"确认后将允许下载，最高 {_format_bytes(DOWNLOAD_LARGE_MAX_BYTES)}"
            )
        return f"下载文件（约 {size_text}）\n{header}\n链接: {url}\n保存至: {dest}\n{trust_summary}"
    if arguments.get("confirm_large_download"):
        return f"大文件下载（大小未知）\n{header}\n链接: {url}\n保存至: {dest}\n{trust_summary}"
    return f"下载文件\n{header}\n链接: {url}\n保存至: {dest}\n{trust_summary}"
