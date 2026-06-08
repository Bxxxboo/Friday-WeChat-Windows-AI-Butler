"""应用版本号 —— 与 PyInstaller version_info 保持一致。"""

__version__ = "1.2.0"
__version_tuple__ = (1, 2, 0, 0)

RELEASE_ZIP_BASENAME = "Friday-Windows"
RELEASE_ZIP_LEGACY = f"{RELEASE_ZIP_BASENAME}.zip"


def release_zip_name(version: str | None = None) -> str:
    """Release 安装包文件名（含版本号）。"""
    v = (version or __version__).strip().lstrip("vV")
    return f"{RELEASE_ZIP_BASENAME}-v{v}.zip"


def resolve_release_zip_path(
    root: "Path | None" = None,
    version: str | None = None,
) -> "Path":
    """定位 release 目录下的安装包（优先带版本号文件）。"""
    from pathlib import Path

    base = Path(__file__).resolve().parents[1] if root is None else Path(root)
    release_dir = base / "release"
    versioned = release_dir / release_zip_name(version)
    if versioned.is_file():
        return versioned
    legacy = release_dir / RELEASE_ZIP_LEGACY
    if legacy.is_file():
        return legacy
    return versioned

# GitHub Releases（备用，国内常需 VPN）
GITHUB_REPO = "Bxxxboo/Friday-Zero-barrier-DeepSeek-Agent-for-Windows"
GITHUB_HOME = f"https://github.com/{GITHUB_REPO}"

# Gitee Releases（默认更新源，国内可直连）。环境变量 FRIDAY_GITEE_REPO 可覆盖。
GITEE_REPO = "Bxxxboo/friday"
GITEE_HOME = f"https://gitee.com/{GITEE_REPO}"
