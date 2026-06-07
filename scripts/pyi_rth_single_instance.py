# PyInstaller runtime hook — 解压完成后、业务代码 import 之前抢占单实例端口
import os
import sys

if sys.platform == "win32":
    from friday.instance_lock import acquire_instance_lock_or_recover, focus_existing_window

    _sock = acquire_instance_lock_or_recover()
    if _sock is None:
        focus_existing_window()
        os._exit(0)
    sys._friday_instance_lock = _sock
