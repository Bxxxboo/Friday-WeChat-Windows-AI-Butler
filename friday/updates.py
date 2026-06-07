"""版本更新检查 —— 对接 GitHub Releases。"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

from friday.version import GITHUB_HOME, GITHUB_REPO, __version__

# 环境变量 FRIDAY_GITHUB_REPO 可覆盖内置源（开发/ fork 用）
_DEFAULT_REPO = os.environ.get("FRIDAY_GITHUB_REPO", GITHUB_REPO).strip()


@dataclass
class UpdateInfo:
    current: str
    latest: str
    update_available: bool
    download_url: str
    release_notes: str
    checked: bool
    source_repo: str = ""
    source_url: str = ""


def github_repo() -> str:
    return _DEFAULT_REPO.strip()


def _parse_version(text: str) -> tuple[int, ...]:
    parts = re.findall(r"\d+", text)
    return tuple(int(p) for p in parts[:4]) or (0,)


def _is_newer(current: str, latest: str) -> bool:
    return _parse_version(latest) > _parse_version(current)


def _pick_download_url(data: dict) -> str:
    fallback = str(data.get("html_url", ""))
    assets = data.get("assets") or []
    preferred: list[str] = []
    for asset in assets:
        name = str(asset.get("name", ""))
        url = str(asset.get("browser_download_url", ""))
        if not url:
            continue
        lower = name.lower()
        if lower.endswith(".zip") and ("windows" in lower or "安装" in name):
            return url
        if lower.endswith(".zip"):
            preferred.append(url)
        elif lower.endswith(".exe"):
            preferred.append(url)
    if preferred:
        return preferred[0]
    return fallback


def check_for_updates(repo: str | None = None) -> UpdateInfo:
    repo = (repo or _DEFAULT_REPO).strip()
    current = __version__
    source_url = f"https://github.com/{repo}" if repo else GITHUB_HOME
    if not repo:
        return UpdateInfo(
            current=current,
            latest=current,
            update_available=False,
            download_url="",
            release_notes="",
            checked=False,
            source_repo="",
            source_url=GITHUB_HOME,
        )

    url = f"https://api.github.com/repos/{repo}/releases/latest"
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "Friday-Desktop"},
    )
    try:
        with urllib.request.urlopen(request, timeout=12.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
        return UpdateInfo(
            current=current,
            latest=current,
            update_available=False,
            download_url="",
            release_notes="无法连接 GitHub 更新服务器",
            checked=True,
            source_repo=repo,
            source_url=source_url,
        )

    latest = str(data.get("tag_name", "")).lstrip("vV") or current
    notes = str(data.get("body", ""))[:800]
    download = _pick_download_url(data)

    return UpdateInfo(
        current=current,
        latest=latest,
        update_available=_is_newer(current, latest),
        download_url=download,
        release_notes=notes,
        checked=True,
        source_repo=repo,
        source_url=source_url,
    )
