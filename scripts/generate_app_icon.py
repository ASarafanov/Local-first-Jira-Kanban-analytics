from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter


ROOT_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = ROOT_DIR / "assets"
ICONSET_DIR = ASSETS_DIR / "app_icon.iconset"
MASTER_ICON_PATH = ASSETS_DIR / "app_icon_1024.png"


def _lerp(a: int, b: int, t: float) -> int:
    return round(a + (b - a) * t)


def _gradient_background(size: int) -> Image.Image:
    image = Image.new("RGBA", (size, size))
    pixels = image.load()

    top = (11, 24, 39)
    bottom = (35, 87, 104)
    glow = (255, 147, 76)

    for y in range(size):
        ty = y / max(size - 1, 1)
        base = tuple(_lerp(top[i], bottom[i], ty) for i in range(3))
        for x in range(size):
            dx = (x - size * 0.76) / size
            dy = (y - size * 0.2) / size
            dist = math.sqrt(dx * dx + dy * dy)
            glow_strength = max(0.0, 1.0 - dist / 0.42) ** 2
            color = tuple(
                min(255, _lerp(base[i], glow[i], glow_strength * 0.5)) for i in range(3)
            )
            pixels[x, y] = (*color, 255)

    rounded_mask = Image.new("L", (size, size), 0)
    mask_draw = ImageDraw.Draw(rounded_mask)
    radius = round(size * 0.23)
    mask_draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=255)

    image.putalpha(rounded_mask)
    return image


def _draw_backplates(draw: ImageDraw.ImageDraw, size: int) -> None:
    plate_w = size * 0.14
    gap = size * 0.05
    start_x = size * 0.18
    top = size * 0.18
    bottom = size * 0.82
    colors = [
        (255, 255, 255, 34),
        (255, 255, 255, 22),
        (255, 255, 255, 14),
    ]
    for index, color in enumerate(colors):
        x0 = start_x + index * (plate_w + gap)
        x1 = x0 + plate_w
        draw.rounded_rectangle((x0, top, x1, bottom), radius=size * 0.05, fill=color)


def _draw_k(size: int) -> Image.Image:
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    ivory = (246, 241, 231, 255)
    accent = (255, 170, 92, 255)
    stroke = round(size * 0.112)

    # Main letterform uses rounded strokes so the icon stays crisp at small sizes.
    draw.line(
        [(size * 0.33, size * 0.23), (size * 0.33, size * 0.77)],
        fill=ivory,
        width=stroke,
        joint="curve",
    )
    draw.line(
        [(size * 0.37, size * 0.5), (size * 0.67, size * 0.24)],
        fill=ivory,
        width=stroke,
        joint="curve",
    )
    draw.line(
        [(size * 0.37, size * 0.5), (size * 0.69, size * 0.78)],
        fill=ivory,
        width=stroke,
        joint="curve",
    )

    # Warm accent bar hints at flow/throughput without cluttering the glyph.
    accent_w = round(size * 0.045)
    draw.line(
        [(size * 0.61, size * 0.22), (size * 0.61, size * 0.79)],
        fill=accent,
        width=accent_w,
        joint="curve",
    )
    return layer


def _compose_master_icon(size: int = 1024) -> Image.Image:
    base = _gradient_background(size)
    content = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    content_draw = ImageDraw.Draw(content)
    _draw_backplates(content_draw, size)

    shadow = _draw_k(size)
    alpha = shadow.getchannel("A").point(lambda value: round(value * 0.45))
    shadow = Image.new("RGBA", (size, size), (6, 15, 26, 255))
    shadow.putalpha(alpha)
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=size * 0.03))
    shadow = ImageChops.offset(shadow, round(size * 0.012), round(size * 0.018))

    glyph = _draw_k(size)
    composed = Image.alpha_composite(base, content)
    composed = Image.alpha_composite(composed, shadow)
    composed = Image.alpha_composite(composed, glyph)
    return composed


def _write_iconset(master_icon: Image.Image) -> None:
    sizes = {
        "icon_16x16.png": 16,
        "icon_16x16@2x.png": 32,
        "icon_32x32.png": 32,
        "icon_32x32@2x.png": 64,
        "icon_128x128.png": 128,
        "icon_128x128@2x.png": 256,
        "icon_256x256.png": 256,
        "icon_256x256@2x.png": 512,
        "icon_512x512.png": 512,
        "icon_512x512@2x.png": 1024,
    }

    ICONSET_DIR.mkdir(parents=True, exist_ok=True)
    for filename, size in sizes.items():
        resized = master_icon.resize((size, size), Image.Resampling.LANCZOS)
        resized.save(ICONSET_DIR / filename)


def main() -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    master_icon = _compose_master_icon()
    master_icon.save(MASTER_ICON_PATH)
    _write_iconset(master_icon)


if __name__ == "__main__":
    main()
