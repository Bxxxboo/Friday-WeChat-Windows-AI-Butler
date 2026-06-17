"""版本更新检查 —— 优先 Gitee（国内免 VPN），GitHub 作备用。"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

from friday.version import GITEE_HOME, GITEE_REPO, GITHUB_HOME, GITHUB_REPO, __version__

_DEFAULT_GITHUB = os.environ.get("FRIDAY_GITHUB_REPO", GITHUB_REPO).strip()
_DEFAULT_GITEE = os.environ.get("FRIDAY_GITEE_REPO", GITEE_REPO).strip()


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
    source_kind: str = ""  # gitee | github
    download_sha256: str = ""


def github_repo() -> str:
    return _DEFAULT_GITHUB


def gitee_repo() -> str:
    return _DEFAULT_GITEE


def _parse_version(text: str) -> tuple[int, ...]:
    parts = re.findall(r"\d+", text)
    return tuple(int(p) for p in parts[:4]) or (0,)


def _is_newer(current: str, latest: str) -> bool:
    return _parse_version(latest) > _parse_version(current)


def _tag_version(data: dict) -> str:
    return str(data.get("tag_name", "")).lstrip("vV")


def _is_source_archive_url(url: str) -> bool:
    return "archive/refs/tags" in (url or "")


def _canonical_update_download_url(repo: str, version: str, source_kind: str) -> str:
    from friday.version import release_update_zip_name

    ver = (version or "").strip().lstrip("vV")
    if not ver or "/" not in repo:
        return ""
    owner, name = repo.split("/", 1)
    fname = release_update_zip_name(ver)
    if source_kind == "gitee":
        return f"https://gitee.com/{owner}/{name}/releases/download/v{ver}/{fname}"
    if source_kind == "github":
        return f"https://github.com/{owner}/{name}/releases/download/v{ver}/{fname}"
    return ""


def _pick_download_sha256(data: dict, download_url: str, *, repo: str = "", source_kind: str = "") -> str:
    from friday.release_hashes import (
        SUMS_FILENAME,
        expected_sha256_for_download,
        filename_from_download_url,
        parse_sums_text,
    )
    from friday.version import release_update_zip_name

    url = (download_url or "").strip()
    ver = _tag_version(data)
    target_name = release_update_zip_name(ver).lower() if ver else filename_from_download_url(url).lower()
    sums_url = ""
    sums_map: dict[str, str] | None = None
    for asset in data.get("assets") or []:
        name = str(asset.get("name", ""))
        if name != SUMS_FILENAME:
            continue
        body = asset.get("body") or asset.get("content") or ""
        if isinstance(body, str) and body.strip():
            sums_map = parse_sums_text(body)
            break
        sums_url = str(asset.get("browser_download_url", "")).strip()
        break
    if sums_map is None and sums_url:
        try:
            from friday.release_hashes import fetch_sums_map

            sums_map = fetch_sums_map(sums_url)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            sums_map = None
    if sums_map and target_name:
        found = sums_map.get(target_name, "")
        if found:
            return found
    if url:
        return expected_sha256_for_download(url, sums_map=sums_map, sums_url=sums_url or None)
    if sums_map and ver:
        canonical = _canonical_update_download_url(repo, ver, source_kind)
        if canonical:
            return expected_sha256_for_download(canonical, sums_map=sums_map)
    return ""


def _pick_download_url(data: dict, *, repo: str = "", source_kind: str = "") -> str:
    from friday.release_hashes import SUMS_FILENAME

    fallback = str(data.get("html_url", ""))
    assets = data.get("assets") or []
    windows_zip = ""
    other_zip: list[str] = []
    other_assets: list[str] = []
    for asset in assets:
        name = str(asset.get("name", ""))
        url = str(asset.get("browser_download_url", ""))
        if not url or _is_source_archive_url(url) or name == SUMS_FILENAME:
            continue
        lower = name.lower()
        if lower.endswith(".zip") and "update" in lower:
            return url
        if lower.endswith(".zip") and ("windows" in lower or "安装" in name or "星期五" in name):
            windows_zip = url
            continue
        if lower.endswith(".zip"):
            other_zip.append(url)
        else:
            other_assets.append(url)
    if windows_zip:
        return windows_zip
    if other_zip:
        return other_zip[0]
    ver = _tag_version(data)
    canonical = _canonical_update_download_url(repo, ver, source_kind)
    if canonical:
        return canonical
    if other_assets:
        return other_assets[0]
    return fallback


def _fetch_json(url: str, *, timeout: float = 12.0) -> dict | None:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "Friday-Desktop"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        return None
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
        return None


def _info_from_release(
    data: dict,
    *,
    current: str,
    repo: str,
    source_url: str,
    source_kind: str,
) -> UpdateInfo:
    latest = str(data.get("tag_name", "")).lstrip("vV") or current
    notes = str(data.get("body", ""))[:800]
    download = _pick_download_url(data, repo=repo, source_kind=source_kind)
    return UpdateInfo(
        current=current,
        latest=latest,
        update_available=_is_newer(current, latest),
        download_url=download,
        download_sha256=_pick_download_sha256(data, download, repo=repo, source_kind=source_kind),
        release_notes=notes,
        checked=True,
        source_repo=repo,
        source_url=source_url,
        source_kind=source_kind,
    )


def _check_github(repo: str, current: str) -> UpdateInfo | None:
    if not repo:
        return None
    data = _fetch_json(f"https://api.github.com/repos/{repo}/releases/latest")
    if not data:
        return None
    return _info_from_release(
        data,
        current=current,
        repo=repo,
        source_url=f"https://github.com/{repo}",
        source_kind="github",
    )


def _check_gitee(repo: str, current: str) -> UpdateInfo | None:
    if not repo:
        return None
    data = _fetch_json(f"https://gitee.com/api/v5/repos/{repo}/releases/latest")
    if not data:
        return None
    return _info_from_release(
        data,
        current=current,
        repo=repo,
        source_url=f"https://gitee.com/{repo}",
        source_kind="gitee",
    )


def _failed(current: str, message: str, *, repo: str = "", source_url: str = "") -> UpdateInfo:
    return UpdateInfo(
        current=current,
        latest=current,
        update_available=False,
        download_url="",
        release_notes=message,
        checked=True,
        source_repo=repo,
        source_url=source_url or GITEE_HOME,
        source_kind="",
    )


def check_for_updates(repo: str | None = None) -> UpdateInfo:
    """检查更新。默认 auto：先 Gitee 后 GitHub。"""
    current = __version__
    if repo is not None:
        repo = repo.strip()
        if not repo:
            return UpdateInfo(
                current=current,
                latest=current,
                update_available=False,
                download_url="",
                release_notes="",
                checked=False,
                source_repo="",
                source_url=GITEE_HOME,
                source_kind="",
            )
        info = _check_gitee(repo, current) or _check_github(repo, current)
        if info:
            return info
        return _failed(current, "更新源暂无 Release 或无法连接", repo=repo)

    mode = os.environ.get("FRIDAY_UPDATE_SOURCE", "auto").strip().lower()
    gitee = _DEFAULT_GITEE
    github = _DEFAULT_GITHUB

    if mode == "github":
        info = _check_github(github, current)
        if info:
            return info
        return _failed(
            current,
            "无法连接 GitHub 更新服务器（国内可能需要 VPN）",
            repo=github,
            source_url=GITHUB_HOME,
        )

    if mode == "gitee":
        info = _check_gitee(gitee, current)
        if info:
            return info
        return _failed(
            current,
            "无法连接 Gitee 更新服务器，或尚未发布 Release",
            repo=gitee,
            source_url=GITEE_HOME,
        )

    # auto：国内优先 Gitee，失败再试 GitHub
    info = _check_gitee(gitee, current)
    if info:
        return info
    info = _check_github(github, current)
    if info:
        return info
    return _failed(
        current,
        "无法获取更新（Gitee / GitHub 均无 Release 或网络不可达）",
        repo=gitee,
        source_url=GITEE_HOME,
    )
