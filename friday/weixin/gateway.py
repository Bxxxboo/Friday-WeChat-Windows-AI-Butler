from __future__ import annotations

import os
import re
import shutil
import socket
import subprocess
import time
from pathlib import Path

from friday.logging_config import get_logger
from friday.weixin.config import openclaw_state_dir
from friday.weixin.openclaw_cli import cli_available, run_openclaw

_log = get_logger("weixin.gateway")

DEFAULT_GATEWAY_PORT = 18789
_START_TIMEOUT_SEC = 45

_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
_DETACHED_PROCESS = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)


def _gateway_port() -> int:
    raw = os.environ.get("OPENCLAW_GATEWAY_PORT", "").strip()
    if raw.isdigit():
        return int(raw)
    from friday.edition import openclaw_gateway_port

    return openclaw_gateway_port()


def probe_gateway(*, port: int | None = None, timeout_sec: float = 2.0) -> bool:
    target_port = port if port is not None else _gateway_port()
    try:
        with socket.create_connection(("127.0.0.1", target_port), timeout=timeout_sec):
            return True
    except OSError:
        return False


def gateway_status(*, port: int | None = None) -> dict[str, object]:
    target_port = port if port is not None else _gateway_port()
    return {
        "running": probe_gateway(port=target_port),
        "port": target_port,
        "cli_available": cli_available(),
    }


def _gateway_cmd_path() -> Path:
    return openclaw_state_dir() / "gateway.cmd"


def _parse_gateway_cmd(path: Path) -> tuple[list[str], dict[str, str]]:
    """从 gateway.cmd 解析 node 启动命令与环境变量。"""
    text = path.read_text(encoding="utf-8", errors="replace")
    env: dict[str, str] = {}
    for line in text.splitlines():
        match = re.match(r'^\s*set\s+"([^"]+)=([^"]*)"\s*$', line, re.I)
        if match:
            env[match.group(1)] = match.group(2)
            continue
        match = re.match(r"^\s*set\s+(\w+)=(.+?)\s*$", line, re.I)
        if match:
            env[match.group(1)] = match.group(2).strip()
    match = re.search(
        r'"([^"]+\.exe)"\s+"([^"]+\.js)"\s+gateway(?:\s+--port\s+(\d+))?',
        text,
        re.I,
    )
    if match:
        node_exe, script, port = match.group(1), match.group(2), match.group(3)
        args = [node_exe, script, "gateway"]
        if port:
            args.extend(["--port", port])
        return args, env
    return [], env


def resolve_gateway_launch(*, port: int | None = None) -> tuple[list[str], dict[str, str]]:
    """解析 Gateway 静默启动参数（优先 gateway.cmd，失败则 node 直启）。"""
    from friday.weixin.config import openclaw_env

    target_port = port if port is not None else _gateway_port()
    env = openclaw_env()
    cmd_path = _gateway_cmd_path()
    if cmd_path.is_file():
        args, file_env = _parse_gateway_cmd(cmd_path)
        env.update(file_env)
        if args:
            return args, env
    fallback = _fallback_gateway_cmd(target_port)
    if fallback:
        env["OPENCLAW_GATEWAY_PORT"] = str(target_port)
        return fallback, env
    return [], env


def _resolve_node_exe() -> str | None:
    from friday.weixin.node_runtime import resolve_node_exe

    return resolve_node_exe()


def _resolve_openclaw_script() -> Path | None:
    from friday.paths import get_appdata_dir
    from friday.weixin.node_runtime import NPM_GLOBAL

    candidates = [
        NPM_GLOBAL / "node_modules" / "openclaw" / "dist" / "index.js",
        get_appdata_dir() / "runtime" / "npm-global" / "node_modules" / "openclaw" / "dist" / "index.js",
        Path(os.environ.get("APPDATA", "")) / "npm" / "node_modules" / "openclaw" / "dist" / "index.js",
        Path.home() / "AppData" / "Roaming" / "npm" / "node_modules" / "openclaw" / "dist" / "index.js",
    ]
    for script in candidates:
        if script.is_file():
            return script
    return None


