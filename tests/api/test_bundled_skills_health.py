"""内置 skill warmup 状态与 /api/health 暴露（P0-2）。"""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

import friday.bundled as bundled_mod
import friday.server as server_mod
from friday.health_check import build_health_payload


def test_bundled_skills_health_ready_when_assets_complete(tmp_appdata, monkeypatch):
    monkeypatch.setattr(bundled_mod, "_skill_warmup", {})
    monkeypatch.setattr(bundled_mod, "bundled_skill_assets_ready", lambda _pid: True)

    payload = build_health_payload(backend_ready=True)
    bs = payload["services"]["bundled_skills"]
    assert bs["status"] == "ok"
    assert bs["skills"]["ppt-master"]["status"] == "ready"


def test_bundled_skills_health_degraded_when_pending(tmp_appdata, monkeypatch):
    monkeypatch.setattr(
        bundled_mod,
        "_skill_warmup",
        {"ppt-master": {"status": "pending", "detail": "资源准备中"}},
    )

    payload = build_health_payload(backend_ready=True)
    bs = payload["services"]["bundled_skills"]
    assert bs["status"] == "degraded"
    assert "准备中" in bs["detail"]
    assert bs["skills"]["ppt-master"]["status"] == "pending"
    assert payload.get("degraded") is True


def test_bundled_skills_health_degraded_when_failed(tmp_appdata, monkeypatch):
    monkeypatch.setattr(
        bundled_mod,
        "_skill_warmup",
        {"ppt-master": {"status": "failed", "detail": "network error"}},
    )

    payload = build_health_payload(backend_ready=True)
    bs = payload["services"]["bundled_skills"]
    assert bs["status"] == "degraded"
    assert bs["skills"]["ppt-master"]["status"] == "failed"


def test_api_health_includes_bundled_skills(tmp_appdata, monkeypatch):
    monkeypatch.setattr(
        bundled_mod,
        "_skill_warmup",
        {"ppt-master": {"status": "ready", "detail": "已就绪"}},
    )
    server_mod._backend_ready = True
    client = TestClient(server_mod.app)

    res = client.get("/api/health")
    assert res.status_code == 200
    bs = res.json()["services"]["bundled_skills"]
    assert bs["skills"]["ppt-master"]["status"] == "ready"
