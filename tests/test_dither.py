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


# --- Palette mapping is deferred to the end; `dither` picks halftone vs flat ---

# orange fill, no outline — keeps the interior a single authored color
_ORANGE_FILL = {
    "type": "rectangle",
    "x_start": 0,
    "y_start": 0,
    "x_end": 39,
    "y_end": 39,
    "fill": "orange",
    "outline": None,
}


def _colors(img):
    return {c for _, c in img.getcolors(maxcolors=1 << 24)}


def _interior(img):
    return {img.getpixel((x, y)) for x in range(5, 35) for y in range(5, 35)}


def test_dither_true_halftones_offpalette_fill():
    # orange on a black/white device with dither => a black/white halftone
    ctx = RenderContext(palette="bw")
    img = render([_ORANGE_FILL], 40, 40, background="white", dither=True, context=ctx)
    assert _interior(img) == {(0, 0, 0), (255, 255, 255)}  # mixed dots = halftone


def test_dither_false_is_flat_nearest():
    # no dithering: a flat nearest-color fill (single solid palette color)
    ctx = RenderContext(palette="bw")
    img = render([_ORANGE_FILL], 40, 40, background="white", dither=False, context=ctx)
    interior = _interior(img)
    assert len(interior) == 1 and interior <= {(0, 0, 0), (255, 255, 255)}


def test_output_always_on_palette_even_without_dither():
    # off-palette fill + off-palette text, no dither -> still strictly on-palette
    ctx = RenderContext(palette="bw")
    els = [_ORANGE_FILL, {"type": "text", "x": 2, "y": 2, "value": "Hi", "size": 14, "color": "red"}]
    img = render(els, 60, 40, background="white", dither=False, context=ctx)
    assert _colors(img) <= {(0, 0, 0), (255, 255, 255)}


def test_inpalette_text_crisp_under_dither():
    # black text on white stays crisp under dithering (both are palette colors,
    # so Floyd–Steinberg diffuses no error — no edge noise).
    ctx = RenderContext(palette="bw")
    el = {"type": "text", "x": 2, "y": 2, "value": "Hi", "size": 16, "color": "black"}
    img = render([el], 60, 24, background="white", dither=True, context=ctx)
    cols = _colors(img)
    assert cols <= {(0, 0, 0), (255, 255, 255)}
    assert (0, 0, 0) in cols  # text actually drawn


# --- Per-element `dither` override (any element; defaults to the global flag) ---


def test_per_element_dither_true_overrides_global_off():
    # global dithering off, but this fill opts in -> it alone becomes a halftone
    ctx = RenderContext(palette="bw")
    el = dict(_ORANGE_FILL, dither=True)
    img = render([el], 40, 40, background="white", dither=False, context=ctx)
    assert _interior(img) == {(0, 0, 0), (255, 255, 255)}


def test_per_element_dither_false_overrides_global_on():
    # global dithering on, but this fill opts out -> it stays a flat solid color
    ctx = RenderContext(palette="bw")
    el = dict(_ORANGE_FILL, dither=False)
    img = render([el], 40, 40, background="white", dither=True, context=ctx)
    assert len(_interior(img)) == 1


def test_per_element_dither_is_selective_within_one_render():
    # one dithered fill (left) + one flat fill (right) in the same image
    ctx = RenderContext(palette="bw")
    left = {
        "type": "rectangle",
        "x_start": 0,
        "y_start": 0,
        "x_end": 19,
        "y_end": 39,
        "fill": "orange",
        "outline": None,
        "dither": True,
    }
    right = {
        "type": "rectangle",
        "x_start": 20,
        "y_start": 0,
        "x_end": 39,
        "y_end": 39,
        "fill": "orange",
        "outline": None,
        "dither": False,
    }
    img = render([left, right], 40, 40, background="white", dither=False, context=ctx)
    left_region = {img.getpixel((x, y)) for x in range(2, 18) for y in range(5, 35)}
    right_region = {img.getpixel((x, y)) for x in range(22, 38) for y in range(5, 35)}
    assert left_region == {(0, 0, 0), (255, 255, 255)}  # halftone
    assert len(right_region) == 1  # flat


def test_per_element_dither_works_inside_group():
    ctx = RenderContext(palette="bw")
    grp = {
        "type": "group",
        "x": 0,
        "y": 0,
        "width": 40,
        "height": 40,
        "elements": [
            {
                "type": "rectangle",
                "x_start": 0,
                "y_start": 0,
                "x_end": 39,
                "y_end": 39,
                "fill": "orange",
                "outline": None,
                "dither": True,
            }
        ],
    }
    img = render([grp], 40, 40, background="white", dither=False, context=ctx)
    assert _interior(img) == {(0, 0, 0), (255, 255, 255)}
