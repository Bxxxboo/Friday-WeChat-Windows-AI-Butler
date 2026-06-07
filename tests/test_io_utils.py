from __future__ import annotations

import json
from pathlib import Path

from friday.io_utils import atomic_write_json, load_json


def test_atomic_write_json_roundtrip(tmp_path: Path):
    path = tmp_path / "data.json"
    atomic_write_json(path, {"a": 1, "b": "测试"})
    assert load_json(path) == {"a": 1, "b": "测试"}
    assert not path.with_suffix(".json.tmp").exists()


def test_atomic_write_creates_backup(tmp_path: Path):
    path = tmp_path / "data.json"
    atomic_write_json(path, {"v": 1})
    atomic_write_json(path, {"v": 2})
    assert load_json(path) == {"v": 2}
    assert path.with_suffix(".json.bak").exists()
    assert load_json(path.with_suffix(".json.bak")) == {"v": 1}


def test_load_json_falls_back_to_bak(tmp_path: Path):
    path = tmp_path / "data.json"
    path.write_text("{broken", encoding="utf-8")
    bak = path.with_suffix(".json.bak")
    bak.write_text(json.dumps({"ok": True}), encoding="utf-8")
    assert load_json(path) == {"ok": True}
