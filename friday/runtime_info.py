"""运行模式与进程信息（设置页「关于」、诊断）。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from friday.paths import is_frozen, resolve_packaged_exe_in_dir
from friday.python_env import AGENT_RUNNER_NAME

_DEV_PYTHON_NAMES = frozenset({"python.exe", "pythonw.exe", "python3.exe"})


def _agent_runner_path(workspace: str) -> tuple[str, str]:
    from friday.python_env import resolve_agent_python

    py, _msg = resolve_agent_python(workspace, auto_setup=False)
    if py and py.is_file():
        return str(py).replace("\\", "/"), py.name
    return "", ""


def runtime_info_payload() -> dict[str, object]:
    """当前进程运行模式与任务管理器显示说明。"""
    exe = Path(sys.executable).resolve()
    main_executable = str(exe).replace("\\", "/")
    main_process_name = exe.name
    pid = os.getpid()

    if is_frozen():
        run_mode = "packaged"
        run_mode_label = "安装包"
        packaged = resolve_packaged_exe_in_dir(exe.parent)
        if packaged is not None:
            main_executable = str(packaged).replace("\\", "/")
            main_process_name = packaged.name
        task_manager_hint = (
            "任务管理器主进程显示为「星期五 - AI 电脑管家」（Friday.exe）。"
            "Agent 执行 Python 脚本时显示 FridayAgent。"
        )
    else:
        run_mode = "dev"
        run_mode_label = "开发"
        if main_process_name.lower() in _DEV_PYTHON_NAMES:
            task_manager_hint = (
                f"当前为开发模式：任务管理器主进程将显示为 Python（{main_process_name}），"
                "而非 Friday.exe。打包安装后才会显示「星期五 - AI 电脑管家」。"
            )
        elif main_process_name.lower() in ("friday.exe", "星期五.exe"):
            task_manager_hint = (
                "当前从 dist 目录直接运行 Friday.exe（非 PyInstaller 冻结）。"
                "任务管理器通常显示为 Friday 或「星期五 - AI 电脑管家」。"
                "Agent 执行 Python 时显示 FridayAgent。"
            )
        else:
            task_manager_hint = (
                f"当前主进程为 {main_process_name}。"
                "开发模式下任务管理器可能显示为 Python 而非品牌化应用名。"
            )

    agent_runner = ""
    agent_runner_name = ""
    try:
        from friday.storage import load_settings, resolved_workspace

        cfg = load_settings()
        workspace = resolved_workspace(cfg)
        agent_runner, agent_runner_name = _agent_runner_path(workspace)
    except OSError:
        pass

    if run_mode == "packaged" and not agent_runner_name:
        agent_runner_name = AGENT_RUNNER_NAME

    return {
        "run_mode": run_mode,
        "run_mode_label": run_mode_label,
        "main_executable": main_executable,
        "main_process_name": main_process_name,
        "pid": pid,
        "agent_runner": agent_runner,
        "agent_runner_name": agent_runner_name,
        "task_manager_hint": task_manager_hint,
    }
