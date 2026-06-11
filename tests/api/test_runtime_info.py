from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import friday.server as server_mod
from friday.auth import ensure_api_token
from friday.runtime_info import runtime_info_payload


def test_runtime_info_dev_mode_warns_python_in_task_manager(monkeypatch, tmp_path):
    fake_pythonw = tmp_path / "pythonw.exe"
    fake_pythonw.write_text("", encoding="utf-8")
    monkeypatch.setattr("friday.runtime_info.sys.executable", str(fake_pythonw))
    with patch("friday.runtime_info.is_frozen", return_value=False):
        with patch("friday.runtime_info._agent_runner_path", return_value=("", "")):
            payload = runtime_info_payload()

    assert payload["run_mode"] == "dev"
    assert payload["run_mode_label"] == "开发"
    assert payload["main_process_name"] == "pythonw.exe"
    assert "任务管理器" in str(payload["task_manager_hint"])
    assert "Python" in str(payload["task_manager_hint"])


def test_runtime_info_packaged_mode(monkeypatch, tmp_path):
    friday_exe = tmp_path / "Friday.exe"
    friday_exe.write_text("", encoding="utf-8")
    agent = tmp_path / "Scripts" / "FridayAgent.exe"
    agent.parent.mkdir(parents=True)
    agent.write_text("", encoding="utf-8")
    monkeypatch.setattr("friday.runtime_info.sys.executable", str(friday_exe))
    with patch("friday.runtime_info.is_frozen", return_value=True):
        with patch(
            "friday.runtime_info.resolve_packaged_exe_in_dir",
            return_value=friday_exe.resolve(),
        ):
            with patch(
                "friday.runtime_info._agent_runner_path",
                return_value=(str(agent).replace("\\", "/"), "FridayAgent.exe"),
            ):
                payload = runtime_info_payload()

    assert payload["run_mode"] == "packaged"
    assert payload["main_process_name"] == "Friday.exe"
    assert payload["agent_runner_name"] == "FridayAgent.exe"
    assert "星期五" in str(payload["task_manager_hint"])
    assert "FridayAgent" in str(payload["task_manager_hint"])


def test_api_version_includes_runtime_info(tmp_appdata):
    server_mod._backend_ready = True
    client = TestClient(server_mod.app)
    token = ensure_api_token()
    res = client.get("/api/version", headers={"X-Friday-Token": token})
    assert res.status_code == 200
    data = res.json()
    assert "version" in data
    assert data.get("run_mode") in {"dev", "packaged"}
    assert data.get("task_manager_hint")

def test_runtime_info_dev_includes_agent_runner_when_present(monkeypatch, tmp_path):
    fake_pythonw = tmp_path / "pythonw.exe"
    fake_pythonw.write_text("", encoding="utf-8")
    monkeypatch.setattr("friday.runtime_info.sys.executable", str(fake_pythonw))
    agent_path = "E:/ws/.python-env/Scripts/FridayAgent.exe"
    with patch("friday.runtime_info.is_frozen", return_value=False):
        with patch(
            "friday.runtime_info._agent_runner_path",
            return_value=(agent_path, "FridayAgent.exe"),
        ):
            payload = runtime_info_payload()

    assert payload["run_mode"] == "dev"
    assert payload["agent_runner_name"] == "FridayAgent.exe"
    assert payload["agent_runner"] == agent_path
