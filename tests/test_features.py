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
