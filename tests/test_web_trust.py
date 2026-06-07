from __future__ import annotations

import pytest

from friday.safety import evaluate_tool
from friday.storage import UserSettings
from friday.tools.web_trust import (
    TrustLevel,
    assess_download_trust,
    resolve_software_key,
)


def test_resolve_software_aliases():
    assert resolve_software_key("Google Chrome") == "chrome"
    assert resolve_software_key("微信") == "wechat"
    assert resolve_software_key("VS Code") == "vscode"
    assert resolve_software_key("网易云音乐") == "netease_music"


def test_block_crack_url():
    report = assess_download_trust(
        "https://bad.example/crack-setup.exe",
        expected_software="chrome",
        use_cache=False,
    )
    assert report.level == TrustLevel.BLOCKED


def test_official_chrome_domain(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "friday.tools.web_trust.inspect_tls",
        lambda hostname, use_cache=True: {"valid": True, "issuer": "Google Trust Services", "reason": ""},
    )
    report = assess_download_trust(
        "https://dl.google.com/chrome/install/latest/chrome_installer.exe",
        expected_software="chrome",
        use_cache=False,
    )
    assert report.level == TrustLevel.OFFICIAL
    assert report.matched_software == "chrome"


def test_domain_mismatch_for_expected_software(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "friday.tools.web_trust.inspect_tls",
        lambda hostname, use_cache=True: {"valid": True, "issuer": "Test CA", "reason": ""},
    )
    report = assess_download_trust(
        "https://unknown-mirror.example/chrome.exe",
        expected_software="chrome",
        use_cache=False,
    )
    assert report.level == TrustLevel.UNVERIFIED
    assert report.domain_mismatch


def test_untrusted_download_blocked_by_default(tmp_appdata, workspace, monkeypatch: pytest.MonkeyPatch):
    def _probe(url: str, *, use_cache: bool = True):
        from friday.tools.web_limits import DownloadProbe
        return DownloadProbe(url=url, content_length=1024)

    def _trust(url, *, expected_software="", use_cache=True):
        from friday.tools.web_trust import TrustReport
        return TrustReport(
            url=url, domain="mirror.example", level=TrustLevel.SUSPICIOUS,
            label="可疑来源", reasons=["疑似第三方下载站"],
        )

    monkeypatch.setattr("friday.tools.web.probe_download", _probe)
    monkeypatch.setattr("friday.tools.web_trust.assess_download_trust", _trust)

    settings = UserSettings(
        allow_downloads=True,
        require_trusted_downloads=True,
        workspace=str(workspace),
    )
    decision = evaluate_tool(
        settings,
        "download_file",
        {
            "url": "https://mirror.example/app.exe",
            "destination": str(workspace / "app.exe"),
            "expected_software": "chrome",
        },
    )
    assert not decision.allowed


def test_untrusted_download_with_confirm(tmp_appdata, workspace, monkeypatch: pytest.MonkeyPatch):
    def _probe(url: str, *, use_cache: bool = True):
        from friday.tools.web_limits import DownloadProbe
        return DownloadProbe(url=url, content_length=1024)

    def _trust(url, *, expected_software="", use_cache=True):
        from friday.tools.web_trust import TrustReport
        return TrustReport(
            url=url, domain="mirror.example", level=TrustLevel.SUSPICIOUS,
            label="可疑来源", reasons=["疑似第三方下载站"],
            expected_software=expected_software,
        )

    monkeypatch.setattr("friday.tools.web.probe_download", _probe)
    monkeypatch.setattr("friday.tools.web_trust.assess_download_trust", _trust)

    settings = UserSettings(allow_downloads=True, workspace=str(workspace))
    decision = evaluate_tool(
        settings,
        "download_file",
        {
            "url": "https://mirror.example/app.exe",
            "destination": str(workspace / "app.exe"),
            "confirm_untrusted_source": True,
        },
    )
    assert decision.allowed
    assert decision.untrusted_download
