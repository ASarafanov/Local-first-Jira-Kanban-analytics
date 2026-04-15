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


def _rounded_panel(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill, outline=None, width: int = 1, radius: int = 28) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, font, fill, *, anchor: str | None = None) -> None:
    draw.text(xy, text, font=font, fill=fill, anchor=anchor)


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        box = draw.textbbox((0, 0), candidate, font=font)
        if box[2] - box[0] <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = word
    if current:
        lines.append(current)
    return lines


def _draw_wrapped_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font,
    fill,
    max_width: int,
    *,
    line_gap: int = 8,
) -> tuple[int, int]:
    x, y = xy
    lines = _wrap_text(draw, text, font, max_width)
    ascent, descent = font.getmetrics() if hasattr(font, "getmetrics") else (20, 6)
    line_height = ascent + descent + line_gap
    for index, line in enumerate(lines):
        draw.text((x, y + index * line_height), line, font=font, fill=fill)
    total_height = max(line_height * len(lines) - line_gap, ascent + descent)
    return max_width, total_height


def _bullet(draw: ImageDraw.ImageDraw, x: int, y: int, number: int, font, fill_bg, fill_text) -> None:
    radius = 23
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill_bg)
    _text(draw, (x, y + 1), str(number), font, fill_text, anchor="mm")


