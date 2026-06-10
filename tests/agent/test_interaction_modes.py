from __future__ import annotations

from friday.interaction_modes import normalize_mode
from friday.safety import evaluate_tool
from friday.storage import UserSettings


def test_normalize_mode_defaults():
    assert normalize_mode(None) == "agent"
    assert normalize_mode("YOLO") == "yolo"
    assert normalize_mode("weird") == "agent"


def test_ask_mode_blocks_write():
    settings = UserSettings(interaction_mode="ask")
    decision = evaluate_tool(settings, "write_text_file", {"path": "a.txt", "content": "x"})
    assert decision.allowed is False
    assert "Ask" in decision.reason


def test_ask_mode_allows_read():
    settings = UserSettings(interaction_mode="ask")
    decision = evaluate_tool(settings, "get_disk_usage", {})
    assert decision.allowed is True
    assert decision.needs_approval is False


def test_yolo_without_unlock_still_needs_approval(workspace):
    settings = UserSettings(
        interaction_mode="yolo",
        workspace=str(workspace).replace("\\", "/"),
        require_approval_writes=True,
    )
    inside = str((workspace / "note.txt").resolve()).replace("\\", "/")
    decision = evaluate_tool(
        settings,
        "write_text_file",
        {"path": inside, "content": "hi"},
        yolo_unlocked=False,
    )
    assert decision.allowed is True
    assert decision.needs_approval is True


def test_yolo_unlocked_auto_approves_workspace_write(workspace):
    settings = UserSettings(
        interaction_mode="yolo",
        workspace=str(workspace).replace("\\", "/"),
        require_approval_writes=True,
    )
    inside = str((workspace / "note.txt").resolve()).replace("\\", "/")
    decision = evaluate_tool(
        settings,
        "write_text_file",
        {"path": inside, "content": "hi"},
        yolo_unlocked=True,
    )
    assert decision.allowed is True
    assert decision.needs_approval is False


def test_yolo_unlocked_still_requires_powershell():
    settings = UserSettings(
        interaction_mode="yolo",
        require_approval_exec=True,
        allow_powershell=True,
    )
    decision = evaluate_tool(
        settings,
        "run_powershell",
        {"command": "Get-Date"},
        yolo_unlocked=True,
    )
    assert decision.allowed is True
    assert decision.needs_approval is True
    assert decision.always_require_approval is True


def test_yolo_unlocked_still_requires_python(workspace):
    settings = UserSettings(
        interaction_mode="yolo",
        workspace=str(workspace).replace("\\", "/"),
        require_approval_exec=True,
        allow_python=True,
    )
    decision = evaluate_tool(
        settings,
        "run_python",
        {"code": "print(1)"},
        yolo_unlocked=True,
    )
    assert decision.allowed is True
    assert decision.needs_approval is True
    assert decision.always_require_approval is True


def test_ask_mode_blocks_powershell():
    settings = UserSettings(interaction_mode="ask")
    decision = evaluate_tool(settings, "run_powershell", {"command": "Get-Date"})
    assert decision.allowed is False
    assert "Ask" in decision.reason


def test_yolo_blocks_outside_workspace(workspace):
    settings = UserSettings(
        interaction_mode="yolo",
        workspace=str(workspace).replace("\\", "/"),
    )
    decision = evaluate_tool(
        settings,
        "write_text_file",
        {"path": "C:/outside.txt", "content": "x"},
        yolo_unlocked=True,
    )
    assert decision.allowed is False
