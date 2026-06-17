"""下载源可信认证 —— 官方域名库、TLS 校验、可疑来源拦截。"""

from __future__ import annotations

import re
import socket
import ssl
import time
from dataclasses import dataclass, field
from enum import IntEnum
from urllib.parse import urlparse

from friday.logging_config import get_logger

_log = get_logger("web_trust")

_TLS_CACHE: dict[str, tuple[float, dict[str, object]]] = {}
_TRUST_CACHE: dict[str, tuple[float, TrustReport]] = {}
_CACHE_TTL = 300.0

# 全球常见软件发布商 / CDN（域名后缀匹配）
_TRUSTED_PUBLISHER_SUFFIXES = (
    "microsoft.com", "windows.net", "azureedge.net", "visualstudio.com",
    "office.com", "live.com",
    "google.com", "google.cn", "googleapis.com", "gstatic.com",
    "mozilla.org", "mozilla.com", "mozilla.net",
    "apple.com", "icloud.com",
    "adobe.com", "adobe.io",
    "github.com", "githubusercontent.com", "github.io",
    "gitlab.com",
    "oracle.com", "java.com",
    "python.org", "pythonhosted.org",
    "nodejs.org",
    "docker.com", "docker.io",
    "zoom.us", "zoom.com",
    "slack.com", "discord.com", "discordapp.com",
    "spotify.com",
    "nvidia.com", "amd.com", "intel.com",
    "7-zip.org",
    "videolan.org",
    "notepad-plus-plus.org",
    "qemu.org",
    "virtualbox.org",
    "wireshark.org",
    "postman.com", "getpostman.com",
    "figma.com",
    "jetbrains.com", "jetbrains.cn",
    "tencent.com", "qq.com", "weixin.qq.com",
    "alibaba.com", "alicdn.com",
    "baidu.com",
    "163.com", "126.net", "music.163.com",
    "huawei.com",
    "lenovo.com", "lenovo.com.cn",
    "wikipedia.org",
    "sourceforge.net",
    "apache.org",
)

# 常见软件 → 官方域名（用于匹配 expected_software）
_SOFTWARE_OFFICIAL: dict[str, dict[str, object]] = {
    "chrome": {
        "aliases": ("chrome", "google chrome", "谷歌浏览器", "chrome浏览器"),
        "domains": ("google.com", "google.cn", "chromium.org"),
        "download_domains": ("dl.google.com", "google.com", "google.cn"),
    },
    "firefox": {
        "aliases": ("firefox", "火狐", "mozilla firefox"),
        "domains": ("mozilla.org", "mozilla.com", "mozilla.net"),
        "download_domains": ("download.mozilla.org", "mozilla.org"),
    },
    "edge": {
        "aliases": ("edge", "microsoft edge", "微软edge"),
        "domains": ("microsoft.com", "microsoftedge.com"),
        "download_domains": ("microsoft.com", "msedge.net"),
    },
    "vscode": {
        "aliases": ("vscode", "visual studio code", "vs code", "代码编辑器"),
        "domains": ("visualstudio.com", "microsoft.com", "github.com"),
        "download_domains": (
            "code.visualstudio.com", "visualstudio.com", "github.com", "githubusercontent.com",
        ),
    },
    "windows": {
        "aliases": ("windows", "win11", "win10", "windows11", "windows10"),
        "domains": ("microsoft.com",),
        "download_domains": ("microsoft.com", "windows.net", "azureedge.net"),
    },
    "office": {
        "aliases": ("office", "microsoft office", "word", "excel", "ppt"),
        "domains": ("microsoft.com", "office.com"),
        "download_domains": ("office.com", "microsoft.com", "aka.ms"),
    },
    "wechat": {
        "aliases": ("wechat", "微信", "weixin"),
        "domains": ("weixin.qq.com", "qq.com", "tencent.com"),
        "download_domains": ("weixin.qq.com", "dldir1.qq.com", "dldir1v6.qq.com"),
    },
    "qq": {
        "aliases": ("qq", "腾讯qq"),
        "domains": ("qq.com", "tencent.com"),
        "download_domains": ("im.qq.com", "dldir1.qq.com"),
    },
    "7zip": {
        "aliases": ("7zip", "7-zip", "7z"),
        "domains": ("7-zip.org",),
        "download_domains": ("7-zip.org",),
    },
    "python": {
        "aliases": ("python", "python3", "pip"),
        "domains": ("python.org",),
        "download_domains": ("python.org",),
    },
    "nodejs": {
        "aliases": ("nodejs", "node.js", "node"),
        "domains": ("nodejs.org",),
        "download_domains": ("nodejs.org",),
    },
    "git": {
        "aliases": ("git", "git for windows"),
        "domains": ("git-scm.com", "github.com"),
        "download_domains": ("git-scm.com", "github.com", "githubusercontent.com"),
    },
    "notepad++": {
        "aliases": ("notepad++", "notepad plus plus", "npp"),
        "domains": ("notepad-plus-plus.org",),
        "download_domains": ("notepad-plus-plus.org", "github.com"),
    },
    "vlc": {
        "aliases": ("vlc", "vlc player"),
        "domains": ("videolan.org",),
        "download_domains": ("videolan.org",),
    },
    "zoom": {
        "aliases": ("zoom", "zoom meetings"),
        "domains": ("zoom.us", "zoom.com"),
        "download_domains": ("zoom.us", "zoom.com"),
    },
    "discord": {
        "aliases": ("discord"),
        "domains": ("discord.com", "discordapp.com"),
        "download_domains": ("discord.com", "discordapp.com"),
    },
    "steam": {
        "aliases": ("steam", "steam客户端"),
        "domains": ("steampowered.com", "steamcommunity.com"),
        "download_domains": ("steampowered.com", "steamstatic.com"),
    },
    "epic": {
        "aliases": ("epic", "epic games"),
        "domains": ("epicgames.com", "unrealengine.com"),
        "download_domains": ("epicgames.com", "launcher-public-service-prod06.ol.epicgames.com"),
    },
    "nvidia": {
        "aliases": ("nvidia", "geforce", "显卡驱动"),
        "domains": ("nvidia.com",),
        "download_domains": ("nvidia.com", "nvidia.cn"),
    },
    "wsl": {
        "aliases": ("wsl", "windows subsystem for linux"),
        "domains": ("microsoft.com",),
        "download_domains": ("wslstorestorage.blob.core.windows.net", "microsoft.com"),
    },
    "netease_music": {
        "aliases": (
            "netease", "netease music", "cloudmusic", "163music",
            "网易云", "网易云音乐", "网易音乐",
        ),
        "domains": ("music.163.com", "163.com", "126.net"),
        "download_domains": ("music.163.com", "126.net", "d1.music.126.net"),
    },
    "kugou": {
        "aliases": ("kugou", "酷狗", "酷狗音乐", "kugou music"),
        "domains": ("kugou.com", "download.kugou.com"),
        "download_domains": ("download.kugou.com", "kugou.com"),
    },
}

