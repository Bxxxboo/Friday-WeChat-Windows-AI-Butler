from __future__ import annotations

import re
import threading
import time
from concurrent.futures import Future
from dataclasses import dataclass
from typing import Any

from friday.logging_config import get_logger
from friday.safety import (
    PendingAction,
    TurnApprovalState,
    describe_approval_detail,
    describe_approval_plain,
    mark_turn_approved,
    should_request_approval,
)
from friday.safety import ToolDecision
from friday.sessions import save_agent_state
from friday.storage import UserSettings, load_settings
from friday.weixin.approval import format_approval_prompt, parse_approval_text
from friday.weixin.client import (
    WeixinAccount,
    resolve_account,
    save_context_token,
    send_peer_text,
)
from friday.weixin.sessions import resolve_session_id

_log = get_logger("weixin.bridge")

MAX_REPLY_CHARS = 3500
APPROVAL_TIMEOUT_SEC = 300

_peer_locks: dict[str, threading.Lock] = {}
_approval_waiters: dict[str, Future[bool]] = {}
_approval_meta: dict[str, dict[str, str]] = {}
_recent_inbound: dict[tuple[str, str], float] = {}
_recent_busy_notice: dict[str, float] = {}
_inbound_meta_lock = threading.Lock()
_processing_keys: set[tuple[str, str]] = set()
_peer_processing_text: dict[str, str] = {}

INBOUND_DEDUPE_SEC = 6.0
BUSY_NOTICE_COOLDOWN_SEC = 20.0

_GREETING_RE = re.compile(
    r"^(你好|您好|嗨|hi|hello|hey|在吗|在不在|早上好|下午好|晚上好)[\s!?。，,~！？]*$",
    re.IGNORECASE,
)
_WEIXIN_GREETING_REPLY = (
    "你好！我是星期五，你的 AI 电脑管家。"
    "你可以让我查看电脑状态、整理文件、处理文档等。有什么需要帮忙的吗？"
)


def _maybe_greeting_reply(text: str) -> str | None:
    if _GREETING_RE.match(text.strip()):
        return _WEIXIN_GREETING_REPLY
    return None


@dataclass
class InboundRequest:
    text: str
    sender_id: str
    account_id: str
    context_token: str = ""
    peer_id: str = ""


def _resolve_peer_id(req: InboundRequest) -> str:
    return (req.sender_id or req.peer_id or "").strip()


@dataclass
class InboundResponse:
    handled: bool
    reply: str = ""


def _peer_lock(peer: str) -> threading.Lock:
    lock = _peer_locks.get(peer)
    if lock is None:
        lock = threading.Lock()
        _peer_locks[peer] = lock
    return lock


def _prune_recent_inbound(now: float) -> None:
    stale = [k for k, ts in _recent_inbound.items() if now - ts > INBOUND_DEDUPE_SEC * 4]
    for k in stale:
        _recent_inbound.pop(k, None)


def _is_recent_duplicate(peer_id: str, text: str, *, now: float | None = None) -> bool:
    """已完成处理的同内容重复投递（非并发竞态）。"""
    key = (peer_id, text.strip())
    ts = time.monotonic() if now is None else now
    _prune_recent_inbound(ts)
    last = _recent_inbound.get(key)
    return last is not None and ts - last < INBOUND_DEDUPE_SEC


def _claim_inbound(peer_id: str, text: str) -> tuple[str, threading.Lock | None]:
    """原子认领入站消息，避免并发重复投递误报 busy。

    返回 (action, lock)：
    - duplicate: 同内容重复，静默忽略
    - busy: 上一条不同内容仍在处理
    - process: 已持有 peer 锁，可开始执行
    """
    normalized = text.strip()
    key = (peer_id, normalized)
    now = time.monotonic()
    lock = _peer_lock(peer_id)

    with _inbound_meta_lock:
        _prune_recent_inbound(now)
        if key in _processing_keys:
            return "duplicate", None
        if _is_recent_duplicate(peer_id, normalized, now=now):
            return "duplicate", None

        active_text = _peer_processing_text.get(peer_id)
        if active_text is not None:
            if active_text == normalized:
                return "duplicate", None
            return "busy", None

        if not lock.acquire(blocking=False):
            active_text = _peer_processing_text.get(peer_id)
            if active_text == normalized:
                return "duplicate", None
            return "busy", None

        _processing_keys.add(key)
        _peer_processing_text[peer_id] = normalized

    return "process", lock


def _finish_inbound(peer_id: str, text: str, lock: threading.Lock) -> None:
    key = (peer_id, text.strip())
    now = time.monotonic()
    try:
        lock.release()
    finally:
        with _inbound_meta_lock:
            _processing_keys.discard(key)
            if _peer_processing_text.get(peer_id) == text.strip():
                _peer_processing_text.pop(peer_id, None)
            _recent_inbound[key] = now
        _log.debug("微信 peer 锁已释放 | peer=%s", peer_id)


def _pending_approval(peer_id: str) -> bool:
    future = _approval_waiters.get(peer_id)
    return future is not None and not future.done()


