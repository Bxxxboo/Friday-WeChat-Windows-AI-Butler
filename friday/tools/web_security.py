"""联网安全 —— SSRF 防护与 URL 校验。"""

from __future__ import annotations

import ipaddress
import re
import socket
from urllib.parse import urlparse, urljoin, urlunparse

_ALLOWED_SCHEMES = {"http", "https"}
_BLOCKED_HOSTS = {
    "localhost",
    "localhost.localdomain",
    "metadata.google.internal",
    "metadata.google",
}
_HOST_RE = re.compile(r"^[a-zA-Z0-9.-]+$")


def _is_blocked_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return True
    return bool(
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


def _resolve_public_ips(hostname: str) -> tuple[list[str], str | None]:
    if not _HOST_RE.match(hostname):
        return [], "主机名格式无效"
    try:
        infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        return [], f"无法解析域名: {exc}"

    ips: list[str] = []
    for info in infos:
        ip = info[4][0]
        if _is_blocked_ip(ip):
            return [], f"目标地址不可访问（内网/保留地址）: {ip}"
        if ip not in ips:
            ips.append(ip)
    if not ips:
        return [], "无法解析域名"
    return ips, None


def validate_public_url(url: str) -> tuple[bool, str]:
    """校验 URL 是否允许访问（仅 http/https，禁止内网 SSRF）。"""
    raw = (url or "").strip()
    if not raw:
        return False, "URL 不能为空"

    parsed = urlparse(raw)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        return False, "仅支持 http:// 或 https:// 链接"

    hostname = (parsed.hostname or "").strip().lower()
    if not hostname:
        return False, "URL 缺少主机名"
    if hostname in _BLOCKED_HOSTS or hostname.endswith(".local"):
        return False, "不允许访问本地或内网地址"

    if hostname.replace(".", "").isdigit():
        if _is_blocked_ip(hostname):
            return False, "不允许访问内网或保留 IP"
        return True, ""

    _, err = _resolve_public_ips(hostname)
    if err:
        return False, err
    return True, ""


def normalize_url(base: str, link: str) -> str | None:
    """将相对链接转为绝对 URL，非法则返回 None。"""
    joined = urljoin(base, (link or "").strip())
    parsed = urlparse(joined)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        return None
    # 去掉 fragment，保留 query
    cleaned = parsed._replace(fragment="")
    return urlunparse(cleaned)
