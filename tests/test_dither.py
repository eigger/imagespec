"""Palette dithering (error diffusion + ordered screens)."""

from __future__ import annotations

import pytest
from PIL import Image, ImageDraw

import imagespec.dither as dither_mod
from imagespec import DITHER_METHODS, RenderContext, RenderError, render, resolve_dither_method
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
    assert partial.mode == expect.mode and partial.tobytes() == expect.tobytes()


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


# ── numpy fast path == pure-Python path ────────────────────────────────────


@pytest.fixture(scope="module")
def dither_scene():
    src = Image.open("examples/dither_methods/source.png").convert("RGB")
    return src.resize((97, 61))  # odd size: exercises edge taps and serpentine turns


@pytest.mark.skipif(dither_mod.np is None, reason="numpy not installed; only the pure path exists")
@pytest.mark.parametrize("palette", [PALETTE_BW, PALETTE_BWR, PALETTE_7], ids=["bw", "bwr", "7"])
@pytest.mark.parametrize("method", DITHER_METHODS)
def test_numpy_and_pure_paths_are_bit_identical(monkeypatch, dither_scene, palette, method):
    # The numpy path adds error to the rows below with array ops; it must feed
    # every cell the same float operands in the same order as the scalar scan.
    fast = dither_to_palette(dither_scene, palette, dither=method, origin=(3, 5))
    monkeypatch.setattr(dither_mod, "np", None)
    pure = dither_to_palette(dither_scene, palette, dither=method, origin=(3, 5))
    assert fast.tobytes() == pure.tobytes()


def test_pure_path_matches_dither_golden(monkeypatch):
    # tests/test_golden.py runs whichever path is installed; pin the pure path
    # to a golden too so a numpy-only CI never masks a pure-path regression.
    monkeypatch.setattr(dither_mod, "np", None)
    src = Image.open("examples/dither_methods/source.png").convert("RGB")
    out = dither_to_palette(src, PALETTE_BWR, dither="jarvis")
    golden = Image.open("tests/golden/dither_jarvis_bwr.png").convert("RGB")
    assert out.tobytes() == golden.tobytes()


@pytest.mark.parametrize("method", sorted(_KERNELS))
def test_on_palette_image_skips_the_diffusion_kernel(method, monkeypatch):
    """Zero incoming error means zero outgoing error: the kernel must not run, result unchanged."""
    img = Image.new("RGB", (30, 20), PALETTE_7[1])
    ImageDraw.Draw(img).rectangle([5, 5, 15, 15], fill=PALETTE_7[3])
    expected = dither_to_palette(img, PALETTE_7, dither=method)

    def boom(*a, **k):
        raise AssertionError("kernel ran for an on-palette image")

    monkeypatch.setattr(dither_mod, "_error_diffuse", boom)
    out = dither_to_palette(img, PALETTE_7, dither=method)
    assert out.tobytes() == img.tobytes() == expected.tobytes()


def test_off_palette_image_still_diffuses():
    img = Image.new("RGB", (20, 20), (128, 128, 128))
    out = dither_to_palette(img, PALETTE_BW, dither="floyd")
    assert _colors(out) == {(0, 0, 0), (255, 255, 255)}


@pytest.mark.parametrize("mode", ["RGB", "RGBA", "P"])
def test_on_palette_fast_path_matches_kernel_for_modes_and_duplicates(mode, monkeypatch):
    pal = [(0, 0, 0), (255, 255, 255), (255, 0, 0), (255, 0, 0)]  # duplicate entry
    img = Image.new("RGB", (16, 16), (255, 0, 0))
    ImageDraw.Draw(img).rectangle([2, 2, 9, 9], fill=(0, 0, 0))
    src = img if mode == "RGB" else img.convert(mode)
    fast = dither_to_palette(src, pal, dither="floyd")
    monkeypatch.setattr(dither_mod, "_quantize_nearest_pillow", lambda im, p: Image.new("RGB", im.size, (1, 2, 3)))
    slow = dither_to_palette(src, pal, dither="floyd")  # forces the kernel
    assert fast.tobytes() == slow.tobytes()


