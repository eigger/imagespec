"""Core render loop: rotation modes, input validation, dispatch."""

from __future__ import annotations

import pytest

from imagespec import RenderError, render


def test_rotation_canvas_keeps_dims(ctx):
    # gicisky behaviour: fixed-resolution panel, output stays width x height
    assert render([], 200, 100, rotate=90, rotate_mode="canvas", context=ctx).size == (200, 100)
    assert render([], 200, 100, rotate=270, rotate_mode="canvas", context=ctx).size == (200, 100)


def test_rotation_image_swaps_dims(ctx):
    # niimbot behaviour: drawing rotates, output dims swap
    assert render([], 200, 100, rotate=90, rotate_mode="image", context=ctx).size == (100, 200)
    assert render([], 200, 100, rotate=270, rotate_mode="image", context=ctx).size == (100, 200)


@pytest.mark.parametrize("rot", [0, 180])
def test_modes_equivalent_for_0_180(ctx, rot):
    a = render([], 200, 100, rotate=rot, rotate_mode="canvas", context=ctx)
    b = render([], 200, 100, rotate=rot, rotate_mode="image", context=ctx)
    assert a.size == b.size == (200, 100)


def test_output_is_rgb(ctx):
    assert render([], 10, 10, context=ctx).mode == "RGB"


def test_invalid_rotate_raises(ctx):
    with pytest.raises(ValueError):
        render([], 10, 10, rotate=45, context=ctx)


def test_invalid_rotate_mode_raises(ctx):
    with pytest.raises(ValueError):
        render([], 10, 10, rotate_mode="sideways", context=ctx)


def test_nonpositive_size_raises(ctx):
    with pytest.raises(ValueError):
        render([], 0, 10, context=ctx)


def test_unknown_type_is_skipped(ctx):
    # unknown elements warn-and-skip, never raise
    assert render([{"type": "bogus"}], 10, 10, context=ctx).size == (10, 10)


def test_invisible_element_is_skipped(ctx):
    el = {"type": "rectangle", "x_start": 0, "y_start": 0, "x_end": 9, "y_end": 9, "fill": "black", "visible": False}
    assert render([el], 10, 10, background="white", context=ctx).getpixel((5, 5)) == (255, 255, 255)


@pytest.mark.parametrize("value", ["False", "false", "off", "no", "none", "0", "0.0", " 0 ", "", 0, 0.0, None])
def test_visible_falsy_strings_hide(ctx, value):
    # HA templates yield strings ("False"), which are truthy in Python; they
    # must still hide the element.
    el = {"type": "rectangle", "x_start": 0, "y_start": 0, "x_end": 9, "y_end": 9, "fill": "black", "visible": value}
    assert render([el], 10, 10, background="white", context=ctx).getpixel((5, 5)) == (255, 255, 255)


@pytest.mark.parametrize("value", ["True", "true", "on", "yes", "1", "0.5", "abc", 1, True])
def test_visible_truthy_strings_show(ctx, value):
    el = {"type": "rectangle", "x_start": 0, "y_start": 0, "x_end": 9, "y_end": 9, "fill": "black", "visible": value}
    assert render([el], 10, 10, background="white", context=ctx).getpixel((5, 5)) == (0, 0, 0)


def test_non_dict_element_raises(ctx):
    with pytest.raises(RenderError):
        render(["not a dict"], 10, 10, context=ctx)


def test_none_payload_ok(ctx):
    assert render(None, 10, 10, context=ctx).size == (10, 10)


def test_context_layout_engine_is_passed_to_fonts():
    from PIL import ImageFont

    from imagespec import RenderContext

    basic = RenderContext(layout_engine=ImageFont.Layout.BASIC).font(None, 12)
    assert basic.layout_engine == ImageFont.Layout.BASIC
    default = RenderContext().font(None, 12)  # Pillow's own default (RAQM if available)
    assert default.layout_engine in (ImageFont.Layout.BASIC, ImageFont.Layout.RAQM)


def test_font_cache_honours_layout_engine_change():
    from PIL import ImageFont

    from imagespec import RenderContext

    ctx = RenderContext(layout_engine=ImageFont.Layout.BASIC)
    basic = ctx.font(None, 12)
    assert ctx.font(None, 12) is basic  # same engine -> cache hit
    ctx.layout_engine = None  # Pillow default (RAQM where available)
    assert ctx.font(None, 12) is not basic  # engine is part of the cache key
