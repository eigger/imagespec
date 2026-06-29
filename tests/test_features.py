"""Behavioural tests for the newer elements: group, pie, dlimg circle mask."""

from __future__ import annotations

import base64
import io

import pytest
from PIL import Image

from imagespec import render


@pytest.fixture
def red_data_url():
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (255, 0, 0)).save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def test_group_offsets_children(ctx):
    # a child rect drawn at (0,0)-(4,4) inside a group offset to (10,10)
    el = {
        "type": "group",
        "x": 10,
        "y": 10,
        "elements": [{"type": "rectangle", "x_start": 0, "y_start": 0, "x_end": 4, "y_end": 4, "fill": "black"}],
    }
    img = render([el], 40, 40, background="white", context=ctx)
    assert img.getpixel((12, 12)) == (0, 0, 0)  # inside the translated child
    assert img.getpixel((2, 2)) == (255, 255, 255)  # untouched by the group


def test_group_clips_to_box(ctx):
    # child extends beyond the group box; the overflow must be clipped away
    el = {
        "type": "group",
        "x": 0,
        "y": 0,
        "width": 10,
        "height": 10,
        "elements": [{"type": "rectangle", "x_start": 0, "y_start": 0, "x_end": 30, "y_end": 30, "fill": "black"}],
    }
    img = render([el], 40, 40, background="white", context=ctx)
    assert img.getpixel((5, 5)) == (0, 0, 0)  # inside the clip box
    assert img.getpixel((20, 20)) == (255, 255, 255)  # clipped


def test_pie_donut_hole_is_background(ctx):
    el = {
        "type": "pie",
        "x": 20,
        "y": 20,
        "radius": 15,
        "inner_radius": 7,
        "values": "a,30;b,50;c,20",
        "background": "white",
    }
    img = render([el], 40, 40, background="white", context=ctx)
    assert img.getpixel((20, 20)) == (255, 255, 255)  # the donut hole


def test_dlimg_circle_mask_clears_corners(ctx, red_data_url):
    el = {"type": "dlimg", "x": 0, "y": 0, "url": red_data_url, "xsize": 20, "ysize": 20, "circle": True}
    img = render([el], 20, 20, background="white", context=ctx)
    assert img.getpixel((10, 10)) == (255, 0, 0)  # center kept
    assert img.getpixel((0, 0)) == (255, 255, 255)  # corner masked out


def test_dlimg_dither_smoke(ctx, red_data_url):
    el = {"type": "dlimg", "x": 0, "y": 0, "url": red_data_url, "xsize": 16, "ysize": 16, "dither": True}
    assert render([el], 20, 20, context=ctx).size == (20, 20)


def test_rich_text_renders(ctx):
    el = {
        "type": "rich_text",
        "x": 2,
        "y": 10,
        "align": "left",
        "spans": [{"text": "temp "}, {"icon": "mdi:thermometer", "size": 14, "color": "red"}, {"text": " 23C"}],
    }
    assert render([el], 80, 20, context=ctx).size == (80, 20)


def test_sparkline_renders(ctx):
    el = {
        "type": "sparkline",
        "x": 0,
        "y": 0,
        "width": 50,
        "height": 20,
        "values": [1, 5, 2, 8, 3, 6],
        "fill": "yellow",
        "dot_last": True,
    }
    assert render([el], 60, 30, context=ctx).size == (60, 30)


def test_legend_draws_swatches(bw_ctx):
    el = {
        "type": "legend",
        "x": 0,
        "y": 0,
        "items": [{"label": "a", "color": "black"}],
        "size": 10,
        "swatch_size": 10,
    }
    img = render([el], 40, 20, background="white", context=bw_ctx)
    # the swatch square (top-left) should be black
    assert img.getpixel((5, 5)) == (0, 0, 0)


def test_legend_accepts_string_items(ctx):
    el = {"type": "legend", "x": 0, "y": 0, "items": "gas,red;water,blue", "size": 8}
    assert render([el], 60, 30, context=ctx).size == (60, 30)


def test_star_rating_partial(ctx):
    el = {"type": "star_rating", "x": 0, "y": 0, "rating": 3, "max": 5, "size": 12, "color": "red"}
    img = render([el], 70, 16, background="white", context=ctx)
    # at least some star pixels are drawn (red on a 4-color device stays red)
    assert any(img.getpixel((x, y)) == (255, 0, 0) for x in range(70) for y in range(16))


def test_battery_fill_proportional(bw_ctx):
    el = {
        "type": "battery",
        "x": 0,
        "y": 0,
        "width": 40,
        "height": 16,
        "level": 50,
        "fill": "black",
        "background": "white",
        "padding": 2,
    }
    img = render([el], 50, 20, background="white", context=bw_ctx)
    # left half (filled) has black; far right interior (empty) stays white
    assert img.getpixel((6, 8)) == (0, 0, 0)
    assert img.getpixel((30, 8)) == (255, 255, 255)


def test_battery_low_color(ctx):
    el = {
        "type": "battery",
        "x": 0,
        "y": 0,
        "width": 40,
        "height": 16,
        "level": 10,
        "low_threshold": 20,
        "low_color": "red",
        "padding": 2,
    }
    img = render([el], 50, 20, background="white", context=ctx)
    assert any(img.getpixel((x, 8)) == (255, 0, 0) for x in range(40))


def test_barcode_pixel_sizing_fits_box(bw_ctx):
    # width/height scale the barcode into a pixel box at (x, y)
    el = {
        "type": "barcode",
        "x": 10,
        "y": 10,
        "data": "12345670",
        "code": "code128",
        "width": 120,
        "height": 40,
        "write_text": False,
    }
    img = render([el], 150, 70, background="white", context=bw_ctx)
    black = [(x, y) for y in range(70) for x in range(150) if img.getpixel((x, y)) == (0, 0, 0)]
    xs = [p[0] for p in black]
    ys = [p[1] for p in black]
    assert black  # bars drawn
    # stays within the requested box (x: 10..130, y: 10..50), pure black/white
    assert min(xs) >= 10 and max(xs) <= 130
    assert min(ys) >= 10 and max(ys) <= 50
    assert {c for _, c in img.getcolors(maxcolors=1 << 24)} <= {(0, 0, 0), (255, 255, 255)}


def test_barcode_width_controls_extent(bw_ctx):
    # a wider target box yields a wider barcode
    def extent(w):
        el = {"type": "barcode", "x": 5, "y": 5, "data": "9876543", "width": w, "height": 30, "write_text": False}
        img = render([el], w + 60, 50, background="white", context=bw_ctx)
        xs = [x for y in range(50) for x in range(w + 60) if img.getpixel((x, y)) == (0, 0, 0)]
        return max(xs) - min(xs)

    assert extent(160) > extent(90)


def test_qrcode_pixel_box_fits_and_square(bw_ctx):
    el = {"type": "qrcode", "x": 5, "y": 5, "data": "https://example.com/p/1", "width": 60, "height": 60}
    img = render([el], 80, 80, background="white", context=bw_ctx)
    black = [(x, y) for y in range(80) for x in range(80) if img.getpixel((x, y)) == (0, 0, 0)]
    xs = [p[0] for p in black]
    ys = [p[1] for p in black]
    assert black
    # fits within the 5..65 box on both axes and is (near-)square
    assert max(xs) <= 65 and max(ys) <= 65
    assert abs((max(xs) - min(xs)) - (max(ys) - min(ys))) <= 1
