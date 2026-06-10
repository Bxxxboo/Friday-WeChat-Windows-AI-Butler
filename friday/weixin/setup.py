from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from friday.config import APP_NAME
from friday.logging_config import get_logger
from friday.paths import extensions_dir
from friday.storage import UserSettings, load_settings, save_settings
from friday.version import __version__
from friday.weixin.client import list_account_ids, resolve_account
from friday.weixin.config import openclaw_state_dir, read_bridge_config, write_bridge_config
from friday.weixin.gateway import ensure_gateway_cmd, ensure_gateway_running, gateway_status
from friday.weixin.node_runtime import ensure_node_npm, npm_command, run_npm_global
from friday.weixin.openclaw_cli import (
    cli_available,
    find_openclaw_script,
    openclaw_argv,
    openclaw_shell_invocation,
    resolve_openclaw_command,
    run_openclaw,
)

_log = get_logger("weixin.setup")

WEIXIN_PLUGIN_ID = "openclaw-weixin"
BRIDGE_PLUGIN_ID = "friday-weixin-bridge"
WEIXIN_NPM_SPEC = "@tencent-weixin/openclaw-weixin@2.4.3"
DEFAULT_WEIXIN_BOT_AGENT = f"Friday/{__version__}"
_LEGACY_WEIXIN_DISPLAY_NAMES = frozenset(
    {
        "",
        "openclaw-weixin",
        "openclaw",
        "OpenClaw",
        "clawbot",
        "ClawBot",
        "微信clawbot",
        "微信ClawBot",
        "微信 ClawBot",
        "微信 clawbot",
    }
)


@dataclass(frozen=True)
class SetupStep:
    id: str
    title: str
    description: str
    status: str  # ok | warn | error | pending
    message: str
    action: str = ""


_CLI_INFO_TTL_SEC = 45.0
_cli_info_cache: tuple[float, tuple[bool, str, str]] | None = None


def invalidate_cli_info_cache() -> None:
    global _cli_info_cache
    _cli_info_cache = None


def _openclaw_cli_available() -> bool:
    return cli_available()


def _openclaw_cli_info() -> tuple[bool, str, str]:
    global _cli_info_cache
    now = time.time()
    if _cli_info_cache is not None and now - _cli_info_cache[0] < _CLI_INFO_TTL_SEC:
        return _cli_info_cache[1]

    if not _openclaw_cli_available():
        result = (False, "", "未找到 openclaw 命令。请先安装 OpenClaw：https://docs.openclaw.ai/install")
        _cli_info_cache = (now, result)
        return result
    try:
        proc = run_openclaw(["--version"], timeout=5)
        version = (proc.stdout or proc.stderr or "").strip().splitlines()[0][:80]
        if proc.returncode == 0 and version:
            result = (True, version, "OpenClaw 已安装")
        else:
            result = (False, version, "OpenClaw 命令不可用，请检查安装")
    except (subprocess.TimeoutExpired, OSError) as exc:
        result = (False, "", f"检测 OpenClaw 失败：{exc}")
    _cli_info_cache = (now, result)
    return result


def _openclaw_config_path() -> Path:
    return openclaw_state_dir() / "openclaw.json"


def _read_openclaw_config() -> dict[str, Any]:
    path = _openclaw_config_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_openclaw_config(data: dict[str, Any]) -> None:
    path = _openclaw_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _plugin_extension_dir(plugin_id: str) -> Path:
    return openclaw_state_dir() / "extensions" / plugin_id


def _weixin_channel_available() -> bool:
    """微信通道是否可用：必须以插件文件已落盘为准（仅 openclaw.json 启用不够）。"""
    return _plugin_installed(WEIXIN_PLUGIN_ID)


def _plugin_tree_usable(root: Path) -> bool:
    if not root.is_dir():
        return False
    has_entry = (
        (root / "index.js").is_file()
        or (root / "dist" / "index.js").is_file()
        or any(root.glob("**/index.js"))
    )
    if not has_entry:
        return False
    return (root / "openclaw.plugin.json").is_file() or (root / "package.json").is_file()