@pytest.mark.parametrize("method", ["floyd", "bayer8"])
def test_global_dither_preserves_already_quantized_palette_pixels(method):
    ctx = RenderContext(palette="7")
    el = {
        "type": "rectangle",
        "x_start": 0,
        "y_start": 0,
        "x_end": 15,
        "y_end": 15,
        "fill": "green",
        "outline": None,
        "dither": False,
    }
    img = render([el], 16, 16, background="white", dither=method, context=ctx)
    assert {color for _, color in img.getcolors(maxcolors=1 << 24)} == {(0, 128, 0)}


@pytest.mark.parametrize("method", ["floyd", "bayer8"])
def test_global_dither_preserves_per_element_override_next_to_other_colors(method):
    ctx = RenderContext(palette="4")
    left = {
        "type": "rectangle",
        "x_start": 0,
        "y_start": 0,
        "x_end": 7,
        "y_end": 15,
        "fill": "#0b00b2",
        "outline": None,
    }
    right = {
        "type": "rectangle",
        "x_start": 8,
        "y_start": 0,
        "x_end": 15,
        "y_end": 15,
        "fill": "red",
        "outline": None,
        "dither": False,
    }
    img = render([left, right], 16, 16, background="white", dither=method, context=ctx)
    cropped = img.crop((8, 0, 16, 16))
    assert {color for _, color in cropped.getcolors(maxcolors=1 << 24)} == {(255, 0, 0)}


def test_later_same_color_element_replaces_an_earlier_dither_override():
    ctx = RenderContext(palette="7")
    rect = {
        "type": "rectangle",
        "x_start": 0,
        "y_start": 0,
        "x_end": 15,
        "y_end": 15,
        "fill": "green",
        "outline": None,
    }
    expected = render([rect], 16, 16, dither="bayer8", context=ctx)
    actual = render([{**rect, "dither": False}, rect], 16, 16, dither="bayer8", context=ctx)
    assert actual.tobytes() == expected.tobytes()


@pytest.mark.parametrize("container", ["group", "column"])
def test_nested_override_replaces_an_overlapping_outer_override(container):
    ctx = RenderContext(palette="7")
    red = {
        "type": "rectangle",
        "x_start": 0,
        "y_start": 0,
        "x_end": 15,
        "y_end": 15,
        "fill": "red",
        "outline": None,
        "dither": False,
    }
    green = {**red, "fill": "green"}
    nested = (
        {"type": "group", "x": 0, "y": 0, "width": 16, "height": 16, "elements": [green]}
        if container == "group"
        else {"type": "column", "x": 0, "y": 0, "width": 16, "height": 16, "elements": [green]}
    )
    img = render([red, nested], 16, 16, dither="bayer8", context=ctx)
    assert {color for _, color in img.getcolors(maxcolors=1 << 24)} == {(0, 128, 0)}


def test_later_overlapping_stack_child_clears_an_earlier_override_mask():
    ctx = RenderContext(palette="7")
    base = {
        "type": "rectangle",
        "x_start": 0,
        "y_start": 0,
        "x_end": 15,
        "y_end": 15,
        "outline": None,
    }
    red = {**base, "fill": "red", "dither": False}
    green = {**base, "fill": "green"}
    row = {"type": "row", "width": 16, "height": 16, "elements": [red, {**green, "class": "-ml-[16]"}]}
    expected = render([green], 16, 16, dither="bayer8", context=ctx)
    actual = render([row], 16, 16, dither="bayer8", context=ctx)
    assert actual.tobytes() == expected.tobytes()


@pytest.mark.skipif(dither_mod.np is None, reason="numpy optional fast path not installed")
def test_numpy_stevenson_arce_handles_images_narrower_than_its_kernel():
    img = Image.new("RGB", (2, 4), (128, 128, 128))
    assert dither_to_palette(img, PALETTE_BW, dither="stevenson-arce").size == img.size


@pytest.mark.parametrize("pal", [[(i % 256, 0, 0) for i in range(300)]])
def test_unrepresentable_palettes_still_diffuse(pal):
    img = Image.new("RGB", (6, 6), (128, 0, 0))
    assert dither_to_palette(img, pal, dither="floyd").size == (6, 6)


