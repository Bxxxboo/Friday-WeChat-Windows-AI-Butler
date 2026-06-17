"""微信 Bot 资料：功能介绍同步与 openclaw-weixin 插件补丁。"""

from __future__ import annotations

import json
import random
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from friday.config import APP_NAME
from friday.logging_config import get_logger
from friday.weixin.client import (
    BOT_AGENT,
    CHANNEL_VERSION,
    ILINK_APP_CLIENT_VERSION,
    ILINK_APP_ID,
    list_account_ids,
    resolve_account,
)
from friday.weixin.config import openclaw_state_dir

_log = get_logger("weixin.profile")

WEIXIN_PLUGIN_ID = "openclaw-weixin"

DEFAULT_WEIXIN_DESCRIPTION = (
    "本机 AI 管家「星期五」的微信通道。"
    "用微信发消息即可远程操作这台电脑，请保持星期五桌面版在运行。"
    "发消息后 24 小时内可收到回复。"
)
_PATCH_MARKER = "// friday-weixin-profile-patch"
_LEGACY_DESCRIPTION_MARKERS = (
    "openclaw 与微信",
    "openclaw与微信",
    "微信clawbot",
    "微信 clawbot",
    "clawbot 仅接收",
    "连接 openclaw",
)


def _openclaw_config_path() -> Path:
    return openclaw_state_dir() / "openclaw.json"


def _read_openclaw_config() -> dict[str, Any]:
    path = _openclaw_config_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_openclaw_config(data: dict[str, Any]) -> None:
    path = _openclaw_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def should_replace_weixin_description(description: Any) -> bool:
    if description is None:
        return True
    text = str(description).strip()
    if not text:
        return True
    lowered = text.casefold()
    return any(marker in lowered for marker in _LEGACY_DESCRIPTION_MARKERS)


def apply_weixin_description(data: dict[str, Any]) -> None:
    channels = data.setdefault("channels", {})
    if not isinstance(channels, dict):
        return
    wx = channels.setdefault(WEIXIN_PLUGIN_ID, {})
    if not isinstance(wx, dict):
        return
    if should_replace_weixin_description(wx.get("description")):
        wx["description"] = DEFAULT_WEIXIN_DESCRIPTION


def _plugin_extension_dir() -> Path:
    return openclaw_state_dir() / "extensions" / WEIXIN_PLUGIN_ID


def patch_weixin_plugin_profile() -> tuple[bool, str]:
    """为已安装的 openclaw-weixin 注入功能介绍/名称读取逻辑。"""
    root = _plugin_extension_dir()
    accounts_js = root / "dist" / "src" / "auth" / "accounts.js"
    api_js = root / "dist" / "src" / "api" / "api.js"
    login_js = root / "dist" / "src" / "auth" / "login-qr.js"
    if not accounts_js.is_file() or not api_js.is_file() or not login_js.is_file():
        return False, "openclaw-weixin 插件未安装，跳过功能介绍补丁"

    changed = False
    accounts_text = accounts_js.read_text(encoding="utf-8")
    if _PATCH_MARKER not in accounts_text:
        insert_after = "export function loadConfigBotAgent() {"
        helper = f"""
{_PATCH_MARKER}
export function loadConfigDescription() {{
    const section = loadRouteTagSection();
    if (!section)
        return undefined;
    const value = section.description;
    return typeof value === "string" && value.trim() ? value : undefined;
}}
export function loadConfigBotName() {{
    const section = loadRouteTagSection();
    if (!section)
        return undefined;
    const value = section.name;
    return typeof value === "string" && value.trim() ? value : undefined;
}}
"""
        if insert_after not in accounts_text:
            return False, "openclaw-weixin accounts.js 结构变化，无法打补丁"
        accounts_text = accounts_text.replace(insert_after, helper + insert_after, 1)
        accounts_js.write_text(accounts_text, encoding="utf-8")
        changed = True

    api_text = api_js.read_text(encoding="utf-8")
    if _PATCH_MARKER not in api_text:
        api_text = api_text.replace(
            "import { loadConfigBotAgent, loadConfigRouteTag } from \"../auth/accounts.js\";",
            "import { loadConfigBotAgent, loadConfigBotName, loadConfigDescription, loadConfigRouteTag } from \"../auth/accounts.js\";",
            1,
        )
        api_text = api_text.replace(
            "export function buildBaseInfo() {\n    return {\n        channel_version: CHANNEL_VERSION,\n        bot_agent: sanitizeBotAgent(loadConfigBotAgent()),\n    };\n}",
            f"""export function buildBaseInfo() {{
{_PATCH_MARKER}
    const info = {{
        channel_version: CHANNEL_VERSION,
        bot_agent: sanitizeBotAgent(loadConfigBotAgent()),
    }};
    const description = loadConfigDescription();
    if (description)
        info.description = description;
    const botName = loadConfigBotName();
    if (botName)
        info.bot_name = botName;
    return info;
}}""",
            1,
        )
        api_js.write_text(api_text, encoding="utf-8")
        changed = True

    login_text = login_js.read_text(encoding="utf-8")
    if _PATCH_MARKER not in login_text:
        login_text = login_text.replace(
            'import { listIndexedWeixinAccountIds, loadWeixinAccount } from "./accounts.js";',
            'import { listIndexedWeixinAccountIds, loadConfigBotName, loadConfigDescription, loadWeixinAccount } from "./accounts.js";\nimport { buildBaseInfo } from "../api/api.js";',
            1,
        )
        login_text = login_text.replace(
            'body: JSON.stringify({ local_token_list: localTokenList }),',
            f"""body: JSON.stringify({{
{_PATCH_MARKER}
            local_token_list: localTokenList,
            ...(loadConfigBotName() ? {{ bot_name: loadConfigBotName() }} : {{}}),
            ...(loadConfigDescription() ? {{ description: loadConfigDescription() }} : {{}}),
            base_info: buildBaseInfo(),
        }}),""",
            1,
        )
        login_js.write_text(login_text, encoding="utf-8")
        changed = True

    if changed:
        _log.info("已为 openclaw-weixin 注入功能介绍补丁 | root=%s", root)
        return True, "已更新微信插件功能介绍补丁"
    return True, "微信插件功能介绍补丁已是最新"


