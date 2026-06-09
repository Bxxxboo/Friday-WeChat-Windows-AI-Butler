from __future__ import annotations

from friday.logging_config import log_file_path, read_recent_log_lines


def test_read_recent_log_lines_empty(tmp_appdata):
    assert read_recent_log_lines() == []
    assert log_file_path().parent == tmp_appdata
