from __future__ import annotations

from friday.weixin.setup import migrate_legacy_openclaw_state


def test_migrate_legacy_openclaw_state(monkeypatch, tmp_path):
    legacy = tmp_path / ".openclaw"
    target = tmp_path / "target"
    legacy.mkdir()
    target.mkdir()
    (legacy / "gateway.cmd").write_text("@echo off", encoding="utf-8")
    ext = legacy / "extensions" / "openclaw-weixin"
    ext.mkdir(parents=True)
    (ext / "index.js").write_text("// wx", encoding="utf-8")

    monkeypatch.setattr("friday.weixin.setup.Path.home", lambda: tmp_path)
    monkeypatch.setattr("friday.weixin.setup.openclaw_state_dir", lambda: target)

    ok, msg = migrate_legacy_openclaw_state()
    assert ok
    assert (target / "gateway.cmd").is_file()
    assert (target / "extensions" / "openclaw-weixin" / "index.js").is_file()
    assert "迁移" in msg
