from __future__ import annotations

from friday.fast_finish import looks_like_multi_step_task, try_fast_finish_reply
from friday.ppt_task import (
    append_ppt_task_hint,
    is_plugin_list_goal,
    is_ppt_task_context,
)


def test_fast_finish_write_text_file():
    reply = try_fast_finish_reply([
        ("write_text_file", {"path": "a.py"}, "已写入: D:\\work\\a.py"),
    ])
    assert reply is not None
    assert "D:\\work\\a.py" in reply


def test_fast_finish_skips_multi_step_goal():
    reply = try_fast_finish_reply(
        [("write_text_file", {}, "已写入: x.py")],
        user_goal="请重构整个项目的所有文件",
    )
    assert reply is None


def test_fast_finish_skips_many_pending_todos():
    reply = try_fast_finish_reply(
        [("write_text_file", {}, "已写入: x.py")],
        pending_todos=5,
    )
    assert reply is None


def test_fast_finish_generate_image():
    reply = try_fast_finish_reply([
        (
            "generate_image",
            {},
            "已生成图片并保存：D:\\img\\a.png\n实际尺寸：1024x1024，模型：ep-1。",
        ),
    ])
    assert reply is not None
    assert "a.png" in reply


def test_fast_finish_requires_single_tool():
    assert try_fast_finish_reply([
        ("read_text_file", {}, "ok"),
        ("write_text_file", {}, "已写入: x.py"),
    ]) is None


def test_fast_finish_plugin_list_pair():
    reply = try_fast_finish_reply(
        [
            ("list_friday_plugins", {}, "尚未安装任何插件。"),
            ("list_plugin_catalog", {}, "推荐插件：\n- demo"),
        ],
        user_goal="GitHub 上有什么 rules 适合星期五",
    )
    assert reply is not None
    assert "已安装" in reply
    assert "推荐" in reply


def test_fast_finish_plugin_catalog_single():
    reply = try_fast_finish_reply(
        [("list_plugin_catalog", {}, "推荐插件列表")],
        user_goal="有哪些扩展插件",
    )
    assert reply is not None
    assert "推荐插件列表" in reply


def test_fast_finish_skips_plugin_list_for_ppt_goal():
    goal = "根据 docx 做一个复习 PPT"
    assert is_ppt_task_context(goal)
    reply = try_fast_finish_reply(
        [("list_friday_plugins", {}, "共 1 个插件：\n- SciPilot")],
        user_goal=goal,
    )
    assert reply is None


def test_fast_finish_skips_plugin_list_without_plugin_intent():
    reply = try_fast_finish_reply(
        [("list_friday_plugins", {}, "共 1 个插件")],
        user_goal="帮我整理桌面文件",
    )
    assert reply is None


def test_multi_step_hint():
    assert looks_like_multi_step_task("批量修改多个文件")
    assert not looks_like_multi_step_task("把 utils.js 里的 showThinking 改个名")


def test_is_ppt_task_context():
    assert is_ppt_task_context("帮我做一个复习PPT")
    assert is_ppt_task_context("你是用的ppt-master做的吗")
    assert not is_ppt_task_context("有哪些扩展插件")


def test_is_plugin_list_goal_excludes_ppt():
    assert not is_plugin_list_goal("做一个复习 PPT")
    assert is_plugin_list_goal("有哪些 skill 插件")


def test_append_ppt_task_hint_injects_skill_path():
    text = append_ppt_task_hint("请做汇报 pptx")
    assert "ppt-master" in text
    assert "SKILL.md" in text
    assert "禁止 list_friday_plugins" in text


def test_fast_finish_skips_write_in_ppt_project():
    path = r"C:\Users\me\Documents\星期五\ppt_project_ppt169_20260618\design_spec.md"
    reply = try_fast_finish_reply(
        [("write_text_file", {}, f"已写入: {path}")],
        user_goal="确认生成",
    )
    assert reply is None


def test_fast_finish_skips_write_when_ppt_goal_in_history():
    reply = try_fast_finish_reply(
        [("write_text_file", {}, "已写入: D:\\work\\a.py")],
        user_goal="根据 docx 做一个复习 PPT",
    )
    assert reply is None


def test_is_ppt_project_artifact_path():
    from friday.ppt_task import is_ppt_project_artifact_path

    assert is_ppt_project_artifact_path(
        r"C:\Users\me\ppt_project_ppt169_20260618\design_spec.md"
    )
    assert not is_ppt_project_artifact_path(r"D:\work\utils.py")


def test_is_short_confirmation():
    from friday.ppt_task import is_short_confirmation

    assert is_short_confirmation("确认生成")
    assert not is_short_confirmation("根据 docx 做一个复习 PPT")


def test_conversation_in_ppt_task_from_blocking_assistant():
    from friday.ppt_task import conversation_in_ppt_task

    messages = [
        {"role": "user", "content": "根据 docx 做复习 PPT"},
        {"role": "assistant", "content": "八项确认建议… BLOCKING 步骤"},
        {"role": "user", "content": "确认生成"},
    ]
    assert conversation_in_ppt_task(messages)


def test_conversation_in_ppt_task_continue_after_confirm():
    from friday.ppt_task import conversation_in_ppt_task

    messages = [
        {"role": "user", "content": "根据 docx 做复习 PPT"},
        {"role": "assistant", "content": "已保存 design_spec.md"},
        {"role": "user", "content": "继续生成PPT"},
    ]
    assert conversation_in_ppt_task(messages)


def test_fast_finish_skips_copy_in_ppt_project():
    path = (
        r"已复制: C:\a\复习文档.md -> "
        r"C:\Users\me\Documents\星期五\ppt_project_ppt169_20260618\sources\复习文档.md"
    )
    reply = try_fast_finish_reply(
        [("copy_file", {}, path)],
        ppt_session_active=True,
    )
    assert reply is None


def test_fast_finish_skips_create_pptx_during_ppt_session():
    reply = try_fast_finish_reply(
        [("create_pptx", {}, "已创建 PPT: D:\\out.pptx")],
        user_goal="继续",
        ppt_session_active=True,
    )
    assert reply is None


def test_is_ppt_task_context_design_spec_phrases():
    assert is_ppt_task_context("按 design_spec 做 SVG 并导出 pptx")
    assert is_ppt_task_context("继续生成PPT")