def _fallback_gateway_cmd(port: int) -> list[str] | None:
    node = _resolve_node_exe()
    if not node:
        return None
    script = _resolve_openclaw_script()
    if not script:
        return None
    return [node, str(script), "gateway", "--port", str(port)]


def write_gateway_cmd(*, port: int | None = None) -> Path:
    """写入 gateway.cmd 到 openclaw 状态目录（一键配置 / 自启依赖）。"""
    target_port = port if port is not None else _gateway_port()
    state_dir = openclaw_state_dir()
    state_dir.mkdir(parents=True, exist_ok=True)
    cmd_path = state_dir / "gateway.cmd"
    node = _resolve_node_exe()
    script = _resolve_openclaw_script()
    if not node or not script:
        raise FileNotFoundError("未找到 node 或 openclaw 安装路径，请先完成 OpenClaw 安装")
    lines = [
        "@echo off",
        f'set "OPENCLAW_STATE_DIR={state_dir}"',
        f'set "OPENCLAW_GATEWAY_PORT={target_port}"',
        f'"{node}" "{script}" gateway --port {target_port}',
    ]
    cmd_path.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")
    _log.info("已写入 gateway.cmd | path=%s port=%d", cmd_path, target_port)
    return cmd_path


def _gateway_cmd_is_current(cmd_path: Path, target_port: int) -> bool:
    if not cmd_path.is_file():
        return False
    try:
        text = cmd_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    state = str(openclaw_state_dir()).replace("/", "\\").lower()
    normalized = text.replace("/", "\\").lower()
    if state not in normalized:
        return False
    if "friday-test" in normalized:
        return False
    return f"--port {target_port}" in text


def ensure_gateway_cmd(*, port: int | None = None, force: bool = False) -> tuple[bool, str]:
    target_port = port if port is not None else _gateway_port()
    cmd_path = _gateway_cmd_path()
    if not force and _gateway_cmd_is_current(cmd_path, target_port):
        return True, f"gateway.cmd 已就绪（{cmd_path}）"
    try:
        path = write_gateway_cmd(port=target_port)
        return True, f"已生成 gateway.cmd（{path}）"
    except (OSError, FileNotFoundError) as exc:
        return False, f"生成 gateway.cmd 失败：{exc}"


def _spawn_hidden(args: list[str], *, extra_env: dict[str, str] | None = None) -> None:
    from friday.weixin.config import openclaw_env

    env = openclaw_env(extra_env)
    subprocess.Popen(
        args,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=_CREATE_NO_WINDOW | _DETACHED_PROCESS,
        close_fds=True,
    )


def _start_gateway_silent(*, port: int | None = None) -> tuple[bool, str]:
    """后台静默启动 Gateway，不弹出 CMD 窗口（不用 openclaw gateway restart）。"""
    args, env = resolve_gateway_launch(port=port)
    if not args:
        return False, "未找到 gateway.cmd 或 openclaw 安装路径"
    try:
        _spawn_hidden(args, extra_env=env)
        _log.info("已后台启动 OpenClaw Gateway（静默）| cmd=%s", " ".join(args[:3]))
        return True, "Gateway 已在后台启动"
    except OSError as exc:
        return False, str(exc)


