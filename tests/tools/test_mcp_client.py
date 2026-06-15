from __future__ import annotations

from pathlib import Path

from friday.mcp_client import (
    default_mcp_config,
    load_mcp_config,
    resolve_mcp_command,
    resolve_npx_command,
    save_mcp_config,
)


def test_mcp_config_roundtrip(tmp_path, monkeypatch):
    from friday import mcp_client as mod

    monkeypatch.setattr(mod, "mcp_config_path", lambda: tmp_path / "mcp_servers.json")
    cfg = default_mcp_config()
    cfg["servers"] = [{"id": "s1", "name": "Test", "command": "echo", "args": [], "enabled": True}]
    save_mcp_config(cfg)
    loaded = load_mcp_config()
    assert len(loaded["servers"]) == 1
    assert loaded["servers"][0]["name"] == "Test"


def test_resolve_mcp_command_npx_from_node_home(tmp_path, monkeypatch):
    from friday.weixin import node_runtime as nr

    node_home = tmp_path / "node"
    node_home.mkdir()
    npx = node_home / "npx.cmd"
    npx.write_text("@echo off", encoding="utf-8")
    monkeypatch.setattr(nr, "NODE_HOME", node_home)
    monkeypatch.setattr("friday.mcp_client.shutil.which", lambda name, path=None: None)
    assert Path(resolve_npx_command() or "").resolve() == npx.resolve()
    assert Path(resolve_mcp_command("npx")).resolve() == npx.resolve()


def test_resolve_mcp_command_absolute_path(tmp_path):
    exe = tmp_path / "tool.cmd"
    exe.write_text("@echo off", encoding="utf-8")
    assert Path(resolve_mcp_command(str(exe))).resolve() == exe.resolve()
