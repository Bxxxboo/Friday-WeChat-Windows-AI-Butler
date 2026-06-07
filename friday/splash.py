"""启动主题色 —— 与 settings.json 对齐，用于 WebView 背景。"""

from __future__ import annotations

import sys

from friday.storage import UserSettings, load_settings

_DARK_BG = "#0a0d12"
_LIGHT_BG = "#f0ebe3"


def splash_background(settings: UserSettings | None = None) -> str:
    return _LIGHT_BG if resolved_boot_theme(settings) == "light" else _DARK_BG


def resolved_boot_theme(settings: UserSettings | None = None) -> str:
    """返回 light / dark。"""
    settings = settings or load_settings()
    theme = (settings.theme or "dark").strip().lower()
    if theme == "system":
        return "dark" if _system_prefers_dark() else "light"
    return "light" if theme == "light" else "dark"


def _system_prefers_dark() -> bool:
    if sys.platform != "win32":
        return True
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return int(value) == 0
    except OSError:
        return True


def blank_html(settings: UserSettings | None = None) -> str:
    """启动占位页 —— 带加载动画，避免长时间纯色空白。"""
    bg = splash_background(settings)
    text = "#5c6578" if resolved_boot_theme(settings) == "light" else "#8b95a8"
    accent = "#b8862e" if resolved_boot_theme(settings) == "light" else "#d4a056"
    return (
        f"<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<style>"
        f"html,body{{margin:0;width:100%;height:100%;background:{bg};"
        f"display:flex;align-items:center;justify-content:center;font-family:'Segoe UI','Microsoft YaHei UI',sans-serif;}}"
        f".boot{{text-align:center;color:{text};}}"
        f".spin{{width:36px;height:36px;margin:0 auto 16px;border:3px solid rgba(128,128,128,.2);"
        f"border-top-color:{accent};border-radius:50%;animation:spin .8s linear infinite;}}"
        f"@keyframes spin{{to{{transform:rotate(360deg);}}}}"
        f"h3{{margin:0 0 6px;font-size:15px;font-weight:600;color:{text};}}"
        f"p{{margin:0;font-size:13px;opacity:.85;}}"
        f"</style></head><body><div class='boot'>"
        f"<div class='spin'></div><h3>星期五</h3><p>正在启动…</p>"
        f"</div></body></html>"
    )