# 高危关键词（URL / 域名）
_BLOCKLIST_PATTERNS = (
    r"crack", r"keygen", r"serial", r"warez", r"patch-only",
    r"破解", r"注册机", r"激活码", r"绿色版.*破解", r"盗版",
    r"\.exe\.exe", r"fake.*download",
)

_SUSPICIOUS_PATTERNS = (
    r"绿色(?:软件|下载|版)", r"软件园", r"下载站", r"装机版",
    r"portable.*crack", r"免安装.*破解",
    r"macwk", r"423down",  # 常见第三方下载站 — 非官方，标记为可疑而非直接拦截
)

# 明确拦截的第三方打包站域名后缀
_BLOCKED_DOMAIN_SUFFIXES = (
    "cracks.com", "keygen.net",
)


class TrustLevel(IntEnum):
    BLOCKED = 0
    SUSPICIOUS = 1
    UNVERIFIED = 2
    NEUTRAL = 3
    TRUSTED = 4
    OFFICIAL = 5


_TRUST_LABELS = {
    TrustLevel.BLOCKED: "已拦截",
    TrustLevel.SUSPICIOUS: "可疑来源",
    TrustLevel.UNVERIFIED: "未验证",
    TrustLevel.NEUTRAL: "HTTPS 已加密",
    TrustLevel.TRUSTED: "可信发布商",
    TrustLevel.OFFICIAL: "官方来源",
}


@dataclass
class TrustReport:
    url: str
    domain: str
    level: TrustLevel
    label: str
    reasons: list[str] = field(default_factory=list)
    tls_valid: bool = False
    tls_issuer: str = ""
    matched_software: str = ""
    expected_software: str = ""
    domain_mismatch: bool = False

    @property
    def is_download_allowed(self) -> bool:
        return self.level >= TrustLevel.NEUTRAL

    @property
    def needs_untrusted_confirm(self) -> bool:
        return self.level in {TrustLevel.UNVERIFIED, TrustLevel.SUSPICIOUS}

    @property
    def is_blocked(self) -> bool:
        return self.level == TrustLevel.BLOCKED


def _normalize_software_name(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip().lower())


