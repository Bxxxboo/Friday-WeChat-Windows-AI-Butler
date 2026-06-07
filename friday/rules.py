"""行为规则 —— 注入系统提示词，持久化到 rules.json。"""

from __future__ import annotations

import time
import uuid
from typing import Any

from friday.io_utils import atomic_write_json, load_json
from friday.logging_config import get_logger
from friday.paths import get_appdata_dir

_log = get_logger("rules")


def _store_path():
    return get_appdata_dir() / "rules.json"


def _normalize_rule(raw: dict[str, Any], *, source: str = "custom", plugin_id: str = "") -> dict[str, Any]:
    return {
        "id": str(raw.get("id", uuid.uuid4().hex[:10])),
        "title": str(raw.get("title", "未命名规则")).strip(),
        "content": str(raw.get("content", "")).strip(),
        "enabled": bool(raw.get("enabled", True)),
        "always_apply": bool(raw.get("always_apply", True)),
        "source": str(raw.get("source", source)),
        "plugin_id": str(raw.get("plugin_id", plugin_id)),
        "created_at": float(raw.get("created_at", time.time())),
    }


def _load_all() -> list[dict[str, Any]]:
    raw = load_json(_store_path())
    if not isinstance(raw, list):
        return []
    return [_normalize_rule(item) for item in raw if isinstance(item, dict)]


def _save_all(items: list[dict[str, Any]]) -> None:
    atomic_write_json(_store_path(), items)


def list_rules(*, include_disabled: bool = True) -> list[dict[str, Any]]:
    items = _load_all()
    if include_disabled:
        return items
    return [r for r in items if r.get("enabled")]


def get_rule(rule_id: str) -> dict[str, Any] | None:
    for rule in _load_all():
        if rule["id"] == rule_id:
            return rule
    return None


def create_rule(payload: dict[str, Any]) -> dict[str, Any]:
    rule = _normalize_rule({
        **payload,
        "id": uuid.uuid4().hex[:10],
        "source": "custom",
        "created_at": time.time(),
    })
    items = _load_all()
    items.append(rule)
    _save_all(items)
    return rule


def update_rule(rule_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    items = _load_all()
    for idx, rule in enumerate(items):
        if rule["id"] != rule_id:
            continue
        if rule.get("source") == "plugin" and any(k in payload for k in ("title", "content")):
            continue
        merged = rule.copy()
        for key in ("title", "content", "enabled", "always_apply"):
            if key in payload and payload[key] is not None:
                merged[key] = payload[key]
        items[idx] = _normalize_rule(merged, source=rule.get("source", "custom"), plugin_id=rule.get("plugin_id", ""))
        _save_all(items)
        return items[idx]
    return None


def delete_rule(rule_id: str) -> bool:
    rule = get_rule(rule_id)
    if rule is None:
        return False
    if rule.get("source") == "plugin":
        return False
    items = [r for r in _load_all() if r["id"] != rule_id]
    _save_all(items)
    return True


def remove_plugin_rules(plugin_id: str) -> int:
    items = [r for r in _load_all() if r.get("plugin_id") != plugin_id]
    removed = len(_load_all()) - len(items)
    _save_all(items)
    return removed


def upsert_plugin_rules(plugin_id: str, rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    remaining = [r for r in _load_all() if r.get("plugin_id") != plugin_id]
    imported: list[dict[str, Any]] = []
    for raw in rules:
        rid = f"{plugin_id}:{raw.get('id', uuid.uuid4().hex[:8])}"
        imported.append(_normalize_rule({
            **raw,
            "id": rid,
            "source": "plugin",
            "plugin_id": plugin_id,
        }, source="plugin", plugin_id=plugin_id))
    _save_all(remaining + imported)
    return imported


def active_rules_prompt() -> str:
    """返回应注入系统提示词的规则文本。"""
    active = [r for r in _load_all() if r.get("enabled") and r.get("always_apply")]
    if not active:
        return ""
    lines = ["\n用户自定义规则（必须遵守）："]
    for idx, rule in enumerate(active, 1):
        title = rule.get("title") or f"规则{idx}"
        content = rule.get("content", "").strip()
        if content:
            lines.append(f"{idx}. [{title}] {content}")
    return "\n".join(lines)