def main() -> None:
    width, height = 1600, 1260
    image = Image.new("RGBA", (width, height), "#f4efe7")
    draw = ImageDraw.Draw(image)

    title_font = _load_font(62, bold=True)
    subtitle_font = _load_font(26)
    section_font = _load_font(30, bold=True)
    body_font = _load_font(24)
    small_font = _load_font(20)
    bullet_font = _load_font(28, bold=True)
    button_font = _load_font(26, bold=True)

    # Background atmosphere.
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse((1080, -160, 1760, 520), fill=(38, 138, 126, 110))
    glow_draw.ellipse((-220, 650, 450, 1230), fill=(255, 178, 118, 95))
    glow = glow.filter(ImageFilter.GaussianBlur(95))
    image = Image.alpha_composite(image, glow)
    draw = ImageDraw.Draw(image)

    # Header.
    header_left = 88
    header_top = 64
    header_width = 1080
    title = "How to open Kanban Metrics on macOS"
    _, title_height = _draw_wrapped_text(
        draw,
        (header_left, header_top),
        title,
        title_font,
        "#1f1b18",
        header_width,
        line_gap=2,
    )
    _draw_wrapped_text(
        draw,
        (header_left, header_top + title_height + 26),
        "If macOS blocks the app because it can’t verify it, use Open Anyway once.",
        subtitle_font,
        "#5c5750",
        1200,
        line_gap=6,
    )

    if ICON_PATH.exists():
        icon = Image.open(ICON_PATH).convert("RGBA").resize((88, 88), Image.Resampling.LANCZOS)
        icon_shell = Image.new("RGBA", (120, 120), (0, 0, 0, 0))
        shell_draw = ImageDraw.Draw(icon_shell)
        shell_draw.rounded_rectangle((10, 10, 110, 110), radius=28, fill=(255, 255, 255, 70))
        icon_shell = icon_shell.filter(ImageFilter.GaussianBlur(5))
        image.alpha_composite(icon_shell, (1380, 40))
        image.alpha_composite(icon, (1396, 56))

    # Main panels.
    left_box = (56, 350, 770, 1156)
    right_box = (828, 350, 1544, 1156)
    _rounded_panel(draw, left_box, fill=(251, 248, 243, 240), outline="#e3d8cb", width=2, radius=34)
    _rounded_panel(draw, right_box, fill=(251, 248, 243, 240), outline="#e3d8cb", width=2, radius=34)

    # Left panel.
    _text(draw, (98, 408), "Steps for the user", section_font, "#2d2824")
    steps = [
        "Double-click the app or its copy in Applications.",
        "When macOS shows the warning, close the dialog.",
        "Open System Settings > Privacy & Security.",
        "Scroll down and click Open Anyway for Kanban Metrics.",
        "Confirm one more time when macOS asks to open it.",
    ]
    y = 480
    for index, step in enumerate(steps, start=1):
        _bullet(draw, 112, y + 10, index, bullet_font, "#1b7c70", "#ffffff")
        _, rendered_height = _draw_wrapped_text(
            draw,
            (154, y - 14),
            step,
            body_font,
            "#413b35",
            540,
            line_gap=6,
        )
        y += max(112, rendered_height + 48)

    note_box = (88, 988, 736, 1142)
    _rounded_panel(draw, note_box, fill="#dbeee8", outline="#b9dbd0", width=2, radius=24)
    _text(draw, (118, 1028), "Tip", section_font, "#1a6f65")
    _draw_wrapped_text(
        draw,
        (118, 1072),
        "The Open Anyway button usually appears after the first blocked launch attempt and may only stay visible for about an hour.",
        small_font,
        "#41605a",
        570,
        line_gap=5,
    )

    # Right panel.
    _text(draw, (870, 406), "What to look for", section_font, "#2d2824")
    _draw_wrapped_text(
        draw,
        (870, 448),
        "The button appears in System Settings after the first blocked launch.",
        small_font,
        "#6f685f",
        560,
        line_gap=4,
    )
    settings_box = (870, 518, 1498, 1102)
    _rounded_panel(draw, settings_box, fill="#ffffff", outline="#ddd5ca", width=2, radius=28)

    # Fake settings window header.
    topbar_box = (896, 540, 1472, 596)
    _rounded_panel(draw, topbar_box, fill="#f5f1eb", outline="#e7ddd1", width=1, radius=18)
    _text(draw, (928, 558), "Privacy & Security", body_font, "#2a2623")
    _text(draw, (1308, 558), "Security", body_font, "#6e655b", anchor="mm")
    _text(draw, (928, 602), "This Mac allows apps from:", small_font, "#8a8177")

    sidebar_box = (896, 634, 1120, 958)
    _rounded_panel(draw, sidebar_box, fill="#f3f0ea", outline="#ebe3d8", width=1, radius=22)
    chip_box = (930, 690, 1088, 738)
    _rounded_panel(draw, chip_box, fill="#e7f3ee", outline="#cae1d8", width=1, radius=17)
    _text(draw, ((chip_box[0] + chip_box[2]) // 2, (chip_box[1] + chip_box[3]) // 2), "App Store", small_font, "#1c6f65", anchor="mm")

    warning_box = (1160, 652, 1462, 880)
    _rounded_panel(draw, warning_box, fill="#fff4eb", outline="#f1cfb2", width=2, radius=22)
    _draw_wrapped_text(
        draw,
        (1188, 694),
        "Kanban Metrics was blocked",
        section_font,
        "#98591c",
        240,
        line_gap=2,
    )
    _draw_wrapped_text(
        draw,
        (1188, 768),
        "macOS couldn’t verify the app. To continue, use Open Anyway below.",
        small_font,
        "#7b5a43",
        238,
        line_gap=6,
    )

    button_box = (1206, 942, 1454, 1014)
    shadow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rounded_rectangle((button_box[0], button_box[1] + 10, button_box[2], button_box[3] + 10), radius=22, fill=(18, 76, 68, 70))
    shadow = shadow.filter(ImageFilter.GaussianBlur(10))
    image.alpha_composite(shadow)
    draw = ImageDraw.Draw(image)
    _rounded_panel(draw, button_box, fill="#1b7c70", outline="#14695f", width=2, radius=22)
    _text(draw, ((button_box[0] + button_box[2]) // 2, (button_box[1] + button_box[3]) // 2), "Open Anyway", button_font, "#ffffff", anchor="mm")

    arrow_color = "#d67a3f"
    shaft_points = [(1148, 914), (1188, 944), (1220, 944), (1248, 964)]
    draw.line(shaft_points, fill=arrow_color, width=7, joint="curve")
    arrow_tip = (1248, 964)
    draw.line([arrow_tip, (1222, 960)], fill=arrow_color, width=7)
    draw.line([arrow_tip, (1238, 938)], fill=arrow_color, width=7)

    footer_box = (60, 1188, 1540, 1236)
    _rounded_panel(draw, footer_box, fill=(255, 255, 255, 185), outline="#e2dbd2", width=1, radius=18)
    _draw_wrapped_text(
        draw,
        (250, 1200),
        "Best long-term fix: distribute a Developer ID signed and notarized build so Gatekeeper allows normal launch.",
        small_font,
        "#5b554f",
        1100,
        line_gap=4,
    )

    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(OUTPUT_PATH, format="PNG", optimize=True)


if __name__ == "__main__":
    main()
