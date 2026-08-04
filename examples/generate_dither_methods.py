"""Generate per-algorithm dither comparison images for docs/dithering.md.

Produces:
  examples/dither_methods_bw.png   — all methods on a B/W palette
  examples/dither_methods_bwr.png  — all methods on a BWR palette
  examples/dither_methods/<method>_{bw,bwr}.png — individual tiles

Usage:
    python examples/generate_dither_methods.py
"""

from __future__ import annotations

import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from imagespec.colors import PALETTE_BW, PALETTE_BWR
from imagespec.dither import DITHER_METHODS, dither_to_palette

ROOT = os.path.abspath(os.path.dirname(__file__))
OUT_DIR = os.path.join(ROOT, "dither_methods")
TILE_W, TILE_H = 256, 128
LABEL_H = 22
PAD = 8
COLS = 4


def _font(size: int = 14):
    for path in (
        os.path.join(os.path.dirname(__file__), "..", "src", "imagespec", "fonts", "DejaVuSans.ttf"),
        r"C:\Windows\Fonts\arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        if os.path.isfile(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                pass
    return ImageFont.load_default()


def source_scene(width: int = TILE_W, height: int = TILE_H) -> Image.Image:
    """Compact scene: rainbow strip, gray ramp, shaded sphere — good dither stress test."""
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    band = height // 3
    for x in range(width):
        t = x / max(width - 1, 1)
        hue = t * 6.0
        sector = int(hue) % 6
        f = hue - int(hue)
        v = 255
        p, q, u = 0, int(v * (1 - f)), int(v * f)
        table = [(v, u, p), (q, v, p), (p, v, u), (p, q, v), (u, p, v), (v, p, q)]
        r, g, b = table[sector]
        draw.line([(x, 0), (x, band - 1)], fill=(r, g, b))

    for x in range(width):
        g = int((x / max(width - 1, 1)) * 255)
        draw.line([(x, band), (x, band * 2 - 1)], fill=(g, g, g))

    draw.rectangle([0, band * 2, width, height], fill=(255, 140, 40))
    cx, cy = width // 2, band * 2 + band // 2
    radius = min(width, band) // 2 - 4
    for y in range(cy - radius, cy + radius + 1):
        for x in range(cx - radius, cx + radius + 1):
            dx, dy = x - cx, y - cy
            if dx * dx + dy * dy > radius * radius:
                continue
            nz = (radius * radius - dx * dx - dy * dy) ** 0.5 / radius
            nx, ny = dx / radius, dy / radius
            intensity = max(0.12, nx * -0.45 + ny * -0.35 + nz * 0.75)
            img.putpixel((x, y), (int(255 * intensity), int(160 * intensity), int(40 * intensity)))
    return img


def _label_tile(tile: Image.Image, method: str, font) -> Image.Image:
    canvas = Image.new("RGB", (TILE_W, TILE_H + LABEL_H), "white")
    canvas.paste(tile, (0, LABEL_H))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([0, 0, TILE_W, LABEL_H], fill=(245, 245, 245))
    draw.text((6, 3), method, fill=(20, 20, 20), font=font)
    return canvas


def build_grid(palette, palette_name: str, source: Image.Image, font) -> Image.Image:
    tiles: list[Image.Image] = []
    for method in DITHER_METHODS:
        dithered = dither_to_palette(source, palette, dither=method)
        single = _label_tile(dithered, method, font)
        single.save(os.path.join(OUT_DIR, f"{method}_{palette_name}.png"))
        tiles.append(single)

    rows = (len(tiles) + COLS - 1) // COLS
    cell_w, cell_h = TILE_W, TILE_H + LABEL_H
    grid_w = COLS * cell_w + (COLS + 1) * PAD
    grid_h = rows * cell_h + (rows + 1) * PAD + 28
    grid = Image.new("RGB", (grid_w, grid_h), (255, 255, 255))
    draw = ImageDraw.Draw(grid)
    title_font = _font(16)
    draw.text((PAD, 6), f"imagespec dither methods — palette={palette_name}", fill=(0, 0, 0), font=title_font)

    for i, tile in enumerate(tiles):
        r, c = divmod(i, COLS)
        x = PAD + c * (cell_w + PAD)
        y = 28 + PAD + r * (cell_h + PAD)
        grid.paste(tile, (x, y))
    return grid


def main() -> None:
    font = _font(13)
    source = source_scene()
    os.makedirs(OUT_DIR, exist_ok=True)
    source.save(os.path.join(OUT_DIR, "source.png"))

    for palette, name in ((PALETTE_BW, "bw"), (PALETTE_BWR, "bwr")):
        grid = build_grid(palette, name, source, font)
        out = os.path.join(ROOT, f"dither_methods_{name}.png")
        grid.save(out)
        print(f"Saved {out}")
    print(f"Saved individual tiles under {OUT_DIR}/")


if __name__ == "__main__":
    main()
