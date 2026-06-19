"""boot_timing 分段记录。"""

from __future__ import annotations

from friday.boot_timing import log_summary, mark, reset, summary


def test_boot_timing_summary_ms():
    reset()
    mark("a")
    mark("b")
    rows = summary()
    assert len(rows) == 2
    assert rows[0]["phase"] == "a"
    assert rows[1]["phase"] == "b"
    assert rows[0]["ms_total"] >= 0
    assert rows[1]["ms_total"] >= rows[0]["ms_total"]
    log_summary(trigger="test")
