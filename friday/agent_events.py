"""Agent WebSocket / 回调事件名常量。"""

from __future__ import annotations

EVENT_AGENT_STEP = "agent_step"
EVENT_ASSISTANT_START = "assistant_start"
EVENT_ASSISTANT_DELTA = "assistant_delta"
EVENT_ASSISTANT_CLEAR = "assistant_clear"
EVENT_REASONING_DELTA = "reasoning_delta"
EVENT_CONTEXT_REBUILD = "context_rebuild"
EVENT_ASK_BLOCKED = "ask_blocked"
EVENT_APPROVAL_AUTO = "approval_auto"
EVENT_TOOL_START = "tool_start"
EVENT_PROGRESS = "progress"
EVENT_FILE_CHANGE = "file_change"
EVENT_OPERATION_LOGGED = "operation_logged"
EVENT_FILE_GENERATED = "file_generated"
EVENT_IMAGE_GENERATED = "image_generated"
EVENT_PLAN_UPDATED = "plan_updated"
