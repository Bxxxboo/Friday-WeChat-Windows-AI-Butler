from __future__ import annotations

from friday.tools.shell import _check_dangerous, run_powershell


def test_check_dangerous_format_disk():
    assert _check_dangerous("format C:") == "格式化磁盘"


def test_check_dangerous_shutdown():
    assert _check_dangerous("Stop-Computer -Force") == "关机/重启"


def test_check_dangerous_safe_command():
    assert _check_dangerous("Get-ChildItem $env:USERPROFILE") is None


def test_run_powershell_blocks_dangerous():
    result = run_powershell("format D:")
    assert "拒绝" in result or "⛔" in result
