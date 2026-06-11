from __future__ import annotations

from pathlib import Path

from friday.update_rollback import (
    BACKUP_DIR_NAME,
    backup_install_dir,
    clear_pending_update,
    guard_startup_after_update,
    has_pending_update,
    install_backup_dir,
    mark_pending_update,
    restore_install_dir,
)


def test_install_backup_dir_sibling(tmp_path: Path):
    install = tmp_path / "Friday"
    install.mkdir()
    assert install_backup_dir(install) == tmp_path / BACKUP_DIR_NAME


def test_backup_and_restore_roundtrip(tmp_path: Path):
    install = tmp_path / "Friday"
    install.mkdir()
    (install / "Friday.exe").write_text("app", encoding="utf-8")
    (install / "note.txt").write_text("keep", encoding="utf-8")

    backup_install_dir(install)
    backup = install_backup_dir(install)
    assert backup.is_dir()
    assert (backup / "Friday.exe").read_text(encoding="utf-8") == "app"

    (install / "Friday.exe").write_text("broken", encoding="utf-8")
    ok, msg = restore_install_dir(install)
    assert ok is True
    assert (install / "Friday.exe").read_text(encoding="utf-8") == "app"
    assert msg


def test_mark_pending_and_clear(tmp_appdata, tmp_path: Path, monkeypatch):
    install = tmp_path / "Friday"
    install.mkdir()
    mark_pending_update(version="9.9.9", install_dir=install)
    assert has_pending_update() is True
    clear_pending_update()
    assert has_pending_update() is False


def test_guard_startup_noop_without_pending(monkeypatch):
    monkeypatch.setattr("friday.update_rollback.is_frozen", lambda: True)
    clear_pending_update()
    assert guard_startup_after_update() is True
