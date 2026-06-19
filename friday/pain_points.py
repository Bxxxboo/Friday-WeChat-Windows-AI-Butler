"""结构化踩坑记忆 —— tag + symptom/cause/fix。"""

from __future__ import annotations

import time
import uuid
from typing import Any

from friday.io_utils import atomic_write_json, load_json
from friday.paths import get_appdata_dir

MAX_PAIN_POINTS = 40
_TAG_RE = __import__("re").compile(r"^[a-z0-9_]{2,32}$")


def _store_path():
    return get_appdata_dir() / "pain_points.json"


def load_pain_points() -> list[dict[str, Any]]:
    data = load_json(_store_path()) or {}
    items = data.get("points") or []
    if not isinstance(items, list):
        return []
    out: list[dict[str, Any]] = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        tag = str(raw.get("tag", "")).strip().lower()
        symptom = str(raw.get("symptom", "")).strip()
        if not tag or not symptom:
            continue
        out.append({
            "id": str(raw.get("id") or uuid.uuid4().hex[:10]),
            "tag": tag,
            "symptom": symptom[:240],
            "cause": str(raw.get("cause", "")).strip()[:240],
            "fix": str(raw.get("fix", "")).strip()[:240],
            "seen_at": float(raw.get("seen_at") or 0),
        })
    out.sort(key=lambda x: float(x.get("seen_at") or 0), reverse=True)
    return out[:MAX_PAIN_POINTS]


def _save_points(points: list[dict[str, Any]]) -> None:
    atomic_write_json(
        _store_path(),
        {"points": points[:MAX_PAIN_POINTS], "version": 1},
    )


def remember_pain_point(
    tag: str,
    symptom: str,
    *,
    cause: str = "",
    fix: str = "",
) -> dict[str, Any]:
    cleaned_tag = str(tag or "").strip().lower().replace("-", "_")
    cleaned_symptom = str(symptom or "").strip()
    if not cleaned_tag or not _TAG_RE.match(cleaned_tag):
        return {"ok": False, "message": "tag 须为 2-32 位小写字母/数字/下划线"}
    if not cleaned_symptom:
        return {"ok": False, "message": "symptom 不能为空"}
    now = time.time()
    points = load_pain_points()
    for item in points:
        if item["tag"] == cleaned_tag:
            item["symptom"] = cleaned_symptom[:240]
            item["cause"] = str(cause or "").strip()[:240]
            item["fix"] = str(fix or "").strip()[:240]
            item["seen_at"] = now
            _save_points(points)
            return {"ok": True, "message": "已更新踩坑记录", "id": item["id"], "tag": cleaned_tag}
    entry = {
        "id": uuid.uuid4().hex[:10],
        "tag": cleaned_tag,
        "symptom": cleaned_symptom[:240],
        "cause": str(cause or "").strip()[:240],
        "fix": str(fix or "").strip()[:240],
        "seen_at": now,
    }
    points.insert(0, entry)
    _save_points(points)
    return {"ok": True, "message": "已记录踩坑", "id": entry["id"], "tag": cleaned_tag}


def search_pain_points(query: str, *, limit: int = 10) -> list[dict[str, Any]]:
    raw = str(query or "").strip().casefold()
    if not raw:
        return []
    cap = max(1, min(limit, 20))
    hits: list[dict[str, Any]] = []
    for item in load_pain_points():
        tag = item["tag"]
        blob = " ".join([tag, item["symptom"], item["cause"], item["fix"]]).casefold()
        tag_match = raw == tag or raw in tag or tag in raw
        text_match = raw in blob
        if not tag_match and not text_match:
            continue
        score = 2 if tag_match else 1
        hits.append({**item, "score": score, "source": "pain_point"})
    hits.sort(key=lambda x: (-int(x.get("score", 0)), -float(x.get("seen_at", 0))))
    return hits[:cap]


def format_pain_point_line(item: dict[str, Any]) -> str:
    parts = [f"[{item.get('tag', '')}] {item.get('symptom', '')}"]
    if item.get("cause"):
        parts.append(f"原因：{item['cause']}")
    if item.get("fix"):
        parts.append(f"处理：{item['fix']}")
    return "；".join(parts)
