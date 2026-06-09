"""自定义 OpenAI 兼容接入 —— 每种能力可保存多条命名配置。"""

from __future__ import annotations

import uuid
from copy import deepcopy
from typing import Any

from friday.storage import UserSettings

Category = str  # llm | vision | image_gen

_CATEGORY: dict[Category, dict[str, str]] = {
    "llm": {
        "provider": "llm_provider",
        "endpoints": "llm_custom_endpoints",
        "active": "llm_custom_active",
        "api_key": "api_key",
        "base_url": "base_url",
        "model": "model",
    },
    "vision": {
        "provider": "vision_provider",
        "endpoints": "vision_custom_endpoints",
        "active": "vision_custom_active",
        "api_key": "vision_api_key",
        "base_url": "vision_base_url",
        "model": "vision_model",
    },
    "image_gen": {
        "provider": "image_gen_provider",
        "endpoints": "image_gen_custom_endpoints",
        "active": "image_gen_custom_active",
        "api_key": "image_gen_api_key",
        "base_url": "image_gen_base_url",
        "model": "image_gen_model",
    },
}

_ENDPOINT_FIELDS = ("id", "name", "api_key", "base_url", "model", "fallback_urls")


def new_endpoint_id() -> str:
    return uuid.uuid4().hex[:12]


def normalize_endpoint(raw: Any) -> dict[str, str] | None:
    if not isinstance(raw, dict):
        return None
    eid = str(raw.get("id") or "").strip() or new_endpoint_id()
    name = str(raw.get("name") or "").strip() or "未命名"
    return {
        "id": eid,
        "name": name,
        "api_key": str(raw.get("api_key") or ""),
        "base_url": str(raw.get("base_url") or "").strip(),
        "model": str(raw.get("model") or "").strip(),
        "fallback_urls": str(raw.get("fallback_urls") or "").strip(),
    }


