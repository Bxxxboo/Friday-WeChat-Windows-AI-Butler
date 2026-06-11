"""CLI：为 embed / 工作区 Python 创建 FridayAgent.exe（供 brand-agent-python.ps1 调用）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from friday.python_env import (  # noqa: E402
    AGENT_RUNNER_NAME,
    brand_embed_agent_python,
    brand_workspace_agent_python,
)


def main() -> int:
    workspace = (sys.argv[1] if len(sys.argv) > 1 else "").strip()
    embed_only = (sys.argv[2] if len(sys.argv) > 2 else "") == "1"
    out: dict[str, str | None] = {
        "embed": None,
        "workspace": None,
        "runner_name": AGENT_RUNNER_NAME,
    }
    embed = brand_embed_agent_python()
    if embed is not None:
        out["embed"] = str(embed)
    if not embed_only and workspace:
        ws_runner = brand_workspace_agent_python(workspace)
        if ws_runner is not None:
            out["workspace"] = str(ws_runner)
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