def _host_domain(hostname: str) -> str:
    host = (hostname or "").strip().lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    return host


def _domain_matches_suffix(host: str, suffix: str) -> bool:
    suffix = suffix.lower().lstrip(".")
    return host == suffix or host.endswith("." + suffix)


def _domain_in_list(host: str, domains: tuple[str, ...] | list[str]) -> bool:
    return any(_domain_matches_suffix(host, item) for item in domains)


def resolve_software_key(expected: str) -> str:
    """将用户/模型提供的软件名解析为注册表 key。"""
    norm = _normalize_software_name(expected)
    if not norm:
        return ""
    for key, meta in _SOFTWARE_OFFICIAL.items():
        aliases = meta.get("aliases", ())
        if norm == key or norm in aliases:
            return key
        for alias in aliases:
            if alias in norm or norm in alias:
                return key
    return ""


def inspect_tls(hostname: str, *, use_cache: bool = True) -> dict[str, object]:
    host = _host_domain(hostname)
    if not host:
        return {"valid": False, "reason": "无效主机名"}

    now = time.time()
    if use_cache and host in _TLS_CACHE:
        cached_at, cached = _TLS_CACHE[host]
        if now - cached_at < _CACHE_TTL:
            return cached

    result: dict[str, object] = {"valid": False, "issuer": "", "reason": ""}
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, 443), timeout=8) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert() or {}
                issuer_parts = dict(x[0] for x in cert.get("issuer", ()))
                org = issuer_parts.get("organizationName") or issuer_parts.get("commonName") or ""
                sans = [entry[1] for entry in cert.get("subjectAltName", ()) if entry[0] == "DNS"]
                cn_parts = dict(x[0] for x in cert.get("subject", ()))
                cn = cn_parts.get("commonName", "")
                names = {cn, *sans}
                hostname_ok = any(
                    name == host or (name.startswith("*.") and host.endswith(name[1:]))
                    for name in names if name
                )
                result = {
                    "valid": bool(hostname_ok),
                    "issuer": str(org),
                    "reason": "" if hostname_ok else "证书域名与站点不匹配",
                }
    except (ssl.SSLError, TimeoutError, OSError) as exc:
        result = {"valid": False, "issuer": "", "reason": str(exc)}

    _TLS_CACHE[host] = (now, result)
    return result


