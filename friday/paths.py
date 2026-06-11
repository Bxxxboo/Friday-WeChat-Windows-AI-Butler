"""Windows 常见文件夹路径解析 & 应用数据目录统一管理。"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def bundle_dir() -> Path:
    """PyInstaller 打包后的资源根目录，开发模式下为项目根目录。"""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parents[1]


def web_dir() -> Path:
    return bundle_dir() / "web"


def extensions_dir() -> Path:
    """内置扩展包目录（含 demo-office 等）。"""
    return bundle_dir() / "extensions"


def app_icon_path() -> Path:
    """应用窗口 / 任务栏图标路径（开发模式与打包模式均可用）。"""
    candidates = [
        bundle_dir() / "assets" / "friday.ico",
        Path(__file__).resolve().parents[1] / "assets" / "friday.ico",
    ]
    for path in candidates:
        if path.is_file():
            return path
    return candidates[0]


def stable_icon_path() -> Path:
    """%APPDATA%/Friday/friday.ico — 纯 ASCII 路径，供快捷方式 IconLocation 使用。"""
    return get_appdata_dir() / "friday.ico"


_PACKAGED_EXE_NAMES = ("Friday.exe", "星期五.exe")


def packaged_exe_names() -> tuple[str, ...]:
    """打包版主程序文件名（新名优先，含旧中文名兼容）。"""
    return _PACKAGED_EXE_NAMES


def resolve_packaged_exe_in_dir(directory: Path) -> Path | None:
    """在安装目录中解析 Friday 主程序 exe（Friday.exe 优先）。"""
    for name in _PACKAGED_EXE_NAMES:
        candidate = directory / name
        if candidate.is_file():
            return candidate.resolve()
    return None


def dist_packaged_exe() -> Path | None:
    """开发树 dist/Friday/ 下的打包 exe（存在则可用于自启/脚本）。"""
    root = bundle_dir() if not is_frozen() else Path(sys.executable).resolve().parent
    if is_frozen():
        return resolve_packaged_exe_in_dir(root)
    dist_dir = root / "dist" / "Friday"
    if not dist_dir.is_dir():
        legacy = root / "dist" / "星期五"
        if legacy.is_dir():
            dist_dir = legacy
    return resolve_packaged_exe_in_dir(dist_dir)


def default_install_dir() -> Path:
    """推荐程序安装目录（Inno Setup 默认与用户无管理员权限安装）。

    程序文件：%LOCALAPPDATA%/Programs/Friday/
    用户数据仍在 get_appdata_dir()（%APPDATA%/Friday/），卸载程序目录时不删除。
    """
    local_app = os.getenv("LOCALAPPDATA")
    if local_app:
        return Path(local_app) / "Programs" / "Friday"
    return Path.home() / "AppData" / "Local" / "Programs" / "Friday"


def get_appdata_dir() -> Path:
    """获取应用数据根目录，不存在则自动创建。

    用户数据：%APPDATA%/Friday（与程序安装目录分离，见 docs/INSTALL-LAYOUT.md）

    用于统一存储：
    - 设置文件 (settings.json)
    - 会话数据 (sessions/)
    - 日志文件 (friday.log)
    - 加密密钥 (.fernet_key)
    """
    from friday.edition import appdata_folder_name

    appdata = os.getenv("APPDATA")
    folder = appdata_folder_name()
    if appdata:
        base = Path(appdata) / folder
    else:
        base = Path(__file__).resolve().parents[1] / "data" / folder
    base.mkdir(parents=True, exist_ok=True)
    return base


def _first_existing(*candidates: Path) -> Path | None:
    for path in candidates:
        if path.is_dir():
            return path
    return None


def default_workspace_path(*, ensure_exists: bool = False) -> Path:
    """默认操作文件夹：用户文档/星期五。"""
    from friday.edition import default_workspace_name

    home = Path.home()
    docs = _first_existing(home / "Documents", home / "文档") or home
    target = docs / default_workspace_name()
    if ensure_exists:
        target.mkdir(parents=True, exist_ok=True)
    return target


def default_workspace() -> str:
    """首次使用的默认操作文件夹。"""
    target = default_workspace_path(ensure_exists=False)
    if target.is_dir():
        return _normalize(target)
    if target.parent.is_dir():
        return _normalize(target.parent)
    return _normalize(Path.home())


def known_folders(default_workspace_path: str = "") -> dict[str, str]:
    """返回用户可理解的文件夹名称到绝对路径的映射。"""
    home = Path.home()
    mapping: dict[str, Path | None] = {
        "桌面": _first_existing(home / "Desktop", home / "桌面"),
        "下载文件夹": _first_existing(home / "Downloads", home / "下载"),
        "文档": _first_existing(home / "Documents", home / "文档"),
        "图片": _first_existing(home / "Pictures", home / "图片"),
        "视频": _first_existing(home / "Videos", home / "视频"),
        "音乐": _first_existing(home / "Music", home / "音乐"),
    }
    if default_workspace_path:
        ws = Path(default_workspace_path).expanduser()
        if ws.is_dir():
            mapping["默认操作文件夹"] = ws

    return {name: _normalize(path) for name, path in mapping.items() if path is not None}


def format_folders_for_prompt(folders: dict[str, str]) -> str:
    if not folders:
        return "（暂无可用路径）"
    return "\n".join(f"- {name}：{path}" for name, path in folders.items())


def _normalize(path: Path | str) -> str:
    return str(Path(path).expanduser().resolve()).replace("\\", "/")


def resolve_folder_alias(text: str) -> str | None:
    """若 text 是已知别名，返回绝对路径。"""
    if not text:
        return None
    key = text.strip()
    folders = known_folders()
    if key in folders:
        return folders[key]
    lowered = key.lower()
    aliases = {
        "desktop": folders.get("桌面"),
        "downloads": folders.get("下载文件夹"),
        "documents": folders.get("文档"),
        "pictures": folders.get("图片"),
        "videos": folders.get("视频"),
        "music": folders.get("音乐"),
        "default workspace": folders.get("默认操作文件夹"),
        "default": folders.get("默认操作文件夹"),
        "workspace": folders.get("默认操作文件夹"),
    }
    result = aliases.get(lowered)
    if result:
        return result
    # 尝试用户自定义 alias
    if "aliases" in folders:
        return folders.get(key)
    return None


__all__ = [
    "app_icon_path",
    "bundle_dir",
    "dist_packaged_exe",
    "packaged_exe_names",
    "resolve_packaged_exe_in_dir",
    "default_install_dir",
    "default_workspace",
    "default_workspace_path",
    "format_folders_for_prompt",
    "get_appdata_dir",
    "is_frozen",
    "known_folders",
    "resolve_folder_alias",
    "stable_icon_path",
    "web_dir",
    "extensions_dir",
]
