from __future__ import annotations

import subprocess

from friday.weixin import node_runtime as nr


def test_node_env_defaults_to_china_registry():
    env = nr.node_env()
    assert env["NPM_CONFIG_REGISTRY"] == nr.NPM_REGISTRY_DEFAULT
    assert "npmmirror.com" in env["NPM_CONFIG_REGISTRY"]


def test_run_npm_retries_on_network_error(monkeypatch):
    calls: list[str] = []

    def fake_once(npm, args, *, timeout, registry, prefix=None, cwd=None):
        calls.append(registry)
        return subprocess.CompletedProcess(args, 1, "", "npm error network timeout")

    monkeypatch.setattr(nr, "npm_command", lambda: "npm.cmd")
    monkeypatch.setattr(nr, "_run_npm_once", fake_once)

    proc = nr.run_npm(["install", "openclaw@latest"], prefix=nr.npm_global_prefix(), global_install=True)
    assert proc.returncode != 0
    assert calls[0] == nr.NPM_REGISTRY_DEFAULT
    assert len(calls) == len(nr.NPM_REGISTRIES)


def test_node_meets_openclaw_minimum():
    assert nr.OPENCLAW_MIN_NODE == (22, 19, 0)
    assert nr.NODE_VERSION == "22.19.0"


def test_resolve_node_exe_prefers_openclaw_compatible(monkeypatch, tmp_path):
    portable = nr.NODE_HOME
    monkeypatch.setattr(nr, "NODE_HOME", tmp_path / "node-v22.19.0-win-x64")
    portable = nr.NODE_HOME
    portable.mkdir(parents=True)
    (portable / "node.exe").write_text("", encoding="utf-8")

    def fake_semver(exe: str):
        if "22.19" in exe.replace("\\", "/"):
            return (22, 19, 0)
        return (22, 14, 0)

    monkeypatch.setattr(nr, "node_semver", fake_semver)
    monkeypatch.setattr(nr.shutil, "which", lambda _name: "C:/Program Files/nodejs/node.exe")

    resolved = nr.resolve_node_exe()
    assert resolved is not None
    assert "22.19" in resolved.replace("\\", "/")


def test_run_npm_stops_on_non_network_error(monkeypatch):
    calls: list[str] = []

    def fake_once(npm, args, *, timeout, registry, prefix=None, cwd=None):
        calls.append(registry)
        return subprocess.CompletedProcess(args, 1, "", "npm error 404 Not Found")

    monkeypatch.setattr(nr, "npm_command", lambda: "npm.cmd")
    monkeypatch.setattr(nr, "_run_npm_once", fake_once)

    nr.run_npm(["install", "openclaw@latest"], prefix=nr.npm_global_prefix(), global_install=True)
    assert calls == [nr.NPM_REGISTRY_DEFAULT]
