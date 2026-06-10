from __future__ import annotations

import sys
from unittest.mock import patch

from friday.python_env import agent_env_dir, find_system_python, get_env_status, setup_agent_env
from friday.safety import RiskLevel, classify_tool, evaluate_tool
from friday.storage import UserSettings
from friday.tools.python_runner import _check_dangerous_code, run_python


def test_classify_python_tools():
    assert classify_tool("python_env_info") == RiskLevel.READ
    assert classify_tool("run_python") == RiskLevel.EXEC
    assert classify_tool("run_python_script") == RiskLevel.EXEC


def test_allow_python_setting(workspace):
    settings = UserSettings(
        allow_python=False,
        workspace=str(workspace).replace("\\", "/"),
    )
    decision = evaluate_tool(settings, "run_python", {"code": "print(1)"})
    assert decision.allowed is False
    assert "Python" in decision.reason


def test_destructive_python_always_requires_approval():
    settings = UserSettings(require_approval_exec=True, allow_python=True)
    decision = evaluate_tool(settings, "run_python", {"code": "import os\nos.remove('x.txt')"})
    assert decision.allowed is True
    assert decision.always_require_approval is True


def test_create_file_python_uses_normal_exec_approval(workspace):
    settings = UserSettings(
        require_approval_exec=True,
        allow_python=True,
        approve_once_per_turn=True,
        workspace=str(workspace).replace("\\", "/"),
    )
    decision = evaluate_tool(
        settings,
        "run_python",
        {"code": "open('new.txt','w').write('hi')"},
    )
    assert decision.allowed is True
    assert decision.needs_approval is True
    assert decision.always_require_approval is False


def test_run_python_script_path_in_workspace(workspace):
    settings = UserSettings(
        restrict_to_workspace=True,
        workspace=str(workspace).replace("\\", "/"),
        allow_python=True,
    )
    outside = "C:/outside/script.py"
    decision = evaluate_tool(settings, "run_python_script", {"path": outside})
    assert decision.allowed is False


def test_check_dangerous_python():
    assert _check_dangerous_code("os.system('format c:')") is not None
    assert _check_dangerous_code("print('hello')") is None


def test_run_python_inline(workspace):
    ws = str(workspace).replace("\\", "/")
    py = sys.executable

    with patch("friday.tools.python_runner.resolve_agent_python", return_value=(py, "mock env")):
        result = run_python("print('friday-py-ok')", cwd=ws, timeout=60)
    assert "friday-py-ok" in result
    assert "exit=0" in result


def test_env_status_not_ready(tmp_path):
    status = get_env_status(str(tmp_path))
    assert status.env_dir == str(agent_env_dir(str(tmp_path))).replace("\\", "/")


def test_find_system_python():
    assert find_system_python() is not None


def test_setup_skips_venv_create_when_only_packages_missing(tmp_path, monkeypatch):
    import subprocess

    ws = str(tmp_path)
    env_dir = agent_env_dir(ws)
    scripts = env_dir / ("Scripts" if sys.platform == "win32" else "bin")
    scripts.mkdir(parents=True)
    venv_py = scripts / ("python.exe" if sys.platform == "win32" else "python")
    venv_py.write_text("", encoding="utf-8")
    (env_dir / "pyvenv.cfg").write_text(f"home = {sys.prefix}\n", encoding="utf-8")

    monkeypatch.setattr("friday.python_env._venv_is_stale", lambda _d: False)
    monkeypatch.setattr("friday.python_env._has_core_packages", lambda _py, _d=None: False)

    venv_calls: list[list[str]] = []

    def fake_run_hidden(args, **kwargs):
        venv_calls.append(list(args))
        return subprocess.CompletedProcess(args, 0, "", "")

    install_calls: list[tuple[Path, Path, Path]] = []

    def fake_install(venv, req, env):
        install_calls.append((venv, req, env))
        return True, "ok"

    req = tmp_path / "requirements-python.txt"
    req.write_text("pandas\n", encoding="utf-8")

    monkeypatch.setattr("friday.python_env._run_hidden", fake_run_hidden)
    monkeypatch.setattr("friday.python_env._install_requirements", fake_install)
    monkeypatch.setattr("friday.python_env.requirements_file", lambda: req)

    ok, msg = setup_agent_env(ws)
    assert ok is True
    assert msg == "ok"
    assert install_calls
    assert not any("venv" in str(call) for call in venv_calls)


def test_setup_progress_background(monkeypatch):
    import threading
    import time

    from friday import python_env as pe

    gate = threading.Event()

    def fake_setup(workspace: str) -> tuple[bool, str]:
        gate.wait(timeout=5)
        pe._report("installing", 50, "正在安装依赖包…", "pandas")
        return True, "done"

    monkeypatch.setattr(pe, "setup_agent_env", fake_setup)

    first = pe.start_setup_agent_env_background("/tmp/ws")
    assert first["started"] is True

    deadline = time.monotonic() + 2
    second = {"already_running": False}
    while time.monotonic() < deadline:
        second = pe.start_setup_agent_env_background("/tmp/ws")
        if second["already_running"]:
            break
        time.sleep(0.02)
    assert second["already_running"] is True

    gate.set()
    if pe._setup_thread:
        pe._setup_thread.join(timeout=5)

    progress = pe.get_setup_progress_dict()
    assert progress["running"] is False
    assert progress["phase"] == "idle"
    assert progress["percent"] == 0


def test_get_setup_progress_idle():
    from friday import python_env as pe

    with pe._setup_lock:
        pe._setup_state.running = False
        pe._setup_state.phase = "idle"
        pe._setup_state.percent = 0
        pe._setup_state.ok = None

    progress = pe.get_setup_progress_dict()
    assert progress["running"] is False
    assert progress["phase"] == "idle"


def test_pip_mirrors_default_domestic_first():
    from friday.python_env import PIP_INDEX_DEFAULT, _PIP_MIRRORS

    assert _PIP_MIRRORS[0][0] == PIP_INDEX_DEFAULT
    assert "npmmirror" in PIP_INDEX_DEFAULT or "tsinghua" in PIP_INDEX_DEFAULT
    assert _PIP_MIRRORS[-1][0] == "https://pypi.org/simple"


def test_report_percent_monotonic():
    from friday import python_env as pe

    with pe._setup_lock:
        pe._setup_state.percent = 0
    pe._report("installing", 50, "first")
    pe._report("installing", 91, "second")
    pe._report("installing", 58, "mirror retry")
    assert pe.get_setup_progress_dict()["percent"] == 91
