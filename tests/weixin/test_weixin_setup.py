from friday.safety import describe_approval_plain
from friday.weixin.openclaw_cli import openclaw_shell_invocation
from friday.weixin.setup import (
    WEIXIN_PLUGIN_ID,
    _plugin_installed,
    _weixin_channel_available,
    collect_setup_steps,
    configure_openclaw_plugins,
    install_openclaw_cli,
    install_weixin_plugin,
    launch_weixin_login_terminal,
    migrate_legacy_openclaw_state,
)


def test_describe_powershell_desktop():
    text = describe_approval_plain(
        "run_powershell",
        {"command": 'Get-ChildItem "C:/Users/test/Desktop" -Name'},
    )
    assert "桌面" in text


def test_describe_powershell_wscript_shortcuts():
    cmd = (
        '$shell = New-Object -ComObject WScript.Shell; '
        'Get-ChildItem "C:/Users/test/Desktop" | ForEach-Object { $shell.CreateShortcut($_.FullName) }'
    )
    text = describe_approval_plain("run_powershell", {"command": cmd})
    assert "桌面" in text or "快捷方式" in text


def test_describe_powershell_includes_command_detail():
    from friday.safety import describe_approval_detail

    cmd = "Get-Service | Where-Object { $_.Status -eq 'Running' }"
    detail = describe_approval_detail("run_powershell", {"command": cmd})
    assert "命令摘要" in detail
    assert "Get-Service" in detail


def test_describe_powershell_no_vague_fallback():
    text = describe_approval_plain(
        "run_powershell",
        {"command": "Get-Service | Select-Object -First 5 Name, Status"},
    )
    assert "系统命令，可能会访问" not in text
    assert "Get-Service" in text or "查看" in text or "程序" in text


def test_collect_setup_steps_shape():
    steps = collect_setup_steps(port=8765, api_token="test")
    assert len(steps) >= 7
    assert steps[0].id == "openclaw_cli"


def test_plugin_installed_detects_dist_index_js(tmp_path, monkeypatch):
    ext = tmp_path / "extensions" / "openclaw-weixin"
    (ext / "dist").mkdir(parents=True)
    (ext / "dist" / "index.js").write_text("// ok", encoding="utf-8")
    (ext / "openclaw.plugin.json").write_text('{"id":"openclaw-weixin"}', encoding="utf-8")
    monkeypatch.setattr("friday.weixin.setup.openclaw_state_dir", lambda: tmp_path)
    from friday.weixin.setup import _plugin_installed

    assert _plugin_installed("openclaw-weixin")


def test_weixin_channel_requires_installed_plugin_not_config_only(tmp_path, monkeypatch):
    cfg = tmp_path / "openclaw.json"
    cfg.write_text(
        '{"channels":{"openclaw-weixin":{"enabled":true}},"plugins":{"allow":["openclaw-weixin"]}}',
        encoding="utf-8",
    )
    ext_root = tmp_path / "extensions" / WEIXIN_PLUGIN_ID
    monkeypatch.setattr("friday.weixin.setup.openclaw_state_dir", lambda: tmp_path)
    monkeypatch.setattr("friday.weixin.setup._openclaw_config_path", lambda: cfg)
    monkeypatch.setattr("friday.weixin.setup._plugin_extension_dir", lambda _pid: ext_root)

    assert not _plugin_installed(WEIXIN_PLUGIN_ID)
    assert not _weixin_channel_available()

    calls: list[str] = []

    def fake_npm_install() -> tuple[bool, str]:
        calls.append("npm")
        ext_root.mkdir(parents=True)
        (ext_root / "index.js").write_text("// test", encoding="utf-8")
        (ext_root / "openclaw.plugin.json").write_text("{}", encoding="utf-8")
        return True, "ok"

    monkeypatch.setattr("friday.weixin.setup._install_weixin_via_npm", fake_npm_install)
    monkeypatch.setattr("friday.weixin.setup._run_openclaw_doctor_repair", lambda: None)

    ok, _ = install_weixin_plugin()
    assert ok
    assert calls == ["npm"]
    assert _weixin_channel_available()


def test_configure_openclaw_plugins_idempotent(tmp_path, monkeypatch):
    cfg = tmp_path / "openclaw.json"
    cfg.write_text("{}", encoding="utf-8")
    monkeypatch.setattr("friday.weixin.setup._openclaw_config_path", lambda: cfg)
    ok, _ = configure_openclaw_plugins()
    assert ok
    data = __import__("json").loads(cfg.read_text(encoding="utf-8"))
    assert "openclaw-weixin" in data["plugins"]["allow"]
    assert data["gateway"]["mode"] == "local"
    assert data["gateway"]["auth"]["mode"] == "token"
    assert data["gateway"]["auth"]["token"]


def test_install_openclaw_cli_no_node(monkeypatch):
    monkeypatch.setattr("friday.weixin.setup._openclaw_cli_available", lambda: False)
    monkeypatch.setattr(
        "friday.weixin.setup.ensure_node_npm",
        lambda: (False, "无法自动安装 Node.js"),
    )
    ok, msg = install_openclaw_cli()
    assert not ok
    assert "Node" in msg


def test_openclaw_shell_invocation_sets_state_dir(monkeypatch, tmp_path):
    cmd = tmp_path / "openclaw.cmd"
    cmd.write_text("@echo off", encoding="utf-8")
    state = tmp_path / "state"
    monkeypatch.setattr(
        "friday.weixin.openclaw_cli.resolve_openclaw_command",
        lambda: ["cmd", "/c", str(cmd)],
    )
    monkeypatch.setattr("friday.weixin.config.openclaw_state_dir", lambda: state)
    monkeypatch.setattr("friday.edition.openclaw_gateway_port", lambda: 18790)

    line = openclaw_shell_invocation(["channels", "login", "--channel", "openclaw-weixin"])
    assert f'OPENCLAW_STATE_DIR={state}' in line
    assert "OPENCLAW_GATEWAY_PORT=18790" in line
    assert "channels login" in line


def test_openclaw_shell_invocation_quotes_cmd_path(monkeypatch, tmp_path):
    cmd = tmp_path / "open claw.cmd"
    cmd.write_text("@echo off", encoding="utf-8")
    monkeypatch.setattr(
        "friday.weixin.openclaw_cli.resolve_openclaw_command",
        lambda: ["cmd", "/c", str(cmd)],
    )
    line = openclaw_shell_invocation(["channels", "login", "--channel", "openclaw-weixin"])
    assert f'"{cmd}"' in line
    assert "channels login" in line


def test_launch_weixin_login_requires_cli(monkeypatch):
    monkeypatch.setattr("friday.weixin.setup._openclaw_cli_available", lambda: False)
    ok, msg = launch_weixin_login_terminal()
    assert not ok
    assert "openclaw" in msg.lower()


def test_launch_weixin_login_opens_terminal(monkeypatch):
    monkeypatch.setattr("friday.weixin.setup._openclaw_cli_available", lambda: True)
    monkeypatch.setattr(
        "friday.weixin.setup.openclaw_shell_invocation",
        lambda _args: "openclaw-test channels login",
    )
    calls: list[list[str]] = []

    def fake_popen(args, **kwargs):
        calls.append(list(args))
        return object()

    monkeypatch.setattr("friday.weixin.setup.subprocess.Popen", fake_popen)
    ok, msg = launch_weixin_login_terminal()
    assert ok
    assert "扫码" in msg
    assert calls and "openclaw-test channels login" in calls[0]
