from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest


def test_autostart_status_non_windows():
    with patch("friday.autostart.sys.platform", "linux"):
        from friday.autostart import autostart_status

        status = autostart_status()
        assert status["available"] is False
        assert status["enabled"] is False


def test_resolve_launch_spec_dev_layout():
    with patch("friday.autostart.sys.platform", "win32"):
        with patch("friday.autostart.is_frozen", return_value=False):
            with patch("friday.autostart.dist_packaged_exe", return_value=None):
                from friday.autostart import resolve_launch_spec

                exe, args, mode, err = resolve_launch_spec()
                if err:
                    pytest.skip(err)
                assert mode == "dev"
                assert exe.endswith("pythonw.exe")
                assert args.endswith('run.py"')


def test_resolve_launch_spec_prefers_dist_packaged_exe(tmp_path: Path):
    packaged = tmp_path / "Friday.exe"
    packaged.write_text("", encoding="utf-8")
    with patch("friday.autostart.sys.platform", "win32"):
        with patch("friday.autostart.is_frozen", return_value=False):
            with patch("friday.autostart.dist_packaged_exe", return_value=packaged):
                from friday.autostart import resolve_launch_spec

                exe, args, mode, err = resolve_launch_spec()
                assert err == ""
                assert mode == "exe"
                assert exe == str(packaged.resolve())
                assert args == ""


def test_resolve_launch_spec_frozen_rejects_pythonw(tmp_path: Path, monkeypatch):
    fake_pythonw = tmp_path / "pythonw.exe"
    fake_pythonw.write_text("", encoding="utf-8")
    monkeypatch.setattr("friday.autostart.sys.executable", str(fake_pythonw))
    with patch("friday.autostart.sys.platform", "win32"):
        with patch("friday.autostart.is_frozen", return_value=True):
            with patch("friday.autostart.resolve_packaged_exe_in_dir", return_value=None):
                from friday.autostart import resolve_launch_spec

                _exe, _args, _mode, err = resolve_launch_spec()
                assert "Friday.exe" in err


def test_autostart_stale_when_recorded_points_to_dev():
    from friday.autostart import _launch_is_stale

    recorded = r'"C:\dev\.python-env\Scripts\pythonw.exe" "C:\Friday\run.py"'
    current = r'"D:\Friday\Friday.exe"'
    assert _launch_is_stale(recorded, current) is True


def test_set_autostart_rejects_pythonw_executable(tmp_path: Path):
    pythonw = tmp_path / "pythonw.exe"
    pythonw.write_text("", encoding="utf-8")
    with patch("friday.autostart.sys.platform", "win32"):
        from friday.autostart import set_autostart_enabled

        result = set_autostart_enabled(True, executable=str(pythonw))
        assert result["ok"] is False
        assert "pythonw" in result["message"].lower() or "Friday.exe" in result["message"]
