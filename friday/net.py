"""轻量网络工具（避免从 server 模块导入）。"""

from __future__ import annotations

import socket


def find_free_port(start: int = 8765) -> int:
    for port in range(start, start + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return start
