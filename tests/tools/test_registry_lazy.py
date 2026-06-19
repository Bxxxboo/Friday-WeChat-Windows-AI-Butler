from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from friday.tools.registry import _IMPORTED, TOOL_DEFINITIONS, ensure_all_tools, get_tool_definitions

_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_lazy_modules_not_loaded_at_import():
    """documents/media/web 仍按需加载；registry import 时不预加载任何子模块。"""
    code = """
import friday.tools.registry as reg
assert "documents" in reg._LAZY_MODULES
assert "media" in reg._LAZY_MODULES
assert "web" in reg._LAZY_MODULES
assert reg._IMPORTED == set(), reg._IMPORTED
"""
    subprocess.run([sys.executable, "-c", code], check=True, cwd=str(_REPO_ROOT))


def test_eager_tools_loaded_on_demand():
    from friday.tools.registry import TOOL_DEFINITIONS, _IMPORTED, _ensure_eager_tools

    _ensure_eager_tools()
    assert "filesystem" in _IMPORTED
    names = {d["function"]["name"] for d in TOOL_DEFINITIONS}
    assert "list_directory" in names
    assert "update_session_plan" in names


def test_lazy_modules_load_on_demand():
    ensure_all_tools()
    names = {d["function"]["name"] for d in get_tool_definitions()}
    assert "create_docx" in names
    assert "read_pdf" in names
    assert "documents" in _IMPORTED
    assert "media" in _IMPORTED