def ensure_gateway_running(
    *,
    port: int | None = None,
    wait_sec: float = _START_TIMEOUT_SEC,
    force_restart: bool = False,
) -> dict[str, object]:
    """探测 Gateway；未运行时静默后台拉起（默认不 restart、不弹窗）。"""
    from friday.weixin.setup import ensure_bridge_plugin_for_gateway, ensure_openclaw_gateway_config, ensure_weixin_plugin_for_gateway

    ensure_openclaw_gateway_config()
    ensure_weixin_plugin_for_gateway()
    plugin_changed = ensure_bridge_plugin_for_gateway()
    ensure_gateway_cmd()
    target_port = port if port is not None else _gateway_port()
    if probe_gateway(port=target_port) and not force_restart and not plugin_changed:
        return {"running": True, "started": False, "port": target_port}

    if (force_restart or plugin_changed) and cli_available():
        try:
            run_openclaw(["gateway", "restart", "--force"], timeout=int(wait_sec))
        except (subprocess.TimeoutExpired, OSError) as exc:
            _log.warning("OpenClaw Gateway restart 失败 | %s", exc)

    if (force_restart or plugin_changed) and probe_gateway(port=target_port):
        if cli_available():
            try:
                run_openclaw(["gateway", "stop"], timeout=15)
                time.sleep(1.0)
            except (subprocess.TimeoutExpired, OSError):
                pass
        if not probe_gateway(port=target_port):
            ok, message = _start_gateway_silent(port=target_port)
            if not ok:
                _log.warning("Gateway 静默重启失败 | %s", message)

    if probe_gateway(port=target_port):
        return {"running": True, "started": force_restart or plugin_changed, "port": target_port}

    ok, message = _start_gateway_silent(port=target_port)
    if not ok:
        return {
            "running": False,
            "started": False,
            "port": target_port,
            "error": message,
        }

    deadline = time.time() + wait_sec
    while time.time() < deadline:
        if probe_gateway(port=target_port):
            _log.info("OpenClaw Gateway 已就绪 | port=%d", target_port)
            return {"running": True, "started": True, "port": target_port}
        time.sleep(0.5)

    _log.warning("OpenClaw Gateway 启动后仍不可连接 | port=%d", target_port)
    return {
        "running": False,
        "started": False,
        "port": target_port,
        "error": "Gateway 启动超时：请检查 openclaw.json 是否含 gateway.mode=local，或在设置 → 微信端 AI 点「启动 Gateway」",
    }


def ensure_gateway_running_background(*, wait_sec: float = _START_TIMEOUT_SEC) -> None:
    """后台静默检查/启动 Gateway，不阻塞调用方（用于定时保活）。"""
    import threading

    def _worker() -> None:
        if probe_gateway():
            return
        result = ensure_gateway_running(wait_sec=wait_sec)
        if result.get("running"):
            _log.info("后台 Gateway 就绪 | port=%s", result.get("port"))
        else:
            _log.warning("后台 Gateway 未就绪 | error=%s", result.get("error", ""))

    threading.Thread(target=_worker, daemon=True, name="weixin-gateway-ensure").start()


def ensure_weixin_gateway_with_retries(
    *,
    attempts: int = 3,
    delay_sec: float = 4.0,
    wait_sec: float = _START_TIMEOUT_SEC,
) -> dict[str, object]:
    """星期五启动后多次尝试拉起 Gateway（新电脑/重启后常见未就绪）。"""
    last: dict[str, object] = {"running": False, "started": False}
    tries = max(1, attempts)
    for index in range(tries):
        if index > 0:
            time.sleep(max(1.0, delay_sec))
        if probe_gateway():
            _log.info("OpenClaw Gateway 已在线 | attempt=%d/%d", index + 1, tries)
            return {"running": True, "started": False, "attempt": index + 1}
        last = ensure_gateway_running(wait_sec=wait_sec)
        if last.get("running"):
            _log.info(
                "OpenClaw Gateway 已拉起 | port=%s attempt=%d/%d",
                last.get("port"),
                index + 1,
                tries,
            )
            return last
        _log.warning(
            "OpenClaw Gateway 启动未就绪 | attempt=%d/%d error=%s",
            index + 1,
            tries,
            last.get("error", ""),
        )
    return last


def ensure_gateway_running_async_delay(*, delay_sec: float = 4.0) -> None:
    """延迟在后台线程静默检查/启动 Gateway，不阻塞星期五启动。"""
    import threading

    from friday.storage import load_settings

    def _worker() -> None:
        time.sleep(max(0.5, delay_sec))
        if not getattr(load_settings(), "weixin_bridge_enabled", True):
            return
        if probe_gateway():
            _log.info("微信桥接：Gateway 已在运行")
            return
        result = ensure_weixin_gateway_with_retries()
        if not result.get("running"):
            _log.warning(
                "微信桥接：Gateway 未能自动启动，微信消息可能无回复。"
                "请在「设置 → 微信桥接」点「启动 Gateway」或「一键配置」。"
                " error=%s",
                result.get("error", ""),
            )

    threading.Thread(target=_worker, daemon=True, name="weixin-gateway-deferred").start()