def _random_wechat_uin() -> str:
    import base64

    return base64.b64encode(str(random.getrandbits(32)).encode()).decode()


def _notify_start_profile(*, base_url: str, token: str, description: str, bot_name: str) -> bool:
    body = {
        "base_info": {
            "channel_version": CHANNEL_VERSION,
            "bot_agent": BOT_AGENT,
            "bot_name": bot_name,
            "description": description,
        },
        "bot_name": bot_name,
        "description": description,
        "function_intro": description,
    }
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/ilink/bot/msg/notifystart",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "AuthorizationType": "ilink_bot_token",
            "Authorization": f"Bearer {token}",
            "X-WECHAT-UIN": _random_wechat_uin(),
            "iLink-App-Id": ILINK_APP_ID,
            "iLink-App-ClientVersion": str(ILINK_APP_CLIENT_VERSION),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError, TimeoutError) as exc:
        _log.warning("同步微信功能介绍失败 | %s", exc)
        return False
    if isinstance(payload, dict) and payload.get("ret") not in (None, 0):
        _log.warning(
            "同步微信功能介绍被拒 | ret=%s errmsg=%s",
            payload.get("ret"),
            payload.get("errmsg"),
        )
        return False
    return True


def sync_weixin_bot_profile() -> tuple[bool, str]:
    """写入 openclaw.json 描述并向 iLink 推送功能介绍（已登录账号）。"""
    data = _read_openclaw_config()
    if not isinstance(data, dict):
        data = {}
    apply_weixin_description(data)
    _write_openclaw_config(data)

    patch_ok, patch_msg = patch_weixin_plugin_profile()
    if not patch_ok:
        if list_account_ids():
            return False, patch_msg
        _log.info("微信插件未安装，仅写入功能介绍配置 | %s", patch_msg)

    cfg = _read_openclaw_config()
    wx = (cfg.get("channels") or {}).get(WEIXIN_PLUGIN_ID) if isinstance(cfg, dict) else None
    description = DEFAULT_WEIXIN_DESCRIPTION
    bot_name = APP_NAME
    if isinstance(wx, dict):
        description = str(wx.get("description") or description).strip() or DEFAULT_WEIXIN_DESCRIPTION
        bot_name = str(wx.get("name") or bot_name).strip() or APP_NAME

    synced = 0
    for account_id in list_account_ids():
        account = resolve_account(account_id)
        if account is None:
            continue
        if _notify_start_profile(
            base_url=account.base_url,
            token=account.token,
            description=description,
            bot_name=bot_name,
        ):
            synced += 1

    if synced:
        return True, f"已同步 {synced} 个微信账号的功能介绍"
    if list_account_ids():
        return False, "功能介绍已写入配置，但推送至微信失败（请重启 Gateway 后重试）"
    return True, "功能介绍默认配置已就绪（扫码绑定后生效）"
