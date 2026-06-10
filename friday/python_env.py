"""Agent 专用 Python 环境 — 位于工作区 .python-env，与星期五应用自身 venv 分离。"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

from friday.logging_config import get_logger
from friday.paths import bundle_dir, get_appdata_dir, is_frozen

_log = get_logger("python_env")

ENV_DIR_NAME = ".python-env"
REQUIREMENTS_NAME = "requirements-python.txt"
# 默认国内 PyPI 镜像，避免新设备访问 pypi.org 需 VPN
PIP_INDEX_DEFAULT = "https://pypi.tuna.tsinghua.edu.cn/simple"
PIP_TRUSTED_HOST_DEFAULT = "pypi.tuna.tsinghua.edu.cn"
EMBED_PYTHON_VERSION = "3.12.10"
EMBED_PYTHON_DIR = get_appdata_dir() / "runtime" / f"python-{EMBED_PYTHON_VERSION}-embed-amd64"
_PACKAGES_OK_MARKER = ".packages_ok"
_packages_cache: dict[str, tuple[float, bool]] = {}
_PACKAGES_CACHE_TTL = 120.0

ProgressReporter = Callable[[str, int, str, str], None]

_setup_lock = threading.Lock()
_setup_thread: threading.Thread | None = None


@dataclass
class _SetupProgressState:
    running: bool = False
    phase: str = "idle"
    percent: int = 0
    message: str = ""
    detail: str = ""
    log: list[str] = field(default_factory=list)
    ok: bool | None = None
    result_message: str = ""


_setup_state = _SetupProgressState()


def _report(phase: str, percent: int, message: str, detail: str = "", *, log_line: str = "") -> None:
    with _setup_lock:
        _setup_state.phase = phase
        clamped = max(0, min(100, percent))
        if phase == "done":
            _setup_state.percent = 100
        else:
            # 切换镜像/重试时也不回退，避免 91% → 58% 的困惑
            _setup_state.percent = max(_setup_state.percent, clamped)
        _setup_state.message = message
        _setup_state.detail = detail[:240]
        if log_line:
            _setup_state.log.append(log_line.strip()[:200])
            if len(_setup_state.log) > 12:
                _setup_state.log = _setup_state.log[-12:]


def get_setup_progress_dict() -> dict[str, object]:
    with _setup_lock:
        return asdict(_setup_state)


def start_setup_agent_env_background(workspace: str) -> dict[str, object]:
    """后台启动初始化；若已在运行则返回 already_running。"""
    global _setup_thread

    with _setup_lock:
        if _setup_state.running:
            if _setup_thread is not None and _setup_thread.is_alive():
                return {"started": False, "already_running": True}
            _log.warning("检测到上次 Python 环境初始化状态卡住，已重置")
            _setup_state.running = False
        _setup_state.running = True
        _setup_state.phase = "starting"
        _setup_state.percent = 0
        _setup_state.message = "正在启动初始化…"
        _setup_state.detail = "首次安装 pandas 等依赖可能需 3–10 分钟，请保持网络畅通"
        _setup_state.log = []
        _setup_state.ok = None
        _setup_state.result_message = ""

    def worker() -> None:
        try:
            _report("checking", 3, "正在检查 Python 环境…")
            ok, msg = setup_agent_env(workspace)
            with _setup_lock:
                _setup_state.ok = ok
                _setup_state.result_message = msg
            if ok:
                _report("done", 100, "初始化完成", msg)
            else:
                _report("error", _setup_state.percent or 5, "初始化失败", msg)
        except Exception as exc:
            _log.exception("Python 环境初始化异常")
            with _setup_lock:
                _setup_state.ok = False
                _setup_state.result_message = str(exc)
            _report("error", _setup_state.percent or 5, "初始化异常", str(exc)[:240])
        finally:
            with _setup_lock:
                _setup_state.running = False
                if _setup_state.ok:
                    _setup_state.phase = "idle"
                    _setup_state.percent = 0
                    _setup_state.message = ""
                    _setup_state.detail = ""
                    _setup_state.log = []
                    _setup_state.ok = None
                    _setup_state.result_message = ""

    _setup_thread = threading.Thread(target=worker, daemon=True, name="python-env-setup")
    _setup_thread.start()
    return {"started": True, "already_running": False}


@dataclass
class PythonEnvStatus:
    ready: bool
    env_dir: str
    python_exe: str
    version: str
    message: str
    packages_installed: bool = False


def agent_env_dir(workspace: str) -> Path:
    return Path(workspace).expanduser().resolve() / ENV_DIR_NAME


def _is_nested_agent_python(path: Path) -> bool:
    """避免用另一个 .python-env 当 base，否则源码目录移动后工作区 venv 会集体失效。"""
    return any(part.lower() == ENV_DIR_NAME for part in path.parts)


def requirements_file() -> Path:
    return bundle_dir() / REQUIREMENTS_NAME


def _venv_python(env_dir: Path) -> Path:
    if sys.platform == "win32":
        return env_dir / "Scripts" / "python.exe"
    return env_dir / "bin" / "python"


def embed_python_exe() -> Path | None:
    exe = EMBED_PYTHON_DIR / "python.exe"
    return exe if exe.is_file() else None


def _configure_embed_python(root: Path) -> None:
    for pth in root.glob("python*._pth"):
        lines = pth.read_text(encoding="utf-8").splitlines()
        updated: list[str] = []
        for line in lines:
            if line.strip() == "#import site":
                updated.append("import site")
            else:
                updated.append(line)
        pth.write_text("\n".join(updated) + "\n", encoding="utf-8")


def _try_winget_python() -> Path | None:
    if sys.platform != "win32":
        return None
    winget = shutil.which("winget")
    if not winget:
        return None
    _log.info("尝试通过 winget 安装 Python 3.12（用户范围）…")
    try:
        proc = subprocess.run(
            [
                winget,
                "install",
                "-e",
                "--id",
                "Python.Python.3.12",
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
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or "").strip()[-300:]
            _log.warning("winget 安装 Python 失败 | %s", tail)
            return None
    except (subprocess.TimeoutExpired, OSError) as exc:
        _log.warning("winget 安装 Python 异常 | %s", exc)
        return None
    return find_system_python(skip_embed=True, skip_winget=True)


def _download_embed_python(on_progress: ProgressReporter | None = None) -> Path | None:
    if embed_python_exe():
        return embed_python_exe()

    import urllib.error
    import urllib.request
    import zipfile

    url = (
        f"https://www.python.org/ftp/python/{EMBED_PYTHON_VERSION}/"
        f"python-{EMBED_PYTHON_VERSION}-embed-amd64.zip"
    )
    EMBED_PYTHON_DIR.parent.mkdir(parents=True, exist_ok=True)
    zip_path = EMBED_PYTHON_DIR.parent / f"python-{EMBED_PYTHON_VERSION}-embed-amd64.zip"
    _log.info("正在下载便携 Python %s …", EMBED_PYTHON_VERSION)
    if on_progress:
        on_progress("downloading_python", 14, f"正在下载便携 Python {EMBED_PYTHON_VERSION}…", "")
    try:
        with urllib.request.urlopen(url, timeout=180) as resp:
            total = int(resp.headers.get("Content-Length") or 0)
            chunks: list[bytes] = []
            downloaded = 0
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                chunks.append(chunk)
                downloaded += len(chunk)
                if on_progress and total > 0:
                    pct = 14 + int(8 * downloaded / total)
                    mb_done = downloaded // (1024 * 1024)
                    mb_total = max(1, total // (1024 * 1024))
                    on_progress(
                        "downloading_python",
                        pct,
                        f"正在下载便携 Python {EMBED_PYTHON_VERSION}…",
                        f"{mb_done} / {mb_total} MB",
                    )
            zip_path.write_bytes(b"".join(chunks))
        if on_progress:
            on_progress("downloading_python", 23, "正在解压便携 Python…", "")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(EMBED_PYTHON_DIR)
        zip_path.unlink(missing_ok=True)
    except (OSError, urllib.error.URLError, zipfile.BadZipFile) as exc:
        _log.warning("下载/解压便携 Python 失败 | %s", exc)
        return None

    _configure_embed_python(EMBED_PYTHON_DIR)
    return embed_python_exe()


def find_system_python(
    *,
    skip_embed: bool = False,
    skip_winget: bool = False,
    on_progress: ProgressReporter | None = None,
) -> Path | None:
    """查找可用于创建 venv 的系统 Python（3.11+）。"""
    candidates: list[Path | str] = []

    if not skip_embed:
        embed = embed_python_exe()
        if embed:
            candidates.append(embed)

    if not is_frozen():
        app_py = Path(sys.executable)
        if app_py.is_file() and not _is_nested_agent_python(app_py):
            candidates.append(app_py)

    local_app = os.getenv("LOCALAPPDATA", "")
    if local_app:
        for ver in ("Python312", "Python313", "Python311"):
            candidates.append(Path(local_app) / "Programs" / "Python" / ver / "python.exe")

    for name in ("python", "py"):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))

    seen: set[str] = set()
    for raw in candidates:
        path = Path(raw)
        key = str(path.resolve()) if path.exists() else str(path)
        if key in seen:
            continue
        seen.add(key)
        if not path.is_file():
            continue
        if _is_nested_agent_python(path):
            continue
        try:
            out = subprocess.run(
                [str(path), "--version"],
                capture_output=True,
                text=True,
                timeout=15,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            text = (out.stdout or out.stderr or "").strip()
            if "Python 3." in text:
                minor = text.split("Python 3.", 1)[1].split(".", 1)[0]
                if minor.isdigit() and int(minor) >= 11:
                    return path
        except (OSError, subprocess.SubprocessError):
            continue

    if skip_winget:
        return None

    if is_frozen() and sys.platform == "win32" and not skip_embed:
        if on_progress:
            on_progress("finding_python", 10, "正在尝试通过 winget 安装 Python 3.12…", "可能需要数分钟")
        winget_py = _try_winget_python()
        if winget_py:
            return winget_py
        return _download_embed_python(on_progress=on_progress)

    return None


def _run_hidden(args: list[str], *, cwd: Path | None = None, timeout: int = 600) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    kwargs: dict = {
        "args": args,
        "capture_output": True,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "timeout": timeout,
        "cwd": str(cwd) if cwd else None,
        "env": env,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    return subprocess.run(**kwargs)


def _python_version(python_exe: Path) -> str:
    try:
        cp = _run_hidden([str(python_exe), "--version"], timeout=15)
        return (cp.stdout or cp.stderr or "").strip() or "未知"
    except (OSError, subprocess.SubprocessError):
        return "未知"


def _packages_marker(env_dir: Path) -> Path:
    return env_dir / _PACKAGES_OK_MARKER


def _mark_packages_ok(env_dir: Path) -> None:
    try:
        _packages_marker(env_dir).write_text("1", encoding="utf-8")
        _packages_cache.pop(str(env_dir), None)
    except OSError:
        pass


def _packages_marker_valid(env_dir: Path, venv_py: Path) -> bool:
    marker = _packages_marker(env_dir)
    if not marker.is_file():
        return False
    try:
        return marker.stat().st_mtime >= venv_py.stat().st_mtime
    except OSError:
        return False


def _has_core_packages(python_exe: Path, env_dir: Path | None = None) -> bool:
    cache_key = str(python_exe)
    now = time.monotonic()
    cached = _packages_cache.get(cache_key)
    if cached and now - cached[0] < _PACKAGES_CACHE_TTL:
        return cached[1]

    if env_dir is not None and _packages_marker_valid(env_dir, python_exe):
        _packages_cache[cache_key] = (now, True)
        return True

    try:
        cp = _run_hidden(
            [str(python_exe), "-c", "import pandas, numpy, requests; print('ok')"],
            timeout=30,
        )
        ok = cp.returncode == 0 and "ok" in (cp.stdout or "")
    except (OSError, subprocess.SubprocessError):
        ok = False

    if ok and env_dir is not None:
        _mark_packages_ok(env_dir)
    _packages_cache[cache_key] = (now, ok)
    return ok


def _venv_is_stale(env_dir: Path) -> bool:
    """检测来自其他机器或已损坏的 venv。"""
    venv_py = _venv_python(env_dir)
    if not venv_py.is_file():
        return True

    cfg = env_dir / "pyvenv.cfg"
    if cfg.is_file():
        for line in cfg.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.lower().startswith("home"):
                continue
            home = Path(line.split("=", 1)[1].strip())
            if home and not home.is_dir():
                return True

    try:
        cp = _run_hidden([str(venv_py), "-c", "print('ok')"], timeout=8)
    except (OSError, subprocess.SubprocessError):
        return True
    return cp.returncode != 0 or "ok" not in (cp.stdout or "")


def resolve_agent_python(workspace: str, *, auto_setup: bool = False) -> tuple[Path | None, str]:
    """返回 Agent 应使用的 python.exe；auto_setup 时在缺失时尝试创建环境。"""
    ws = Path(workspace).expanduser().resolve()
    ws.mkdir(parents=True, exist_ok=True)
    env_dir = agent_env_dir(str(ws))
    venv_py = _venv_python(env_dir)

    if venv_py.is_file():
        if _venv_is_stale(env_dir):
            _log.warning("工作区 Python 环境已失效，准备重建 | dir=%s", env_dir)
            shutil.rmtree(env_dir, ignore_errors=True)
            if not auto_setup:
                return None, (
                    "工作区 Python 环境已失效（常见于从其他电脑拷贝工作区）。"
                    "请在「设置 → Python 环境」点击「初始化 Python 环境」。"
                )
        else:
            return venv_py, str(env_dir)

    if not auto_setup:
        return None, f"工作区 Python 环境尚未初始化：{env_dir}"

    ok, msg = setup_agent_env(str(ws))
    if ok and venv_py.is_file():
        return venv_py, msg
    return None, msg


def _pip_module_cmd(venv_py: Path, *pip_args: str) -> list[str]:
    return [str(venv_py), "-m", "pip", *pip_args]


def _pip_index_args(index_url: str | None, trusted_host: str | None) -> list[str]:
    if not index_url:
        return []
    args = ["-i", index_url]
    if trusted_host:
        args.extend(["--trusted-host", trusted_host])
    return args


def _ensure_pip_available(venv_py: Path) -> None:
    cp = _run_hidden(_pip_module_cmd(venv_py, "--version"), timeout=30)
    if cp.returncode == 0:
        return
    _log.warning("pip 不可用，尝试 ensurepip | python=%s", venv_py)
    _run_hidden([str(venv_py), "-m", "ensurepip", "--upgrade"], timeout=120)


def _upgrade_pip_best_effort(venv_py: Path) -> None:
    cp = _run_hidden(
        _pip_module_cmd(
            venv_py,
            "install",
            "--upgrade",
            "pip",
            "--disable-pip-version-check",
            *_pip_index_args(PIP_INDEX_DEFAULT, PIP_TRUSTED_HOST_DEFAULT),
        ),
        timeout=180,
    )
    if cp.returncode != 0:
        _log.warning(
            "pip upgrade skipped: %s",
            (cp.stderr or cp.stdout or "").strip()[:240],
        )


def _materialize_requirements(req: Path, env_dir: Path) -> Path:
    """复制 requirements 到工作区 venv（避免打包临时目录或只读路径导致 pip 读失败）。"""
    dest = env_dir / ".requirements-install.txt"
    try:
        shutil.copy2(req, dest)
        return dest
    except OSError:
        return req


_PIP_MIRRORS: list[tuple[str, str | None]] = [
    (PIP_INDEX_DEFAULT, PIP_TRUSTED_HOST_DEFAULT),
    ("https://mirrors.aliyun.com/pypi/simple/", "mirrors.aliyun.com"),
    ("https://pypi.org/simple", "pypi.org"),
]


class _ProgressHeartbeat:
    def __init__(self, phase: str, start_pct: int, end_pct: int, message: str) -> None:
        self._phase = phase
        with _setup_lock:
            current = _setup_state.percent
        self._pct = max(start_pct, current)
        self._end_pct = max(end_pct, self._pct)
        self._message = message
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name="python-env-heartbeat")

    def _run(self) -> None:
        while not self._stop.wait(2.0):
            self._pct = min(self._end_pct, self._pct + 1)
            _report(self._phase, self._pct, self._message, "仍在运行，请稍候…")

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=1.0)


def _run_pip_streaming(
    venv_py: Path,
    pip_args: tuple[str, ...],
    *,
    timeout: int = 900,
    index_url: str | None = None,
    trusted_host: str | None = None,
) -> tuple[int, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env["PYTHONUNBUFFERED"] = "1"
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    full_args = list(pip_args)
    if index_url:
        full_args.extend(["-i", index_url])
    if trusted_host:
        full_args.extend(["--trusted-host", trusted_host])
    kwargs: dict = {
        "args": _pip_module_cmd(venv_py, *full_args),
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "env": env,
        "bufsize": 1,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    proc = subprocess.Popen(**kwargs)
    assert proc.stdout is not None
    lines: list[str] = []
    deadline = time.monotonic() + timeout
    with _setup_lock:
        pip_percent = max(46, _setup_state.percent)
    for raw in proc.stdout:
        if time.monotonic() > deadline:
            proc.kill()
            return 124, "安装 Python 依赖超时，请稍后在设置页重试。"
        line = raw.rstrip()
        if not line:
            continue
        lines.append(line)
        pip_percent = min(91, pip_percent + 1)
        short = line[:160]
        if line.startswith("Collecting "):
            pkg = line.split("Collecting ", 1)[1].split()[0]
            _report("installing", pip_percent, f"正在收集：{pkg}", short, log_line=line)
        elif "Downloading" in line:
            _report("installing", pip_percent, "正在下载依赖包…", short, log_line=line)
        elif "Installing collected packages" in line:
            _report("installing", 88, "正在安装到虚拟环境…", short, log_line=line)
        elif line.startswith("Successfully installed"):
            _report("installing", 92, "依赖安装完成", short, log_line=line)
        else:
            _report("installing", pip_percent, "正在安装依赖包…", short, log_line=line)

    try:
        proc.wait(timeout=max(1, int(deadline - time.monotonic())))
    except subprocess.TimeoutExpired:
        proc.kill()
        return 124, "安装 Python 依赖超时，请稍后在设置页重试。"
    tail = "\n".join(lines[-20:])
    return proc.returncode or 0, tail


def _install_requirements(venv_py: Path, req: Path, env_dir: Path) -> tuple[bool, str]:
    _packages_marker(env_dir).unlink(missing_ok=True)
    _packages_cache.pop(str(venv_py), None)
    req = _materialize_requirements(req, env_dir)

    _report("installing", 42, "正在准备 pip…")
    heartbeat = _ProgressHeartbeat("installing", 42, 44, "正在准备 pip…")
    heartbeat.start()
    try:
        _ensure_pip_available(venv_py)
        _upgrade_pip_best_effort(venv_py)
    finally:
        heartbeat.stop()

    _report("installing", 45, "正在安装依赖包（首次可能需数分钟）…", req.name)
    last_output = ""
    mirror_count = len(_PIP_MIRRORS)
    for idx, (mirror, trusted) in enumerate(_PIP_MIRRORS):
        if idx > 0:
            with _setup_lock:
                current = _setup_state.percent
            _report(
                "installing",
                current,
                "当前镜像未完成，正在切换备用 PyPI 源…",
                mirror or "",
            )
        floor = 45 + idx * 15
        cap = 88 if idx < mirror_count - 1 else 94
        heartbeat = _ProgressHeartbeat(
            "installing",
            max(floor, 45),
            max(cap, floor + 1),
            "正在下载并安装依赖包…",
        )
        heartbeat.start()
        try:
            install_args = ("install", "-r", str(req), "--disable-pip-version-check")
            code, output = _run_pip_streaming(
                venv_py,
                install_args,
                timeout=900,
                index_url=mirror,
                trusted_host=trusted,
            )
        finally:
            heartbeat.stop()
        last_output = output
        if code == 124:
            return False, output
        if code == 0:
            break
        _log.warning("pip install 失败 | mirror=%s tail=%s", mirror or "default", output[-240:])
    else:
        err = last_output.strip()
        return False, f"安装依赖失败（已尝试国内镜像与官方源）：{err[:500]}"

    _report("verifying", 95, "正在校验 pandas / numpy / requests…")
    _packages_cache.pop(str(venv_py), None)
    if not _has_core_packages(venv_py, env_dir):
        return False, (
            "依赖安装完成但校验失败（pandas / numpy / requests 仍不可用）。"
            "请检查网络或代理后重试「初始化 Python 环境」。"
        )

    _mark_packages_ok(env_dir)
    return True, f"Python 环境已就绪：{venv_py} ({_python_version(venv_py)})"


def setup_agent_env(workspace: str) -> tuple[bool, str]:
    """在工作区创建 .python-env 并安装 requirements-python.txt。"""
    ws = Path(workspace).expanduser().resolve()
    ws.mkdir(parents=True, exist_ok=True)
    env_dir = agent_env_dir(str(ws))
    venv_py = _venv_python(env_dir)

    if venv_py.is_file():
        if _venv_is_stale(env_dir):
            _log.warning("重建失效的工作区 Python 环境 | dir=%s", env_dir)
            _report("creating_venv", 28, "检测到旧环境失效，正在重建…")
            shutil.rmtree(env_dir, ignore_errors=True)
            venv_py = _venv_python(env_dir)
        elif _has_core_packages(venv_py, env_dir):
            return True, f"Python 环境已就绪：{venv_py} ({_python_version(venv_py)})"

    if not venv_py.is_file():
        _report("finding_python", 8, "正在查找 Python 3.11+ 解释器…")
        base = find_system_python(on_progress=_report)
        if not base:
            return False, (
                "无法自动准备 Python 3.11+（需联网）。"
                "可在设置 → Python 环境 重试，或手动安装：https://www.python.org/downloads/"
            )

        if env_dir.exists():
            shutil.rmtree(env_dir, ignore_errors=True)

        _log.info("创建 Agent Python 环境 | workspace=%s", ws)
        _report("creating_venv", 32, "正在创建虚拟环境…", str(base.name))
        try:
            cp = _run_hidden([str(base), "-m", "venv", str(env_dir)], cwd=ws, timeout=120)
        except subprocess.TimeoutExpired:
            return False, "创建虚拟环境超时，请稍后重试。"
        if cp.returncode != 0:
            err = (cp.stderr or cp.stdout or "").strip()
            return False, f"创建虚拟环境失败：{err[:400]}"

        venv_py = _venv_python(env_dir)
        if not venv_py.is_file():
            return False, f"虚拟环境创建后未找到解释器：{venv_py}"

    req = requirements_file()
    if not req.is_file():
        return True, f"环境已创建（{_python_version(venv_py)}），但未找到 {REQUIREMENTS_NAME}，跳过依赖安装。"

    return _install_requirements(venv_py, req, env_dir)


def python_ready_light(workspace: str) -> bool:
    """轻量检查：不 spawn Python 进程。"""
    env_dir = agent_env_dir(workspace)
    venv_py = _venv_python(env_dir)
    return venv_py.is_file() and _packages_marker_valid(env_dir, venv_py)


def get_env_status(workspace: str) -> PythonEnvStatus:
    ws = Path(workspace).expanduser().resolve()
    env_dir = agent_env_dir(str(ws))
    venv_py = _venv_python(env_dir)

    if not venv_py.is_file():
        base = find_system_python()
        hint = (
            "点击「初始化 Python 环境」或在对话中让星期五执行复杂 Python 任务时会自动创建。"
        )
        if not base:
            hint = "未检测到 Python 3.11+。在设置页点「初始化 Python 环境」可自动下载便携 Python（需联网）。"
        return PythonEnvStatus(
            ready=False,
            env_dir=str(env_dir).replace("\\", "/"),
            python_exe="",
            version="",
            message=hint,
            packages_installed=False,
        )

    version = _python_version(venv_py)
    packages = _has_core_packages(venv_py, env_dir)
    return PythonEnvStatus(
        ready=packages,
        env_dir=str(env_dir).replace("\\", "/"),
        python_exe=str(venv_py).replace("\\", "/"),
        version=version,
        message="已就绪，可用于 run_python / run_python_script。" if packages else "环境存在但依赖未装全，请重新初始化。",
        packages_installed=packages,
    )


def env_dict(workspace: str) -> dict[str, object]:
    status = get_env_status(workspace)
    progress = get_setup_progress_dict()
    payload: dict[str, object] = {
        "ready": status.ready,
        "env_dir": status.env_dir,
        "python_exe": status.python_exe,
        "version": status.version,
        "message": status.message,
        "packages_installed": status.packages_installed,
        "system_python_available": find_system_python() is not None,
        "setup_running": bool(progress.get("running")),
        "setup_progress": progress,
    }
    if not status.ready and progress.get("result_message") and not progress.get("running"):
        payload["last_setup_error"] = progress.get("result_message")
    return payload
