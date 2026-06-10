"""Vision Bridge — 豆包等多模态 API，为 DeepSeek 提供图片描述能力。"""

from __future__ import annotations

import base64
import io
import mimetypes
import time
from pathlib import Path

from friday.config import VISION_HTTP_TIMEOUT
from friday.logging_config import get_logger
from friday.storage import UserSettings

_log = get_logger("vision")

# 识图专用短 prompt，减少输出 token、加快响应
_FAST_PROMPT = (
    "这是用户截图。用简体中文简要说明：界面/文字/图表/错误信息。"
    "可见文字尽量逐条列出，控制在 350 字内。"
)

_SUPPORTED_MIME = frozenset({"image/png", "image/jpeg", "image/gif", "image/webp"})

# 火山引擎视觉 API 要求图片边长 ≥14px；旧 1×1 探针会返回 400 InvalidParameter
_TEST_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAIAAACQkWg2AAAAI0lEQVR4nGO8siCMgRTARJJqhlENxAEmItXBwagGYgDJoQQAq+UB6i6tUwYAAAAASUVORK5CYII="
)

# 聊天截图：小图快传
_MAX_VISION_EDGE = 1280
_COMPRESS_IF_OVER = 180 * 1024
_JPEG_QUALITY = 76
_VISION_MAX_TOKENS = 512
_VISION_DETAIL = "low"

_vision_cache: dict[str, tuple[float, str]] = {}
_VISION_CACHE_MAX = 24
_VISION_CACHE_TTL = 600.0


_PLACEHOLDER_VISION_KEYS = frozenset({"ark-your-key-here", "sk-your-key-here"})


def _vision_provider_id(settings: UserSettings) -> str:
    from friday.model_providers import infer_vision_provider

    return (infer_vision_provider(settings) or "ark").strip()


def vision_config_hint(settings: UserSettings) -> str:
    """视觉配置未完成时的简短原因（供设置页状态展示）。"""
    if not settings.vision_enabled:
        return ""
    key = settings.vision_api_key.strip()
    if not key or key in _PLACEHOLDER_VISION_KEYS:
        return "请填写视觉 API Key"
    provider = _vision_provider_id(settings)
    if provider == "ark":
        if key.startswith("sk-"):
            return "Key 格式不匹配：火山方舟需 ark- 开头"
        model = settings.vision_model.strip()
        if not model:
            return "请填写 ep- 推理接入点"
        if not model.startswith("ep-"):
            return "推理端点需 ep- 开头"
    return ""


def vision_ready(settings: UserSettings) -> bool:
    if not settings.vision_enabled:
        return False
    if vision_config_hint(settings):
        return False
    key = settings.vision_api_key.strip()
    return bool(key and key not in _PLACEHOLDER_VISION_KEYS)


def masked_vision_key(settings: UserSettings) -> str:
    key = settings.vision_api_key.strip()
    if not key:
        return "未设置"
    if len(key) <= 8:
        return "****"
    return f"{key[:4]}...{key[-4:]}"


def build_vision_prompt(user_text: str = "") -> str:
    question = (user_text or "").strip()
    if question:
        return f"{_FAST_PROMPT}\n用户关心：{question}"
    return _FAST_PROMPT


def is_vision_error(message: str) -> bool:
    text = (message or "").strip()
    if not text:
        return True
    markers = ("视觉 API 调用失败", "视觉辅助模型未配置", "未配置视觉模型", "找不到图片", "不支持")
    return any(m in text for m in markers)


def compose_chat_message(
    text: str,
    image_path: str = "",
    vision_summary: str = "",
    *,
    image_paths: list[str] | None = None,
) -> str:
    """组装带截图的用户消息；若已预识图则注入结果，跳过二次工具调用。"""
    base = (text or "").strip()
    paths: list[str] = []
    if image_paths:
        paths = [p.strip() for p in image_paths if (p or "").strip()]
    elif (image_path or "").strip():
        paths = [image_path.strip()]
    summary = (vision_summary or "").strip()

    if summary and paths and not is_vision_error(summary):
        parts = [f"[截图视觉分析]\n{summary}"]
        if base:
            parts.append(f"[用户问题]\n{base}")
        parts.append("[说明] 视觉分析已完成，请直接据此回答，勿再调用 describe_image。")
        return "\n\n".join(parts)

    if not paths:
        return base

    if len(paths) == 1:
        hint = (
            f"[用户粘贴了截图，绝对路径: {paths[0]}，"
            "请先用 describe_image 分析图片内容，再根据用户问题回答。]"
        )
    else:
        listing = "\n".join(f"{idx}. {path}" for idx, path in enumerate(paths, start=1))
        hint = (
            f"[用户粘贴了 {len(paths)} 张截图，请对每张图依次调用 describe_image 分析，再根据用户问题回答。"
            f"绝对路径：\n{listing}]"
        )
    if base:
        return f"{base}\n\n{hint}"
    if len(paths) > 1:
        return f"请分析我粘贴的这 {len(paths)} 张截图。\n\n{hint}"
    return f"请分析我粘贴的这张截图。\n\n{hint}"


def _vision_client(api_key: str, base_url: str, settings: UserSettings | None = None):
    from friday.api_connect import build_openai_client
    from friday.config import VISION_HTTP_TIMEOUT

    return build_openai_client(
        api_key,
        base_url,
        settings,
        read_timeout=float(VISION_HTTP_TIMEOUT),
    )


