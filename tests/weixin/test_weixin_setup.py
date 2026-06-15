from friday.safety import describe_approval_plain
from friday.weixin.openclaw_cli import openclaw_shell_invocation
from friday.weixin.setup import (
    WEIXIN_PLUGIN_ID,
    _plugin_installed,
    _should_replace_weixin_display_name,
    _weixin_channel_available,
    collect_setup_steps,
    configure_openclaw_plugins,
    ensure_openclaw_gateway_config,
    ensure_weixin_branding,
    install_openclaw_cli,
    install_weixin_plugin,
    launch_weixin_login_terminal,
    migrate_legacy_openclaw_state,
)


def test_describe_python_exchange_rate_query():
    from friday.safety import describe_approval_detail, describe_approval_plain

    code = (
        'import requests\n'
        'url = "https://open.er-api.com/v6/latest/USD"\n'
        'response = requests.get(url, timeout=10)\n'
        'data = response.json()\n'
    )
    plain = describe_approval_plain("run_python", {"code": code})
    assert "下载" not in plain
    assert "USD" in plain or "汇率" in plain
    detail = describe_approval_detail("run_python", {"code": code})
    assert "目标位置" not in detail
    assert "「USD」" not in detail
    assert "不会修改" in detail or "只读" in plain


def test_format_approval_prompt_structure():
    from friday.weixin.approval import format_approval_prompt

    text = format_approval_prompt(
        "查询 USD 的公开汇率（只读，不会改本地文件）",
        preview="· 会访问互联网读取数据\n· 不会修改或删除你电脑上的文件",
    )
    assert "准备做什么" in text
    assert "补充说明" in text
    assert "请你决定" in text
    assert "import requests" not in text


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


def test_collect_setup_steps_llm_api_generic_title():
    steps = collect_setup_steps(port=8765, api_token="test")
    api_step = next(s for s in steps if s.id == "friday_api")
    assert api_step.title == "大模型 API"
    assert "DeepSeek API" not in api_step.title
    assert "共用" in api_step.description
    if api_step.status != "ok":
        assert api_step.action == "open_api_settings"


def test_collect_setup_steps_llm_api_shows_mimo_when_configured(monkeypatch):
    from friday.storage import UserSettings

    settings = UserSettings(
        api_key="sk-abcdefgh12345678",
        llm_provider="mimo",
        base_url="https://api.xiaomimimo.com/v1",
        model="mimo-v2-flash",
    )
    monkeypatch.setattr("friday.weixin.setup.load_settings", lambda: settings)
    steps = collect_setup_steps(port=8765, api_token="test")
    api_step = next(s for s in steps if s.id == "friday_api")
    assert api_step.status == "ok"
    assert api_step.action == ""
    assert "MiMo" in api_step.message
    assert "mimo-v2-flash" in api_step.message
    assert "xiaomimimo.com" in api_step.message


def test_setup_status_payload_includes_llm_api(monkeypatch):
    from friday.storage import UserSettings

    settings = UserSettings(
        api_key="sk-abcdefgh12345678",
        llm_provider="mimo",
        base_url="https://api.xiaomimimo.com/v1",
        model="mimo-v2-flash",
    )
    monkeypatch.setattr("friday.weixin.setup.load_settings", lambda: settings)
    monkeypatch.setattr("friday.weixin.setup.list_account_ids", lambda: [])
    monkeypatch.setattr("friday.weixin.setup.resolve_account", lambda: None)
    monkeypatch.setattr("friday.weixin.setup.gateway_status", lambda: {"running": False})
    monkeypatch.setattr("friday.weixin.setup.read_bridge_config", lambda: {})
    monkeypatch.setattr("friday.weixin.setup._openclaw_cli_info", lambda: (False, "", "未安装"))
    from friday.weixin.setup import setup_status_payload

    payload = setup_status_payload(port=8765, api_token="t")
    llm = payload["llm_api"]
    assert llm["ready"] is True
    assert llm["provider"] == "mimo"
    assert llm["provider_label"] == "小米 MiMo"
    assert llm["base_url"] == "https://api.xiaomimimo.com/v1"
    assert llm["model"] == "mimo-v2-flash"


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


