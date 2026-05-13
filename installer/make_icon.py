"""Generate installer/melody-sheet.ico from a programmatic design.

The design echoes the app's editorial visual identity: matte charcoal field
with a single stark serif glyph plus a few staff lines. The output is a
multi-resolution Windows ICO (16, 24, 32, 48, 64, 128, 256 px) that the
PyInstaller spec and Inno Setup script both consume.

Run:
    apps/api/.venv/bin/python installer/make_icon.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


OUTPUT = Path(__file__).resolve().parent / "melody-sheet.ico"
SIZES = [16, 24, 32, 48, 64, 128, 256]

# Brand palette (editorial / matte) — match the Tailwind config from apps/web.
BG = (24, 24, 24)          # near-black ink
INK = (250, 246, 240)      # ivory cream
STAFF = (250, 246, 240, 110)  # translucent staff lines
ACCENT = (140, 50, 60)     # matte burgundy (rosin tone)


# Try a few fonts that ship with macOS / Windows / Linux that have nice
# serif italic glyphs. Fall back to Pillow's default font if none load.
SERIF_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Times New Roman Italic.ttf",
    "/System/Library/Fonts/Supplemental/Georgia Italic.ttf",
    "/System/Library/Fonts/Supplemental/Baskerville.ttc",
    "/Library/Fonts/Georgia.ttf",
    "C:\\Windows\\Fonts\\timesi.ttf",
    "C:\\Windows\\Fonts\\georgiai.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVu-Serif-Italic.ttf",
]


def _load_serif(size: int) -> ImageFont.FreeTypeFont:
    for path in SERIF_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size, index=0)
            except Exception:
                continue
    return ImageFont.load_default()


def _draw_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), BG + (255,))
    draw = ImageDraw.Draw(img)

    # Staff lines — 5 horizontal lines spanning the middle. Skip on tiny sizes.
    if size >= 32:
        staff_top = int(size * 0.30)
        staff_height = int(size * 0.36)
        line_spacing = staff_height / 4
        staff_left = int(size * 0.12)
        staff_right = size - staff_left
        line_width = max(1, size // 64)
        for i in range(5):
            y = staff_top + int(i * line_spacing)
            draw.line(
                [(staff_left, y), (staff_right, y)],
                fill=STAFF,
                width=line_width,
            )

    # Big serif "M" centered, slight downward bias to balance staff above.
    # On very small icons the M alone reads as MelodySheet's monogram.
    glyph = "M"
    target_height_ratio = 0.80 if size >= 32 else 0.92
    # Iterate to find the largest font size whose rendered glyph still fits.
    chosen_size = int(size * target_height_ratio)
    while chosen_size > 6:
        font = _load_serif(chosen_size)
        bbox = draw.textbbox((0, 0), glyph, font=font)
        gw = bbox[2] - bbox[0]
        gh = bbox[3] - bbox[1]
        if gw <= size * 0.78 and gh <= size * target_height_ratio:
            break
        chosen_size -= 1
    font = _load_serif(chosen_size)
    bbox = draw.textbbox((0, 0), glyph, font=font)
    gw = bbox[2] - bbox[0]
    gh = bbox[3] - bbox[1]
    gx = (size - gw) // 2 - bbox[0]
    # Lift the glyph just slightly into the upper-mid so it intersects staff.
    gy = (size - gh) // 2 - bbox[1] - int(size * 0.02)
    draw.text((gx, gy), glyph, font=font, fill=INK)

    # Small accent: rosin-colored dot at the right baseline ("note" placement).
    if size >= 24:
        dot_radius = max(2, size // 32)
        dot_x = int(size * 0.78)
        dot_y = int(size * 0.66)
        draw.ellipse(
            [
                (dot_x - dot_radius, dot_y - dot_radius),
                (dot_x + dot_radius, dot_y + dot_radius),
            ],
            fill=ACCENT,
        )

    return img


def main() -> int:
    frames = [_draw_icon(sz) for sz in SIZES]
    largest = frames[-1]
    largest.save(
        OUTPUT,
        format="ICO",
        sizes=[(sz, sz) for sz in SIZES],
        append_images=frames[:-1],
    )
    print(f"Wrote {OUTPUT} ({OUTPUT.stat().st_size} bytes, {len(SIZES)} sizes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
