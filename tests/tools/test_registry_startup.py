"""registry 冷 import 不应加载工具子模块。"""

from __future__ import annotations

import subprocess
import sys


def test_registry_import_does_not_load_tool_modules():
    code = """
import friday.tools.registry as reg
assert reg._IMPORTED == set(), reg._IMPORTED
assert reg.TOOL_DEFINITIONS == []
assert reg.TOOL_MAP == {}
"""
    subprocess.run([sys.executable, "-c", code], check=True, cwd=str(__import__("pathlib").Path(__file__).resolve().parents[2]))
