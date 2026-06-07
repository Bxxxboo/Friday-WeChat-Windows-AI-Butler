"""Windows 单实例锁 —— 防止重复点击快捷方式启动多个窗口。"""

from __future__ import annotations

import sys

from friday.instance_lock import acquire_instance_lock_or_recover, focus_existing_window

_acquired = False


def ensure_single_instance() -> None:
    """已存在实例时激活其窗口并退出当前进程。"""
    global _acquired
    if _acquired:
        return

    existing = getattr(sys, "_friday_instance_lock", None)
    if existing is not None:
        _acquired = True
        return

    sock = acquire_instance_lock_or_recover()
    if sock is None:
        focus_existing_window()
        sys.exit(0)

    sys._friday_instance_lock = sock
    _acquired = True
