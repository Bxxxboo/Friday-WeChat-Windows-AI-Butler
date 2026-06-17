from __future__ import annotations

from pathlib import Path

import pytest

from friday.config import (
    DOWNLOAD_LARGE_MAX_BYTES,
    DOWNLOAD_LARGE_THRESHOLD_BYTES,
    DOWNLOAD_MAX_BYTES,
    WEB_PAGE_MAX_BYTES,
)
from friday.safety import WRITE_TOOLS, classify_tool, evaluate_tool
from friday.storage import UserSettings
from friday.tools.web_limits import DownloadProbe, download_byte_limit, format_bytes
from friday.tools.web_security import validate_public_url


@pytest.fixture
def small_probe(monkeypatch: pytest.MonkeyPatch):
    def _probe(url: str, *, use_cache: bool = True) -> DownloadProbe:
        return DownloadProbe(url=url, final_url=url, content_length=50 * 1024 * 1024)

    def _trust(url, *, expected_software="", use_cache=True):
        from friday.tools.web_trust import TrustLevel, TrustReport
        return TrustReport(
            url=url, domain="example.com", level=TrustLevel.TRUSTED, label="可信发布商",
        )

    monkeypatch.setattr("friday.tools.web.probe_download", _probe)
    monkeypatch.setattr("friday.tools.web_trust.assess_download_trust", _trust)


@pytest.fixture
def large_probe(monkeypatch: pytest.MonkeyPatch):
    def _probe(url: str, *, use_cache: bool = True) -> DownloadProbe:
        return DownloadProbe(url=url, final_url=url, content_length=3 * 1024 ** 3)

    def _trust(url, *, expected_software="", use_cache=True):
        from friday.tools.web_trust import TrustLevel, TrustReport
        return TrustReport(
            url=url, domain="example.com", level=TrustLevel.TRUSTED, label="可信发布商",
        )

    monkeypatch.setattr("friday.tools.web.probe_download", _probe)
    monkeypatch.setattr("friday.tools.web_trust.assess_download_trust", _trust)


@pytest.mark.parametrize(
    "url,ok",
    [
        ("http://127.0.0.1/file.exe", False),
        ("http://localhost/setup.exe", False),
        ("https://192.168.1.1/pkg.msi", False),
        ("ftp://example.com/a.zip", False),
        ("https://example.com/app.exe", True),
    ],
)
def test_validate_public_url(url: str, ok: bool):
    passed, _ = validate_public_url(url)
    assert passed is ok


def test_download_file_is_write_tool():
    assert "download_file" in WRITE_TOOLS
    assert classify_tool("download_file").value == "write"
    assert classify_tool("browse_webpage").value == "read"


def test_download_limits():
    assert WEB_PAGE_MAX_BYTES == 10 * 1024 * 1024
    assert DOWNLOAD_MAX_BYTES == 2 * 1024 ** 3
    assert DOWNLOAD_LARGE_THRESHOLD_BYTES == 1024 ** 3
    assert DOWNLOAD_LARGE_MAX_BYTES == 10 * 1024 ** 3
    assert download_byte_limit(allow_large=False) == DOWNLOAD_MAX_BYTES
    assert download_byte_limit(allow_large=True) == DOWNLOAD_LARGE_MAX_BYTES


def test_browse_webpage_disabled(tmp_appdata):
    settings = UserSettings(allow_web_browse=False)
    decision = evaluate_tool(settings, "browse_webpage", {"url": "https://example.com"})
    assert not decision.allowed


def test_download_disabled(tmp_appdata, small_probe):
    settings = UserSettings(allow_downloads=False)
    decision = evaluate_tool(
        settings,
        "download_file",
        {"url": "https://example.com/a.exe", "destination": "C:/temp"},
    )
    assert not decision.allowed


def test_download_allows_user_specified_path_outside_workspace(tmp_appdata, workspace: Path, small_probe):
    outside = "E:/NeteaseCloudMusic_Setup.exe"
    settings = UserSettings(restrict_to_workspace=True, workspace=str(workspace), allow_downloads=True)
    decision = evaluate_tool(
        settings,
        "download_file",
        {"url": "https://example.com/a.exe", "destination": outside},
    )
    assert decision.allowed

    inside = str(workspace / "app.exe")
    decision = evaluate_tool(
        settings,
        "download_file",
        {"url": "https://example.com/a.exe", "destination": inside},
    )
    assert decision.allowed
    assert not decision.large_download


def test_large_download_requires_special_approval(large_probe, workspace: Path):
    settings = UserSettings(
        allow_downloads=True,
        require_approval_writes=False,
        workspace=str(workspace),
    )
    decision = evaluate_tool(
        settings,
        "download_file",
        {"url": "https://example.com/big.iso", "destination": str(workspace / "big.iso")},
    )
    assert decision.allowed
    assert decision.large_download
    assert decision.needs_approval
    assert decision.download_size_bytes == 3 * 1024 ** 3


def test_large_download_blocked_above_hard_cap(large_probe, monkeypatch: pytest.MonkeyPatch):
    def _huge(url: str, *, use_cache: bool = True) -> DownloadProbe:
        return DownloadProbe(url=url, content_length=20 * 1024 ** 3)

    monkeypatch.setattr("friday.tools.web.probe_download", _huge)
    settings = UserSettings(allow_downloads=True)
    decision = evaluate_tool(
        settings,
        "download_file",
        {"url": "https://example.com/huge.iso", "destination": "D:/Downloads"},
    )
    assert not decision.allowed


def test_allow_large_skips_reapproval(large_probe, workspace: Path):
    settings = UserSettings(
        allow_downloads=True,
        require_approval_writes=True,
        workspace=str(workspace),
    )
    decision = evaluate_tool(
        settings,
        "download_file",
        {
            "url": "https://example.com/big.iso",
            "destination": str(workspace / "big.iso"),
            "_allow_large": True,
        },
    )
    assert decision.allowed
    assert not decision.large_download


def test_extract_page_links():
    from friday.tools.web import _extract_page

    html = """
    <html><head><title>Demo App</title></head>
    <body>
      <a href="/files/setup.exe">Download</a>
      <a href="https://other.example/docs">Docs</a>
    </body></html>
    """
    parsed = _extract_page(html, "https://example.com/page")
    assert parsed["title"] == "Demo App"
    assert any("setup.exe" in item["url"] for item in parsed["download_links"])


def test_format_bytes():
    assert "GB" in format_bytes(3 * 1024 ** 3)
    assert "MB" in format_bytes(50 * 1024 ** 2)
