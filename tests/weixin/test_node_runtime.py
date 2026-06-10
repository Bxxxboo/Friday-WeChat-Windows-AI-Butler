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


def test_run_npm_stops_on_non_network_error(monkeypatch):
    calls: list[str] = []

    def fake_once(npm, args, *, timeout, registry, prefix=None, cwd=None):
        calls.append(registry)
        return subprocess.CompletedProcess(args, 1, "", "npm error 404 Not Found")

    monkeypatch.setattr(nr, "npm_command", lambda: "npm.cmd")
    monkeypatch.setattr(nr, "_run_npm_once", fake_once)

    nr.run_npm(["install", "openclaw@latest"], prefix=nr.npm_global_prefix(), global_install=True)
    assert calls == [nr.NPM_REGISTRY_DEFAULT]
