"""联网限制与下载探测类型。"""

from __future__ import annotations

from dataclasses import dataclass

from friday.config import DOWNLOAD_LARGE_MAX_BYTES, DOWNLOAD_MAX_BYTES


@dataclass
class DownloadProbe:
    url: str
    final_url: str = ""
    content_length: int | None = None
    error: str = ""


def format_bytes(num: int) -> str:
    if num >= 1024 ** 3:
        return f"{num / (1024 ** 3):.2f} GB"
    if num >= 1024 ** 2:
        return f"{num / (1024 ** 2):.1f} MB"
    if num >= 1024:
        return f"{num / 1024:.1f} KB"
    return f"{num} B"


def download_byte_limit(*, allow_large: bool) -> int:
    return DOWNLOAD_LARGE_MAX_BYTES if allow_large else DOWNLOAD_MAX_BYTES
