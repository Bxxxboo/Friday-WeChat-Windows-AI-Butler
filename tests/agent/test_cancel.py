from __future__ import annotations

import threading
import time

from friday.tools.registry import CANCELLED_TOOL_MESSAGE, TOOL_MAP, execute_tool


def test_execute_tool_respects_cancel_event():
    cancel = threading.Event()

    def slow_tool() -> str:
        time.sleep(5)
        return "done"

    TOOL_MAP["test_slow_cancel"] = slow_tool
    try:
        cancel.set()
        result = execute_tool("test_slow_cancel", {}, cancel_event=cancel)
        assert result == CANCELLED_TOOL_MESSAGE
    finally:
        TOOL_MAP.pop("test_slow_cancel", None)
