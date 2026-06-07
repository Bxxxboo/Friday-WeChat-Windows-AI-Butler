"""原子文件写入 —— 防止崩溃时 JSON 半写损坏。"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

from friday.logging_config import get_logger

_log = get_logger("io_utils")


def atomic_write_text(path: Path, content: str, *, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        bak = path.with_suffix(f"{path.suffix}.bak")
        try:
            shutil.copy2(path, bak)
        except OSError:
            pass
    tmp = path.with_suffix(f"{path.suffix}.tmp")
    try:
        with open(tmp, "w", encoding=encoding, newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except Exception:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
        raise


def atomic_write_json(path: Path, data: Any, *, indent: int = 2) -> None:
    content = json.dumps(data, ensure_ascii=False, indent=indent)
    atomic_write_text(path, content)


def load_json(path: Path, default: Any = None) -> Any:
    """读取 JSON；主文件损坏时尝试 .bak 回退。"""
    if not path.exists():
        return default

    for candidate in (path, path.with_suffix(f"{path.suffix}.bak")):
        if not candidate.exists():
            continue
        try:
            return json.loads(candidate.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            _log.warning("读取 JSON 失败 | path=%s error=%s", candidate, exc)
    return default
