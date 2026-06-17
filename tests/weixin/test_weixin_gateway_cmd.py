from __future__ import annotations

from friday.weixin.config import openclaw_env
from friday.weixin.gateway import (
    _gateway_cmd_is_current,
    _parse_gateway_cmd,
    ensure_gateway_cmd,
    write_gateway_cmd,
)


def test_openclaw_env_sets_state_dir(monkeypatch, tmp_path):
    monkeypatch.setattr("friday.weixin.config.openclaw_state_dir", lambda: tmp_path)
    env = openclaw_env()
    assert env["OPENCLAW_STATE_DIR"] == str(tmp_path)


def test_write_gateway_cmd(monkeypatch, tmp_path):
    monkeypatch.setattr("friday.weixin.gateway.openclaw_state_dir", lambda: tmp_path)
    monkeypatch.setattr("friday.weixin.gateway._resolve_node_exe", lambda: "C:\\node\\node.exe")
    fake_script = tmp_path / "openclaw" / "dist" / "index.js"
    fake_script.parent.mkdir(parents=True)
    fake_script.write_text("// stub", encoding="utf-8")
    monkeypatch.setattr("friday.weixin.gateway._resolve_openclaw_script", lambda: fake_script)

    path = write_gateway_cmd(port=18789)
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "OPENCLAW_STATE_DIR" in text
    assert "OPENCLAW_GATEWAY_PORT=18789" in text
    assert "gateway --port 18789" in text


def test_gateway_cmd_is_current_rejects_friday_test_path(monkeypatch, tmp_path):
    monkeypatch.setattr("friday.weixin.gateway.openclaw_state_dir", lambda: tmp_path)
    stale = tmp_path / "gateway.cmd"
    stale.write_text(
        "\r\n".join(
            [
                "@echo off",
                r'set "OPENCLAW_STATE_DIR=C:\Users\me\AppData\Roaming\Friday-Test\openclaw"',
                "set OPENCLAW_GATEWAY_PORT=18790",
                '"C:\\node\\node.exe" "C:\\openclaw\\dist\\index.js" gateway --port 18790',
            ]
        )
        + "\r\n",
        encoding="utf-8",
    )
    assert not _gateway_cmd_is_current(stale, 18789)


def test_ensure_gateway_cmd_idempotent(monkeypatch, tmp_path):
    monkeypatch.setattr("friday.weixin.gateway.openclaw_state_dir", lambda: tmp_path)
    monkeypatch.setattr("friday.weixin.gateway._resolve_node_exe", lambda: "C:\\node\\node.exe")
    fake_script = tmp_path / "index.js"
    fake_script.write_text("// stub", encoding="utf-8")
    monkeypatch.setattr("friday.weixin.gateway._resolve_openclaw_script", lambda: fake_script)

    ok1, _ = ensure_gateway_cmd()
    ok2, _ = ensure_gateway_cmd()
    assert ok1 and ok2
    assert (tmp_path / "gateway.cmd").is_file()


def test_parse_gateway_cmd_quoted_paths(tmp_path):
    cmd = tmp_path / "gateway.cmd"
    cmd.write_text(
        '\r\n'.join(
            [
                "@echo off",
                f'set "OPENCLAW_STATE_DIR={tmp_path}"',
                'set "OPENCLAW_GATEWAY_PORT=18790"',
                '"C:\\Program Files\\nodejs\\node.exe" '
                '"C:\\Users\\me\\AppData\\Roaming\\npm\\node_modules\\openclaw\\dist\\index.js" '
                "gateway --port 18790",
            ]
        )
        + "\r\n",
        encoding="utf-8",
    )
    args, env = _parse_gateway_cmd(cmd)
    assert args[0].endswith("node.exe")
    assert args[1].endswith("index.js")
    assert args[2:] == ["gateway", "--port", "18790"]
    assert env["OPENCLAW_GATEWAY_PORT"] == "18790"