def _plugin_installed(plugin_id: str) -> bool:
    ext = _plugin_extension_dir(plugin_id)
    if _plugin_tree_usable(ext):
        return True

    state = openclaw_state_dir()
    npm_projects = state / "npm" / "projects"
    if npm_projects.is_dir():
        for manifest in npm_projects.glob("**/openclaw.plugin.json"):
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(data, dict) and data.get("id") == plugin_id:
                if _plugin_tree_usable(manifest.parent):
                    return True

    cfg = _read_openclaw_config()
    plugins = cfg.get("plugins") if isinstance(cfg, dict) else None
    installs = plugins.get("installs") if isinstance(plugins, dict) else None
    if isinstance(installs, dict):
        record = installs.get(plugin_id)
        if isinstance(record, dict):
            raw_path = str(record.get("installPath") or record.get("path") or "").strip()
            if raw_path and _plugin_tree_usable(Path(raw_path)):
                return True
    return False


def _weixin_plugin_source() -> Path | None:
    local = Path(__file__).resolve().parents[2] / "openclaw-weixin" / "package"
    if (local / "openclaw.plugin.json").is_file():
        return local
    bundled = extensions_dir().parent / "openclaw-weixin" / "package"
    if (bundled / "openclaw.plugin.json").is_file():
        return bundled
    return None


def _bridge_plugin_source() -> Path:
    return extensions_dir() / BRIDGE_PLUGIN_ID


def _config_plugins_ready() -> tuple[bool, str]:
    data = _read_openclaw_config()
    plugins = data.get("plugins")
    if not isinstance(plugins, dict):
        return False, "openclaw.json 中缺少 plugins 配置"
    allow = plugins.get("allow") or []
    if not isinstance(allow, list):
        allow = []
    missing = [pid for pid in (WEIXIN_PLUGIN_ID, BRIDGE_PLUGIN_ID) if pid not in allow]
    entries = plugins.get("entries") or {}
    disabled = [
        pid
        for pid in (WEIXIN_PLUGIN_ID, BRIDGE_PLUGIN_ID)
        if not isinstance(entries, dict) or not entries.get(pid, {}).get("enabled", False)
    ]
    channels = data.get("channels") or {}
    weixin_channel = channels.get(WEIXIN_PLUGIN_ID) if isinstance(channels, dict) else None
    channel_ok = isinstance(weixin_channel, dict) and weixin_channel.get("enabled", True)
    if missing or disabled:
        return False, f"需启用插件：{', '.join(missing + disabled)}"
    if not channel_ok:
        return False, "微信通道未在 openclaw.json 中启用"
    return True, "OpenClaw 插件白名单与通道配置已就绪"


def _copy_plugin_tree(source: Path, plugin_id: str) -> tuple[bool, str]:
    if not source.is_dir():
        return False, f"插件源目录不存在：{source}"
    dest = _plugin_extension_dir(plugin_id)
    dest.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        target = dest / item.name
        if item.is_dir():
            if target.exists():
                shutil.rmtree(target, ignore_errors=True)
            shutil.copytree(item, target)
        elif item.is_file():
            shutil.copy2(item, target)
    if _plugin_installed(plugin_id):
        return True, f"{plugin_id} 已复制到 {dest}"
    return False, f"{plugin_id} 复制后仍不可用"


def migrate_legacy_openclaw_state() -> tuple[bool, str]:
    """将其他 OpenClaw 状态目录中的插件迁移到 ~/.openclaw（若目标不同）。"""
    target = openclaw_state_dir()
    legacy = Path.home() / ".openclaw"
    if not legacy.is_dir() or legacy.resolve() == target.resolve():
        return True, "无需迁移 OpenClaw 状态"
    target.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []

    for name in ("openclaw.json", "gateway.cmd"):
        src = legacy / name
        dst = target / name
        if src.is_file() and not dst.is_file():
            shutil.copy2(src, dst)
            copied.append(name)

    legacy_ext = legacy / "extensions"
    target_ext = target / "extensions"
    if legacy_ext.is_dir():
        target_ext.mkdir(parents=True, exist_ok=True)
        for plugin_dir in legacy_ext.iterdir():
            if not plugin_dir.is_dir():
                continue
            dst = target_ext / plugin_dir.name
            if dst.exists():
                continue
            shutil.copytree(plugin_dir, dst)
            copied.append(f"extensions/{plugin_dir.name}")

    legacy_wx = legacy / "openclaw-weixin"
    target_wx = target / "openclaw-weixin"
    if legacy_wx.is_dir() and not target_wx.exists():
        shutil.copytree(legacy_wx, target_wx)
        copied.append("openclaw-weixin")

    if not copied:
        return True, "未发现可迁移的 OpenClaw 数据"
    _log.info("已迁移 OpenClaw 状态 | from=%s to=%s items=%s", legacy, target, copied)
    return True, f"已从 ~/.openclaw 迁移：{', '.join(copied)}"


