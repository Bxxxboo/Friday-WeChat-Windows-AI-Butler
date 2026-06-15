from __future__ import annotations

from friday.dream_task import _dedupe_lines, run_dream_if_due
from friday.storage import UserSettings


def test_dream_dedupe_fallback(tmp_path, monkeypatch):
    saved: list[str] = []
    before = "# 工作区记忆\n\n- 规则 A\n- 规则 A\n- 规则 B\n"

    monkeypatch.setattr("friday.dream_task.load_memory", lambda _ws: before)
    monkeypatch.setattr(
        "friday.dream_task.save_memory",
        lambda _ws, content, via="dream": saved.append(content),
    )
    monkeypatch.setattr("friday.dream_task.memory_path", lambda _ws: tmp_path / "MEMORY.md")
    monkeypatch.setattr("friday.dream_task._distill_with_llm", lambda *_a, **_k: None)
    monkeypatch.setattr("friday.dream_task._mark_ran", lambda: None)

    cfg = UserSettings(dream_memory_enabled=True)
    cfg.api_key = ""
    result = run_dream_if_due(settings=cfg, force=True)
    assert result["ok"] is True
    assert result["ran"] is True
    assert saved
    assert saved[0].count("规则 A") == 1


def test_dedupe_lines_removes_near_duplicates():
    text = "规则一\n规则一\n规则二"
    out = _dedupe_lines(text)
    assert out.count("规则一") == 1
    assert "规则二" in out
