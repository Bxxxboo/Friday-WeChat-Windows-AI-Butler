"""大模型 / 视觉 / 生图服务商预设（OpenAI 兼容为主）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from friday.storage import UserSettings


@dataclass(frozen=True)
class ModelOption:
    id: str
    label_zh: str
    label_en: str = ""


@dataclass(frozen=True)
class ProviderPreset:
    id: str
    label_zh: str
    label_en: str
    default_base_url: str
    key_placeholder: str
    models: tuple[ModelOption, ...]
    model_kind: str = "select"  # select | text | endpoint
    hint_zh: str = ""
    hint_en: str = ""
    key_link: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label_zh": self.label_zh,
            "label_en": self.label_en or self.label_zh,
            "default_base_url": self.default_base_url,
            "key_placeholder": self.key_placeholder,
            "model_kind": self.model_kind,
            "hint_zh": self.hint_zh,
            "hint_en": self.hint_en or self.hint_zh,
            "key_link": self.key_link,
            "models": [
                {"id": m.id, "label_zh": m.label_zh, "label_en": m.label_en or m.label_zh}
                for m in self.models
            ],
        }


def _llm_providers() -> tuple[ProviderPreset, ...]:
    return (
        ProviderPreset(
            id="deepseek",
            label_zh="DeepSeek",
            label_en="DeepSeek",
            default_base_url="https://api.deepseek.com",
            key_placeholder="sk-...",
            key_link="https://platform.deepseek.com/api_keys",
            models=(
                ModelOption("deepseek-v4-flash", "deepseek-v4-flash（推荐，便宜快）", "deepseek-v4-flash (fast)"),
                ModelOption("deepseek-v4-pro", "deepseek-v4-pro（复杂推理）", "deepseek-v4-pro (reasoning)"),
                ModelOption("deepseek-chat", "deepseek-chat（兼容旧名）", "deepseek-chat (legacy)"),
            ),
        ),
        ProviderPreset(
            id="mimo",
            label_zh="小米 MiMo",
            label_en="Xiaomi MiMo",
            default_base_url="https://api.xiaomimimo.com/v1",
            key_placeholder="sk-...",
            hint_zh="切换服务商时会自动恢复此前保存的 MiMo 配置。",
            hint_en="Saved MiMo settings restore automatically when you switch back.",
            models=(
                ModelOption("mimo-v2-flash", "mimo-v2-flash（推荐，便宜快）", "mimo-v2-flash (fast)"),
                ModelOption("mimo-v2.5-pro", "mimo-v2.5-pro"),
            ),
        ),
        ProviderPreset(
            id="openai",
            label_zh="OpenAI",
            label_en="OpenAI",
            default_base_url="https://api.openai.com/v1",
            key_placeholder="sk-...",
            key_link="https://platform.openai.com/api-keys",
            models=(
                ModelOption("gpt-4o", "gpt-4o"),
                ModelOption("gpt-4o-mini", "gpt-4o-mini（便宜快）", "gpt-4o-mini (fast)"),
                ModelOption("o3-mini", "o3-mini（推理）", "o3-mini (reasoning)"),
            ),
        ),
        ProviderPreset(
            id="moonshot",
            label_zh="Moonshot / Kimi",
            label_en="Moonshot / Kimi",
            default_base_url="https://api.moonshot.cn/v1",
            key_placeholder="sk-...",
            key_link="https://platform.moonshot.cn/console/api-keys",
            models=(
                ModelOption("kimi-k2-0711-preview", "kimi-k2（推荐）", "kimi-k2"),
                ModelOption("moonshot-v1-32k", "moonshot-v1-32k"),
                ModelOption("moonshot-v1-8k", "moonshot-v1-8k"),
            ),
        ),
        ProviderPreset(
            id="qwen",
            label_zh="通义千问（DashScope 兼容）",
            label_en="Qwen (DashScope compatible)",
            default_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            key_placeholder="sk-...",
            key_link="https://bailian.console.aliyun.com/",
            models=(
                ModelOption("qwen-plus", "qwen-plus"),
                ModelOption("qwen-turbo", "qwen-turbo（便宜快）", "qwen-turbo (fast)"),
                ModelOption("qwen-max", "qwen-max"),
            ),
        ),
        ProviderPreset(
            id="zhipu",
            label_zh="智谱 GLM",
            label_en="Zhipu GLM",
            default_base_url="https://open.bigmodel.cn/api/paas/v4",
            key_placeholder="...",
            key_link="https://open.bigmodel.cn/usercenter/apikeys",
            models=(
                ModelOption("glm-4-plus", "glm-4-plus"),
                ModelOption("glm-4-flash", "glm-4-flash（便宜快）", "glm-4-flash (fast)"),
                ModelOption("glm-4-air", "glm-4-air"),
            ),
        ),
        ProviderPreset(
            id="siliconflow",
            label_zh="SiliconFlow",
            label_en="SiliconFlow",
            default_base_url="https://api.siliconflow.cn/v1",
            key_placeholder="sk-...",
            key_link="https://cloud.siliconflow.cn/account/ak",
            models=(
                ModelOption("deepseek-ai/DeepSeek-V3", "DeepSeek-V3"),
                ModelOption("Qwen/Qwen2.5-72B-Instruct", "Qwen2.5-72B"),
                ModelOption("Pro/deepseek-ai/DeepSeek-R1", "DeepSeek-R1"),
            ),
        ),
    )


def _vision_providers() -> tuple[ProviderPreset, ...]:
    return (
        ProviderPreset(
            id="ark",
            label_zh="火山方舟 / 豆包",
            label_en="Volcengine Ark / Doubao",
            default_base_url="https://ark.cn-beijing.volces.com/api/v3",
            key_placeholder="ark-...",
            key_link="https://console.volcengine.com/ark",
            model_kind="endpoint",
            hint_zh="「视觉模型/端点」请填推理接入点 ID（如 ep-2026…），不是裸模型名。",
            hint_en="Use inference endpoint ID (ep-…), not a bare model name.",
            models=(),
        ),
        ProviderPreset(
            id="openai",
            label_zh="OpenAI 多模态",
            label_en="OpenAI vision",
            default_base_url="https://api.openai.com/v1",
            key_placeholder="sk-...",
            key_link="https://platform.openai.com/api-keys",
            models=(
                ModelOption("gpt-4o", "gpt-4o"),
                ModelOption("gpt-4o-mini", "gpt-4o-mini"),
            ),
        ),
        ProviderPreset(
            id="qwen_vl",
            label_zh="通义千问 VL",
            label_en="Qwen VL",
            default_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            key_placeholder="sk-...",
            key_link="https://bailian.console.aliyun.com/",
            models=(
                ModelOption("qwen-vl-plus", "qwen-vl-plus"),
                ModelOption("qwen-vl-max", "qwen-vl-max"),
            ),
        ),
        ProviderPreset(
            id="zhipu_vl",
            label_zh="智谱 GLM-4V",
            label_en="Zhipu GLM-4V",
            default_base_url="https://open.bigmodel.cn/api/paas/v4",
            key_placeholder="...",
            key_link="https://open.bigmodel.cn/usercenter/apikeys",
            models=(
                ModelOption("glm-4v-plus", "glm-4v-plus"),
                ModelOption("glm-4v-flash", "glm-4v-flash"),
            ),
        ),
        ProviderPreset(
            id="moonshot_vl",
            label_zh="Moonshot 视觉",
            label_en="Moonshot vision",
            default_base_url="https://api.moonshot.cn/v1",
            key_placeholder="sk-...",
            key_link="https://platform.moonshot.cn/console/api-keys",
            models=(ModelOption("moonshot-v1-8k-vision-preview", "moonshot-v1-8k-vision-preview"),),
        ),
        ProviderPreset(
            id="mimo",
            label_zh="小米 MiMo",
            label_en="Xiaomi MiMo",
            default_base_url="https://api.xiaomimimo.com/v1",
            key_placeholder="sk-...",
            hint_zh="识图请用 mimo-v2.5 或 mimo-v2-omni；mimo-v2.5-pro 不支持图片。",
            hint_en="Use mimo-v2.5 or mimo-v2-omni for vision; mimo-v2.5-pro does not accept images.",
            models=(
                ModelOption("mimo-v2.5", "mimo-v2.5（识图推荐）", "mimo-v2.5 (vision)"),
                ModelOption("mimo-v2-omni", "mimo-v2-omni", "mimo-v2-omni"),
            ),
        ),
    )


def _image_gen_providers() -> tuple[ProviderPreset, ...]:
    return (
        ProviderPreset(
            id="openai_compat",
            label_zh="OpenAI 兼容中转",
            label_en="OpenAI-compatible relay",
            default_base_url="https://next.zhima.world",
            key_placeholder="sk-...",
            hint_zh="适用于多数 OpenAI Images API 兼容中转站。",
            hint_en="For OpenAI Images API compatible relays.",
            models=(),
            model_kind="text",
        ),
        ProviderPreset(
            id="ark",
            label_zh="火山方舟",
            label_en="Volcengine Ark",
            default_base_url="https://ark.cn-beijing.volces.com/api/v3",
            key_placeholder="ark-...",
            key_link="https://console.volcengine.com/ark",
            hint_zh="模型名称请填方舟推理接入点或 Seedream 等生图模型 ID。",
            hint_en="Use Ark endpoint or Seedream model ID.",
            models=(),
            model_kind="text",
        ),
        ProviderPreset(
            id="openai",
            label_zh="OpenAI 官方",
            label_en="OpenAI official",
            default_base_url="https://api.openai.com/v1",
            key_placeholder="sk-...",
            key_link="https://platform.openai.com/api-keys",
            models=(
                ModelOption("dall-e-3", "dall-e-3"),
                ModelOption("gpt-image-1", "gpt-image-1"),
            ),
            model_kind="text",
        ),
        ProviderPreset(
            id="siliconflow",
            label_zh="SiliconFlow 生图",
            label_en="SiliconFlow images",
            default_base_url="https://api.siliconflow.cn/v1",
            key_placeholder="sk-...",
            key_link="https://cloud.siliconflow.cn/account/ak",
            hint_zh="如 Kwai-Kolors、Stable Diffusion 等，模型名以平台文档为准。",
            hint_en="See SiliconFlow docs for model IDs.",
            models=(
                ModelOption("Kwai-Kolors/Kolors", "Kolors"),
                ModelOption("stabilityai/stable-diffusion-3-5-large", "SD 3.5 Large"),
            ),
            model_kind="text",
        ),
        ProviderPreset(
            id="qwen",
            label_zh="通义万相（DashScope）",
            label_en="Qwen Wanx (DashScope)",
            default_base_url="https://dashscope.aliyuncs.com/api/v1",
            key_placeholder="sk-...",
            key_link="https://bailian.console.aliyun.com/",
            hint_zh="万相接口与 OpenAI 略有差异，若失败请改用 OpenAI 兼容模式或中转。",
            hint_en="Wanx API may differ; try compatible relay if needed.",
            models=(ModelOption("wanx-v1", "wanx-v1"),),
            model_kind="text",
        ),
        ProviderPreset(
            id="mimo",
            label_zh="小米 MiMo",
            label_en="Xiaomi MiMo",
            default_base_url="https://api.xiaomimimo.com/v1",
            key_placeholder="sk-...",
            hint_zh="请填平台提供的生图 model ID（非 mimo-v2.5 识图模型）。默认尺寸建议 1920×1920。",
            hint_en="Use a dedicated image-gen model ID (not mimo-v2.5 vision). Default size: 1920×1920.",
            models=(),
            model_kind="text",
        ),
    )


_CUSTOM_ENTRY = ProviderPreset(
    id="_custom_entry",
    label_zh="自定义",
    label_en="Custom",
    default_base_url="",
    key_placeholder="sk-... / 任意 Key",
    model_kind="text",
    hint_zh="OpenAI 兼容 API，填写 Base URL 与模型 ID。",
    hint_en="OpenAI-compatible API — set base URL and model ID.",
    models=(),
)


_LLM = {p.id: p for p in _llm_providers()}
_VISION = {p.id: p for p in _vision_providers()}
_IMAGE_GEN = {p.id: p for p in _image_gen_providers()}


def providers_catalog() -> dict[str, list[dict[str, Any]]]:
    return {
        "llm": [p.to_dict() for p in _llm_providers()],
        "vision": [p.to_dict() for p in _vision_providers()],
        "image_gen": [p.to_dict() for p in _image_gen_providers()],
    }


def get_llm_provider(provider_id: str) -> ProviderPreset:
    from friday.custom_endpoints import is_custom_provider_id

    if is_custom_provider_id(provider_id):
        return _CUSTOM_ENTRY
    return _LLM.get(provider_id) or _LLM["deepseek"]


def get_vision_provider(provider_id: str) -> ProviderPreset:
    from friday.custom_endpoints import is_custom_provider_id

    if is_custom_provider_id(provider_id):
        return _CUSTOM_ENTRY
    return _VISION.get(provider_id) or _VISION["ark"]


def get_image_gen_provider(provider_id: str) -> ProviderPreset:
    from friday.custom_endpoints import is_custom_provider_id

    if is_custom_provider_id(provider_id):
        return _CUSTOM_ENTRY
    return _IMAGE_GEN.get(provider_id) or _IMAGE_GEN["openai_compat"]


def default_image_gen_base_url(provider_id: str) -> str:
    preset = get_image_gen_provider(provider_id)
    return preset.default_base_url.rstrip("/")


def default_image_gen_size(provider_id: str, base_url: str = "") -> str:
    if provider_id == "mimo" or "xiaomimimo" in (base_url or "").lower():
        return "1920x1920"
    return "1024x1024"


def _host(url: str) -> str:
    try:
        return (urlparse(url).netloc or "").lower()
    except Exception:
        return ""


def infer_llm_provider(settings: UserSettings) -> str:
    stored = (getattr(settings, "llm_provider", "") or "").strip()
    from friday.custom_endpoints import is_custom_provider_id

    if stored and (stored in _LLM or is_custom_provider_id(stored)):
        return stored
    host = _host(settings.base_url)
    if "deepseek" in host:
        return "deepseek"
    if "openai.com" in host:
        return "openai"
    if "moonshot" in host:
        return "moonshot"
    if "dashscope" in host or "aliyuncs.com" in host:
        return "qwen"
    if "bigmodel.cn" in host:
        return "zhipu"
    if "siliconflow" in host:
        return "siliconflow"
    if "xiaomimimo" in host or "mimo" in host:
        return "mimo"
    if host:
        from friday.custom_endpoints import get_endpoints, provider_id_for_endpoint

        endpoints = get_endpoints(settings, "llm")
        if endpoints:
            return provider_id_for_endpoint(endpoints[0]["id"])
        return "deepseek"
    return "deepseek"


def infer_vision_provider(settings: UserSettings) -> str:
    stored = (getattr(settings, "vision_provider", "") or "").strip()
    from friday.custom_endpoints import is_custom_provider_id

    if stored and (stored in _VISION or is_custom_provider_id(stored)):
        return stored
    host = _host(settings.vision_base_url)
    if "volces.com" in host or "ark" in host:
        return "ark"
    if "openai.com" in host:
        return "openai"
    if "dashscope" in host or "aliyuncs.com" in host:
        return "qwen_vl"
    if "bigmodel.cn" in host:
        return "zhipu_vl"
    if "moonshot" in host:
        return "moonshot_vl"
    if "xiaomimimo" in host or "mimo" in host:
        return "mimo"
    if host:
        from friday.custom_endpoints import get_endpoints, provider_id_for_endpoint

        endpoints = get_endpoints(settings, "vision")
        if endpoints:
            return provider_id_for_endpoint(endpoints[0]["id"])
        return "ark"
    return "ark"


def default_vision_model(provider_id: str) -> str:
    preset = get_vision_provider(provider_id)
    if preset.model_kind == "endpoint":
        return ""
    if preset.models:
        return preset.models[0].id
    return ""


def normalize_vision_model(provider_id: str, model: str) -> str:
    """校验视觉模型是否与服务商匹配；不匹配则回退到该服务商默认值。"""
    preset = get_vision_provider(provider_id)
    raw = (model or "").strip()
    if preset.model_kind == "endpoint":
        return raw if raw.startswith("ep-") else ""
    valid = {m.id for m in preset.models}
    if raw in valid:
        return raw
    return default_vision_model(provider_id)


def default_image_gen_model(provider_id: str) -> str:
    preset = get_image_gen_provider(provider_id)
    if preset.models:
        return preset.models[0].id
    return ""


def normalize_image_gen_model(provider_id: str, model: str) -> str:
    """校验生图模型是否与服务商匹配；不匹配则回退到该服务商默认值。"""
    preset = get_image_gen_provider(provider_id)
    raw = (model or "").strip()
    if preset.models:
        valid = {m.id for m in preset.models}
        return raw if raw in valid else preset.models[0].id
    if provider_id == "ark":
        return raw if raw.startswith("ep-") else ""
    if raw.startswith("ep-"):
        return ""
    if raw in {"mimo-v2.5", "mimo-v2-omni", "mimo-v2.5-pro"}:
        return ""
    return raw


def llm_service_label(settings: UserSettings) -> str:
    preset = get_llm_provider(infer_llm_provider(settings))
    return preset.label_zh
