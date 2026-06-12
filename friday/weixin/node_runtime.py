"""为微信桥接准备 Node.js / npm（系统已有则复用，否则自动安装到 AppData）。"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from friday.logging_config import get_logger
from friday.paths import get_appdata_dir

_log = get_logger("weixin.node")

NODE_VERSION = "22.19.0"
OPENCLAW_MIN_NODE = (22, 19, 0)
NODE_ZIP_NAME = f"node-v{NODE_VERSION}-win-x64.zip"
NODE_ROOT = get_appdata_dir() / "runtime" / "node"
NODE_HOME = NODE_ROOT / f"node-v{NODE_VERSION}-win-x64"
NPM_GLOBAL = get_appdata_dir() / "runtime" / "npm-global"

# 默认国内源，避免新设备访问 registry.npmjs.org 需 VPN
NPM_REGISTRY_DEFAULT = "https://registry.npmmirror.com"
NPM_REGISTRIES: tuple[str, ...] = (
    NPM_REGISTRY_DEFAULT,
    "https://mirrors.cloud.tencent.com/npm/",
    "https://registry.npmjs.org",
)


def _creationflags() -> int:
    return subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def node_semver(exe: str) -> tuple[int, int, int] | None:
    try:
        proc = subprocess.run(
            [exe, "-v"],
            capture_output=True,
            text=True,
            timeout=15,
            encoding="utf-8",
            errors="replace",
            creationflags=_creationflags(),
        )
        text = (proc.stdout or proc.stderr or "").strip()
        match = re.search(r"v?(\d+)\.(\d+)\.(\d+)", text)
        if not match:
            return None
        return int(match.group(1)), int(match.group(2)), int(match.group(3))
    except (OSError, subprocess.TimeoutExpired):
        return None


def node_meets_openclaw(exe: str) -> bool:
    version = node_semver(exe)
    return version is not None and version >= OPENCLAW_MIN_NODE


def resolve_node_exe() -> str | None:
    """优先使用满足 OpenClaw 最低版本 (22.19+) 的 Node。"""
    portable = NODE_HOME / "node.exe"
    system = shutil.which("node")
    candidates: list[str] = []
    if portable.is_file():
        candidates.append(str(portable))
    if system:
        candidates.append(system)
    for exe in candidates:
        if node_meets_openclaw(exe):
            return exe
    return candidates[0] if candidates else None


def _system_npm() -> str | None:
    for name in ("npm.cmd", "npm"):
        found = shutil.which(name)
        if found:
            return found
    return None


def _friday_npm() -> str | None:
    candidate = NODE_HOME / "npm.cmd"
    return str(candidate) if candidate.is_file() else None


def npm_command() -> str | None:
    return _system_npm() or _friday_npm()


def npm_global_prefix() -> Path:
    NPM_GLOBAL.mkdir(parents=True, exist_ok=True)
    return NPM_GLOBAL


def openclaw_cmd_in_friday_prefix() -> Path | None:
    for name in ("openclaw.cmd", "openclaw"):
        path = NPM_GLOBAL / name
        if path.is_file():
            return path
    return None


def node_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = os.environ.copy()
    path_parts: list[str] = []
    if NODE_HOME.is_dir():
        path_parts.append(str(NODE_HOME))
    if NPM_GLOBAL.is_dir():
        path_parts.append(str(NPM_GLOBAL))
    existing = env.get("PATH", "")
    if path_parts:
        env["PATH"] = os.pathsep.join(path_parts + ([existing] if existing else []))
    env.setdefault("NPM_CONFIG_REGISTRY", NPM_REGISTRY_DEFAULT)
    env.setdefault("npm_config_registry", NPM_REGISTRY_DEFAULT)
    if extra:
        env.update(extra)
    return env


def _npm_network_error(output: str) -> bool:
    text = (output or "").lower()
    needles = (
        "network",
        "etimedout",
        "econnrefused",
        "enotfound",
        "fetch failed",
        "connect timeout",
        "socket hang up",
    )
    return any(n in text for n in needles)


def _run_npm_once(
    npm: str,
    args: list[str],
    *,
    timeout: int,
    registry: str,
    prefix: Path | None = None,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    cmd = [npm, *args]
    if prefix is not None:
        cmd.extend(["--prefix", str(prefix)])
    env = node_env(
        {
            "NPM_CONFIG_REGISTRY": registry,
            "npm_config_registry": registry,
        }
    )
    if prefix is not None:
        env["NPM_CONFIG_PREFIX"] = str(prefix)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        encoding="utf-8",
        errors="replace",
        creationflags=_creationflags(),
        env=env,
        cwd=str(cwd) if cwd else None,
    )


def run_npm(
    args: list[str],
    *,
    timeout: int = 600,
    prefix: Path | None = None,
    cwd: Path | None = None,
    global_install: bool = False,
) -> subprocess.CompletedProcess[str]:
    """执行 npm 命令；默认国内源，网络失败时自动切换镜像。"""
    npm = npm_command()
    if not npm:
        raise FileNotFoundError("npm not available")

    npm_args = list(args)
    if (
        global_install
        and npm_args
        and npm_args[0] == "install"
        and "--global" not in npm_args
        and "-g" not in npm_args
    ):
        npm_args = ["install", "--global", *npm_args[1:]]

    last: subprocess.CompletedProcess[str] | None = None
    for registry in NPM_REGISTRIES:
        proc = _run_npm_once(
            npm,
            npm_args,
            timeout=timeout,
            registry=registry,
            prefix=prefix,
            cwd=cwd,
        )
        last = proc
        if proc.returncode == 0:
            if registry != NPM_REGISTRY_DEFAULT:
                _log.info("npm 命令成功 | registry=%s", registry)
            return proc
        detail = (proc.stderr or proc.stdout or "").strip()
        if not _npm_network_error(detail):
            return proc
        _log.warning("npm 网络失败，切换镜像 | registry=%s tail=%s", registry, detail[-200:])

    assert last is not None
    return last


def run_npm_global(args: list[str], *, timeout: int = 600) -> subprocess.CompletedProcess[str]:
    return run_npm(args, timeout=timeout, prefix=npm_global_prefix(), global_install=True)


def _try_winget_node() -> bool:
    if os.name != "nt":
        return False
    winget = shutil.which("winget")
    if not winget:
        return False
    _log.info("尝试通过 winget 安装 Node.js LTS（用户范围）…")
    try:
        proc = subprocess.run(
            [
                winget,
                "install",
                "-e",
                "--id",
                "OpenJS.NodeJS.LTS",
                "--accept-package-agreements",
                "--accept-source-agreements",
                "--scope",
                "user",
            ],
            capture_output=True,
            text=True,
            timeout=900,
            encoding="utf-8",
            errors="replace",
            creationflags=_creationflags(),
        )
        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or "").strip()[-300:]
            _log.warning("winget 安装 Node 失败 | code=%s %s", proc.returncode, tail)
            return False
        return _system_npm() is not None
    except (subprocess.TimeoutExpired, OSError) as exc:
        _log.warning("winget 安装 Node 异常 | %s", exc)
        return False


def _download_portable_node() -> bool:
    if (NODE_HOME / "node.exe").is_file() and (NODE_HOME / "npm.cmd").is_file():
        return True

    NODE_ROOT.mkdir(parents=True, exist_ok=True)
    url = f"https://nodejs.org/dist/v{NODE_VERSION}/{NODE_ZIP_NAME}"
    zip_path = NODE_ROOT / NODE_ZIP_NAME
    _log.info("正在下载便携 Node.js %s …", NODE_VERSION)
    try:
        with urllib.request.urlopen(url, timeout=120) as resp:
            zip_path.write_bytes(resp.read())
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(NODE_ROOT)
        zip_path.unlink(missing_ok=True)
    except (OSError, urllib.error.URLError, zipfile.BadZipFile) as exc:
        _log.warning("下载/解压 Node 失败 | %s", exc)
        return False

    ok = (NODE_HOME / "node.exe").is_file() and (NODE_HOME / "npm.cmd").is_file()
    if ok:
        _log.info("便携 Node.js 已就绪 | path=%s", NODE_HOME)
    return ok


def ensure_node_npm() -> tuple[bool, str]:
    """确保本机可用 npm；必要时自动安装 Node（winget → 便携包）。"""
    portable_node = NODE_HOME / "node.exe"
    if portable_node.is_file() and node_meets_openclaw(str(portable_node)):
        npm = _friday_npm()
        if npm:
            return True, f"便携 Node.js {NODE_VERSION} 已就绪"

    system_node = shutil.which("node")
    if system_node and node_meets_openclaw(system_node) and _system_npm():
        return True, "Node.js 已可用"

    if _try_winget_node():
        npm = _system_npm()
        if npm:
            return True, "已通过 winget 安装 Node.js"

    if _download_portable_node():
        npm = _friday_npm()
        if npm:
            return True, f"已下载便携 Node.js {NODE_VERSION} 到 %APPDATA%\\Friday\\runtime\\node"

    return False, (
        "无法自动安装 Node.js（需联网）。请手动安装 Node 22+：https://nodejs.org，"
        "或在 PowerShell 执行：iwr -useb https://openclaw.ai/install.ps1 | iex"
    )


