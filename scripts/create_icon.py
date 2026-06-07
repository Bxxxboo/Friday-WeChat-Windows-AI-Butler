from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ICON_PATH = ROOT / "assets" / "friday.ico"

# 与 web/styles.css 品牌色一致
BG_TOP = (10, 13, 18)
ACCENT = (212, 160, 86)
ACCENT_HI = (240, 204, 140)

ICON_SIZES = (256, 128, 64, 48, 32, 24, 16)


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name, scale in (("msyhbd.ttc", 1.0), ("msyh.ttc", 1.05), ("simhei.ttf", 1.0)):
        try:
            return ImageFont.truetype(name, max(8, int(size * scale)))
        except OSError:
            continue
    return ImageFont.load_default()


def render_icon(size: int) -> Image.Image:
    """按目标尺寸单独渲染，保证 16px 任务栏也清晰。"""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    pad = max(1, size // 14)
    radius = max(3, size // 5)
    border = max(1, size // 28)
    outer = (pad, pad, size - pad - 1, size - pad - 1)

    draw.rounded_rectangle(outer, radius=radius, fill=ACCENT)

    # 内缩 1px 覆盖描边抗锯齿缝，消除金框与底色之间的白线
    overlap = 1
    inner = (
        outer[0] + border - overlap,
        outer[1] + border - overlap,
        outer[2] - border + overlap,
        outer[3] - border + overlap,
    )
    inner_r = max(1, radius - border + overlap)
    draw.rounded_rectangle(inner, radius=inner_r, fill=BG_TOP + (255,))

    font_scale = 0.56 if size >= 32 else 0.62
    font = _load_font(int(size * font_scale))
    text = "五"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = (size - tw) // 2 - bbox[0]
    ty = (size - th) // 2 - bbox[1] + max(0, size // 32)

    if size >= 48:
        draw.text((tx + 1, ty + 2), text, fill=(0, 0, 0, 180), font=font)
        draw.text((tx, ty - 1), text, fill=ACCENT_HI, font=font)
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
    frames = [render_icon(s) for s in ICON_SIZES]
    frames[0].save(
        ICON_PATH,
        format="ICO",
        sizes=[(s, s) for s in ICON_SIZES],
        append_images=frames[1:],
    )
    print(f"created: {ICON_PATH}")


if __name__ == "__main__":
    main()
