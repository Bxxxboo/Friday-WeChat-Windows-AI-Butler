from __future__ import annotations

from friday.tools.registry import TOOL_DEFINITIONS, _IMPORTED, ensure_all_tools, get_tool_definitions


def test_eager_tools_loaded_without_lazy_modules():
    assert "list_directory" in {d["function"]["name"] for d in TOOL_DEFINITIONS}
    assert "documents" not in _IMPORTED
    assert "media" not in _IMPORTED


def test_lazy_modules_load_on_demand():
    ensure_all_tools()
    names = {d["function"]["name"] for d in get_tool_definitions()}
    assert "create_docx" in names
    assert "read_pdf" in names
    assert "documents" in _IMPORTED
    assert "media" in _IMPORTED
