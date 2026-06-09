from __future__ import annotations

from friday.tools.registry import get_tool_definitions_for_messages, is_download_task_context


def test_download_intent_detected():
    assert is_download_task_context("帮我把酷狗音乐下载到E盘")
    assert is_download_task_context("download chrome installer")


def test_download_context_hides_powershell():
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "下载酷狗音乐到 E:/setup.exe"},
    ]
    names = {(d.get("function") or {}).get("name") for d in get_tool_definitions_for_messages(messages)}
    assert "run_powershell" not in names
    assert "open_url" not in names
    assert "download_software" in names


def test_normal_context_keeps_powershell():
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "列出桌面文件"},
    ]
    names = {(d.get("function") or {}).get("name") for d in get_tool_definitions_for_messages(messages)}
    assert "run_powershell" in names
