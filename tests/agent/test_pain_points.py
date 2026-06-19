"""结构化踩坑记忆与检索。"""

from __future__ import annotations

from friday.memory_search import search_saved_memory
from friday.pain_points import load_pain_points, remember_pain_point, search_pain_points


def test_remember_pain_point_merge_same_tag(tmp_path, monkeypatch):
    monkeypatch.setattr("friday.pain_points.get_appdata_dir", lambda: tmp_path)

    first = remember_pain_point("weixin_send", "微信消息发送失败", cause="未登录", fix="重启微信")
    assert first["ok"] is True
    assert len(load_pain_points()) == 1

    second = remember_pain_point("weixin_send", "发送超时", fix="检查网络")
    assert second["ok"] is True
    points = load_pain_points()
    assert len(points) == 1
    assert points[0]["symptom"] == "发送超时"
    assert points[0]["fix"] == "检查网络"


def test_search_pain_points_by_keyword(tmp_path, monkeypatch):
    monkeypatch.setattr("friday.pain_points.get_appdata_dir", lambda: tmp_path)
    remember_pain_point("api_key", "DeepSeek 401", fix="更新 API Key")
    hits = search_pain_points("401")
    assert len(hits) == 1
    assert hits[0]["tag"] == "api_key"


def test_search_saved_memory_includes_pain_points(tmp_path, monkeypatch):
    monkeypatch.setattr("friday.pain_points.get_appdata_dir", lambda: tmp_path)
    monkeypatch.setattr("friday.user_memory.get_appdata_dir", lambda: tmp_path)
    remember_pain_point("weixin_send", "微信发送失败", fix="检查联系人名")
    hits = search_saved_memory("weixin_send", limit=5)
    assert any(h.get("source") == "pain_point" for h in hits)
