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
    theme = (settings.theme or "light").strip().lower()
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
    return boot_splash_html(settings, status="正在启动服务…")


def boot_splash_html(settings: UserSettings | None = None, *, status: str = "正在启动…") -> str:
    """即时启动页 —— 与主界面 boot overlay 视觉一致，用于窗口先显示、后端后加载。"""
    from friday.edition import window_title

    bg = splash_background(settings)
    light = resolved_boot_theme(settings) == "light"
    text = "#5c6578" if light else "#8b95a8"
    accent = "#b8862e" if light else "#d4a056"
    primary = "#4070b8" if light else "#5b8fd9"
    border = "rgba(180, 150, 100, 0.22)" if light else "rgba(212, 160, 86, 0.14)"
    mark_bg = "rgba(184, 134, 46, 0.12)" if light else "rgba(212, 160, 86, 0.16)"
    mark_fill = "linear-gradient(145deg, rgba(184,134,46,0.13), rgba(250,247,242,0.95))" if light else f"linear-gradient(145deg,{mark_bg},transparent)"
    title = window_title()
    safe_status = (
        status.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
    safe_title = (
        title.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
    return (
        f"<!DOCTYPE html><html lang='zh-CN'><head><meta charset='utf-8'>"
        f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{safe_title}</title>"
        f"<style>"
        f"html,body{{margin:0;width:100%;height:100%;background:{bg};overflow:hidden;"
        f"font-family:'Segoe UI','Microsoft YaHei UI',sans-serif;color:{text};}}"
        f".wrap{{position:fixed;inset:0;display:flex;align-items:center;justify-content:center;"
        f"animation:fadeIn .45s cubic-bezier(.22,1,.36,1) both;}}"
        f".card{{text-align:center;animation:rise .55s cubic-bezier(.22,1,.36,1) both;}}"
        f".mark{{width:52px;height:52px;margin:0 auto 18px;border-radius:16px;display:grid;"
        f"place-items:center;font-size:22px;font-weight:600;color:{accent};"
        f"background:{mark_fill};border:1px solid {border};"
        f"box-shadow:0 0 28px rgba(180,134,46,0.08);}}"
        f".spin{{width:28px;height:28px;margin:0 auto 12px;border:2.5px solid rgba(128,128,128,.14);"
        f"border-top-color:{accent};border-right-color:{primary};border-radius:50%;"
        f"animation:spin .95s cubic-bezier(.45,.15,.55,.85) infinite;}}"
        f".status{{margin:0;font-size:14px;min-height:1.4em;opacity:.92;}}"
        f".bar{{width:min(220px,72vw);height:3px;margin:18px auto 0;border-radius:999px;"
        f"background:rgba(128,128,128,.14);overflow:hidden;}}"
        f".bar span{{display:block;width:38%;height:100%;border-radius:inherit;"
        f"background:linear-gradient(90deg,transparent,{accent},{primary},transparent);"
        f"animation:slide 1.35s cubic-bezier(.22,1,.36,1) infinite;}}"
        f"@keyframes fadeIn{{from{{opacity:0}}to{{opacity:1}}}}"
        f"@keyframes rise{{from{{opacity:0;transform:translateY(10px) scale(.98)}}"
        f"to{{opacity:1;transform:none}}}}"
        f"@keyframes spin{{to{{transform:rotate(360deg)}}}}"
        f"@keyframes pulse{{0%,100%{{transform:scale(1)}}50%{{transform:scale(1.03)}}}}"
        f"@keyframes slide{{0%{{transform:translateX(-120%)}}100%{{transform:translateX(320%)}}}}"
        f"</style></head><body><div class='wrap'><div class='card'>"
        f"<div class='mark' aria-hidden='true'>五</div>"
        f"<div class='spin' aria-hidden='true'></div>"
        f"<p class='status'>{safe_status}</p>"
        f"<div class='bar' aria-hidden='true'><span></span></div>"
        f"</div></div></body></html>"
    )
