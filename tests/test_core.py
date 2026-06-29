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


def test_non_dict_element_raises(ctx):
    with pytest.raises(RenderError):
        render(["not a dict"], 10, 10, context=ctx)


def test_none_payload_ok(ctx):
    assert render(None, 10, 10, context=ctx).size == (10, 10)
