from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def _npm_prefix_roots() -> list[Path]:
    from friday.paths import get_appdata_dir
    from friday.weixin.node_runtime import NPM_GLOBAL

    roots: list[Path] = [NPM_GLOBAL, get_appdata_dir() / "runtime" / "npm-global"]
    for env_key in ("APPDATA", "LOCALAPPDATA"):
        base = os.environ.get(env_key, "")
        if base:
            roots.append(Path(base) / "npm")
    home_npm = Path.home() / "AppData" / "Roaming" / "npm"
    roots.append(home_npm)

    seen: set[str] = set()
    unique: list[Path] = []
    for root in roots:
        key = str(root).lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(root)
    return unique


def find_openclaw_script() -> Path | None:
    rel_paths = (
        "node_modules/openclaw/dist/index.js",
        "node_modules/openclaw/openclaw.mjs",
        "node_modules/openclaw/bin/openclaw.js",
    )
    for root in _npm_prefix_roots():
        for rel in rel_paths:
            candidate = root / rel
            if candidate.is_file():
                return candidate
    return None


def find_openclaw_cmd() -> Path | None:
    from friday.weixin.node_runtime import openclaw_cmd_in_friday_prefix

    found = openclaw_cmd_in_friday_prefix()
    if found:
        return found
    for root in _npm_prefix_roots():
        for rel in (
            "openclaw.cmd",
            "openclaw",
            "bin/openclaw.cmd",
            "node_modules/.bin/openclaw.cmd",
        ):
            candidate = root / rel
            if candidate.is_file():
                return candidate
    return None


def resolve_node_exe() -> str | None:
    from friday.weixin.node_runtime import resolve_node_exe as _resolve

    return _resolve()


def resolve_openclaw_command() -> list[str]:
    """返回可执行的 openclaw 命令前缀（Windows 上可能是 cmd /c openclaw.cmd 或 node index.js）。"""
    found = shutil.which("openclaw")
    if found:
        return [found]

    cmd = find_openclaw_cmd()
    if cmd:
        if os.name == "nt" and cmd.suffix.lower() not in {".exe"}:
            return ["cmd", "/c", str(cmd)]
        return [str(cmd)]

    script = find_openclaw_script()
    node = resolve_node_exe()
    if script and node:
        return [node, str(script)]

    return ["openclaw"]


def cli_available() -> bool:
    return resolve_openclaw_command() != ["openclaw"]


def openclaw_argv(extra_args: list[str]) -> list[str]:
    """构建 openclaw 参数列表（供 subprocess / cmd /k 使用）。"""
    cli = resolve_openclaw_command()
    if cli[0] == "cmd" and len(cli) >= 3 and cli[1] == "/c":
        return [cli[2], *extra_args]
    return [*cli, *extra_args]


def openclaw_shell_invocation(extra_args: list[str]) -> str:
    """构建可在 cmd /k 中执行的 openclaw 命令行（含带空格路径）。"""
    from friday.edition import openclaw_gateway_port
    from friday.weixin.config import openclaw_state_dir

    state = openclaw_state_dir()
    prefix = (
        f'set "OPENCLAW_STATE_DIR={state}" && '
        f'set "OPENCLAW_GATEWAY_PORT={openclaw_gateway_port()}" && '
    )
    argv = openclaw_argv(extra_args)
    parts = [f'"{p}"' if (" " in p or p.lower().endswith((".cmd", ".exe", ".js", ".mjs"))) else p for p in argv]
    return prefix + " ".join(parts)


def run_openclaw(
    args: list[str],
    *,
    timeout: int = 120,
    capture_output: bool = True,
) -> subprocess.CompletedProcess[str]:
    from friday.weixin.config import openclaw_env

    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    cmd = [*resolve_openclaw_command(), *args]
    return subprocess.run(
        cmd,
        capture_output=capture_output,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        creationflags=creationflags,
        env=openclaw_env(),
    )
