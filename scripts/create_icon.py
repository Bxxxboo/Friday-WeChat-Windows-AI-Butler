from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ICON_PATH = ROOT / "assets" / "friday.ico"

# 与启动加载动画 .app-boot-mark / splash 一致：暖色底 + 金色「五」
BG_TOP = (250, 247, 242)
BG_BOTTOM = (240, 233, 224)
ACCENT = (184, 134, 46)
ACCENT_HI = (201, 153, 72)
BORDER = (212, 196, 168)

ICON_SIZES = (256, 128, 64, 48, 32, 24, 16)


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name, scale in (("msyhbd.ttc", 1.0), ("msyh.ttc", 1.05), ("simhei.ttf", 1.0)):
        try:
            return ImageFont.truetype(name, max(8, int(size * scale)))
        except OSError:
            continue
    return ImageFont.load_default()


def _draw_vertical_gradient(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    radius: int,
    top: tuple[int, int, int],
    bottom: tuple[int, int, int],
) -> None:
    x0, y0, x1, y1 = box
    height = max(1, y1 - y0 + 1)
    for y in range(y0, y1 + 1):
        t = (y - y0) / max(1, height - 1)
        color = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        draw.rounded_rectangle((x0, y, x1, y), radius=radius, fill=color)


def render_icon(size: int) -> Image.Image:
    """按目标尺寸单独渲染，保证 16px 任务栏也清晰。"""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    pad = max(1, size // 16)
    radius = max(4, int(size * 0.31))
    outer = (pad, pad, size - pad - 1, size - pad - 1)

    _draw_vertical_gradient(draw, outer, radius, BG_TOP, BG_BOTTOM)

    border_w = max(1, size // 64)
    draw.rounded_rectangle(outer, radius=radius, outline=BORDER + (255,), width=border_w)

    font_scale = 0.52 if size >= 32 else 0.58
    font = _load_font(int(size * font_scale))
    text = "五"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = (size - tw) // 2 - bbox[0]
    ty = (size - th) // 2 - bbox[1] + max(0, size // 40)

    if size >= 48:
        draw.text((tx, ty + 1), text, fill=(160, 120, 40, 90), font=font)
        draw.text((tx, ty - 1), text, fill=ACCENT_HI + (220,), font=font)
    draw.text((tx, ty), text, fill=ACCENT, font=font)

    return _flatten_icon(img, outer, radius)


def _flatten_icon(
    img: Image.Image,
    outer: tuple[int, int, int, int],
    radius: int,
) -> Image.Image:
    """圆角矩形外透明、内部全部不透明，供 Windows ICO 使用。"""
    w, h = img.size
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle(outer, radius=radius, fill=255)
    flat = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    flat.paste(img, mask=mask)
    rgb = flat.convert("RGB")
    out = rgb.convert("RGBA")
    out.putalpha(mask)
    return out


def main() -> None:
    ICON_PATH.parent.mkdir(parents=True, exist_ok=True)
    # 256 主图 + sizes 让 Pillow 写入多分辨率（append_images 在部分版本只存一帧）
    master = render_icon(256).convert("RGBA")
    master.save(
        ICON_PATH,
        format="ICO",
        sizes=[(s, s) for s in ICON_SIZES],
    )
    print(f"created: {ICON_PATH}")


if __name__ == "__main__":
    main()
