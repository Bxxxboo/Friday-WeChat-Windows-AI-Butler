from __future__ import annotations

import sys
from unittest.mock import patch

from friday.python_env import agent_env_dir, find_system_python, get_env_status
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