def normalize_endpoints(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in raw:
        entry = normalize_endpoint(item)
        if not entry or entry["id"] in seen:
            continue
        seen.add(entry["id"])
        out.append(entry)
    return out


def _cfg(category: Category) -> dict[str, str]:
    return _CATEGORY[category]


def get_endpoints(settings: UserSettings, category: Category) -> list[dict[str, str]]:
    field = _cfg(category)["endpoints"]
    return normalize_endpoints(getattr(settings, field, None))


CUSTOM_PREFIX = "c:"
ADD_CUSTOM_VALUE = "__add_custom__"

_DEFAULT_BUILTIN: dict[Category, str] = {
    "llm": "deepseek",
    "vision": "ark",
    "image_gen": "openai_compat",
}


def is_custom_provider_id(provider_id: str) -> bool:
    return str(provider_id or "").startswith(CUSTOM_PREFIX)


def provider_id_for_endpoint(endpoint_id: str) -> str:
    return f"{CUSTOM_PREFIX}{endpoint_id}"


def endpoint_id_from_provider(provider_id: str) -> str | None:
    if not is_custom_provider_id(provider_id):
        return None
    return provider_id[len(CUSTOM_PREFIX) :].strip() or None


def endpoint_to_provider_dict(endpoint: dict[str, str]) -> dict[str, str]:
    return {
        "id": provider_id_for_endpoint(endpoint["id"]),
        "label_zh": endpoint.get("name") or "未命名",
        "label_en": endpoint.get("name") or "Unnamed",
        "default_base_url": endpoint.get("base_url") or "",
        "key_placeholder": "sk-... / 任意 Key",
        "model_kind": "text",
        "user_custom": True,
    }


def active_provider_id(settings: UserSettings, category: Category) -> str:
    c = _cfg(category)
    stored = str(getattr(settings, c["provider"], "") or "").strip()
    if is_custom_provider_id(stored):
        return stored
    if stored == "custom":
        active = get_active_id(settings, category)
        if active:
            return provider_id_for_endpoint(active)
    return stored


def get_active_id(settings: UserSettings, category: Category) -> str:
    c = _cfg(category)
    stored = str(getattr(settings, c["provider"], "") or "").strip()
    from_provider = endpoint_id_from_provider(stored)
    if from_provider:
        return from_provider
    return str(getattr(settings, c["active"], "") or "").strip()


def find_endpoint(endpoints: list[dict[str, str]], endpoint_id: str) -> dict[str, str] | None:
    eid = (endpoint_id or "").strip()
    if not eid:
        return None
    for item in endpoints:
        if item.get("id") == eid:
            return item
    return None


def is_custom_provider(settings: UserSettings, category: Category) -> bool:
    provider = str(getattr(settings, _cfg(category)["provider"], "") or "").strip()
    return is_custom_provider_id(provider) or provider == "custom"


def snapshot_from_active(settings: UserSettings, category: Category) -> dict[str, str]:
    c = _cfg(category)
    return {
        "api_key": str(getattr(settings, c["api_key"], "") or ""),
        "base_url": str(getattr(settings, c["base_url"], "") or "").strip(),
        "model": str(getattr(settings, c["model"], "") or "").strip(),
        "fallback_urls": str(getattr(settings, "image_gen_fallback_urls", "") or "").strip()
        if category == "image_gen"
        else "",
    }


def apply_endpoint_to_active(settings: UserSettings, category: Category, endpoint: dict[str, str]) -> UserSettings:
    c = _cfg(category)
    patch: dict[str, str] = {
        c["api_key"]: endpoint.get("api_key") or "",
        c["base_url"]: endpoint.get("base_url") or "",
        c["model"]: endpoint.get("model") or "",
        c["active"]: endpoint.get("id") or "",
    }
    if category == "image_gen":
        patch["image_gen_fallback_urls"] = endpoint.get("fallback_urls") or ""
    return settings.merge(patch)


def upsert_endpoint(
    settings: UserSettings,
    category: Category,
    *,
    endpoint_id: str = "",
    name: str = "",
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    fallback_urls: str | None = None,
    preserve_key_if_empty: bool = True,
) -> UserSettings:
    """将当前表单写入自定义列表（新增或更新）并设为 active。"""
    endpoints = deepcopy(get_endpoints(settings, category))
    active = snapshot_from_active(settings, category)
    eid = (endpoint_id or get_active_id(settings, category) or "").strip() or new_endpoint_id()
    existing = find_endpoint(endpoints, eid)
    key_val = active["api_key"] if api_key is None else api_key
    if preserve_key_if_empty and not str(key_val or "").strip() and existing:
        key_val = existing.get("api_key") or ""

    if name and str(name).strip():
        display_name = str(name).strip()
    elif existing and existing.get("name"):
        display_name = str(existing.get("name")).strip()
    else:
        display_name = "未命名"

    entry = {
        "id": eid,
        "name": display_name,
        "api_key": key_val,
        "base_url": active["base_url"] if base_url is None else (base_url or "").strip(),
        "model": active["model"] if model is None else (model or "").strip(),
        "fallback_urls": active["fallback_urls"]
        if fallback_urls is None
        else (fallback_urls or "").strip(),
    }

    replaced = False
    for idx, item in enumerate(endpoints):
        if item.get("id") == eid:
            endpoints[idx] = entry
            replaced = True
            break
    if not replaced:
        endpoints.append(entry)

    c = _cfg(category)
    merged = settings.merge(
        {
            c["endpoints"]: endpoints,
            c["active"]: eid,
            c["provider"]: provider_id_for_endpoint(eid),
            c["api_key"]: entry["api_key"],
            c["base_url"]: entry["base_url"],
            c["model"]: entry["model"],
        }
    )
    if category == "image_gen":
        merged = merged.merge({"image_gen_fallback_urls": entry["fallback_urls"]})
    return merged


def switch_custom_endpoint(settings: UserSettings, category: Category, endpoint_id: str) -> UserSettings:
    endpoints = get_endpoints(settings, category)
    ep = find_endpoint(endpoints, endpoint_id)
    if not ep:
        return settings
    c = _cfg(category)
    merged = apply_endpoint_to_active(settings, category, ep)
    return merged.merge({c["provider"]: provider_id_for_endpoint(endpoint_id)})


def delete_custom_endpoint(settings: UserSettings, category: Category, endpoint_id: str) -> UserSettings:
    eid = (endpoint_id or "").strip()
    endpoints = [e for e in get_endpoints(settings, category) if e.get("id") != eid]
    c = _cfg(category)
    current = active_provider_id(settings, category)
    patch: dict[str, object] = {c["endpoints"]: endpoints}
    deleting_active = endpoint_id_from_provider(current) == eid or get_active_id(settings, category) == eid
    if deleting_active:
        if endpoints:
            merged = settings.merge(patch)
            return switch_custom_endpoint(merged, category, endpoints[0]["id"])
        default = _DEFAULT_BUILTIN[category]
        merged = settings.merge({c["endpoints"]: endpoints, c["active"]: ""})
        if category == "llm":
            from friday.llm_profiles import switch_llm_provider

            return switch_llm_provider(merged, default)
        from friday.category_profiles import switch_category_profile

        return switch_category_profile(merged, category, default)
    return settings.merge(patch)


def add_blank_endpoint(settings: UserSettings, category: Category, *, name: str = "") -> UserSettings:
    endpoints = deepcopy(get_endpoints(settings, category))
    eid = new_endpoint_id()
    label = (name or "").strip() or f"配置 {len(endpoints) + 1}"
    entry = {
        "id": eid,
        "name": label,
        "api_key": "",
        "base_url": "",
        "model": "",
        "fallback_urls": "",
    }
    endpoints.append(entry)
    c = _cfg(category)
    pid = provider_id_for_endpoint(eid)
    merged = settings.merge({c["endpoints"]: endpoints, c["active"]: eid, c["provider"]: pid})
    return apply_endpoint_to_active(merged, category, entry)


def seed_custom_endpoints(settings: UserSettings, category: Category) -> UserSettings:
    if get_endpoints(settings, category):
        return settings
    provider = str(getattr(settings, _cfg(category)["provider"], "") or "").strip()
    if provider != "custom" and not is_custom_provider_id(provider):
        return settings
    snap = snapshot_from_active(settings, category)
    if not any(snap.values()):
        return settings
    name = snap["model"] or snap["base_url"] or "默认配置"
    updated = upsert_endpoint(
        settings,
        category,
        name=name[:40],
        api_key=snap["api_key"],
        base_url=snap["base_url"],
        model=snap["model"],
        fallback_urls=snap["fallback_urls"],
        preserve_key_if_empty=False,
    )
    c = _cfg(category)
    active = get_active_id(updated, category)
    if active:
        return updated.merge({c["provider"]: provider_id_for_endpoint(active)})
    return updated


def seed_all_custom_endpoints(settings: UserSettings) -> UserSettings:
    for cat in _CATEGORY:
        settings = seed_custom_endpoints(settings, cat)
    return settings


def masked_key(api_key: str) -> str:
    key = (api_key or "").strip()
    if not key:
        return "未设置"
    if len(key) <= 8:
        return "****"
    return f"{key[:4]}...{key[-4:]}"


def endpoints_summary(settings: UserSettings, category: Category) -> list[dict[str, object]]:
    active = get_active_id(settings, category)
    out: list[dict[str, object]] = []
    for ep in get_endpoints(settings, category):
        key = (ep.get("api_key") or "").strip()
        configured = bool(key and key not in {"sk-your-key-here"})
        out.append(
            {
                "id": ep["id"],
                "name": ep["name"],
                "configured": configured,
                "api_key_masked": masked_key(key),
                "base_url": ep.get("base_url") or "",
                "model": ep.get("model") or "",
                "fallback_urls": ep.get("fallback_urls") or "",
                "provider_id": provider_id_for_endpoint(ep["id"]),
                "active": ep["id"] == active or provider_id_for_endpoint(ep["id"]) == active_provider_id(settings, category),
            }
        )
    return out


def switch_category_provider(settings: UserSettings, category: Category, new_provider_id: str) -> UserSettings:
    """切换视觉/生图服务商（含用户自定义条目）。"""
    if category == "llm":
        from friday.llm_profiles import switch_llm_provider

        return switch_llm_provider(settings, new_provider_id)

    from friday.category_profiles import switch_category_profile

    return switch_category_profile(settings, category, new_provider_id)


def merge_custom_settings(current: UserSettings, payload: dict) -> UserSettings | None:
    category = str(payload.get("custom_endpoint_category") or "").strip()
    if category not in _CATEGORY:
        if payload.get("switch_vision_profile") and payload.get("vision_provider"):
            return switch_category_provider(current, "vision", str(payload["vision_provider"]))
        if payload.get("switch_image_gen_profile") and payload.get("image_gen_provider"):
            return switch_category_provider(current, "image_gen", str(payload["image_gen_provider"]))
        return None

    if payload.get("switch_custom_endpoint") and payload.get("custom_endpoint_id"):
        updated = switch_custom_endpoint(current, category, str(payload["custom_endpoint_id"]))
        c = _cfg(category)
        return updated.merge({c["provider"]: provider_id_for_endpoint(str(payload["custom_endpoint_id"]))})

    if payload.get("add_custom_endpoint"):
        name = str(payload.get("custom_endpoint_name") or "").strip()
        return add_blank_endpoint(current, category, name=name)

    if payload.get("delete_custom_endpoint") and payload.get("custom_endpoint_id"):
        return delete_custom_endpoint(current, category, str(payload["custom_endpoint_id"]))

    return None


def persist_custom_on_save(settings: UserSettings, payload: dict) -> UserSettings:
    """保存设置时，若当前为用户自定义条目则同步到列表。"""
    for category, c in _CATEGORY.items():
        provider_field = c["provider"]
        if provider_field not in payload and not is_custom_provider(settings, category):
            continue
        provider = str(payload.get(provider_field) or getattr(settings, provider_field, "") or "").strip()
        if not is_custom_provider_id(provider):
            continue
        eid = endpoint_id_from_provider(provider) or str(payload.get("custom_endpoint_id") or get_active_id(settings, category))
        settings = upsert_endpoint(
            settings,
            category,
            endpoint_id=eid or "",
            name=str(payload.get("custom_endpoint_name") or "").strip(),
            preserve_key_if_empty=True,
        )
        if eid:
            settings = settings.merge({provider_field: provider_id_for_endpoint(eid)})
    return settings