@pytest.mark.parametrize(
    "pal",
    [
        [(i % 256, (i * 7) % 256, 0) for i in range(300)],
        # Equidistant tie-breaking: (10, 0, 0) is distance^2 100 from both (0, 0, 0) and (20, 0, 0), plus >256 colors.
        [(0, 0, 0), (20, 0, 0), *[(i % 256, 128, (i // 256) * 50 + 50) for i in range(260)]],
    ],
)
def test_unrepresentable_palette_none_dither_matches_numpy_and_pure(monkeypatch, pal):
    img = Image.new("RGB", (12, 70), (10, 0, 0))
    fast = dither_to_palette(img, pal, dither="none")
    monkeypatch.setattr(dither_mod, "np", None)
    pure = dither_to_palette(img, pal, dither="none")
    assert fast.tobytes() == pure.tobytes()
    assert _colors(fast) <= set(pal)


@pytest.mark.parametrize("bad_pal", [[(300, 0, 0), (0, 0, 0)], [(-10, 0, 0), (255, 255, 255)]])
@pytest.mark.parametrize("method", ["none", "floyd", "bayer8"])
def test_out_of_range_palette_channels_raise_value_error(bad_pal, method):
    img = Image.new("RGB", (4, 4), (128, 128, 128))
    with pytest.raises(ValueError, match="0..255"):
        dither_to_palette(img, bad_pal, dither=method)


@pytest.mark.parametrize("method", ["bayer2", "bayer4", "bayer8", "bayer16", "clustered4", "clustered8"])
@pytest.mark.parametrize("color", [(0, 128, 0), (255, 165, 0)])
def test_ordered_dither_preserves_exact_in_palette_colors(monkeypatch, method, color):
    img = Image.new("RGB", (16, 16), color)
    fast = dither_to_palette(img, PALETTE_7, dither=method)
    assert _colors(fast) == {color}
    monkeypatch.setattr(dither_mod, "np", None)
    pure = dither_to_palette(img, PALETTE_7, dither=method)
    assert _colors(pure) == {color}


def test_later_off_palette_element_replaces_earlier_dither_override():
    ctx = RenderContext(palette="7")
    rect = {
        "type": "rectangle",
        "x_start": 0,
        "y_start": 0,
        "x_end": 15,
        "y_end": 15,
        "fill": "#208020",
        "outline": None,
    }
    expected = render([rect], 16, 16, dither="bayer8", context=ctx)
    actual = render([{**rect, "dither": False}, rect], 16, 16, dither="bayer8", context=ctx)
    assert len(_colors(expected)) > 1
    assert actual.tobytes() == expected.tobytes()


@pytest.mark.parametrize("rotate", [0, 90])
def test_nested_child_dither_false_preserved_inside_isolated_group(rotate):
    # Floyd diffusion from off-palette #000000 background (-150 error) would flip inset white
    # pixels to (150, 150, 150) if child dither=False protection were not propagated.
    pal = [(150, 150, 150, 255), (255, 255, 255, 255)]
    floyd_ctx = RenderContext(palette=pal)
    grp_floyd = {
        "type": "group",
        "x": 0,
        "y": 0,
        "width": 16,
        "height": 16,
        "rotate": rotate,
        "dither": "floyd",
        "elements": [
            {"type": "rectangle", "x_start": 0, "y_start": 0, "x_end": 15, "y_end": 15, "fill": "#000000"},
            {
                "type": "rectangle",
                "x_start": 4,
                "y_start": 4,
                "x_end": 11,
                "y_end": 11,
                "fill": "white",
                "outline": None,
                "dither": False,
            },
        ],
    }
    img_floyd = render([grp_floyd], 16, 16, background="white", dither=False, context=floyd_ctx)
    assert _colors(img_floyd.crop((4, 4, 12, 12))) == {(255, 255, 255)}

    # Ordered dithering on BW dithers the outer #808080 fill while keeping the inset flat.
    bw_ctx = RenderContext(palette="bw")
    grp_bayer = {
        "type": "group",
        "x": 0,
        "y": 0,
        "width": 16,
        "height": 16,
        "rotate": rotate,
        "dither": "bayer8",
        "elements": [
            {"type": "rectangle", "x_start": 0, "y_start": 0, "x_end": 15, "y_end": 15, "fill": "#808080"},
            {
                "type": "rectangle",
                "x_start": 4,
                "y_start": 4,
                "x_end": 11,
                "y_end": 11,
                "fill": "#808080",
                "outline": None,
                "dither": False,
            },
        ],
    }
    img_bayer = render([grp_bayer], 16, 16, dither=False, context=bw_ctx)
    assert _colors(img_bayer) == {(0, 0, 0), (255, 255, 255)}
    assert _colors(img_bayer.crop((4, 4, 12, 12))) == {(255, 255, 255)}


def test_isolated_floyd_does_not_bleed_transparent_error_into_opaque_shape():
    pal_no_black = [(60, 60, 60, 255), (255, 255, 255, 255)]
    ctx = RenderContext(palette=pal_no_black)
    el = {"type": "circle", "x": 20, "y": 20, "radius": 10, "fill": "white", "outline": None, "dither": "floyd"}
    img = render([el], 40, 40, background="white", context=ctx)
    assert _colors(img) == {(255, 255, 255)}

    rot_el = {**el, "rotate": 90}
    rot_img = render([rot_el], 40, 40, background="white", context=ctx)
    assert _colors(rot_img) == {(255, 255, 255)}


def test_draw_rotated_rotates_dither_protected_mask_and_isolates_failures():
    from imagespec.dispatch import _draw_rotated
    from imagespec.state import RenderState

    # Top half is off-palette #000000 (-150 error on pal) on the left; rotate=90 turns left->top
    # and right->bottom, so the protected bottom half receives diffused error from above unless
    # tile_mask is preserved through rotation.
    pal = [(150, 150, 150, 255), (255, 255, 255, 255)]
    ctx = RenderContext(palette=pal)
    base = Image.new("RGBA", (16, 16), (255, 255, 255, 255))
    state = RenderState(img=base, canvas_width=16, canvas_height=16, context=ctx)

    def paint_split(st, el):
        st.img.paste((0, 0, 0, 255), (0, 0, 8, 16))
        st.img.paste((255, 255, 255, 255), (8, 0, 16, 16))
        assert st.dither_protected is not None
        st.dither_protected.paste(255, (8, 0, 16, 16))

    _draw_rotated(state, {"type": "rectangle"}, paint_split, 90, "floyd")
    assert state.img is base
    assert _colors(base.crop((0, 8, 16, 16)).convert("RGB")) == {(255, 255, 255)}
    assert state.dither_protected is not None and state.dither_protected.getbbox() == (0, 0, 16, 16)

    # Non-dithered rotation preserves the rotated child protection mask on state.dither_protected.
    base2 = Image.new("RGBA", (16, 16), (255, 255, 255, 255))
    old_mask = Image.new("L", (16, 16), 0)
    state2 = RenderState(img=base2, canvas_width=16, canvas_height=16, context=ctx, dither_protected=old_mask)
    _draw_rotated(state2, {"type": "rectangle"}, paint_split, 90, None)
    assert state2.dither_protected is not None
    assert state2.dither_protected.getbbox() == (0, 8, 16, 16)

    # Invalid dither method during _draw_rotated leaves state.img and state.dither_protected intact.
    base3 = Image.new("RGBA", (16, 16), (255, 255, 255, 255))
    sentinel_mask = Image.new("L", (16, 16), 123)
    state3 = RenderState(img=base3, canvas_width=16, canvas_height=16, context=ctx, dither_protected=sentinel_mask)
    with pytest.raises(ValueError):
        _draw_rotated(state3, {"type": "rectangle"}, paint_split, 90, "invalid-method")
    assert state3.img is base3
    assert state3.dither_protected is sentinel_mask


def test_dispatch_restores_state_on_handler_exception():
    from imagespec.dispatch import _draw_isolated, _draw_rotated, render_element
    from imagespec.state import RenderState

    ctx = RenderContext(palette="bw")
    base = Image.new("RGBA", (16, 16), (255, 255, 255, 255))
    mask = Image.new("L", (16, 16), 255)
    state = RenderState(img=base, canvas_width=16, canvas_height=16, context=ctx, dither_protected=mask)

    def boom(st, el):
        st.img = Image.new("RGBA", (4, 4), (0, 0, 0, 255))
        st.dither_protected = Image.new("L", (4, 4), 0)
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        _draw_isolated(state, {"type": "rectangle"}, boom, "floyd")
    assert state.img is base and state.dither_protected is mask

    with pytest.raises(RuntimeError, match="boom"):
        _draw_rotated(state, {"type": "rectangle"}, boom, 90, "floyd")
    assert state.img is base and state.dither_protected is mask

    # Also exercise render_element's old_protected isolation branch when a handler raises.
    with pytest.raises(RenderError):
        render_element(state, {"type": "polygon", "points": "bad"})
    assert state.img is base and state.dither_protected is mask
