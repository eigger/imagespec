"""Palette dithering (error diffusion + ordered screens)."""

from __future__ import annotations

import pytest
from PIL import Image, ImageDraw

from imagespec import DITHER_METHODS, RenderContext, render, resolve_dither_method
from imagespec.colors import PALETTE_7, PALETTE_BW, PALETTE_BWR
from imagespec.dither import _KERNELS, DITHER_ATKINSON, dither_to_palette


def _colors(img):
    return {c for _, c in img.getcolors(maxcolors=1 << 24)}


def _interior(img):
    return {img.getpixel((x, y)) for x in range(5, 35) for y in range(5, 35)}


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


@pytest.mark.parametrize(
    "raw, expected",
    [
        (True, "floyd"),
        (False, "none"),
        (1, "floyd"),
        (0, "none"),
        (None, "none"),
        ("floyd", "floyd"),
        ("Floyd-Steinberg", "floyd"),
        ("atkinson", "atkinson"),
        ("bayer8", "bayer8"),
        ("bayer", "bayer8"),
        ("clustered-dot-4", "clustered4"),
        ("sierra-lite", "sierra-lite"),
        ("stevenson-arce", "stevenson-arce"),
    ],
)
def test_resolve_dither_method(raw, expected):
    assert resolve_dither_method(raw) == expected


def test_resolve_dither_method_unknown():
    with pytest.raises(ValueError, match="unknown dither method"):
        resolve_dither_method("not-a-real-method")


def test_per_element_json_compat_int_and_null():
    """Hosts often send JSON 1/0/null instead of bool."""
    ctx = RenderContext(palette="bw")
    for value in (1, 0, None):
        el = dict(_ORANGE_FILL, dither=value)
        img = render([el], 40, 40, background="white", dither=False, context=ctx)
        assert img.size == (40, 40)


@pytest.mark.parametrize("method", DITHER_METHODS)
def test_every_method_stays_on_palette(method):
    gray = Image.new("RGB", (24, 24), (128, 128, 128))
    out = dither_to_palette(gray, PALETTE_BW, dither=method)
    colors = {c for _, c in out.getcolors()}
    assert colors <= {(0, 0, 0), (255, 255, 255)}
    if method == "none":
        assert len(colors) == 1
    else:
        assert len(colors) == 2


@pytest.mark.parametrize("palette", [PALETTE_BW, PALETTE_BWR, PALETTE_7])
@pytest.mark.parametrize("method", ["none", "floyd", "bayer8", "atkinson"])
def test_palette_smoke_multicolor(palette, method):
    src = Image.new("RGB", (32, 16), (128, 90, 40))
    out = dither_to_palette(src, palette, dither=method)
    allowed = {tuple(c[:3]) for c in palette}
    assert _colors(out) <= allowed


def test_kernel_weights_match_divisor():
    """Energy conservation: weight sum == divisor (Atkinson is the known exception)."""
    for name, (kernel, divisor) in _KERNELS.items():
        total = sum(w for _, _, w in kernel)
        if name == DITHER_ATKINSON:
            assert total == 6 and divisor == 8
        else:
            assert total == divisor, f"{name}: sum={total} divisor={divisor}"


def _gray_ramp(width: int = 256, height: int = 32) -> Image.Image:
    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)
    for x in range(width):
        g = int(round(x * 255 / max(width - 1, 1)))
        draw.line([(x, 0), (x, height - 1)], fill=(g, g, g))
    return img


def _block_mean_abs_err(src: Image.Image, out: Image.Image, block: int = 8) -> float:
    """Mean |luma(src) - luma(out)| after averaging each block×block cell."""
    w, h = src.size
    src_px = src.convert("RGB").load()
    out_px = out.convert("RGB").load()
    errs: list[float] = []
    for y0 in range(0, h - block + 1, block):
        for x0 in range(0, w - block + 1, block):
            s_sum = o_sum = 0.0
            n = block * block
            for y in range(y0, y0 + block):
                for x in range(x0, x0 + block):
                    sr, sg, sb = src_px[x, y]
                    or_, og, ob = out_px[x, y]
                    s_sum += 0.299 * sr + 0.587 * sg + 0.114 * sb
                    o_sum += 0.299 * or_ + 0.587 * og + 0.114 * ob
            errs.append(abs(s_sum / n - o_sum / n))
    return sum(errs) / len(errs)


