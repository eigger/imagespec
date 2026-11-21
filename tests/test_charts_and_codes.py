"""Regression tests for progress_bar, sparkline, and barcode edge cases."""

from __future__ import annotations

import pytest
from PIL import Image

from imagespec import RenderContext, render
from imagespec.elements.charts import progress_bar
from imagespec.state import RenderState


def _colors(img: Image.Image) -> set[tuple[int, ...]]:
    return {color for _, color in img.getcolors(maxcolors=1 << 24)}


def test_progress_bar_percentage_text_is_1bit_crisp():
    ctx = RenderContext(palette="bw")
    raw = Image.new("RGBA", (100, 30), "white")
    state = RenderState(img=raw, canvas_width=100, canvas_height=30, context=ctx)
    progress_bar(
        state,
        {
            "x_start": 0,
            "y_start": 0,
            "x_end": 99,
            "y_end": 29,
            "progress": 20,
            "fill": "black",
            "background": "white",
            "outline": "black",
            "show_percentage": True,
        },
    )
    pixels = _colors(raw)  # RGBA bytes before any final palette snap
    assert pixels <= {(0, 0, 0, 255), (255, 255, 255, 255)}


@pytest.mark.parametrize("direction", ["right", "left", "up", "down"])
def test_progress_bar_zero_progress_with_radius_draws_no_fill(direction):
    ctx = RenderContext(palette="4")
    img = render(
        [
            {
                "type": "progress_bar",
                "x_start": 5,
                "y_start": 5,
                "x_end": 45,
                "y_end": 25,
                "progress": 0,
                "radius": 4,
                "direction": direction,
                "fill": "red",
                "outline": None,
            }
        ],
        50,
        30,
        background="white",
        context=ctx,
    )
    assert (255, 0, 0) not in _colors(img)


def test_fractional_widths_on_progress_bar_and_sparkline(ctx):
    els = [
        {
            "type": "progress_bar",
            "x_start": 2,
            "y_start": 2,
            "x_end": 50,
            "y_end": 16,
            "progress": 50,
            "width": 1.5,
            "outline": "black",
            "fill": "red",
        },
        {
            "type": "sparkline",
            "x": 2,
            "y": 20,
            "width": 48,
            "height": 18,
            "values": [1, 4, 2, 5],
            "width_line": 1.5,
            "color": "yellow",
        },
    ]
    img = render(els, 60, 40, background="white", strict=True, context=ctx)
    assert img.size == (60, 40)
    colors = _colors(img)
    assert (0, 0, 0) in colors
    assert (255, 0, 0) in colors
    assert (255, 255, 0) in colors


@pytest.mark.parametrize("color,expected_fg", [("black", (0, 0, 0)), ("white", (255, 255, 255))])
@pytest.mark.parametrize("scaled", [True, False])
@pytest.mark.parametrize("write_text", [True, False])
def test_barcode_null_bgcolor_is_transparent_over_background(ctx, color, expected_fg, scaled, write_text):
    spec: dict[str, object] = {
        "type": "barcode",
        "x": 5,
        "y": 2,
        "data": "1234",
        "bgcolor": None,
        "color": color,
        "write_text": write_text,
    }
    if scaled:
        spec["width"] = 80
        spec["height"] = 30
    img = render([spec], 160, 100, background="red", context=ctx)
    colors = _colors(img)
    assert expected_fg in colors
    assert (255, 0, 0) in colors
    assert colors == {expected_fg, (255, 0, 0)}


def test_barcode_null_color_draws_solid_bgcolor_and_both_null_is_noop(ctx):
    solid = render(
        [
            {
                "type": "barcode",
                "x": 0,
                "y": 0,
                "data": "1234",
                "color": None,
                "bgcolor": "red",
                "width": 30,
                "height": 10,
                "write_text": False,
            }
        ],
        30,
        10,
        background="white",
        context=ctx,
    )
    assert _colors(solid) == {(255, 0, 0)}

    noop = render(
        [{"type": "barcode", "x": 0, "y": 0, "data": "1234", "color": None, "bgcolor": None}],
        30,
        10,
        background="yellow",
        context=ctx,
    )
    assert _colors(noop) == {(255, 255, 0)}


@pytest.mark.parametrize("direction", ["right", "left", "up", "down"])
def test_progress_bar_1px_span_fills_at_100_percent_and_empty_at_0(direction):
    ctx = RenderContext(palette="4")
    coords = (
        {"x_start": 10, "y_start": 2, "x_end": 10, "y_end": 18}
        if direction in ("right", "left")
        else {"x_start": 2, "y_start": 10, "x_end": 18, "y_end": 10}
    )
    full = render(
        [
            {
                "type": "progress_bar",
                **coords,
                "progress": 100,
                "direction": direction,
                "width": 0,
                "fill": "red",
                "background": "white",
                "outline": None,
            }
        ],
        24,
        24,
        background="white",
        context=ctx,
    )
    assert (255, 0, 0) in _colors(full)

    empty = render(
        [
            {
                "type": "progress_bar",
                **coords,
                "progress": 0,
                "direction": direction,
                "width": 0,
                "fill": "red",
                "background": "white",
                "outline": None,
            }
        ],
        24,
        24,
        background="white",
        context=ctx,
    )
    assert (255, 0, 0) not in _colors(empty)


def test_subpixel_positive_width_draws_visible_ink_while_zero_hides(ctx):
    pb_half = render(
        [
            {
                "type": "progress_bar",
                "x_start": 2,
                "y_start": 2,
                "x_end": 22,
                "y_end": 14,
                "progress": 0,
                "fill": None,
                "background": None,
                "outline": "black",
                "width": 0.5,
            }
        ],
        28,
        20,
        background="white",
        context=ctx,
    )
    assert (0, 0, 0) in _colors(pb_half)

    pb_zero = render(
        [
            {
                "type": "progress_bar",
                "x_start": 2,
                "y_start": 2,
                "x_end": 22,
                "y_end": 14,
                "progress": 0,
                "fill": None,
                "background": None,
                "outline": "black",
                "width": 0,
            }
        ],
        28,
        20,
        background="white",
        context=ctx,
    )
    assert (0, 0, 0) not in _colors(pb_zero)

    sp_half = render(
        [
            {
                "type": "sparkline",
                "x": 2,
                "y": 2,
                "width": 20,
                "height": 12,
                "values": [1, 3, 2],
                "color": "black",
                "width_line": 0.5,
            }
        ],
        28,
        20,
        background="white",
        context=ctx,
    )
    assert (0, 0, 0) in _colors(sp_half)