def test_install_weixin_plugin_repairs_missing_runtime_deps(tmp_path, monkeypatch):
    ext = tmp_path / "extensions" / "openclaw-weixin"
    (ext / "dist").mkdir(parents=True)
    (ext / "dist" / "index.js").write_text("// ok", encoding="utf-8")
    (ext / "openclaw.plugin.json").write_text('{"id":"openclaw-weixin"}', encoding="utf-8")
    (ext / "package.json").write_text(
        '{"dependencies":{"zod":"^4.3.6","qrcode-terminal":"0.12.0"}}',
        encoding="utf-8",
    )
    monkeypatch.setattr("friday.weixin.setup.openclaw_state_dir", lambda: tmp_path)
    monkeypatch.setattr("friday.weixin.setup._plugin_extension_dir", lambda _pid: ext)

    calls: list[str] = []

    def fake_ensure_deps(plugin_dir):
        calls.append(str(plugin_dir))
        nm = plugin_dir / "node_modules" / "zod"
        nm.mkdir(parents=True)
        (nm / "package.json").write_text("{}", encoding="utf-8")
        (plugin_dir / "node_modules" / "qrcode-terminal").mkdir(parents=True)
        return True, "微信插件运行时依赖已安装"

    monkeypatch.setattr("friday.weixin.setup._ensure_plugin_runtime_deps", fake_ensure_deps)
    monkeypatch.setattr("friday.weixin.setup.configure_openclaw_plugins", lambda: (True, "ok"))
    monkeypatch.setattr("friday.weixin.setup._run_openclaw_doctor_repair", lambda: None)
    monkeypatch.setattr("friday.weixin.setup._install_weixin_via_npm", lambda: (False, "should not run"))

    ok, msg = install_weixin_plugin()
    assert ok
    assert calls == [str(ext)]
    assert "依赖" in msg


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
    assert data["channels"]["openclaw-weixin"]["name"] == "星期五"
    assert data["channels"]["openclaw-weixin"]["botAgent"].startswith("Friday/")
    assert "星期五" in data["channels"]["openclaw-weixin"]["description"]
    assert data["agents"]["list"][0]["identity"]["name"] == "星期五"
    bridge_hooks = data["plugins"]["entries"]["friday-weixin-bridge"]["hooks"]
    assert bridge_hooks["timeoutMs"] == 600_000


def test_apply_bridge_hook_timeout_clamps_legacy_value(tmp_path, monkeypatch):
    cfg = tmp_path / "openclaw.json"
    cfg.write_text(
        '{"plugins":{"entries":{"friday-weixin-bridge":{"enabled":true,'
        '"hooks":{"timeoutMs":620000}}}}}',
        encoding="utf-8",
    )
    monkeypatch.setattr("friday.weixin.setup._openclaw_config_path", lambda: cfg)
    ok, _ = ensure_openclaw_gateway_config()
    assert ok
    data = __import__("json").loads(cfg.read_text(encoding="utf-8"))
    assert data["plugins"]["entries"]["friday-weixin-bridge"]["hooks"]["timeoutMs"] == 600_000
    assert data["gateway"]["mode"] == "local"


def test_should_replace_weixin_display_name():
    assert _should_replace_weixin_display_name(None)
    assert _should_replace_weixin_display_name("微信clawbot")
    assert _should_replace_weixin_display_name("OpenClaw")
    assert not _should_replace_weixin_display_name("我的自定义助手")