@pytest.mark.parametrize(
    "method, limit",
    [
        ("floyd", 5.0),
        ("bayer8", 5.0),
        ("stevenson-arce", 8.0),
        ("atkinson", 15.0),  # intentionally discards 1/4 of error → higher MAE
        ("bayer2", 20.0),
    ],
)
def test_gray_ramp_block_mae(method, limit):
    src = _gray_ramp()
    out = dither_to_palette(src, PALETTE_BW, dither=method)
    assert _block_mean_abs_err(src, out) < limit


def test_ordered_origin_phase_matches_full_canvas():
    """Cropped ordered dither with origin= must match full-image Bayer phase."""
    src = _gray_ramp(64, 32)
    full = dither_to_palette(src, PALETTE_BW, dither="bayer8")
    ox, oy, rw, rh = 16, 8, 32, 16
    crop = src.crop((ox, oy, ox + rw, oy + rh))
    partial = dither_to_palette(crop, PALETTE_BW, dither="bayer8", origin=(ox, oy))
    expect = full.crop((ox, oy, ox + rw, oy + rh))
    assert list(partial.get_flattened_data()) == list(expect.get_flattened_data())


def test_render_accepts_method_string():
    ctx = RenderContext(palette="bw")
    img = render([_ORANGE_FILL], 40, 40, background="white", dither="atkinson", context=ctx)
    assert _interior(img) == {(0, 0, 0), (255, 255, 255)}


def test_dither_true_halftones_offpalette_fill():
    ctx = RenderContext(palette="bw")
    img = render([_ORANGE_FILL], 40, 40, background="white", dither=True, context=ctx)
    assert _interior(img) == {(0, 0, 0), (255, 255, 255)}


def test_dither_false_is_flat_nearest():
    ctx = RenderContext(palette="bw")
    img = render([_ORANGE_FILL], 40, 40, background="white", dither=False, context=ctx)
    interior = _interior(img)
    assert len(interior) == 1 and interior <= {(0, 0, 0), (255, 255, 255)}


def test_output_always_on_palette_even_without_dither():
    ctx = RenderContext(palette="bw")
    els = [_ORANGE_FILL, {"type": "text", "x": 2, "y": 2, "value": "Hi", "size": 14, "color": "red"}]
    img = render(els, 60, 40, background="white", dither=False, context=ctx)
    assert _colors(img) <= {(0, 0, 0), (255, 255, 255)}


def test_inpalette_text_crisp_under_dither():
    ctx = RenderContext(palette="bw")
    el = {"type": "text", "x": 2, "y": 2, "value": "Hi", "size": 16, "color": "black"}
    img = render([el], 60, 24, background="white", dither=True, context=ctx)
    cols = _colors(img)
    assert cols <= {(0, 0, 0), (255, 255, 255)}
    assert (0, 0, 0) in cols


def test_per_element_dither_true_overrides_global_off():
    ctx = RenderContext(palette="bw")
    el = dict(_ORANGE_FILL, dither=True)
    img = render([el], 40, 40, background="white", dither=False, context=ctx)
    assert _interior(img) == {(0, 0, 0), (255, 255, 255)}


def test_per_element_dither_false_overrides_global_on():
    ctx = RenderContext(palette="bw")
    el = dict(_ORANGE_FILL, dither=False)
    img = render([el], 40, 40, background="white", dither=True, context=ctx)
    assert len(_interior(img)) == 1


def test_per_element_method_string_overrides_global():
    ctx = RenderContext(palette="bw")
    el = dict(_ORANGE_FILL, dither="bayer8")
    img = render([el], 40, 40, background="white", dither=False, context=ctx)
    assert _interior(img) == {(0, 0, 0), (255, 255, 255)}


def test_per_element_dither_is_selective_within_one_render():
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
    assert left_region == {(0, 0, 0), (255, 255, 255)}
    assert len(right_region) == 1


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
