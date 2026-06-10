"""打包后必须能 import 的全部工具模块。"""

import importlib

import pytest

from friday.tools.registry import _EAGER_MODULES, _LAZY_MODULES


@pytest.mark.parametrize("name", [* _EAGER_MODULES, *_LAZY_MODULES])
def test_tools_module_importable(name: str):
    mod = importlib.import_module(f"friday.tools.{name}")
    assert mod is not None
