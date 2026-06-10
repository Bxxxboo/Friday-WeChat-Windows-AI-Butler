"""微信桥接相关 HTTP 路由。"""

from __future__ import annotations

import asyncio
import os

from fastapi import FastAPI

from friday.api.schemas import (
    AutostartPayload,
    WeixinBridgeTogglePayload,
    WeixinInboundPayload,
    WeixinInboundResponse,
    WeixinSetupRunPayload,
)


def register_weixin_routes(app: FastAPI) -> None:
    @app.get("/api/weixin/gateway/autostart")
    async def get_openclaw_autostart() -> dict[str, object]:
        from friday.openclaw_autostart import openclaw_autostart_status

        return openclaw_autostart_status()

    @app.put("/api/weixin/gateway/autostart")
    async def set_openclaw_autostart(payload: AutostartPayload) -> dict[str, object]:
        from friday.openclaw_autostart import set_openclaw_autostart_enabled

        return set_openclaw_autostart_enabled(payload.enabled)

    @app.post("/api/weixin/inbound", response_model=WeixinInboundResponse)
    async def weixin_inbound(payload: WeixinInboundPayload) -> WeixinInboundResponse:
        from friday.logging_config import get_logger
        from friday.weixin import handle_inbound
        from friday.weixin.bridge import InboundRequest

        log = get_logger("weixin.inbound")
        peer = (payload.sender_id or payload.peer_id or "").strip()
        preview = (payload.text or "").strip().replace("\n", " ")[:80]
        log.info("收到微信消息 | peer=%s chars=%d preview=%s", peer, len(payload.text or ""), preview)

        result = await asyncio.to_thread(
            handle_inbound,
            InboundRequest(
                text=payload.text,
                sender_id=payload.sender_id,
                peer_id=payload.peer_id,
                account_id=payload.account_id,
                context_token=payload.context_token,
            ),
        )
        if result.handled and result.reply:
            log.info("微信回复待 OpenClaw 通道发送 | peer=%s chars=%d", peer, len(result.reply))
        elif result.handled:
            log.info("微信回复已 iLink 送达 | peer=%s", peer)
        elif not result.handled:
            log.warning("微信消息未处理 | peer=%s handled=false", peer)
        return WeixinInboundResponse(handled=result.handled, reply=result.reply)

    @app.get("/api/weixin/status")
    async def weixin_status() -> dict[str, object]:
        from friday.weixin.setup import weixin_status_payload

        return await asyncio.to_thread(weixin_status_payload)

    @app.get("/api/weixin/setup/status")
    async def weixin_setup_status() -> dict[str, object]:
        from friday.auth import get_api_token
        from friday.weixin.setup import setup_status_payload

        port = int(os.environ.get("FRIDAY_PORT", "8765"))
        return await asyncio.to_thread(
            setup_status_payload,
            port=port,
            api_token=get_api_token(),
        )

    @app.post("/api/weixin/setup/run")
    async def weixin_setup_run(payload: WeixinSetupRunPayload) -> dict[str, object]:
        from friday.auth import get_api_token
        from friday.weixin.setup import run_setup_action

        port = int(os.environ.get("FRIDAY_PORT", "8765"))
        return await asyncio.to_thread(
            run_setup_action,
            payload.action,
            port=port,
            api_token=get_api_token(),
        )

    @app.post("/api/weixin/setup/toggle")
    async def weixin_setup_toggle(payload: WeixinBridgeTogglePayload) -> dict[str, object]:
        from friday.weixin.setup import set_bridge_enabled

        updated = await asyncio.to_thread(set_bridge_enabled, payload.enabled)
        return {"ok": True, "bridge_enabled": getattr(updated, "weixin_bridge_enabled", True)}

    @app.get("/api/weixin/setup/login-url")
    async def weixin_setup_login_url() -> dict[str, object]:
        from friday.weixin.login_runner import read_cached_login_url

        url = await asyncio.to_thread(read_cached_login_url)
        return {"ok": bool(url), "url": url}

    @app.post("/api/weixin/setup/open-login-url")
    async def weixin_setup_open_login_url() -> dict[str, object]:
        from friday.weixin.login_runner import open_cached_login_url_in_browser

        ok, message = await asyncio.to_thread(open_cached_login_url_in_browser)
        return {"ok": ok, "message": message}
