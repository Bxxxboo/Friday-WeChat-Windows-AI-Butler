from __future__ import annotations

from friday.tools.registry import parse_tool_arguments


def test_parse_tool_arguments_empty():
    assert parse_tool_arguments("") == {}


def test_parse_tool_arguments_valid():
    assert parse_tool_arguments('{"path": "a.txt"}') == {"path": "a.txt"}


def test_parse_tool_arguments_invalid_json():
    result = parse_tool_arguments("{not-json")
    assert "__parse_error__" in result
