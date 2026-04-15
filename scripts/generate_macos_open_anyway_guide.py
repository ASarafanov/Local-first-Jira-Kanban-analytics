from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = ROOT_DIR / "assets"
OUTPUT_PATH = ASSETS_DIR / "open_anyway_guide.png"
ICON_PATH = ASSETS_DIR / "app_icon_1024.png"


def _load_font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = []
    if bold:
        candidates.extend(
            [
                "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                "/System/Library/Fonts/Supplemental/Helvetica.ttc",
                "/System/Library/Fonts/Supplemental/GillSans.ttc",
            ]
        )
    else:
        candidates.extend(
            [
                "/System/Library/Fonts/Supplemental/Arial.ttf",
                "/System/Library/Fonts/Supplemental/Helvetica.ttc",
                "/System/Library/Fonts/Supplemental/GillSans.ttc",
            ]
        )
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, font, fill, *, anchor: str | None = None) -> None:
    draw.text(xy, text, font=font, fill=fill, anchor=anchor)


def _rounded_panel(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill, outline=None, width: int = 1, radius: int = 28) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _bullet(draw: ImageDraw.ImageDraw, x: int, y: int, number: int, font, fill_bg, fill_text) -> None:
    radius = 24
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill_bg)
    _text(draw, (x, y + 1), str(number), font, fill_text, anchor="mm")


def main() -> None:
    width, height = 1600, 1120
    image = Image.new("RGBA", (width, height), "#f4efe7")
    draw = ImageDraw.Draw(image)

    title_font = _load_font(64, bold=True)
    subtitle_font = _load_font(32)
    section_font = _load_font(28, bold=True)
    body_font = _load_font(24)
    small_font = _load_font(20)
    bullet_font = _load_font(28, bold=True)

    # Background glow.
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse((1020, -120, 1650, 520), fill=(31, 126, 115, 110))
    glow_draw.ellipse((-220, 620, 420, 1200), fill=(255, 179, 120, 95))
    glow = glow.filter(ImageFilter.GaussianBlur(90))
    image = Image.alpha_composite(image, glow)
    draw = ImageDraw.Draw(image)

    # Header.
    draw.multiline_text(
        (110, 74),
        "How to open the app\non macOS",
        font=title_font,
        fill="#1e1b18",
        spacing=4,
    )
    _text(
        draw,
        (110, 232),
        "If macOS blocks Kanban Metrics because it can’t verify it, use Open Anyway once.",
        subtitle_font,
        "#5f5a54",
    )

    if ICON_PATH.exists():
        icon = Image.open(ICON_PATH).convert("RGBA").resize((84, 84), Image.Resampling.LANCZOS)
        image.alpha_composite(icon, (1430, 48))

    # Main split layout.
    left_box = (68, 234, 778, 1032)
    right_box = (820, 234, 1532, 1032)
    _rounded_panel(draw, left_box, fill=(252, 249, 244, 240), outline="#e2d8cb", width=2, radius=36)
    _rounded_panel(draw, right_box, fill=(252, 249, 244, 240), outline="#e2d8cb", width=2, radius=36)

    # Left: steps.
    _text(draw, (112, 292), "Steps for the user", section_font, "#2b2622")
    steps = [
        "Double-click the app or the copy in Applications.",
        "When macOS shows the warning, close the dialog.",
        "Open System Settings > Privacy & Security.",
        "Scroll down and click Open Anyway for Kanban Metrics.",
        "Confirm one more time when macOS asks to open it.",
    ]
    y = 374
    for index, step in enumerate(steps, start=1):
        _bullet(draw, 124, y + 6, index, bullet_font, "#16786e", "#ffffff")
        draw.multiline_text((168, y - 18), step, font=body_font, fill="#3f3934", spacing=6)
        y += 110

    note_box = (104, 842, 742, 1014)
    _rounded_panel(draw, note_box, fill="#dff0ea", outline="#b4d7cd", width=2, radius=24)
    _text(draw, (130, 902), "Tip", section_font, "#176e64")
    draw.multiline_text(
        (130, 934),
        "The Open Anyway button usually appears after the first\nblocked launch attempt and may only stay visible for\nabout an hour.",
        font=small_font,
        fill="#35534d",
        spacing=6,
    )

    # Right: faux system settings view.
    _text(draw, (864, 292), "What to look for", section_font, "#2b2622")
    settings_box = (864, 334, 1488, 972)
    _rounded_panel(draw, settings_box, fill="#ffffff", outline="#d9d2c9", width=2, radius=28)
    sidebar_box = (886, 358, 1108, 948)
    _rounded_panel(draw, sidebar_box, fill="#f5f2ec", outline="#ece5db", width=1, radius=20)
    _text(draw, (918, 404), "Privacy & Security", body_font, "#2a2623")
    _text(draw, (918, 446), "This Mac allows apps from:", small_font, "#857d73")

    chip_box = (918, 478, 1068, 524)
    _rounded_panel(draw, chip_box, fill="#e6f2ee", outline="#c7ddd6", width=1, radius=16)
    _text(draw, (993, 501), "App Store", small_font, "#1a6f65", anchor="mm")

    content_x = 1140
    _text(draw, (content_x, 404), "Security", body_font, "#2a2623")
    warning_box = (1140, 448, 1458, 650)
    _rounded_panel(draw, warning_box, fill="#fff4eb", outline="#f0ceb2", width=2, radius=20)
    _text(draw, (1168, 486), "Kanban Metrics was blocked", section_font, "#8f4b11")
    draw.multiline_text(
        (1168, 530),
        "macOS couldn’t verify the app.\nTo continue, use Open Anyway below.",
        font=small_font,
        fill="#7a5a40",
        spacing=8,
    )

    button_box = (1214, 780, 1448, 848)
    shadow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rounded_rectangle((button_box[0], button_box[1] + 8, button_box[2], button_box[3] + 8), radius=20, fill=(22, 73, 66, 70))
    shadow = shadow.filter(ImageFilter.GaussianBlur(8))
    image.alpha_composite(shadow)
    draw = ImageDraw.Draw(image)
    _rounded_panel(draw, button_box, fill="#1b7c70", outline="#156a60", width=2, radius=20)
    _text(draw, ((button_box[0] + button_box[2]) // 2, (button_box[1] + button_box[3]) // 2), "Open Anyway", section_font, "#ffffff", anchor="mm")

    arrow_points = [(1188, 734), (1240, 770), (1248, 756), (1294, 804), (1278, 814), (1232, 766), (1222, 782)]
    draw.line(arrow_points, fill="#d46f38", width=10, joint="curve")

    footer_box = (68, 1048, 1532, 1100)
    _rounded_panel(draw, footer_box, fill=(255, 255, 255, 190), outline="#e1d9cf", width=1, radius=20)
    _text(
        draw,
        (800, 1074),
        "Best long-term fix: distribute a Developer ID signed and notarized build so Gatekeeper allows normal launch.",
        small_font,
        "#5b554f",
        anchor="mm",
    )

    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(OUTPUT_PATH, format="PNG", optimize=True)


if __name__ == "__main__":
    main()
