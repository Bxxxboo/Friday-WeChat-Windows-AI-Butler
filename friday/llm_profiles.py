"""大模型服务商配置记忆 —— 按 provider 分别保存 Key / URL / 模型，支持一键切换。"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from friday.custom_endpoints import (
    endpoint_id_from_provider,
    find_endpoint,
    get_endpoints,
    is_custom_provider_id,
    upsert_endpoint,
)
from friday.model_providers import get_llm_provider, infer_llm_provider
from friday.storage import UserSettings


def normalize_profiles(raw: Any) -> dict[str, dict[str, str]]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, str]] = {}
    for provider_id, entry in raw.items():
        if not isinstance(entry, dict):
            continue
        pid = str(provider_id or "").strip()
        if not pid or is_custom_provider_id(pid) or pid == "custom":
            continue
        out[pid] = {
            "api_key": str(entry.get("api_key") or ""),
            "base_url": str(entry.get("base_url") or "").strip(),
            "model": str(entry.get("model") or "").strip(),
        }
    return out


def active_provider_id(settings: UserSettings) -> str:
    stored = (getattr(settings, "llm_provider", "") or "").strip()
    if stored:
        return stored
    return infer_llm_provider(settings)


def snapshot_profile(
    settings: UserSettings,
    *,
    provider_id: str | None = None,
    profiles: dict[str, dict[str, str]] | None = None,
) -> dict[str, dict[str, str]]:
    pid = (provider_id or active_provider_id(settings)).strip() or "deepseek"
    store = deepcopy(profiles if profiles is not None else normalize_profiles(settings.llm_profiles))
    if is_custom_provider_id(pid) or pid == "custom":
        return store
    store[pid] = {
        "api_key": settings.api_key,
        "base_url": (settings.base_url or "").strip(),
        "model": (settings.model or "").strip(),
    }
    return store


def default_model_for(provider_id: str) -> str:
    preset = get_llm_provider(provider_id)
    if preset.models:
        return preset.models[0].id
    return UserSettings.model


# 切换大模型时，同步视觉配置（同平台共用 Key / URL / 识图模型）
_LLM_VISION_SYNC: dict[str, dict[str, str]] = {
    "mimo": {
        "vision_provider": "mimo",
        "vision_base_url": "https://api.xiaomimimo.com/v1",
        "vision_model": "mimo-v2.5",
    },
}


def switch_llm_provider(settings: UserSettings, new_provider: str) -> UserSettings:
    new_id = (new_provider or "").strip() or "deepseek"
    old_id = active_provider_id(settings)
    profiles = normalize_profiles(settings.llm_profiles)

    if old_id != new_id and is_custom_provider_id(old_id):
        old_eid = endpoint_id_from_provider(old_id)
        if old_eid and find_endpoint(get_endpoints(settings, "llm"), old_eid):
            settings = upsert_endpoint(settings, "llm", endpoint_id=old_eid, preserve_key_if_empty=True)
    elif old_id and old_id != "custom" and old_id != new_id:
        profiles = snapshot_profile(settings, provider_id=old_id, profiles=profiles)

    if is_custom_provider_id(new_id):
        eid = endpoint_id_from_provider(new_id)
        ep = find_endpoint(get_endpoints(settings, "llm"), eid or "") if eid else None
        if ep:
            return settings.merge(
                {
                    "llm_provider": new_id,
                    "llm_profiles": profiles,
                    "llm_custom_active": ep["id"],
                    "api_key": ep.get("api_key") or "",
                    "base_url": ep.get("base_url") or "",
                    "model": ep.get("model") or "",
                }
            )
        return settings.merge({"llm_provider": new_id, "llm_profiles": profiles})

    saved = profiles.get(new_id) or {}
    preset = get_llm_provider(new_id)
    base_url = (saved.get("base_url") or preset.default_base_url or UserSettings.base_url).strip()
    model = (saved.get("model") or default_model_for(new_id)).strip()
    merged = settings.merge(
        {
            "llm_provider": new_id,
            "llm_profiles": profiles,
            "api_key": saved.get("api_key") or "",
            "base_url": base_url,
            "model": model,
        }
    )
    sync = _LLM_VISION_SYNC.get(new_id)
    if sync:
        from friday.model_providers import normalize_vision_model

        merged = merged.merge(
            {
                **sync,
                "vision_model": normalize_vision_model(sync["vision_provider"], sync["vision_model"]),
                "vision_api_key": merged.api_key,
            }
        )
    elif old_id in _LLM_VISION_SYNC and new_id not in _LLM_VISION_SYNC:
        from friday.category_profiles import switch_category_profile
        from friday.custom_endpoints import active_provider_id as active_category_provider

        vision_pid = active_category_provider(merged, "vision")
        if vision_pid and not is_custom_provider_id(vision_pid):
            merged = switch_category_profile(merged, "vision", vision_pid)
    return merged


def persist_active_profile(settings: UserSettings) -> UserSettings:
    pid = active_provider_id(settings)
    if is_custom_provider_id(pid):
        eid = endpoint_id_from_provider(pid)
        return upsert_endpoint(settings, "llm", endpoint_id=eid or "", preserve_key_if_empty=True)
    profiles = snapshot_profile(settings, provider_id=pid)
    return settings.merge({"llm_profiles": profiles})


def seed_profiles_from_active(settings: UserSettings) -> UserSettings:
    profiles = normalize_profiles(settings.llm_profiles)
    if profiles:
        return settings
    pid = active_provider_id(settings)
    if is_custom_provider_id(pid) or pid == "custom":
        return settings.merge({"llm_profiles": {}})
    if not settings.api_key.strip() and not settings.base_url.strip():
        return settings.merge({"llm_profiles": {}})
    return settings.merge({"llm_profiles": snapshot_profile(settings, provider_id=pid, profiles={})})


def masked_profile_key(api_key: str) -> str:
    key = (api_key or "").strip()
    if not key:
        return "未设置"
    if len(key) <= 8:
        return "****"
    return f"{key[:4]}...{key[-4:]}"


def profiles_summary(settings: UserSettings) -> dict[str, dict[str, object]]:
    profiles = normalize_profiles(settings.llm_profiles)
    active = active_provider_id(settings)
    out: dict[str, dict[str, object]] = {}
    for pid, entry in profiles.items():
        key = (entry.get("api_key") or "").strip()
        configured = bool(key and key not in {"sk-your-key-here"})
        out[pid] = {
            "configured": configured,
            "api_key_masked": masked_profile_key(key),
            "base_url": entry.get("base_url") or "",
            "model": entry.get("model") or "",
            "active": pid == active,
        }
    return out


def merge_llm_settings(current: UserSettings, payload: dict) -> UserSettings | None:
    if payload.get("switch_llm_profile") and payload.get("llm_provider"):
        return switch_llm_provider(current, str(payload["llm_provider"]))
    new_provider = str(payload.get("llm_provider") or "").strip()
    old_provider = active_provider_id(current)
    explicit_key = "api_key" in payload and str(payload.get("api_key") or "").strip()
    if new_provider and new_provider != old_provider and not explicit_key:
        return switch_llm_provider(current, new_provider)
    return None


def llm_config_hint(settings: UserSettings) -> str:
    key = settings.api_key.strip()
    if not key:
        return "请填写大模型 API Key"
    if key == "sk-your-key-here" or key.startswith("sk-test"):
        return "当前 Key 为占位/测试值，请粘贴真实 API Key 并点保存"
    active = active_provider_id(settings)
    profiles = normalize_profiles(settings.llm_profiles)
    if active == "mimo" and active not in profiles:
        deepseek_key = str((profiles.get("deepseek") or {}).get("api_key") or "").strip()
        if deepseek_key and deepseek_key == key:
            return "当前仍为 DeepSeek 的 Key，请粘贴 MiMo Key 并保存"
    return ""


def _llm_profile_configured(profiles: dict[str, dict[str, str]], provider_id: str) -> bool:
    saved = profiles.get(provider_id) or {}
    key = str(saved.get("api_key") or "").strip()
    if not key or key in {"sk-your-key-here"}:
        return False
    return bool(str(saved.get("model") or "").strip() or str(saved.get("base_url") or "").strip())


def align_llm_active_from_profile(settings: UserSettings) -> UserSettings:
    """顶层 llm_provider / Key / URL / 模型为空或与 profile 脱节时，从 profile 回填（更新后防回退 DeepSeek）。"""
    active = active_provider_id(settings)
    if is_custom_provider_id(active):
        return settings

    profiles = normalize_profiles(settings.llm_profiles)
    if not profiles:
        return settings

    saved = profiles.get(active) or {}
    patch: dict[str, Any] = {}
    for field, prof_key in (
        ("api_key", "api_key"),
        ("base_url", "base_url"),
        ("model", "model"),
    ):
        current = str(getattr(settings, field) or "").strip()
        stored = str(saved.get(prof_key) or "").strip()
        if not current and stored:
            patch[field] = stored

    merged = settings.merge(patch) if patch else settings
    if _llm_profile_configured(profiles, active):
        return merged

    current_key = merged.api_key.strip()
    current_url = (merged.base_url or "").strip().rstrip("/")
    for pid, entry in profiles.items():
        if pid == active or not _llm_profile_configured(profiles, pid):
            continue
        p_key = str(entry.get("api_key") or "").strip()
        p_url = str(entry.get("base_url") or "").strip().rstrip("/")
        if current_key and p_key == current_key:
            return switch_llm_provider(merged, pid)
        if current_url and p_url and current_url == p_url:
            return switch_llm_provider(merged, pid)

    configured = [pid for pid in profiles if _llm_profile_configured(profiles, pid)]
    if len(configured) == 1 and configured[0] != active:
        return switch_llm_provider(merged, configured[0])
    return merged


def repair_llm_key_alignment(settings: UserSettings) -> UserSettings:
    """顶层 api_key 与当前服务商 profile 不一致时，以 profile 为准。"""
    active = active_provider_id(settings)
    if is_custom_provider_id(active):
        return settings
    profiles = normalize_profiles(settings.llm_profiles)
    saved = profiles.get(active) or {}
    saved_key = str(saved.get("api_key") or "").strip()
    current_key = settings.api_key.strip()
    if not saved_key or saved_key == current_key:
        return settings
    saved_url = str(saved.get("base_url") or "").strip().rstrip("/")
    active_url = (settings.base_url or "").strip().rstrip("/")
    if saved_url and active_url and saved_url != active_url:
        return settings
    return settings.merge({"api_key": saved_key})