def _busy_reply(peer_id: str, *, pending_approval: bool) -> str:
    if pending_approval:
        return "我还在等你审批上一条操作，请回复「同意」或「拒绝」。"
    now = time.monotonic()
    last = _recent_busy_notice.get(peer_id, 0.0)
    if now - last < BUSY_NOTICE_COOLDOWN_SEC:
        return ""
    _recent_busy_notice[peer_id] = now
    return "上一条还在处理中，请等回复完成后再发新消息。"


def _truncate_reply(text: str) -> str:
    body = (text or "").strip()
    if len(body) <= MAX_REPLY_CHARS:
        return body or "（已完成，无文字回复）"
    return body[: MAX_REPLY_CHARS - 20] + "\n\n…（内容过长已截断）"


def _format_weixin_agent_error(exc: BaseException) -> str:
    from friday.api_connect import format_api_error

    text = str(exc or "").strip()
    if isinstance(exc, ValueError) and "会话不存在" in text:
        return "会话数据异常，请在桌面版侧边栏打开「我的微信」后重试。"
    detail = format_api_error(exc, context="api_test", service="大模型 API").split("\n")[0].strip()
    if not detail:
        detail = text[:200] if text else ""
    if detail:
        if len(detail) > 280:
            detail = detail[:277] + "…"
        return f"执行出错：{detail}"
    return "执行出错，请稍后重试，或在星期五桌面版查看日志。"


def _save_weixin_agent_state(session_id: str, agent: Any, *, user_message: str) -> None:
    try:
        saved = save_agent_state(
            session_id,
            agent.messages,
            user_text=user_message,
            activate=False,
        )
    except ValueError:
        _log.warning("微信会话不存在，尝试重建后保存 | session=%s", session_id)
        from friday.sessions import create_session

        saved = create_session("我的微信", title_pinned=True, activate=False)
        save_agent_state(saved.id, agent.messages, user_text=user_message, activate=False)
    except Exception:
        _log.exception("微信会话保存失败 | session=%s", session_id)
        return
    try:
        from friday.ws_broadcast import notify_session_updated

        notify_session_updated(saved.id, source="weixin")
    except Exception:
        pass


def _make_weixin_approval_bridge(
    *,
    peer_id: str,
    account: WeixinAccount,
) -> Any:
    def approval_bridge(action: PendingAction) -> bool:
        from friday.interaction_modes import normalize_mode, tool_allowed_in_mode

        settings = load_settings()
        mode = normalize_mode(getattr(settings, "interaction_mode", "agent"))
        if not tool_allowed_in_mode(action.tool_name, mode):
            return False

        pseudo = ToolDecision(
            allowed=True,
            needs_approval=True,
            large_download=action.large_download,
            untrusted_download=action.untrusted_download,
        )
        state = TurnApprovalState()
        if not should_request_approval(settings, pseudo, state):
            return True

        prompt = format_approval_prompt(
            describe_approval_plain(action.tool_name, action.arguments),
            preview=describe_approval_detail(action.tool_name, action.arguments),
        )
        try:
            send_peer_text(account, peer_id=peer_id, text=prompt)
        except RuntimeError as exc:
            _log.warning("审批消息 iLink 发送失败 | peer=%s err=%s", peer_id, exc)
            return False

        future: Future[bool] = Future()
        _approval_waiters[peer_id] = future
        _approval_meta[peer_id] = {
            "account_id": account.account_id,
        }
        _log.info(
            "等待微信审批 | peer=%s summary=%s",
            peer_id,
            describe_approval_plain(action.tool_name, action.arguments)[:80],
        )
        approved = False
        try:
            approved = future.result(timeout=APPROVAL_TIMEOUT_SEC)
        except TimeoutError:
            try:
                send_peer_text(
                    account,
                    peer_id=peer_id,
                    text="审批已超时，本次操作已取消。",
                )
            except RuntimeError:
                pass
            return False
        finally:
            _approval_waiters.pop(peer_id, None)
            _approval_meta.pop(peer_id, None)

        if approved:
            mark_turn_approved(state, pseudo)
        return approved

    return approval_bridge


def _run_agent(
    *,
    session_id: str,
    text: str,
    peer_id: str,
    account: WeixinAccount,
    context_token: str,
) -> str:
    from friday.agent import FridayAgent
    from friday.sessions import get_session

    settings = load_settings()
    if not settings.api_ready:
        return "请先在星期五桌面版「设置 → API 连接」中配置并保存大模型 API Key。"

    approval_bridge = _make_weixin_approval_bridge(
        peer_id=peer_id,
        account=account,
    )
    session = get_session(session_id)
    try:
        agent = FridayAgent(settings, approval_bridge)
    except Exception as exc:  # noqa: BLE001
        _log.exception("微信 Agent 初始化失败 | peer=%s session=%s", peer_id, session_id)
        return _format_weixin_agent_error(exc)
    if session:
        agent.load_history(session.agent_messages)
    agent.operation_meta = {
        "session_id": session_id,
        "trigger": "weixin",
        "schedule_id": "",
    }

    user_message = f"[来自微信 remote]\n{text.strip()}"
    try:
        result = agent.run(user_message)
    except Exception as exc:  # noqa: BLE001
        _log.exception("微信 Agent 执行失败 | peer=%s session=%s", peer_id, session_id)
        return _format_weixin_agent_error(exc)
    _save_weixin_agent_state(session_id, agent, user_message=user_message)
    return _truncate_reply(result)


