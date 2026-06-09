"""将星期五主模型切换为小米 MiMo（Key 仅从环境变量读取，不落盘到仓库）。"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

MIMO_BASE_URL = "https://api.xiaomimimo.com/v1"
DEFAULT_MODEL = os.environ.get("MIMO_MODEL", "mimo-v2-flash").strip() or "mimo-v2-flash"
ENCRYPTION_PREFIX = "fernet:"


def _appdata_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    return Path(base) / "Friday"


def _encrypt_key(plaintext: str, key_path: Path) -> str:
    if not plaintext:
        return ""
    from cryptography.fernet import Fernet

    if key_path.is_file():
        f = Fernet(key_path.read_bytes())
    else:
        key = Fernet.generate_key()
        key_path.write_bytes(key)
        f = Fernet(key)
    token = f.encrypt(plaintext.encode("utf-8"))
    return ENCRYPTION_PREFIX + token.decode("utf-8")


def main() -> int:
    api_key = (os.environ.get("MIMO_API_KEY") or os.environ.get("FRIDAY_MIMO_API_KEY") or "").strip()
    if not api_key:
        print("请设置环境变量 MIMO_API_KEY 后再运行本脚本。", file=sys.stderr)
        print("示例：$env:MIMO_API_KEY='sk-...'; python scripts/configure-mimo.py", file=sys.stderr)
        return 1

    appdata = _appdata_dir()
    settings_path = appdata / "settings.json"
    if not settings_path.is_file():
        print(f"未找到 settings.json：{settings_path}", file=sys.stderr)
        return 1

    data = json.loads(settings_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        print("settings.json 格式无效", file=sys.stderr)
        return 1

    data["api_key"] = _encrypt_key(api_key)
    data["base_url"] = MIMO_BASE_URL
    data["model"] = DEFAULT_MODEL
    data["llm_provider"] = "mimo"
    profiles = data.get("llm_profiles") if isinstance(data.get("llm_profiles"), dict) else {}
    profiles["mimo"] = {
        "api_key": data["api_key"],
        "base_url": MIMO_BASE_URL,
        "model": DEFAULT_MODEL,
    }
    data["llm_profiles"] = profiles

    backup = settings_path.with_suffix(".json.bak")
    if settings_path.is_file():
        backup.write_bytes(settings_path.read_bytes())
    settings_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    masked = api_key[:7] + "…" + api_key[-4:] if len(api_key) > 12 else "（已保存）"
    print(f"已写入 {settings_path}")
    print(f"base_url={MIMO_BASE_URL} model={DEFAULT_MODEL} key={masked}")
    print("请重启星期五或在设置里点「测试连接」验证。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
