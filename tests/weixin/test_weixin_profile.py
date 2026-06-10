from __future__ import annotations

import json
from pathlib import Path

from friday.weixin.profile import (
    DEFAULT_WEIXIN_DESCRIPTION,
    apply_weixin_description,
    patch_weixin_plugin_profile,
    should_replace_weixin_description,
    sync_weixin_bot_profile,
)


def test_should_replace_weixin_description():
    assert should_replace_weixin_description(None)
    assert should_replace_weixin_description(
        "连接 OpenClaw 与微信。当你发消息后，微信ClawBot 仅接收 OpenClaw 24 小时内的回复。"
    )
    assert not should_replace_weixin_description(DEFAULT_WEIXIN_DESCRIPTION)


def test_apply_weixin_description_replaces_legacy(tmp_path, monkeypatch):
    cfg = tmp_path / "openclaw.json"
    cfg.write_text(
        '{"channels":{"openclaw-weixin":{"enabled":true,'
        '"description":"连接 OpenClaw 与微信。当你发消息后，微信ClawBot 仅接收 OpenClaw 24 小时内的回复。"}}}',
        encoding="utf-8",
    )
    monkeypatch.setattr("friday.weixin.profile.openclaw_state_dir", lambda: tmp_path)
    monkeypatch.setattr("friday.weixin.profile._openclaw_config_path", lambda: cfg)
    data = json.loads(cfg.read_text(encoding="utf-8"))
    apply_weixin_description(data)
    assert data["channels"]["openclaw-weixin"]["description"] == DEFAULT_WEIXIN_DESCRIPTION


def test_patch_weixin_plugin_profile_idempotent(tmp_path, monkeypatch):
    root = tmp_path / "extensions" / "openclaw-weixin" / "dist" / "src"
    (root / "auth").mkdir(parents=True)
    (root / "api").mkdir(parents=True)
    accounts = root / "auth" / "accounts.js"
    api = root / "api" / "api.js"
    login = root / "auth" / "login-qr.js"
    accounts.write_text(
        'export function loadConfigBotAgent() {\n    return undefined;\n}\n',
        encoding="utf-8",
    )
    api.write_text(
        'import { loadConfigBotAgent, loadConfigRouteTag } from "../auth/accounts.js";\n'
        "export function buildBaseInfo() {\n"
        "    return {\n"
        "        channel_version: CHANNEL_VERSION,\n"
        "        bot_agent: sanitizeBotAgent(loadConfigBotAgent()),\n"
        "    };\n"
        "}\n",
        encoding="utf-8",
    )
    login.write_text(
        'import { listIndexedWeixinAccountIds, loadWeixinAccount } from "./accounts.js";\n'
        "async function fetchQRCode(apiBaseUrl, botType) {\n"
        '    const rawText = await apiPostFetch({ body: JSON.stringify({ local_token_list: localTokenList }), });\n'
        "}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("friday.weixin.profile.openclaw_state_dir", lambda: tmp_path)
    ok1, _ = patch_weixin_plugin_profile()
    ok2, _ = patch_weixin_plugin_profile()
    assert ok1 and ok2
    assert "loadConfigDescription" in accounts.read_text(encoding="utf-8")
    assert "loadConfigDescription" in api.read_text(encoding="utf-8")
    assert "buildBaseInfo()" in login.read_text(encoding="utf-8")


def test_sync_weixin_bot_profile_without_accounts(tmp_path, monkeypatch):
    cfg = tmp_path / "openclaw.json"
    cfg.write_text("{}", encoding="utf-8")
    monkeypatch.setattr("friday.weixin.profile.openclaw_state_dir", lambda: tmp_path)
    monkeypatch.setattr("friday.weixin.profile._openclaw_config_path", lambda: cfg)
    monkeypatch.setattr("friday.weixin.profile.list_account_ids", lambda: [])
    monkeypatch.setattr(
        "friday.weixin.profile.patch_weixin_plugin_profile",
        lambda: (False, "skip"),
    )
    ok, msg = sync_weixin_bot_profile()
    assert ok
    assert "扫码" in msg
    data = json.loads(cfg.read_text(encoding="utf-8"))
    assert data["channels"]["openclaw-weixin"]["description"] == DEFAULT_WEIXIN_DESCRIPTION
