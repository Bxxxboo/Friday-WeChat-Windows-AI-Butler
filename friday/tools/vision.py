"""视觉工具 —— describe_image，桥接豆包等多模态模型。"""

from __future__ import annotations

from friday.storage import load_settings
from friday.tools._decorators import register_tool
from friday.vision import describe_image, vision_ready


@register_tool(
    name="describe_image",
    description=(
        "将本地图片发送给视觉辅助模型（豆包/Ark 等），返回文字描述。"
        "DeepSeek 本身看不懂图片，分析截图、照片、界面、图表时必须先调用此工具。"
        "path 为图片绝对路径（可用 screenshot 工具先截屏）。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "图片文件路径（PNG/JPEG/GIF/WebP）",
            },
            "prompt": {
                "type": "string",
                "description": "可选。对视觉模型的提问，如「读出图中错误信息」",
            },
        },
        "required": ["path"],
    },
)
def describe_image_tool(path: str, prompt: str = "") -> str:
    settings = load_settings()
    return describe_image(settings, path, prompt)


@register_tool(
    name="vision_status",
    description="检查视觉辅助模型（豆包/Ark）是否已在设置中配置",
    parameters={"type": "object", "properties": {}},
)
def vision_status() -> str:
    settings = load_settings()
    if not settings.vision_enabled:
        return "视觉辅助未启用。请在 设置 → API 连接 中开启并填写豆包 API。"
    if not vision_ready(settings):
        return "视觉辅助已启用但未配置 API Key，请在设置中填写。"
    model = settings.vision_model or "（未指定模型/端点）"
    base = settings.vision_base_url or "https://ark.cn-beijing.volces.com/api/v3"
    return f"视觉辅助已就绪\n模型/端点: {model}\nBase URL: {base}"
