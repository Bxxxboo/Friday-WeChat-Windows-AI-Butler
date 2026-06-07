from __future__ import annotations

import json
from pathlib import Path

import pytest

from friday.plugins import (
    format_plugin_catalog,
    install_github_skill,
    install_local_plugin,
    install_plugin,
    install_plugin_from_manifest,
    list_plugins,
    parse_github_skill_source,
    parse_github_source,
    resolve_plugin_source,
    resolve_plugin_source,
    uninstall_plugin,
)
from friday.rules import active_rules_prompt, create_rule, list_rules, update_rule
from friday.skills import list_skills, update_skill


_DEMO_MANIFEST = {
    "id": "demo-office",
    "name": "办公增强示例包",
    "version": "1.0.0",
    "description": "测试插件",
    "skills": [
        {
            "id": "standup",
            "label": "站会摘要",
            "icon": "🗣️",
            "category": "plugin",
            "prompt": "写站会摘要",
        }
    ],
    "rules": [
        {
            "id": "concise",
            "title": "简洁回复",
            "content": "回答要简洁。",
            "enabled": True,
            "always_apply": True,
        }
    ],
}


def test_parse_github_source_variants():
    assert parse_github_source("octocat/repo") == ("octocat", "repo", "main")
    assert parse_github_source("octocat/repo@dev") == ("octocat", "repo", "dev")
    assert parse_github_source("https://github.com/octocat/repo") == ("octocat", "repo", "main")
    assert parse_github_source("https://github.com/octocat/repo/tree/main") == ("octocat", "repo", "main")


def test_create_rule_and_prompt(tmp_appdata):
    create_rule({"title": "测试规则", "content": "始终用列表回答。"})
    rules = list_rules()
    assert any(r["title"] == "测试规则" for r in rules)
    prompt = active_rules_prompt()
    assert "测试规则" in prompt
    assert "始终用列表回答" in prompt


def test_disable_rule_excludes_from_prompt(tmp_appdata):
    rule = create_rule({"title": "临时", "content": "内容", "always_apply": True})
    update_rule(rule["id"], {"enabled": False})
    assert "临时" not in active_rules_prompt()


def test_install_plugin_from_manifest(tmp_appdata):
    entry = install_plugin_from_manifest(_DEMO_MANIFEST, source="local")
    assert entry["id"] == "demo-office"
    assert entry["skill_count"] == 1
    assert entry["rule_count"] == 1

    plugins = list_plugins()
    assert len(plugins) == 1

    skills = list_skills(include_disabled=True)
    assert any(s["id"] == "demo-office:standup" and s["source"] == "plugin" for s in skills)

    rules = list_rules()
    assert any(r["id"] == "demo-office:concise" and r["source"] == "plugin" for r in rules)

    prompt = active_rules_prompt()
    assert "简洁回复" in prompt


def test_toggle_plugin_skill(tmp_appdata):
    install_plugin_from_manifest(_DEMO_MANIFEST, source="local")
    skill_id = "demo-office:standup"
    update_skill(skill_id, {"enabled": False})
    enabled = [s for s in list_skills(include_disabled=False) if s["id"] == skill_id]
    assert enabled == []


def test_uninstall_plugin(tmp_appdata):
    install_plugin_from_manifest(_DEMO_MANIFEST, source="local")
    assert uninstall_plugin("demo-office")
    assert list_plugins() == []
    assert not any(s.get("plugin_id") == "demo-office" for s in list_skills(include_disabled=True))
    assert not any(r.get("plugin_id") == "demo-office" for r in list_rules())


def test_install_local_demo_plugin(tmp_appdata):
    entry = install_local_plugin("demo-office")
    assert entry["id"] == "demo-office"
    assert entry["skill_count"] >= 1
    assert entry["rule_count"] >= 1


def test_install_plugin_local_prefix(tmp_appdata):
    entry = install_plugin("local:demo-office")
    assert entry["name"] == "办公增强示例包"


def test_parse_github_skill_source():
    assert parse_github_skill_source("octocat/repo/my-skill") == (
        "octocat", "repo", "main", "my-skill",
    )
    assert parse_github_skill_source("octocat/repo@dev/my-skill") == (
        "octocat", "repo", "dev", "my-skill",
    )


def test_resolve_plugin_source_storage_analyzer():
    resolved = resolve_plugin_source("storage-analyzer")
    assert resolved == "skill:KKKKhazix/khazix-skills/storage-analyzer"
    # 猜错的 owner/repo 若末尾是已知插件 id，也会纠正到推荐来源
    assert resolve_plugin_source("friday-ai/storage-analyzer") == (
        "skill:KKKKhazix/khazix-skills/storage-analyzer"
    )


def test_install_github_skill_storage_analyzer(tmp_appdata, monkeypatch):
    """从 GitHub 安装 storage-analyzer（mock 下载）。"""
    sample_manifest = {
        "id": "storage-analyzer",
        "name": "Storage Analyzer",
        "version": "1.0.0",
        "description": "test",
        "author": "test",
        "skills": [{
            "id": "storage-analyzer",
            "label": "存储分析",
            "icon": "💾",
            "category": "plugin",
            "prompt": "读 {plugin_dir}/SKILL.md",
        }],
        "rules": [],
    }

    def fake_download(owner, repo, ref, skill_path, dest):
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "SKILL.md").write_text("# Storage Analyzer\n", encoding="utf-8")
        (dest / "scripts").mkdir(exist_ok=True)
        (dest / "scripts" / "scan.py").write_text("print('ok')\n", encoding="utf-8")

    monkeypatch.setattr(
        "friday.plugins._download_github_skill_folder",
        fake_download,
    )
    monkeypatch.setattr(
        "friday.paths.extensions_dir",
        lambda: Path(__file__).resolve().parents[1] / "extensions",
    )

    entry = install_github_skill("KKKKhazix/khazix-skills/storage-analyzer")
    assert entry["id"] == "storage-analyzer"
    assert entry["skill_count"] == 2

    skills = list_skills(include_disabled=True)
    assert any(s["id"] == "storage-analyzer:storage-analyzer" for s in skills)
    skill = next(s for s in skills if s["id"] == "storage-analyzer:storage-analyzer")
    assert "{plugin_dir}" not in skill["prompt"]
    assert "SKILL.md" in skill["prompt"]
