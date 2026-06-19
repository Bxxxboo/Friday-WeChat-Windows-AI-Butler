from __future__ import annotations

from pathlib import Path


def test_friday_spec_includes_weixin_send_tool():
    """PyInstaller 须显式打包 weixin_send，否则启动时 eager import 报 ModuleNotFoundError。"""
    text = Path("friday.spec").read_text(encoding="utf-8")
    assert "friday.tools.weixin_send" in text
    assert "friday.weixin.ui_send" in text


def test_friday_spec_includes_full_ppt_master_extension():
    """安装包须含完整 ppt-master skill，不可仅 manifest（P0-1 离线可用）。"""
    text = Path("friday.spec").read_text(encoding="utf-8")
    assert 'rel.startswith("ppt-master/")' not in text
    assert "skill 首次启动下载" not in text
