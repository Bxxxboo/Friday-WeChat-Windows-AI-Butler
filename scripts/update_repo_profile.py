#!/usr/bin/env python3
"""更新 GitHub / Gitee 仓库简介（Description）与主页链接。"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from friday.version import GITEE_HOME, GITEE_REPO, GITHUB_HOME, GITHUB_REPO

DESCRIPTION_ZH = (
    "微信能遥控的 Windows AI 电脑管家——大模型听懂人话，本地工具真正动手。"
    "（星期五 · Friday-WeChat-Windows-AI-Butler）"
)
DESCRIPTION_EN = (
    "WeChat-remote Windows AI butler: LLM understands intent, local tools execute. "
    "Multi-model desktop agent with OpenClaw WeChat bridge."
)
HOMEPAGE = f"{GITEE_HOME}/releases"
GITHUB_API = "https://api.github.com"
GITEE_API = "https://gitee.com/api/v5"


def _github_request(method: str, path: str, token: str, data: dict | None = None) -> dict:
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(
        f"{GITHUB_API}{path}",
        data=body,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "Friday-Desktop",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method=method,
    )
    if body is not None:
        req.add_header("Content-Type", "application/json; charset=utf-8")
    with urllib.request.urlopen(req, timeout=60) as resp:
        text = resp.read().decode("utf-8")
        return json.loads(text) if text else {}


def _gitee_patch(owner_repo: str, token: str, fields: dict[str, str]) -> dict:
    owner, repo = owner_repo.split("/", 1)
    payload = {"access_token": token, **fields}
    body = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{GITEE_API}/repos/{owner}/{repo}",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
        method="PATCH",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        text = resp.read().decode("utf-8")
        return json.loads(text) if text else {}


def update_github(*, token: str, description: str, homepage: str) -> None:
    repo = GITHUB_REPO
    print(f"GitHub: PATCH {repo} ...")
    result = _github_request(
        "PATCH",
        f"/repos/{repo}",
        token,
        {"description": description, "homepage": homepage},
    )
    print(f"  description: {result.get('description', '')[:80]}")
    print(f"  homepage: {result.get('homepage', '')}")


def update_gitee(*, token: str, description: str, homepage: str) -> None:
    repo = GITEE_REPO
    print(f"Gitee: PATCH {repo} ...")
    result = _gitee_patch(repo, token, {"description": description, "homepage": homepage})
    print(f"  description: {str(result.get('description', ''))[:80]}")
    print(f"  homepage: {result.get('homepage', '')}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Update GitHub/Gitee repo description")
    parser.add_argument("--description", default=DESCRIPTION_ZH, help="仓库简介（中文）")
    parser.add_argument("--description-en", default=DESCRIPTION_EN, help="GitHub 备用英文简介")
    parser.add_argument("--homepage", default=HOMEPAGE, help="仓库主页（默认 Gitee Releases）")
    parser.add_argument("--skip-github", action="store_true")
    parser.add_argument("--skip-gitee", action="store_true")
    args = parser.parse_args()

    ok = True
    if not args.skip_github:
        token = os.environ.get("GITHUB_TOKEN", "").strip()
        if not token:
            print("GITHUB_TOKEN not set; skip GitHub", file=sys.stderr)
            ok = False
        else:
            try:
                update_github(token=token, description=args.description_en, homepage=args.homepage)
            except urllib.error.HTTPError as exc:
                print(f"GitHub failed: {exc.code} {exc.reason}", file=sys.stderr)
                ok = False

    if not args.skip_gitee:
        token = os.environ.get("GITEE_TOKEN", "").strip()
        if not token:
            print("GITEE_TOKEN not set; skip Gitee", file=sys.stderr)
            ok = False
        else:
            try:
                update_gitee(token=token, description=args.description, homepage=args.homepage)
            except urllib.error.HTTPError as exc:
                print(f"Gitee failed: {exc.code} {exc.reason}", file=sys.stderr)
                ok = False

    if ok:
        print("Done.")
        print(f"  GitHub: {GITHUB_HOME}")
        print(f"  Gitee:  {GITEE_HOME}")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
