"""Vision Bridge — 通过豆包/Ark 多模态模型识别图片。
Reasonix Code 专用：直接运行，返回图片的文字描述。

用法：
  python .reasonix/scripts/vision_bridge.py <图片路径> [可选: 自定义提示词]

依赖：cryptography（用于解密 Friday 的 Fernet 密钥）
配置来源：%APPDATA%/Friday/settings.json + .fernet_key
"""

import base64
import json
import os
import sys
import urllib.request
from pathlib import Path

SETTINGS_PATH = Path(os.environ["APPDATA"]) / "Friday" / "settings.json"
FERNET_KEY_PATH = Path(os.environ["APPDATA"]) / "Friday" / ".fernet_key"

VISION_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_PROMPT = "请详细描述这张图片中显示的内容，包括任何错误信息、文字、界面元素。如果是中文界面请保留原文。"


def _decrypt_fernet(stored: str) -> str:
    if not stored or not stored.startswith("fernet:"):
        return stored
    from cryptography.fernet import Fernet

    key = FERNET_KEY_PATH.read_bytes()
    f = Fernet(key)
    token = stored[len("fernet:"):].encode()
    return f.decrypt(token).decode()


def _load_vision_config() -> dict:
    settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    return {
        "api_key": _decrypt_fernet(settings.get("vision_api_key", "")),
        "base_url": settings.get("vision_base_url", VISION_BASE_URL).rstrip("/"),
        "model": settings.get("vision_model", ""),
        "enabled": settings.get("vision_enabled", False),
    }


def describe_image(image_path: str, prompt: str = "") -> str:
    """调用 Ark Vision API 识别图片，返回文字描述。"""
    cfg = _load_vision_config()
    if not cfg["enabled"] or not cfg["api_key"]:
        return "[vision-bridge] 视觉辅助未启用或未配置 API Key"

    img_path = Path(image_path)
    if not img_path.is_file():
        return f"[vision-bridge] 图片不存在: {image_path}"

    # 读取并编码图片
    ext = img_path.suffix.lower()
    mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp"}
    mime = mime_map.get(ext, "image/png")
    with open(img_path, "rb") as fh:
        img_b64 = base64.b64encode(fh.read()).decode()

    user_prompt = prompt.strip() or DEFAULT_PROMPT

    payload = {
        "model": cfg["model"],
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{img_b64}"}},
                {"type": "text", "text": user_prompt},
            ]
        }],
        "max_tokens": 1024,
    }

    url = f"{cfg['base_url']}/chat/completions"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg['api_key']}",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            content = result["choices"][0]["message"]["content"]
            return content
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:500]
        return f"[vision-bridge] HTTP {e.code}: {body}"
    except Exception as e:
        return f"[vision-bridge] 请求失败: {e}"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python vision_bridge.py <图片路径> [自定义提示]")
        sys.exit(1)

    image_path = sys.argv[1]
    custom_prompt = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""
    result = describe_image(image_path, custom_prompt)
    print(result)
