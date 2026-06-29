"""Floyd–Steinberg dithering to a device palette.

Snapping each pixel to its nearest palette color (what `quantize_color` does for
named element colors) looks bad for photos/logos on a 2–7 color panel. Dithering
trades spatial resolution for perceived color depth and looks dramatically better.
"""

from __future__ import annotations

from PIL import Image


def _palette_image(palette) -> Image.Image:
    """Build a 'P'-mode image whose palette is ``palette`` (list of RGBA)."""
    rgbs = [tuple(c[:3]) for c in palette]
    flat: list[int] = []
    for c in rgbs:
        flat.extend(c)
    # Pad to 256 entries by repeating the first color (never introduce a new one).
    pad = list(rgbs[0])
    while len(flat) < 768:
        flat.extend(pad)
    pal_img = Image.new("P", (1, 1))
    pal_img.putpalette(flat)
    return pal_img


def dither_to_palette(img: Image.Image, palette, *, dither: bool = True) -> Image.Image:
    """Return ``img`` quantized to ``palette`` (RGB), optionally dithered."""
    rgb = img.convert("RGB")
    pal_img = _palette_image(palette)
    mode = Image.Dither.FLOYDSTEINBERG if dither else Image.Dither.NONE
    return rgb.quantize(palette=pal_img, dither=mode).convert("RGB")
