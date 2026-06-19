from __future__ import annotations

from friday.goal_verifier import should_verify, verify_goal_complete
from friday.sessions import create_session, save_session_fields
from friday.storage import UserSettings


def test_should_verify_open_todos(tmp_appdata):
    session = create_session("goal", activate=False)
    save_session_fields(
        session.id,
        todos=[{"text": "压缩备份", "done": False}],
    )
    settings = UserSettings(goal_verifier_enabled=True, context_smart_enabled=True)
    assert should_verify(session.id, "任务已完成，请查收。", settings=settings)


def test_verify_blocks_with_open_todos(tmp_appdata):
    session = create_session("goal2", activate=False)
    save_session_fields(
        session.id,
        todos=[{"text": "上传报告", "done": False}],
    )
    settings = UserSettings(goal_verifier_enabled=True, context_smart_enabled=True)
    result = verify_goal_complete(session.id, "已经全部完成了。", settings=settings)
    assert result.get("block") is True


def test_should_not_verify_partial_step_without_open_todos(tmp_appdata):
    session = create_session("部分完成", activate=False)
    save_session_fields(
        session.id,
        plan_markdown="1. 整理桌面\n2. 压缩旧文件\n3. 清理回收站",
        todos=[{"text": "整理桌面", "done": True}, {"text": "压缩旧文件", "done": True}],
    )
    settings = UserSettings(goal_verifier_enabled=True, context_smart_enabled=True)
    assert should_verify(session.id, "步骤 1 已完成，继续压缩。", settings=settings) is False


def test_parse_llm_json_strips_markdown_fence():
    from friday.goal_verifier import _parse_llm_json

    raw = '```json\n{"complete": false, "reason": "还差一步"}\n```'
    data = _parse_llm_json(raw)
    assert data["complete"] is False
    assert "还差" in data["reason"]


def test_verify_blocks_weixin_claim_without_evidence(tmp_appdata, monkeypatch):
    session = create_session("weixin-ev", activate=False)
    settings = UserSettings(
        goal_verifier_enabled=True,
        goal_verifier_evidence_required=True,
        context_smart_enabled=True,
    )
    monkeypatch.setattr(type(settings), "api_ready", property(lambda self: False))
    reply = "已成功发送给张三，请查收。"
    result = verify_goal_complete(session.id, reply, settings=settings, evidence=[])
    assert result.get("block") is True
    assert "微信" in str(result.get("reason", ""))


def test_verify_allows_weixin_with_success_evidence(tmp_appdata, monkeypatch):
    session = create_session("weixin-ok", activate=False)
    settings = UserSettings(
        goal_verifier_enabled=True,
        goal_verifier_evidence_required=True,
        context_smart_enabled=True,
    )
    monkeypatch.setattr(type(settings), "api_ready", property(lambda self: False))
    evidence = [{
        "tool": "send_weixin_contact_message",
        "success": True,
        "result": "已发送给 张三",
        "summary": "发微信",
        "args": {},
    }]
    reply = "已成功发送给张三。"
    result = verify_goal_complete(session.id, reply, settings=settings, evidence=evidence)
    assert result.get("block") is not True


def test_verify_skips_evidence_gate_when_disabled(tmp_appdata, monkeypatch):
    session = create_session("weixin-off", activate=False)
    settings = UserSettings(
        goal_verifier_enabled=True,
        goal_verifier_evidence_required=False,
        context_smart_enabled=True,
    )
    monkeypatch.setattr(type(settings), "api_ready", property(lambda self: False))
    reply = "已成功发送给张三。"
    result = verify_goal_complete(session.id, reply, settings=settings, evidence=[])
    assert result.get("block") is not True


def test_casual_reply_not_blocked_by_stale_missing_path(tmp_appdata, monkeypatch):
    from friday.goal_evidence import check_evidence_gates

    settings = UserSettings(goal_verifier_enabled=True, goal_verifier_evidence_required=True)
    monkeypatch.setattr(type(settings), "api_ready", property(lambda self: False))
    evidence = [{
        "tool": "write_text_file",
        "success": True,
        "args": {"path": "E:\\no-such-file.txt"},
        "result": "已写入",
    }]
    result = check_evidence_gates("好的，还有别的需要吗？", evidence)
    assert result is None


def test_historical_weixin_summary_not_blocked(tmp_appdata):
    from friday.goal_evidence import check_evidence_gates

    result = check_evidence_gates(
        "之前已成功发送给张三的内容如下：……",
        evidence=[],
    )
    assert result is None


def test_path_gate_blocks_when_completion_claimed(tmp_appdata):
    from friday.goal_evidence import check_evidence_gates

    evidence = [{
        "tool": "write_text_file",
        "success": True,
        "args": {"path": "E:\\missing-report.docx"},
        "result": "已写入",
    }]
    result = check_evidence_gates("报告已完成，文件在 E:\\missing-report.docx", evidence)
    assert result is not None
    assert result.get("block") is True


def test_collect_session_evidence_respects_since(tmp_appdata):
    import time

    from friday.goal_evidence import collect_session_evidence
    from friday.operations import log_operation

    session_id = "sess-turn-filter"
    old_ts = time.time() - 3600
    log_operation("list_directory", {"path": "C:\\"}, "ok-old", session_id=session_id)
    # 模拟旧记录：直接写入带旧 ts 不可行，用 since 过滤新记录
    since = time.time()
    time.sleep(0.01)
    log_operation("read_text_file", {"path": "x.txt"}, "ok-new", session_id=session_id)
    bundle = collect_session_evidence(session_id, since=since)
    assert len(bundle) == 1
    assert bundle[0]["tool"] == "read_text_file"
