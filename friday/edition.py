"""星期五桌面版标识（AppData、端口、自启命名等）。"""

from __future__ import annotations


def window_title() -> str:
    return "星期五"


def display_version(version: str) -> str:
    return version


def instance_port() -> int:
    return 58765


def app_user_model_id() -> str:
    return "Friday.AIDesktop.2"


def appdata_folder_name() -> str:
    return "Friday"


def default_workspace_name() -> str:
    return "星期五"


def appdata_hint() -> str:
    return rf"%APPDATA%\{appdata_folder_name()}"


def autostart_task_name() -> str:
    return "Friday Desktop"


def autostart_vbs_name() -> str:
    return "Friday-Desktop.vbs"


def openclaw_autostart_task_name() -> str:
    return "Friday OpenClaw Gateway"


def openclaw_autostart_vbs_name() -> str:
    return "Friday-OpenClaw-Gateway.vbs"


def openclaw_launcher_vbs_name() -> str:
    return "Friday-OpenClaw-Gateway-Launcher.vbs"


def openclaw_gateway_port() -> int:
    return 18789
