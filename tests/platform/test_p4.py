from __future__ import annotations

import json

from friday.operations import export_operations, log_operation, replay_prompt
from friday.schedules import compute_next_run, create_schedule, mark_schedule_run
from friday.skills import create_skill, delete_skill, list_skills, list_skills_grouped
from friday.updates import _is_newer, check_for_updates


def test_list_skills_includes_builtins():
    skills = list_skills()
    assert len(skills) >= 13
    assert any(s["id"] == "sys-status" and s["builtin"] for s in skills)


def test_create_and_delete_custom_skill(tmp_appdata):
    skill = create_skill({"label": "测试技能", "prompt": "做点什么", "icon": "🧪"})
    assert skill["label"] == "测试技能"
    assert not skill["builtin"]

    all_skills = list_skills()
    assert any(s["id"] == skill["id"] for s in all_skills)

    assert delete_skill(skill["id"])
    assert not any(s["id"] == skill["id"] for s in list_skills())


def test_list_skills_grouped(tmp_appdata):
    create_skill({"label": "自定义", "prompt": "hello"})
    groups = list_skills_grouped()
    cats = {g["category"] for g in groups}
    assert "system" in cats
    assert "custom" in cats


def test_operations_filter_and_replay(tmp_appdata):
    log_operation("write_text_file", {"path": "a.txt"}, "ok", session_id="s1")
    log_operation("list_directory", {"path": "."}, "ok", session_id="s1")

    from friday.operations import list_operations

    writes = list_operations(writes_only=True)
    assert len(writes) == 1
    assert writes[0]["tool"] == "write_text_file"

    prompt = replay_prompt(writes[0]["id"])
    assert prompt and "write_text_file" in prompt


def test_export_operations_json(tmp_appdata):
    log_operation("move_file", {"src": "a", "dst": "b"}, "moved")
    content, media_type, filename = export_operations(format="json", writes_only=True)
    assert filename.endswith(".json")
    assert "application/json" in media_type
    data = json.loads(content)
    assert len(data) >= 1


def test_export_operations_csv(tmp_appdata):
    log_operation("write_text_file", {"path": "x"}, "done")
    content, media_type, filename = export_operations(format="csv")
    assert filename.endswith(".csv")
    assert "text/csv" in media_type
    assert "tool" in content.splitlines()[0]


def test_schedule_interval_next_run():
    nxt = compute_next_run("interval", 9, 0, interval_hours=6, after=1000.0)
    assert nxt == 1000.0 + 6 * 3600


def test_schedule_retry_on_failure(tmp_appdata):
    task = create_schedule({
        "title": "重试测试",
        "prompt": "hello",
        "frequency": "interval",
        "interval_hours": 1,
        "retry_on_failure": True,
        "max_retries": 2,
    })
    updated = mark_schedule_run(task.id, status="error", message="fail")
    assert updated is not None
    assert updated.retry_count == 1
    assert updated.next_run_at is not None


def test_version_compare():
    assert _is_newer("1.0.0", "1.1.0")
    assert not _is_newer("1.2.0", "1.1.0")


def test_check_updates_without_repo():
    info = check_for_updates(repo="")
    assert info.checked is False
    assert info.update_available is False