def _install_weixin_via_npm() -> tuple[bool, str]:
    import tempfile

    from friday.weixin.node_runtime import run_npm

    if not npm_command():
        return False, "npm 不可用，无法安装微信插件"
    tmp = Path(tempfile.mkdtemp(prefix="friday-weixin-"))
    try:
        proc = run_npm(
            ["install", WEIXIN_NPM_SPEC],
            timeout=600,
            prefix=tmp,
        )
        detail = (proc.stderr or proc.stdout or "").strip()[-400:]
        if proc.returncode != 0:
            return False, f"npm 安装微信插件失败：{detail or proc.returncode}"
        candidates = list(tmp.glob("node_modules/**/openclaw.plugin.json"))
        if not candidates:
            candidates = list(tmp.glob("node_modules/**/package.json"))
        for marker in candidates:
            pkg_root = marker.parent
            if (pkg_root / "index.js").is_file() or any(pkg_root.glob("**/index.js")):
                return _copy_plugin_tree(pkg_root, WEIXIN_PLUGIN_ID)
        return False, "npm 已执行但未找到 openclaw-weixin 包内容"
    except (subprocess.TimeoutExpired, OSError) as exc:
        return False, f"npm 安装微信插件异常：{exc}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _should_replace_weixin_display_name(name: Any) -> bool:
    if name is None:
        return True
    text = str(name).strip()
    if not text:
        return True
    lowered = text.casefold()
    if lowered in {item.casefold() for item in _LEGACY_WEIXIN_DISPLAY_NAMES if item}:
        return True
    return lowered.endswith("clawbot") or lowered.endswith(" openclaw")


def _apply_agent_branding(data: dict[str, Any]) -> None:
    """写入 OpenClaw 默认 agent 显示名「星期五」，覆盖 ClawBot/OpenClaw 遗留名。"""
    agents = data.setdefault("agents", {})
    if not isinstance(agents, dict):
        return
    agent_list = agents.get("list")
    if not isinstance(agent_list, list):
        agent_list = []
        agents["list"] = agent_list

    main: dict[str, Any] | None = None
    for entry in agent_list:
        if isinstance(entry, dict) and entry.get("id") == "main":
            main = entry
            break
    if main is None:
        main = {"id": "main", "default": True}
        agent_list.insert(0, main)

    if _should_replace_weixin_display_name(main.get("name")):
        main["name"] = APP_NAME

    identity = main.get("identity")
    if not isinstance(identity, dict):
        identity = {}
        main["identity"] = identity
    if _should_replace_weixin_display_name(identity.get("name")):
        identity["name"] = APP_NAME

    ui = data.setdefault("ui", {})
    if isinstance(ui, dict):
        assistant = ui.get("assistant")
        if not isinstance(assistant, dict):
            assistant = {}
            ui["assistant"] = assistant
        if _should_replace_weixin_display_name(assistant.get("name")):
            assistant["name"] = APP_NAME


def _apply_weixin_channel_branding(data: dict[str, Any]) -> None:
    """微信通道默认显示名与 botAgent（覆盖「微信clawbot」等遗留默认）。"""
    channels = data.get("channels")
    if not isinstance(channels, dict):
        return
    wx = channels.get(WEIXIN_PLUGIN_ID)
    if not isinstance(wx, dict):
        return

    if _should_replace_weixin_display_name(wx.get("name")):
        wx["name"] = APP_NAME
    wx["botAgent"] = DEFAULT_WEIXIN_BOT_AGENT

    accounts = wx.get("accounts")
    if isinstance(accounts, dict):
        for account_cfg in accounts.values():
            if isinstance(account_cfg, dict) and _should_replace_weixin_display_name(
                account_cfg.get("name")
            ):
                account_cfg["name"] = APP_NAME

    for account_id in list_account_ids():
        accounts = wx.setdefault("accounts", {})
        if not isinstance(accounts, dict):
            accounts = {}
            wx["accounts"] = accounts
        account_cfg = accounts.setdefault(account_id, {})
        if isinstance(account_cfg, dict) and _should_replace_weixin_display_name(
            account_cfg.get("name")
        ):
            account_cfg["name"] = APP_NAME


