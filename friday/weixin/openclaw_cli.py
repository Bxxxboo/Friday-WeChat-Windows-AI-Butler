from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def resolve_openclaw_command() -> list[str]:
    """返回可执行的 openclaw 命令前缀（Windows 上可能是 cmd /c openclaw.cmd）。"""
    found = shutil.which("openclaw")
    if found:
        return [found]
    if os.name == "nt":
        from friday.paths import get_appdata_dir

        for cmd_path in (
            get_appdata_dir() / "runtime" / "npm-global" / "openclaw.cmd",
            Path(os.environ.get("APPDATA", "")) / "npm" / "openclaw.cmd",
        ):
            if cmd_path.is_file():
                return ["cmd", "/c", str(cmd_path)]
    return ["openclaw"]


def cli_available() -> bool:
    cli = resolve_openclaw_command()
    if cli != ["openclaw"]:
        return True
    return shutil.which("openclaw") is not None


def openclaw_shell_invocation(extra_args: list[str]) -> str:
    """构建可在 cmd /k 中执行的 openclaw 命令行（含带空格路径）。"""
    from friday.edition import openclaw_gateway_port
    from friday.weixin.config import openclaw_state_dir

    state = openclaw_state_dir()
    prefix = (
        f'set "OPENCLAW_STATE_DIR={state}" && '
        f'set "OPENCLAW_GATEWAY_PORT={openclaw_gateway_port()}" && '
    )
    cli = resolve_openclaw_command()
    if cli[0] == "cmd" and len(cli) >= 3 and cli[1] == "/c":
        parts = [f'"{cli[2]}"']
    else:
        parts = [f'"{p}"' if " " in p else p for p in cli]
    parts.extend(extra_args)
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
