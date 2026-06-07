from __future__ import annotations

from unittest.mock import patch

from friday.updates import _pick_download_url, check_for_updates, github_repo
from friday.version import GITHUB_REPO


def test_github_repo_default():
    assert github_repo() == GITHUB_REPO
    assert "/" in github_repo()


def test_pick_download_prefers_windows_zip():
    url = _pick_download_url(
        {
            "html_url": "https://github.com/o/r/releases/tag/v1",
            "assets": [
                {"name": "notes.txt", "browser_download_url": "https://x/notes.txt"},
                {"name": "other.zip", "browser_download_url": "https://x/other.zip"},
                {"name": "Friday-Windows.zip", "browser_download_url": "https://x/win.zip"},
            ],
        }
    )
    assert url == "https://x/win.zip"


def test_check_updates_no_repo_override(monkeypatch):
    monkeypatch.delenv("FRIDAY_GITHUB_REPO", raising=False)
    payload = {
        "tag_name": "v1.0.1",
        "body": "fix",
        "html_url": "https://github.com/o/r/releases/tag/v1.0.1",
        "assets": [{"name": "Friday-Windows.zip", "browser_download_url": "https://x/a.zip"}],
    }

    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            import json

            return json.dumps(payload).encode("utf-8")

    with patch("urllib.request.urlopen", return_value=FakeResp()):
        info = check_for_updates()

    assert info.checked is True
    assert info.source_repo == GITHUB_REPO
    assert info.update_available is True
    assert info.latest == "1.0.1"
    assert info.download_url == "https://x/a.zip"