def ensure_weixin_branding() -> tuple[bool, str]:
    """同步 openclaw.json 中的微信/agent 显示名与功能介绍。"""
    data = _read_openclaw_config()
    if not isinstance(data, dict):
        data = {}
    _apply_agent_branding(data)
    _apply_weixin_channel_branding(data)
    from friday.weixin.profile import apply_weixin_description, sync_weixin_bot_profile

    apply_weixin_description(data)
    _write_openclaw_config(data)
    ok, msg = sync_weixin_bot_profile()
    if ok:
        return True, f"微信显示名与功能介绍已设为「{APP_NAME}」（{msg}）"
    return False, msg


def _apply_gateway_config(data: dict[str, Any]) -> dict[str, Any]:
    """写入 OpenClaw Gateway 本地模式与认证（新版 openclaw 必需 gateway.mode）。"""
    gateway = data.get("gateway")
    if not isinstance(gateway, dict):
        gateway = {}
    gateway["mode"] = "local"
    auth = gateway.get("auth")
    if not isinstance(auth, dict):
        auth = {}
    if not str(auth.get("mode", "")).strip():
        auth["mode"] = "token"
    if not str(auth.get("token", "")).strip():
        auth["token"] = secrets.token_hex(24)
    gateway["auth"] = auth
    data["gateway"] = gateway
    return data


def ensure_openclaw_gateway_config() -> tuple[bool, str]:
    data = _read_openclaw_config()
    if not isinstance(data, dict):
        data = {}
    _apply_gateway_config(data)
    _write_openclaw_config(data)
    return True, "Gateway 配置已写入 openclaw.json"


def configure_openclaw_plugins() -> tuple[bool, str]:
    data = _read_openclaw_config()
    if not isinstance(data, dict):
        data = {}
    plugins = data.setdefault("plugins", {})
    allow = list(plugins.get("allow") or [])
    for pid in (WEIXIN_PLUGIN_ID, BRIDGE_PLUGIN_ID):
        if pid not in allow:
            allow.append(pid)
    plugins["allow"] = allow
    entries = plugins.setdefault("entries", {})
    for pid in (WEIXIN_PLUGIN_ID, BRIDGE_PLUGIN_ID):
        entry = entries.setdefault(pid, {})
        if isinstance(entry, dict):
            entry["enabled"] = True
    bridge_entry = entries.get(BRIDGE_PLUGIN_ID)
    if isinstance(bridge_entry, dict):
        hooks = bridge_entry.setdefault("hooks", {})
        if isinstance(hooks, dict):
            hooks.setdefault("timeoutMs", 620_000)
    channels = data.setdefault("channels", {})
    wx = channels.setdefault(WEIXIN_PLUGIN_ID, {})
    if isinstance(wx, dict):
        wx["enabled"] = True
    session = data.setdefault("session", {})
    if isinstance(session, dict) and session.get("dmScope") != "per-account-channel-peer":
        session["dmScope"] = "per-account-channel-peer"
    _apply_agent_branding(data)
    _apply_weixin_channel_branding(data)
    from friday.weixin.profile import apply_weixin_description, patch_weixin_plugin_profile

    apply_weixin_description(data)
    _apply_gateway_config(data)
    _write_openclaw_config(data)
    patch_weixin_plugin_profile()
    _log.info("已写入 OpenClaw 微信相关配置")
    return True, f"配置已写入 {openclaw_state_dir() / 'openclaw.json'}"