def test_ensure_weixin_branding_replaces_legacy_name(tmp_path, monkeypatch):
    cfg = tmp_path / "openclaw.json"
    cfg.write_text(
        '{"channels":{"openclaw-weixin":{"enabled":true,"name":"微信clawbot"}}}',
        encoding="utf-8",
    )
    monkeypatch.setattr("friday.weixin.setup._openclaw_config_path", lambda: cfg)
    monkeypatch.setattr("friday.weixin.setup.list_account_ids", lambda: [])
    ok, msg = ensure_weixin_branding()
    assert ok
    assert "星期五" in msg
    data = __import__("json").loads(cfg.read_text(encoding="utf-8"))
    assert data["channels"]["openclaw-weixin"]["name"] == "星期五"
    assert data["agents"]["list"][0]["name"] == "星期五"


def test_ensure_weixin_branding_keeps_custom_name(tmp_path, monkeypatch):
    cfg = tmp_path / "openclaw.json"
    cfg.write_text(
        '{"channels":{"openclaw-weixin":{"enabled":true,"name":"小助手"}}}',
        encoding="utf-8",
    )
    monkeypatch.setattr("friday.weixin.setup._openclaw_config_path", lambda: cfg)
    monkeypatch.setattr("friday.weixin.setup.list_account_ids", lambda: [])
    ensure_weixin_branding()
    data = __import__("json").loads(cfg.read_text(encoding="utf-8"))
    assert data["channels"]["openclaw-weixin"]["name"] == "小助手"


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


def test_resolve_openclaw_command_uses_node_script_fallback(monkeypatch, tmp_path):
    from friday.weixin import openclaw_cli

    prefix = tmp_path / "npm-global"
    script = prefix / "node_modules" / "openclaw" / "dist" / "index.js"
    script.parent.mkdir(parents=True)
    script.write_text("// openclaw", encoding="utf-8")
    node = tmp_path / "node.exe"
    node.write_text("", encoding="utf-8")

    monkeypatch.setattr(openclaw_cli, "find_openclaw_cmd", lambda: None)
    monkeypatch.setattr(openclaw_cli, "find_openclaw_script", lambda: script)
    monkeypatch.setattr(openclaw_cli, "resolve_node_exe", lambda: str(node))
    monkeypatch.setattr(openclaw_cli.shutil, "which", lambda _name: None)

    assert openclaw_cli.resolve_openclaw_command() == [str(node), str(script)]
    assert openclaw_cli.cli_available() is True


def test_openclaw_shell_invocation_node_script(monkeypatch, tmp_path):
    node = tmp_path / "node.exe"
    script = tmp_path / "index.js"
    node.write_text("", encoding="utf-8")
    script.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        "friday.weixin.openclaw_cli.resolve_openclaw_command",
        lambda: [str(node), str(script)],
    )
    line = openclaw_shell_invocation(["gateway", "status"])
    assert f'"{node}"' in line
    assert f'"{script}"' in line
    assert "gateway status" in line


def test_launch_weixin_login_requires_cli(monkeypatch):
    monkeypatch.setattr("friday.weixin.setup._openclaw_cli_available", lambda: False)
    ok, msg = launch_weixin_login_terminal()
    assert not ok
    assert "openclaw" in msg.lower()


def test_launch_weixin_login_opens_terminal(monkeypatch):
    monkeypatch.setattr("friday.weixin.setup._openclaw_cli_available", lambda: True)
    monkeypatch.setattr("friday.weixin.setup._weixin_channel_available", lambda: True)
    monkeypatch.setattr("friday.weixin.setup.configure_openclaw_plugins", lambda: (True, "ok"))
    monkeypatch.setattr("friday.weixin.setup.start_gateway", lambda: (True, "running"))
    monkeypatch.setattr("friday.weixin.login_runner.clear_cached_login_url", lambda: None)
    monkeypatch.setattr(
        "friday.weixin.login_runner.launch_weixin_login_console",
        lambda: (True, "已打开扫码窗口；浏览器会自动弹出扫码页"),
    )
    from friday.weixin.setup import launch_weixin_login_terminal

    ok, msg = launch_weixin_login_terminal()
    assert ok
    assert "浏览器" in msg
