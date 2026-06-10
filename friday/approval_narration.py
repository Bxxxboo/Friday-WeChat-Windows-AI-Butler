"""审批文案 facade：模板 + 后台 LLM 润色。"""

from __future__ import annotations

import json
import re
import threading
from collections.abc import Callable

from friday.approval_descriptions import (
    GENERIC_APPROVAL_PLAIN,
    describe_approval_detail,
    describe_approval_plain,
    humanize_tool_name,
    summarize_preview,
)
from friday.logging_config import get_logger
from friday.safety import PendingAction
from friday.storage import UserSettings, load_settings

_log = get_logger("approval.narration")

_NARRATION_SYSTEM = (
    "你是「星期五」，正在向用户申请执行电脑操作的许可。"
    "根据用户诉求、你刚才的准备说明、以及即将执行的操作参数，"
    "用 1～2 句简体中文说明「准备做什么」。"
    "要求：具体（路径/文件名/网址/程序/数据范围至少提一项），简单好懂，像管家口头说明；"
    "禁止出现英文工具函数名、API 名、代码片段；"
    "禁止空泛表述如「执行一项操作」「需要你确认的操作」。"
    "只输出说明正文，不要标题、不要列表符号。"
)

_NARRATE_CONNECT_TIMEOUT = 5.0
_NARRATE_READ_TIMEOUT = 12.0


def is_generic_approval_plain(text: str) -> bool:
    return (text or "").strip() == GENERIC_APPROVAL_PLAIN


def build_approval_preview(action: PendingAction, *, plain: str | None = None) -> str:
    """统一补充说明：下载类走 probe/trust，其余用 detail（与 plain 去重）。"""
    summary = (plain if plain is not None else describe_approval_plain(
        action.tool_name,
        action.arguments,
    )).strip()
    if action.tool_name in {"download_file", "download_software"}:
        return summarize_preview(action.tool_name, action.arguments).strip()
    detail = describe_approval_detail(action.tool_name, action.arguments).strip()
    if detail and detail != summary:
        return detail
    return ""


def build_approval_template_copy(action: PendingAction) -> tuple[str, str]:
    """同步 (主说明, 补充说明)，供桌面 / 微信立即展示。"""
    plain = describe_approval_plain(action.tool_name, action.arguments)
    preview = build_approval_preview(action, plain=plain)
    return plain, preview


def build_approval_user_copy(
    action: PendingAction,
    *,
    settings: UserSettings | None = None,
) -> tuple[str, str]:
    """返回 (summary, preview)；同步路径仅模板，不调用 LLM。"""
    del settings
    return build_approval_template_copy(action)


def enrich_approval_summary_async(
    action: PendingAction,
    *,
    settings: UserSettings | None = None,
    on_narrated: Callable[[str], None] | None = None,
) -> None:
    """后台 LLM 润色；成功且与模板不同时调用 on_narrated。"""

    def _run() -> None:
        active_settings = settings if settings is not None else load_settings()
        if not active_settings.api_ready:
            return
        template_plain, _ = build_approval_template_copy(action)
        narrated = narrate_approval(action, settings=active_settings)
        if not narrated or narrated == template_plain or on_narrated is None:
            return
        try:
            on_narrated(narrated)
        except Exception as exc:  # noqa: BLE001
            _log.warning(
                "审批说明刷新回调失败 | tool=%s err=%s",
                action.tool_name,
                exc,
            )

    threading.Thread(
        target=_run,
        daemon=True,
        name="approval-narrate",
    ).start()


def narrate_approval(
    action: PendingAction,
    *,
    settings: UserSettings | None = None,
) -> str:
    """调用大模型将待审批操作译为自然语言；失败时返回空串。"""
    if settings is None:
        settings = load_settings()
    if not settings.api_ready:
        return ""

    payload = {
        "用户诉求": _short_user_goal(action.user_goal),
        "助手刚才说明": _clean_assistant_note(action.assistant_note),
        "操作类型": humanize_tool_name(action.tool_name),
        "参数摘要": _safe_args_summary(action.tool_name, action.arguments),
    }
    if action.large_download:
        payload["备注"] = "这是较大文件的下载，会占用磁盘空间"
    if action.untrusted_download:
        payload["备注"] = f"下载来源需确认：{action.trust_label or '非官方来源'}"

    try:
        from friday.api_connect import build_openai_client

        client = build_openai_client(
            settings.api_key,
            settings.base_url,
            settings,
            connect_timeout=_NARRATE_CONNECT_TIMEOUT,
            read_timeout=_NARRATE_READ_TIMEOUT,
            max_retries=1,
        )
        response = client.chat.completions.create(
            model=settings.model,
            messages=[
                {"role": "system", "content": _NARRATION_SYSTEM},
                {
                    "role": "user",
                    "content": json.dumps(payload, ensure_ascii=False),
                },
            ],
            temperature=0.2,
            max_tokens=160,
        )
        text = str(response.choices[0].message.content or "").strip()
        text = re.sub(r"\s+", " ", text).strip(" \"'")
        if len(text) < 8 or is_generic_approval_plain(text):
            return ""
        if len(text) > 220:
            text = text[:217].rstrip() + "…"
        return text
    except Exception as exc:  # noqa: BLE001
        _log.warning(
            "审批说明生成失败，将使用模板兜底 | tool=%s err=%s",
            action.tool_name,
            exc,
        )
        return ""


def _short_user_goal(text: str, *, max_len: int = 48) -> str:
    raw = re.sub(r"^\[来自微信 remote\]\s*", "", (text or "").strip(), flags=re.I)
    raw = re.sub(r"\s+", " ", raw)
    if not raw:
        return ""
    if len(raw) <= max_len:
        return raw
    return raw[: max_len - 1].rstrip() + "…"


def _clean_assistant_note(text: str) -> str:
    raw = re.sub(r"\s+", " ", (text or "").strip())
    return raw[:500]


def _safe_args_summary(tool_name: str, arguments: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in (arguments or {}).items():
        if str(key).startswith("_"):
            continue
        text = str(value).strip()
        if not text:
            continue
        if key in {"code", "command"} and len(text) > 240:
            text = text[:240].rstrip() + "…"
        if len(text) > 320:
            text = text[:320].rstrip() + "…"
        out[str(key)] = text
    return out