def optimize_image_bytes(data: bytes) -> tuple[bytes, str]:
    """压缩截图供识图/粘贴保存，统一 JPEG、限制边长。"""
    if len(data) <= _COMPRESS_IF_OVER:
        try:
            from PIL import Image

            img = Image.open(io.BytesIO(data))
            img.load()
            if max(img.size) <= _MAX_VISION_EDGE:
                return data, _mime_from_bytes(data)
        except Exception:
            return data, _mime_from_bytes(data)

    try:
        from PIL import Image

        img = Image.open(io.BytesIO(data))
        img.load()
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        w, h = img.size
        scale = min(1.0, _MAX_VISION_EDGE / max(w, h))
        if scale < 1.0:
            img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.Resampling.BILINEAR)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=_JPEG_QUALITY, optimize=True)
        out = buf.getvalue()
        _log.debug("图片优化 %dKB -> %dKB", len(data) // 1024, len(out) // 1024)
        return out, "image/jpeg"
    except Exception as exc:  # noqa: BLE001
        _log.warning("图片优化失败，使用原图 | %s", exc)
        return data, _mime_from_bytes(data)


def _mime_from_bytes(data: bytes) -> str:
    if data.startswith(b"\x89PNG"):
        return "image/png"
    if data.startswith(b"\xff\xd8"):
        return "image/jpeg"
    if data.startswith(b"GIF"):
        return "image/gif"
    return "image/jpeg"


def _prepare_image_bytes(path: Path) -> tuple[bytes, str, str]:
    raw = path.read_bytes()
    mime_type, _ = mimetypes.guess_type(str(path))
    if mime_type not in _SUPPORTED_MIME and not raw:
        raise ValueError(f"不支持的图片格式: {mime_type or '未知'}（支持 PNG/JPEG/GIF/WebP）")

    optimized, out_mime = optimize_image_bytes(raw)
    if len(optimized) < len(raw):
        _log.info(
            "视觉图片已优化 | path=%s %dKB -> %dKB",
            path.name,
            len(raw) // 1024,
            len(optimized) // 1024,
        )
    return optimized, out_mime, _VISION_DETAIL


def _cache_key(path: Path) -> str:
    stat = path.stat()
    return f"{path.resolve()}:{stat.st_mtime_ns}:{stat.st_size}"


def _cache_get(key: str) -> str | None:
    entry = _vision_cache.get(key)
    if not entry:
        return None
    ts, value = entry
    if time.time() - ts > _VISION_CACHE_TTL:
        _vision_cache.pop(key, None)
        return None
    return value


def _cache_put(key: str, value: str) -> None:
    if len(_vision_cache) >= _VISION_CACHE_MAX:
        oldest = min(_vision_cache.items(), key=lambda item: item[1][0])[0]
        _vision_cache.pop(oldest, None)
    _vision_cache[key] = (time.time(), value)


def describe_image(
    settings: UserSettings,
    image_path: str,
    prompt: str = "",
    *,
    max_tokens: int = _VISION_MAX_TOKENS,
) -> str:
    """调用视觉辅助模型描述图片（OpenAI 兼容接口，默认豆包 Ark）。"""
    if not vision_ready(settings):
        return (
            "视觉辅助模型未配置。请在「设置 → API 连接」中启用并填写豆包/Ark API Key 与推理接入点 ID。"
        )

    path = Path(image_path).expanduser()
    if not path.is_file():
        return f"找不到图片: {path}"

    cache_key = _cache_key(path)
    cached = _cache_get(cache_key)
    if cached is not None:
        _log.info("视觉缓存命中 | path=%s", image_path)
        return cached

    try:
        data, mime, detail = _prepare_image_bytes(path)
    except (FileNotFoundError, ValueError) as exc:
        return str(exc)

    b64 = base64.standard_b64encode(data).decode("utf-8")
    text_prompt = (prompt or _FAST_PROMPT).strip()
    model = settings.vision_model.strip()
    if not model:
        return "未配置视觉模型/端点 ID。请在设置中填写 ep- 开头的推理接入点。"
    base_url = settings.vision_base_url.strip() or "https://ark.cn-beijing.volces.com/api/v3"

    _log.info("开始识图 | path=%s model=%s %dKB detail=%s", path.name, model, len(data) // 1024, detail)
    t0 = time.perf_counter()
    try:
        client = _vision_client(settings.vision_api_key.strip(), base_url, settings)
        response = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": text_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime};base64,{b64}",
                                "detail": detail,
                            },
                        },
                    ],
                }
            ],
        )
        content = (response.choices[0].message.content or "").strip()
        if not content:
            return "视觉模型未返回有效内容。"
        elapsed = time.perf_counter() - t0
        _log.info("识图完成 | %.1fs chars=%d", elapsed, len(content))
        _cache_put(cache_key, content)
        return content
    except Exception as exc:  # noqa: BLE001
        _log.warning("Vision API 失败 | %s", exc)
        from friday.api_connect import format_api_error

        return f"视觉 API 调用失败: {format_api_error(exc, context='api_test', service='视觉 API')}"


def test_vision_connection(settings: UserSettings) -> tuple[bool, str]:
    from friday.api_connect import diagnose_vision, invalidate_probe_cache

    hint = vision_config_hint(settings)
    if not vision_ready(settings):
        return False, hint or "请先勾选「启用视觉辅助」并填写 API Key，再点「保存视觉设置」"
    steps = diagnose_vision(settings, include_api=True)
    if steps and steps[-1].ok:
        invalidate_probe_cache(clear_auth=False)
        return True, steps[-1].detail
    failed = next((s for s in reversed(steps) if not s.ok), steps[-1] if steps else None)
    if failed is None:
        return False, "视觉测试失败"
    msg = failed.detail
    if failed.hint:
        msg = f"{msg}\n{failed.hint}"
    return False, msg