def _deliver_weixin_reply(
    account: WeixinAccount,
    *,
    peer_id: str,
    reply: str,
    context_token: str = "",
) -> InboundResponse:
    """优先经 iLink 直接发微信；失败时把文案交回 OpenClaw 通道。"""
    body = (reply or "").strip()
    if not body:
        return InboundResponse(handled=True, reply="")
    try:
        send_peer_text(
            account,
            peer_id=peer_id,
            text=body,
            fallback_token=context_token,
        )
        return InboundResponse(handled=True, reply="")
    except RuntimeError as exc:
        _log.warning("微信 iLink 发送失败，改由 OpenClaw 通道回复 | peer=%s err=%s", peer_id, exc)
        return InboundResponse(handled=True, reply=body)


def _resolve_pending_approval(peer_id: str, text: str, account: WeixinAccount) -> InboundResponse | None:
    future = _approval_waiters.get(peer_id)
    if future is None or future.done():
        return None

    decision = parse_approval_text(text)
    if decision is None:
        return _deliver_weixin_reply(
            account,
            peer_id=peer_id,
            reply="请回复「同意」或「拒绝」。",
            context_token="",
        )

    future.set_result(decision)
    ack = "好的，已同意，继续执行。" if decision else "好的，已拒绝该操作。"
    _log.info("微信审批已回复 | peer=%s approved=%s", peer_id, decision)
    try:
        send_peer_text(account, peer_id=peer_id, text=ack)
    except RuntimeError as exc:
        _log.warning("审批确认 iLink 发送失败，改由 OpenClaw 通道回复 | peer=%s err=%s", peer_id, exc)
        return InboundResponse(handled=True, reply=ack)
    return InboundResponse(handled=True, reply="")



def handle_inbound(req: InboundRequest) -> InboundResponse:
    text = (req.text or "").strip()
    peer_id = _resolve_peer_id(req)
    if not peer_id:
        return InboundResponse(handled=True, reply="无法识别发送者。")
    if not text:
        return InboundResponse(handled=True, reply="请发送文字指令。")

    settings = load_settings()
    if not getattr(settings, "weixin_bridge_enabled", True):
        return InboundResponse(
            handled=True,
            reply="微信桥接已关闭。请在星期五「设置 → 微信桥接」勾选「启用微信桥接」。",
        )

    account = resolve_account(req.account_id)
    if account is None:
        return InboundResponse(
            handled=True,
            reply="微信通道未登录。请在星期五「设置 → 微信桥接」完成扫码登录。",
        )

    context_token = (req.context_token or "").strip()
    if context_token:
        save_context_token(account.account_id, peer_id, context_token)

    approval_hit = _resolve_pending_approval(peer_id, text, account)
    if approval_hit is not None:
        return approval_hit

    if parse_approval_text(text) is not None:
        return _deliver_weixin_reply(
            account,
            peer_id=peer_id,
            reply="当前没有待审批的操作。",
            context_token=context_token,
        )

    action, lock = _claim_inbound(peer_id, text)
    if action == "duplicate":
        _log.debug("微信重复消息已忽略 | peer=%s preview=%s", peer_id, text[:40])
        return InboundResponse(handled=True, reply="")
    if action == "busy":
        busy = _busy_reply(peer_id, pending_approval=_pending_approval(peer_id))
        if not busy:
            _log.debug("微信并发消息已忽略 | peer=%s preview=%s", peer_id, text[:40])
            return InboundResponse(handled=True, reply="")
        _log.info("微信消息并发被拒 | peer=%s preview=%s", peer_id, text[:40])
        return _deliver_weixin_reply(
            account,
            peer_id=peer_id,
            reply=busy,
            context_token=context_token,
        )
    assert lock is not None

    session_id = resolve_session_id(account.account_id, peer_id)
    try:
        greeting = _maybe_greeting_reply(text)
        if greeting is not None and settings.api_ready:
            _log.info("微信问候快路径 | peer=%s session=%s", peer_id, session_id)
            return _deliver_weixin_reply(
                account,
                peer_id=peer_id,
                reply=greeting,
                context_token=context_token,
            )
        _log.info("微信任务开始 | peer=%s session=%s", peer_id, session_id)
        reply = _run_agent(
            session_id=session_id,
            text=text,
            peer_id=peer_id,
            account=account,
            context_token=context_token,
        )
        _log.info("微信任务完成 | peer=%s chars=%d", peer_id, len(reply))
        return _deliver_weixin_reply(
            account,
            peer_id=peer_id,
            reply=reply,
            context_token=context_token,
        )
    except Exception as exc:  # noqa: BLE001
        _log.exception("微信任务执行失败 | peer=%s", peer_id)
        return _deliver_weixin_reply(
            account,
            peer_id=peer_id,
            reply=_format_weixin_agent_error(exc),
            context_token=context_token,
        )
    finally:
        _finish_inbound(peer_id, text, lock)
