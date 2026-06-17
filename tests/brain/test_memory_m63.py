from __future__ import annotations

from friday.memory_events import events_path, log_memory_event
from friday.memory_search import search_saved_memory
from friday.tools.memory_tools import search_past_conversations
from friday.tools.memory_tools import search_saved_memory as tool_search_saved


def test_log_memory_event(tmp_path, monkeypatch):
    monkeypatch.setattr("friday.memory_events.get_appdata_dir", lambda: tmp_path)
    log_memory_event("remember", "abc", detail="测试记忆")
    path = events_path()
    assert path.exists()
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert "remember" in lines[0]
    assert "测试记忆" in lines[0]


def test_search_saved_memory_user_and_workspace(tmp_path, monkeypatch):
    monkeypatch.setattr("friday.user_memory.get_appdata_dir", lambda: tmp_path)
    monkeypatch.setattr(
        "friday.memory_search.resolved_workspace",
        lambda _cfg: str(tmp_path / "workspace"),
    )
    monkeypatch.setattr(
        "friday.memory_search.load_memory",
        lambda _ws: "- 项目使用 Python 3.12\n- 默认工作区 D:\\Friday",
    )

    from friday.user_memory import remember_fact

    remember_fact("下载默认保存到 E盘")
    hits = search_saved_memory("Python")
    assert any(h.get("source") == "workspace_memory" for h in hits)
    hits2 = search_saved_memory("E盘")
    assert any(h.get("source") == "user_memory" for h in hits2)


def test_search_past_conversations_tool(tmp_appdata, monkeypatch):
    from friday.history_index import ensure_schema
    from friday.sessions import create_session, save_agent_state

    ensure_schema()
    session = create_session("工具搜索", activate=False)
    save_agent_state(
        session.id,
        [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "帮我整理 Friday 配置文件"},
        ],
        user_text="整理配置",
    )
    out = search_past_conversations("Friday", limit=5)
    assert "Friday" in out
    assert "未找到" not in out


def test_search_saved_memory_tool(tmp_path, monkeypatch):
    monkeypatch.setattr("friday.user_memory.get_appdata_dir", lambda: tmp_path)
    monkeypatch.setattr("friday.memory_search.resolved_workspace", lambda _cfg: "/tmp/ws")
    monkeypatch.setattr("friday.memory_search.load_memory", lambda _ws: "")

    from friday.user_memory import remember_fact

    remember_fact("喜欢用深色主题")
    out = tool_search_saved("深色")
    assert "深色" in out