def assess_download_trust(
    url: str,
    *,
    expected_software: str = "",
    use_cache: bool = True,
) -> TrustReport:
    """评估下载链接可信度。"""
    raw = (url or "").strip()
    cache_key = f"{raw}|{expected_software.lower()}"
    now = time.time()
    if use_cache and cache_key in _TRUST_CACHE:
        cached_at, cached = _TRUST_CACHE[cache_key]
        if now - cached_at < _CACHE_TTL:
            return cached

    parsed = urlparse(raw)
    host = _host_domain(parsed.hostname or "")
    reasons: list[str] = []
    level = TrustLevel.NEUTRAL
    matched = ""
    software_key = resolve_software_key(expected_software)
    lower_blob = f"{raw} {host}".lower()

    if not host:
        report = TrustReport(
            url=raw, domain="", level=TrustLevel.BLOCKED,
            label=_TRUST_LABELS[TrustLevel.BLOCKED], reasons=["URL 无效"],
        )
        _TRUST_CACHE[cache_key] = (now, report)
        return report

    for suffix in _BLOCKED_DOMAIN_SUFFIXES:
        if _domain_matches_suffix(host, suffix):
            reasons.append(f"域名在拦截列表: {suffix}")
            report = TrustReport(
                url=raw, domain=host, level=TrustLevel.BLOCKED,
                label=_TRUST_LABELS[TrustLevel.BLOCKED], reasons=reasons,
                expected_software=expected_software,
            )
            _TRUST_CACHE[cache_key] = (now, report)
            return report

    for pattern in _BLOCKLIST_PATTERNS:
        if re.search(pattern, lower_blob, re.I):
            reasons.append(f"命中高危特征: {pattern}")
            report = TrustReport(
                url=raw, domain=host, level=TrustLevel.BLOCKED,
                label=_TRUST_LABELS[TrustLevel.BLOCKED], reasons=reasons,
                expected_software=expected_software,
            )
            _TRUST_CACHE[cache_key] = (now, report)
            return report

    suspicious_hit = any(re.search(p, lower_blob, re.I) for p in _SUSPICIOUS_PATTERNS)
    if suspicious_hit:
        reasons.append("疑似第三方下载站或非官方打包页")
        level = TrustLevel.SUSPICIOUS

    tls_valid = False
    tls_issuer = ""
    domain_mismatch = False

    if parsed.scheme == "https":
        tls = inspect_tls(host, use_cache=use_cache)
        tls_valid = bool(tls.get("valid"))
        tls_issuer = str(tls.get("issuer") or "")
        if tls_valid:
            reasons.append(f"TLS 证书有效（签发: {tls_issuer or '未知 CA'}）")
            if level < TrustLevel.NEUTRAL:
                level = TrustLevel.NEUTRAL
        else:
            reason = str(tls.get("reason") or "TLS 校验失败")
            reasons.append(reason)
            level = TrustLevel.UNVERIFIED
    else:
        reasons.append("非 HTTPS 链接，无法验证站点身份")
        level = TrustLevel.UNVERIFIED

    if software_key:
        meta = _SOFTWARE_OFFICIAL[software_key]
        official_domains = tuple(meta.get("domains", ()))
        download_domains = tuple(meta.get("download_domains", official_domains))
        matched = software_key
        if _domain_in_list(host, download_domains):
            level = TrustLevel.OFFICIAL
            reasons.append(f"域名匹配 {software_key} 官方下载渠道")
        elif _domain_in_list(host, official_domains):
            level = TrustLevel.OFFICIAL
            reasons.append(f"域名匹配 {software_key} 官方网站")
        elif level >= TrustLevel.NEUTRAL:
            level = TrustLevel.UNVERIFIED
            domain_mismatch = True
            reasons.append(
                f"域名与 {software_key} 官方渠道不符（官方: {', '.join(download_domains[:3])}）"
            )

    if level <= TrustLevel.SUSPICIOUS and _domain_in_list(host, _TRUSTED_PUBLISHER_SUFFIXES):
        level = TrustLevel.TRUSTED
        reasons.append("属于已知软件发布商域名")
    elif level == TrustLevel.NEUTRAL and _domain_in_list(host, _TRUSTED_PUBLISHER_SUFFIXES):
        level = TrustLevel.TRUSTED
        reasons.append("属于已知软件发布商域名")

    if suspicious_hit and level >= TrustLevel.TRUSTED:
        level = TrustLevel.SUSPICIOUS
        reasons.append("虽为知名域名，但页面路径疑似第三方转载")

    report = TrustReport(
        url=raw,
        domain=host,
        level=level,
        label=_TRUST_LABELS.get(level, "未知"),
        reasons=reasons,
        tls_valid=tls_valid,
        tls_issuer=tls_issuer,
        matched_software=matched,
        expected_software=expected_software,
        domain_mismatch=domain_mismatch,
    )
    _TRUST_CACHE[cache_key] = (now, report)
    return report


def format_trust_report(report: TrustReport) -> str:
    lines = [
        f"来源评级: {report.label} ({report.level.name})",
        f"域名: {report.domain}",
        f"链接: {report.url}",
    ]
    if report.expected_software:
        lines.append(f"期望软件: {report.expected_software}")
    if report.matched_software:
        lines.append(f"匹配软件: {report.matched_software}")
    if report.tls_valid:
        lines.append(f"TLS: 有效（{report.tls_issuer or '未知 CA'}）")
    elif report.url.startswith("https://"):
        lines.append("TLS: 无效或未通过主机名校验")
    else:
        lines.append("TLS: 不适用（HTTP）")

    if report.reasons:
        lines.append("说明:")
        for item in report.reasons:
            lines.append(f"- {item}")

    if report.is_blocked:
        lines.append("\n结论: 不建议从此来源下载。")
    elif report.needs_untrusted_confirm:
        lines.append("\n结论: 非官方/未充分验证来源，需用户明确确认后再下载。")
    elif report.level == TrustLevel.OFFICIAL:
        lines.append("\n结论: 推荐从此官方来源下载。")
    else:
        lines.append("\n结论: 可下载，但请再次核对软件名称与文件后缀。")
    return "\n".join(lines)


def pick_best_download_link(
    links: list[dict[str, str]],
    *,
    expected_software: str = "",
) -> list[dict[str, object]]:
    """为下载链接打分并排序，返回带 trust 字段的列表。"""
    scored: list[dict[str, object]] = []
    for item in links:
        url = str(item.get("url", ""))
        report = assess_download_trust(url, expected_software=expected_software)
        scored.append({
            **item,
            "trust_level": int(report.level),
            "trust_label": report.label,
            "trust_reasons": report.reasons[:3],
            "recommended": report.level >= TrustLevel.TRUSTED,
        })
    scored.sort(key=lambda x: int(x.get("trust_level", 0)), reverse=True)
    return scored
