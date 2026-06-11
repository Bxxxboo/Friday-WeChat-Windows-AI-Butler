"""一键更新备份与失败回滚（M2.7 / M2.8）。"""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any

from friday.logging_config import get_logger
from friday.paths import get_appdata_dir, is_frozen

_log = get_logger("update_rollback")

BACKUP_DIR_NAME = "Friday.bak"
MAX_STARTUP_FAILURES = 3


def install_backup_dir(install_dir: Path) -> Path:
    return install_dir.parent / BACKUP_DIR_NAME


def _updates_meta_dir() -> Path:
    path = get_appdata_dir() / "updates"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _pending_path() -> Path:
    return _updates_meta_dir() / "pending-update.json"


def _failures_path() -> Path:
    return _updates_meta_dir() / "startup-failures.json"


def backup_install_dir(install_dir: Path) -> Path:
    """更新前整目录备份到与安装目录同级的 Friday.bak。"""
    backup = install_backup_dir(install_dir)
    if backup.exists():
        shutil.rmtree(backup, ignore_errors=True)
    shutil.copytree(install_dir, backup)
    _log.info("安装目录已备份 | src=%s backup=%s", install_dir, backup)
    return backup


def restore_install_dir(install_dir: Path, *, source: Path | None = None) -> tuple[bool, str]:
    """从 Friday.bak 恢复安装目录。"""
    backup = source or install_backup_dir(install_dir)
    if not backup.is_dir():
        return False, f"未找到备份目录：{backup}"
    try:
        if install_dir.exists():
            shutil.rmtree(install_dir, ignore_errors=True)
        shutil.copytree(backup, install_dir)
        _unblock_tree(install_dir)
        _log.info("已从备份恢复安装目录 | install=%s backup=%s", install_dir, backup)
        return True, "已从备份恢复上一版本。"
    except OSError as exc:
        _log.exception("恢复安装目录失败")
        return False, str(exc)


def mark_pending_update(*, version: str, install_dir: Path) -> None:
    payload = {
        "version": version,
        "install_dir": str(install_dir).replace("\\", "/"),
        "backup_dir": str(install_backup_dir(install_dir)).replace("\\", "/"),
        "marked_at": time.time(),
    }
    _pending_path().write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _failures_path().unlink(missing_ok=True)


def clear_pending_update() -> None:
    _pending_path().unlink(missing_ok=True)
    _failures_path().unlink(missing_ok=True)


def has_pending_update() -> bool:
    return _pending_path().is_file()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _record_startup_failure() -> int:
    path = _failures_path()
    data = _read_json(path) if path.is_file() else {}
    count = int(data.get("count") or 0) + 1
    data["count"] = count
    data["last_at"] = time.time()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return count


def guard_startup_after_update() -> bool:
    """打包版启动时：若更新后连续启动失败则自动回滚。返回 False 表示应退出进程。"""
    if not is_frozen() or sys.platform != "win32":
        return True
    if not _pending_path().is_file():
        return True

    from friday.update_installer import app_install_dir

    install = app_install_dir()
    if install is None:
        clear_pending_update()
        return True

    failures = _record_startup_failure()
    if failures < MAX_STARTUP_FAILURES:
        return True

    ok, msg = restore_install_dir(install)
    clear_pending_update()
    if ok:
        _notify_rollback(msg)
        _restart_exe(install)
        return False
    _notify_rollback(f"自动回滚失败：{msg}")
    return False


def _unblock_tree(root: Path) -> None:
    if sys.platform != "win32":
        return
    try:
        import subprocess

        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                f"Get-ChildItem -LiteralPath '{root}' -Recurse -ErrorAction SilentlyContinue | "
                "Unblock-File -ErrorAction SilentlyContinue",
            ],
            capture_output=True,
            timeout=120,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        pass


def _restart_exe(install_dir: Path) -> None:
    from friday.paths import resolve_packaged_exe_in_dir

    exe = resolve_packaged_exe_in_dir(install_dir)
    if not exe or not exe.is_file():
        return
    try:
        import subprocess

        subprocess.Popen(
            [str(exe)],
            cwd=str(install_dir),
            creationflags=getattr(subprocess, "DETACHED_PROCESS", 0),
            close_fds=True,
        )
    except OSError:
        _log.exception("回滚后重启失败")


def _notify_rollback(message: str) -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(  # type: ignore[attr-defined]
            None,
            message + "\n\n应用将尝试以备份版本重新启动。",
            "星期五 - 更新回滚",
            0x40,
        )
    except (AttributeError, OSError):
        _log.warning("回滚通知 | %s", message)
