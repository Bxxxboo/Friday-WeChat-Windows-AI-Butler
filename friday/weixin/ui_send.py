"""微信桌面客户端 UI 自动化：向指定联系人发送文字消息。"""
from __future__ import annotations

import ctypes
import platform
import time
from typing import Any

import psutil
import pyperclip

# 层 1 校验用：工具成功时必须包含此前缀
SEND_SUCCESS_MARKER = "✅ 已发送给"


def format_send_success(contact: str, text: str) -> str:
    preview = text if len(text) <= 40 else text[:37] + "…"
    return f"{SEND_SUCCESS_MARKER} {contact}：{preview}"


def _require_windows() -> None:
    if platform.system() != "Windows":
        raise RuntimeError("仅支持 Windows 微信桌面版")


def _weixin_pids() -> list[int]:
    names = {"Weixin.exe", "WeChat.exe"}
    return [
        p.info["pid"]
        for p in psutil.process_iter(["pid", "name"])
        if p.info.get("name") in names
    ]


def _main_hwnd(pid: int, win32gui: Any, win32process: Any, win32con: Any) -> int | None:
    candidates: list[tuple[int, int]] = []

    def cb(hwnd, _):
        _, p = win32process.GetWindowThreadProcessId(hwnd)
        if p != pid:
            return
        cls = win32gui.GetClassName(hwnd)
        title = win32gui.GetWindowText(hwnd)
        if cls != "Qt51514QWindowIcon" or title not in ("微信", "Weixin"):
            return
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        area = max(0, right - left) * max(0, bottom - top)
        candidates.append((hwnd, area))

    win32gui.EnumWindows(cb, None)
    if not candidates:
        return None

    candidates.sort(key=lambda item: item[1], reverse=True)
    if candidates[0][1] >= 400_000:
        return candidates[0][0]

    for hwnd, _ in candidates:
        if win32gui.GetWindowRect(hwnd)[0] <= -1000:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    time.sleep(0.8)

    best: tuple[int, int] | None = None

    def cb2(hwnd, _):
        nonlocal best
        _, p = win32process.GetWindowThreadProcessId(hwnd)
        if p != pid:
            return
        cls = win32gui.GetClassName(hwnd)
        title = win32gui.GetWindowText(hwnd)
        if cls != "Qt51514QWindowIcon" or title not in ("微信", "Weixin"):
            return
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        area = max(0, right - left) * max(0, bottom - top)
        if area > (best[1] if best else 0):
            best = (hwnd, area)

    win32gui.EnumWindows(cb2, None)
    return best[0] if best else candidates[0][0]


def _close_overlays(pyautogui: Any) -> None:
    for _ in range(3):
        pyautogui.press("escape")
        time.sleep(0.25)


def _focus_hwnd(hwnd: int, win32gui: Any, win32con: Any, pyautogui: Any) -> tuple[int, int, int, int]:
    if win32gui.IsIconic(hwnd):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        time.sleep(0.8)
    user32 = ctypes.windll.user32
    user32.keybd_event(win32con.VK_MENU, 0, 0, 0)
    user32.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
    try:
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        pass
    time.sleep(0.4)
    rect = win32gui.GetWindowRect(hwnd)
    cx = (rect[0] + rect[2]) // 2
    cy = (rect[1] + rect[3]) // 2
    pyautogui.click(cx, cy)
    time.sleep(0.3)
    return rect


def _sidebar_search_point(rect: tuple[int, int, int, int]) -> tuple[int, int]:
    left, top, right, bottom = rect
    width = right - left
    height = bottom - top
    x = left + 56 + int(min(width * 0.12, 160))
    y = top + int(height * 0.055)
    return x, y


def _sidebar_result_point(rect: tuple[int, int, int, int]) -> tuple[int, int]:
    left, top, right, bottom = rect
    width = right - left
    height = bottom - top
    x = left + 56 + int(min(width * 0.12, 160))
    y = top + int(height * 0.13)
    return x, y


def _chat_input_point(rect: tuple[int, int, int, int]) -> tuple[int, int]:
    left, top, right, bottom = rect
    width = right - left
    height = bottom - top
    x = left + int(width * 0.55)
    y = bottom - int(height * 0.08)
    return x, y


def _open_contact(rect: tuple[int, int, int, int], contact: str, pyautogui: Any) -> None:
    sx, sy = _sidebar_search_point(rect)
    pyautogui.click(sx, sy)
    time.sleep(0.5)
    pyperclip.copy(contact)
    pyautogui.hotkey("ctrl", "a")
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.9)
    rx, ry = _sidebar_result_point(rect)
    pyautogui.click(rx, ry)
    time.sleep(0.8)


def send_text_to_contact(contact: str, message: str) -> None:
    """在微信桌面版侧边栏搜索联系人并发送文字。失败抛 RuntimeError / FileNotFoundError。"""
    _require_windows()
    contact = (contact or "").strip()
    message = (message or "").strip()
    if not contact:
        raise ValueError("联系人不能为空")
    if not message:
        raise ValueError("消息内容不能为空")

    try:
        import pyautogui
        import win32con
        import win32gui
        import win32process
    except ImportError as exc:
        raise RuntimeError(
            "缺少微信 UI 自动化依赖（pyautogui / pywin32）。请安装后重试。"
        ) from exc

    pyautogui.FAILSAFE = False
    pyautogui.PAUSE = 0.12

    hwnd = None
    for candidate in _weixin_pids():
        hwnd = _main_hwnd(candidate, win32gui, win32process, win32con)
        if hwnd:
            break
    if not hwnd:
        raise RuntimeError("未找到微信主窗口，请先登录并打开微信")

    _close_overlays(pyautogui)
    rect = _focus_hwnd(hwnd, win32gui, win32con, pyautogui)
    _close_overlays(pyautogui)
    _open_contact(rect, contact, pyautogui)

    ix, iy = _chat_input_point(rect)
    pyautogui.click(ix, iy)
    time.sleep(0.3)
    pyperclip.copy(message)
    pyautogui.hotkey("ctrl", "a")
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.4)
    pyautogui.press("enter")
    time.sleep(0.5)