def _run_openclaw_doctor_repair() -> None:
    """非交互修复 openclaw.json 与缺失插件（避免 Gateway 启动时再弹「安装插件？」）。"""
    if not _openclaw_cli_available():
        return
    try:
        run_openclaw(
            ["doctor", "--repair", "--yes", "--non-interactive"],
            timeout=180,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        _log.warning("openclaw doctor --repair 未完成 | %s", exc)


def ensure_weixin_plugin_for_gateway() -> None:
    """Gateway 启动前预装微信插件，避免 OpenClaw 在终端里交互式询问。"""
    if _plugin_installed(WEIXIN_PLUGIN_ID):
        return
    install_weixin_plugin()


def ensure_bridge_plugin_for_gateway() -> bool:
    """Gateway 启动前同步桥接插件；若文件有更新则返回 True（需重启 Gateway 加载）。"""
    ok, msg, changed = sync_bridge_plugin(force=False)
    if not ok:
        _log.warning("桥接插件同步失败 | %s", msg)
        return False
    if changed:
        _log.info("桥接插件已更新，需重启 Gateway | %s", msg)
    return changed


def install_weixin_plugin() -> tuple[bool, str]:
    if _plugin_installed(WEIXIN_PLUGIN_ID):
        configure_openclaw_plugins()
        _run_openclaw_doctor_repair()
        return True, "微信通道插件已安装"

    source = _weixin_plugin_source()
    if source and source.is_dir():
        ok, msg = _copy_plugin_tree(source, WEIXIN_PLUGIN_ID)
        if ok:
            configure_openclaw_plugins()
            _run_openclaw_doctor_repair()
            return True, msg

    ok, msg = _install_weixin_via_npm()
    if ok:
        configure_openclaw_plugins()
        _run_openclaw_doctor_repair()
        return True, msg

    try:
        proc = run_openclaw(["plugins", "install", WEIXIN_NPM_SPEC, "--force"], timeout=300)
        detail = (proc.stderr or proc.stdout or "").strip()[-400:]
        if proc.returncode == 0 or _plugin_installed(WEIXIN_PLUGIN_ID):
            configure_openclaw_plugins()
            _run_openclaw_doctor_repair()
            return True, "微信通道插件安装完成"
        _log.warning("openclaw plugins install weixin 失败 | %s", detail)
    except subprocess.TimeoutExpired:
        _log.warning("openclaw plugins install weixin 超时")
    except OSError as exc:
        _log.warning("openclaw plugins install weixin 异常 | %s", exc)

    return False, msg or "微信通道插件安装失败，请检查网络后重试"


def sync_bridge_plugin(*, force: bool = False) -> tuple[bool, str, bool]:
    """将内置 friday-weixin-bridge 同步到 OpenClaw 扩展目录。返回 (ok, message, changed)。"""
    src = _bridge_plugin_source()
    if not src.is_dir():
        return False, f"未找到内置桥接插件：{src}", False

    dest = _plugin_extension_dir(BRIDGE_PLUGIN_ID)
    src_index = src / "index.js"
    dest_index = dest / "index.js"
    changed = force
    if src_index.is_file() and dest_index.is_file():
        changed = force or src_index.read_bytes() != dest_index.read_bytes()
    elif src_index.is_file():
        changed = True

    if not changed and _plugin_installed(BRIDGE_PLUGIN_ID):
        configure_openclaw_plugins()
        return True, "星期五桥接插件已是最新", False

    ok, msg = _copy_plugin_tree(src, BRIDGE_PLUGIN_ID)
    if ok:
        configure_openclaw_plugins()
        _run_openclaw_doctor_repair()
        return True, msg, True
    return False, msg, False


def install_bridge_plugin() -> tuple[bool, str]:
    ok, msg, _changed = sync_bridge_plugin(force=False)
    if ok:
        return True, msg

    src = _bridge_plugin_source()
    if not src.is_dir():
        return False, f"未找到内置桥接插件：{src}"

    ok, msg = _copy_plugin_tree(src, BRIDGE_PLUGIN_ID)
    if ok:
        configure_openclaw_plugins()
        _run_openclaw_doctor_repair()
        return True, msg

    try:
        proc = run_openclaw(["plugins", "install", str(src), "--force"], timeout=120)
        if proc.returncode == 0 and _plugin_installed(BRIDGE_PLUGIN_ID):
            configure_openclaw_plugins()
            _run_openclaw_doctor_repair()
            return True, "星期五桥接插件已安装"
        detail = (proc.stderr or proc.stdout or "").strip()[-300:]
        if detail:
            _log.warning("openclaw plugins install bridge 非零退出 | %s", detail)
    except (subprocess.TimeoutExpired, OSError) as exc:
        _log.warning("openclaw plugins install bridge 异常 | %s", exc)

    return False, "桥接插件安装失败"


def start_gateway(*, force_restart: bool = False) -> tuple[bool, str]:
    from friday.weixin.gateway import ensure_gateway_running

    cfg_ok, cfg_msg = ensure_openclaw_gateway_config()
    if not cfg_ok:
        return False, cfg_msg
    ok_cmd, cmd_msg = ensure_gateway_cmd(force=True)
    if not ok_cmd:
        return False, cmd_msg
    ensure_weixin_plugin_for_gateway()
    plugin_changed = ensure_bridge_plugin_for_gateway()
    need_restart = force_restart or plugin_changed
    result = ensure_gateway_running(force_restart=need_restart)
    if result.get("running"):
        if need_restart and not result.get("started"):
            _log.warning(
                "Gateway 已在运行但桥接插件可能未热加载，建议手动重启 Gateway | plugin_changed=%s",
                plugin_changed,
            )
        return True, f"Gateway 已就绪（{cfg_msg}；{cmd_msg}）"
    return False, str(result.get("error") or "Gateway 未能启动")


def sync_friday_bridge(port: int, token: str) -> tuple[bool, str]:
    write_bridge_config(port, token, enabled=True)
    settings = load_settings()
    if not getattr(settings, "weixin_bridge_enabled", True):
        save_settings(settings.merge({"weixin_bridge_enabled": True}))
    if not read_bridge_config():
        return False, "桥接配置文件写入失败"
    return True, "星期五桥接配置已同步"


def launch_weixin_login_terminal() -> tuple[bool, str]:
    if not _openclaw_cli_available():
        return False, "未找到 openclaw 命令，请先完成 OpenClaw 安装"
    if not _weixin_channel_available():
        ok, msg = install_weixin_plugin()
        if not ok:
            return False, f"微信通道插件未安装：{msg}"
    configure_openclaw_plugins()
    gw_ok, gw_msg = start_gateway()
    if not gw_ok:
        return False, f"OpenClaw Gateway 未能启动，无法扫码登录：{gw_msg}"
    from friday.weixin.login_runner import clear_cached_login_url, launch_weixin_login_console

    clear_cached_login_url()
    ok, msg = launch_weixin_login_console()
    if ok:
        return True, f"{msg} 扫码完成后点「刷新状态」。"
    return ok, msg


def install_openclaw_cli() -> tuple[bool, str]:
    """安装 Node（若缺失）并通过 npm 安装 OpenClaw CLI。"""
    invalidate_cli_info_cache()
    if _openclaw_cli_available():
        _, ver, _ = _openclaw_cli_info()
        suffix = f"（{ver}）" if ver else ""
        return True, f"OpenClaw 已安装{suffix}"

    node_ok, node_msg = ensure_node_npm()
    if not node_ok:
        return False, node_msg

    _log.info("正在通过 npm 安装 OpenClaw… | %s", node_msg)
    try:
        proc = run_npm_global(["install", "openclaw@latest"])
        detail = (proc.stderr or proc.stdout or "").strip()
        tail = detail[-400:] if detail else ""
        if proc.returncode != 0:
            return False, f"npm 安装 OpenClaw 失败：{tail or proc.returncode}"
    except subprocess.TimeoutExpired:
        return False, "安装 OpenClaw 超时，请检查网络后重试"
    except OSError as exc:
        return False, f"安装 OpenClaw 异常：{exc}"

    invalidate_cli_info_cache()
    if not _openclaw_cli_available():
        script = find_openclaw_script()
        hint = f"（已检测到 {script.name}，但缺少 node.exe）" if script else ""
        return False, (
            "OpenClaw 安装完成但命令不可用"
            f"{hint}。请重启星期五后重试，或检查 %APPDATA%\\Friday\\runtime\\npm-global。"
        )

    _, ver, _ = _openclaw_cli_info()
    suffix = f"（{ver}）" if ver else ""
    return True, f"OpenClaw 安装完成{suffix}（{node_msg}）"


def collect_setup_steps(*, port: int = 8765, api_token: str = "") -> list[SetupStep]:
    cli_ok, cli_ver, cli_msg = _openclaw_cli_info()
    weixin_installed = _weixin_channel_available()
    bridge_installed = _plugin_installed(BRIDGE_PLUGIN_ID)
    config_ok, config_msg = _config_plugins_ready()
    accounts = list_account_ids()
    gw = gateway_status()
    bridge_cfg = read_bridge_config()
    settings = load_settings()
    from friday.edition import openclaw_gateway_port

    gateway_port = openclaw_gateway_port()

    steps = [
        SetupStep(
            id="openclaw_cli",
            title="OpenClaw 命令行",
            description="接收微信消息、转发指令到星期五",
            status="ok" if cli_ok else "error",
            message=f"{cli_msg}" + (f"（{cli_ver}）" if cli_ver else "")
            + ("" if cli_ok else "；可一键自动安装 Node.js + OpenClaw"),
            action="" if cli_ok else "install_openclaw",
        ),
        SetupStep(
            id="weixin_plugin",
            title="微信通道插件",
            description="让 OpenClaw 连接微信 iLink 通道",
            status="ok" if weixin_installed else ("warn" if cli_ok else "pending"),
            message="已安装" if weixin_installed else "尚未安装 openclaw-weixin",
            action="" if weixin_installed else "install_weixin",
        ),
        SetupStep(
            id="bridge_plugin",
            title="星期五桥接插件",
            description="把微信文字消息转给本机星期五执行",
            status="ok" if bridge_installed else ("warn" if cli_ok else "pending"),
            message="已安装" if bridge_installed else "尚未安装 friday-weixin-bridge",
            action="" if bridge_installed else "install_bridge",
        ),
        SetupStep(
            id="openclaw_config",
            title="OpenClaw 配置",
            description="启用插件白名单与微信通道",
            status="ok" if config_ok else ("warn" if cli_ok else "pending"),
            message=config_msg,
            action="" if config_ok else "configure",
        ),
        SetupStep(
            id="weixin_login",
            title="微信扫码登录",
            description="绑定你的微信，与「星期五」对话",
            status="ok" if accounts else ("warn" if cli_ok else "pending"),
            message=f"已登录 {len(accounts)} 个账号" if accounts else "尚未登录，需扫码一次",
            action="" if accounts else "login",
        ),
        SetupStep(
            id="gateway",
            title="OpenClaw Gateway",
            description=f"微信消息中转服务（本机 {gateway_port} 端口）",
            status="ok" if gw.get("running") else ("warn" if cli_ok else "pending"),
            message="运行中" if gw.get("running") else "未运行（微信会显示无法连接 OpenClaw）",
            action="" if gw.get("running") else "start_gateway",
        ),
        SetupStep(
            id="friday_bridge",
            title="连接星期五",
            description="写入桥接令牌，让插件找到本机星期五",
            status="ok" if bridge_cfg else "pending",
            message="桥接配置已就绪" if bridge_cfg else "桥接配置未写入",
            action="" if bridge_cfg else "sync_bridge",
        ),
        SetupStep(
            id="friday_api",
            title="DeepSeek API",
            description="星期五执行指令需要大模型 Key",
            status="ok" if settings.api_ready else "warn",
            message="API 已配置" if settings.api_ready else "请先在「API 连接」中保存 DeepSeek Key",
            action="" if settings.api_ready else "open_api_settings",
        ),
    ]
    return steps


def setup_ready(*, port: int = 8765, api_token: str = "") -> bool:
    steps = collect_setup_steps(port=port, api_token=api_token)
    required = {"openclaw_cli", "openclaw_config", "weixin_login", "gateway", "friday_bridge"}
    optional_ok = _weixin_channel_available() and _plugin_installed(BRIDGE_PLUGIN_ID)
    core_ok = all(step.status == "ok" for step in steps if step.id in required)
    return core_ok and optional_ok


def run_setup_action(action: str, *, port: int, api_token: str) -> dict[str, Any]:
    action = (action or "").strip().lower()
    handlers = {
        "install_openclaw": install_openclaw_cli,
        "install_weixin": install_weixin_plugin,
        "install_bridge": install_bridge_plugin,
        "configure": configure_openclaw_plugins,
        "start_gateway": start_gateway,
        "sync_bridge": lambda: sync_friday_bridge(port, api_token),
        "login": launch_weixin_login_terminal,
    }
    if action == "full":
        messages: list[str] = []
        critical_ok = True

        migrate_ok, migrate_msg = migrate_legacy_openclaw_state()
        messages.append(f"{'✓' if migrate_ok else '→'} {migrate_msg}")

        if not _openclaw_cli_available():
            ok, msg = install_openclaw_cli()
            messages.append(f"{'✓' if ok else '✗'} {msg}")
            if not ok:
                invalidate_cli_info_cache()
                steps = collect_setup_steps(port=port, api_token=api_token)
                return {
                    "ok": False,
                    "message": "\n".join(messages),
                    "steps": [_step_to_dict(s) for s in steps],
                    "ready": False,
                }

        sequence = (
            ("install_weixin", install_weixin_plugin),
            ("install_bridge", install_bridge_plugin),
            ("configure", configure_openclaw_plugins),
            ("gateway_cmd", ensure_gateway_cmd),
            ("sync_bridge", lambda: sync_friday_bridge(port, api_token)),
            ("start_gateway", start_gateway),
        )
        for key, fn in sequence:
            ok, msg = fn()
            messages.append(f"{'✓' if ok else '✗'} {msg}")
            if not ok and key in {"install_weixin", "install_bridge", "configure", "sync_bridge"}:
                critical_ok = False

        if critical_ok and not list_account_ids():
            ok, msg = launch_weixin_login_terminal()
            messages.append(f"{'→' if ok else '✗'} {msg}")
            if ok:
                messages.append("→ 请在弹出窗口中用微信扫码；完成后点「刷新状态」")
        elif list_account_ids():
            messages.append("✓ 微信已登录，可直接发消息测试")

        invalidate_cli_info_cache()
        steps = collect_setup_steps(port=port, api_token=api_token)
        ready = setup_ready(port=port, api_token=api_token)
        return {
            "ok": critical_ok,
            "message": "\n".join(messages),
            "steps": [_step_to_dict(s) for s in steps],
            "ready": ready,
        }
    handler = handlers.get(action)
    if handler is None:
        return {"ok": False, "message": f"未知操作：{action}"}
    ok, message = handler()
    invalidate_cli_info_cache()
    steps = collect_setup_steps(port=port, api_token=api_token)
    return {
        "ok": ok,
        "message": message,
        "steps": [_step_to_dict(s) for s in steps],
        "ready": setup_ready(port=port, api_token=api_token),
    }


def _step_to_dict(step: SetupStep) -> dict[str, str]:
    return {
        "id": step.id,
        "title": step.title,
        "description": step.description,
        "status": step.status,
        "message": step.message,
        "action": step.action,
    }


def setup_status_payload(*, port: int, api_token: str) -> dict[str, Any]:
    steps = collect_setup_steps(port=port, api_token=api_token)
    settings = load_settings()
    return {
        "ready": setup_ready(port=port, api_token=api_token),
        "bridge_enabled": getattr(settings, "weixin_bridge_enabled", True),
        "accounts": list_account_ids(),
        "account_ready": resolve_account() is not None,
        "openclaw_gateway": gateway_status(),
        "steps": [_step_to_dict(s) for s in steps],
    }


def weixin_status_payload() -> dict[str, Any]:
    cfg = read_bridge_config()
    account = resolve_account()
    gw = gateway_status()
    return {
        "bridge_config": bool(cfg),
        "bridge_enabled": getattr(load_settings(), "weixin_bridge_enabled", True),
        "accounts": list_account_ids(),
        "account_ready": account is not None,
        "openclaw_gateway": gw,
        "openclaw_connected": bool(gw.get("running")),
    }


def set_bridge_enabled(enabled: bool) -> UserSettings:
    settings = load_settings()
    updated = settings.merge({"weixin_bridge_enabled": enabled})
    save_settings(updated)
    return updated
