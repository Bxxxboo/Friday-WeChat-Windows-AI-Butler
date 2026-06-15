from __future__ import annotations

from friday.user_memory import forget_fact, format_for_prompt, load_facts, remember_fact


def test_remember_and_forget_fact(tmp_path, monkeypatch):
    monkeypatch.setattr("friday.user_memory.get_appdata_dir", lambda: tmp_path)
    monkeypatch.setattr("friday.memory_events.get_appdata_dir", lambda: tmp_path)
    first = remember_fact("下载软件默认保存到 E:\\软件")
    assert first["ok"] is True
    facts = load_facts()
    assert len(facts) == 1
    assert "E:\\软件" in facts[0]["text"]

    dup = remember_fact("下载软件默认保存到 E:\\软件")
    assert dup["ok"] is True
    assert len(load_facts()) == 1

    prompt = format_for_prompt()
    assert "用户长期偏好" in prompt
    assert "E:\\软件" in prompt

    removed = forget_fact("E:\\软件")
    assert removed["ok"] is True
    assert load_facts() == []


def test_remember_logs_event(tmp_path, monkeypatch):
    monkeypatch.setattr("friday.user_memory.get_appdata_dir", lambda: tmp_path)
    monkeypatch.setattr("friday.memory_events.get_appdata_dir", lambda: tmp_path)
    remember_fact("测试偏好")
    path = tmp_path / "memory_events.jsonl"
    assert path.exists()
    assert "remember" in path.read_text(encoding="utf-8")
