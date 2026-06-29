"""Floyd–Steinberg dithering."""

from __future__ import annotations

from PIL import Image

from imagespec import RenderContext, render
from imagespec.colors import PALETTE_BW
from imagespec.dither import dither_to_palette


def test_dither_emits_only_palette_colors():
    gray = Image.new("RGB", (20, 20), (128, 128, 128))
    out = dither_to_palette(gray, PALETTE_BW)
    colors = {c for _, c in out.getcolors()}
    assert colors <= {(0, 0, 0), (255, 255, 255)}
    assert len(colors) == 2  # a mid-gray must dither into both


def test_dither_none_snaps():
    gray = Image.new("RGB", (10, 10), (100, 100, 100))
    out = dither_to_palette(gray, PALETTE_BW, dither=False)
    assert {c for _, c in out.getcolors()} == {(0, 0, 0)}  # 100 nearest black, no dithering


def test_render_dither_param_smoke():
    ctx = RenderContext(palette="bw")
    img = render([], 20, 20, background="white", dither=True, context=ctx)
    assert img.mode == "RGB" and img.size == (20, 20)
