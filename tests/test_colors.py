"""Palette resolution and color quantization."""

from __future__ import annotations

import pytest

from imagespec import get_palette, quantize_color, render
from imagespec.colors import PALETTE_4, PALETTE_BW, black, red, white


def test_bw_snaps_red_to_black():
    assert quantize_color("red", PALETTE_BW) == black


def test_4color_keeps_red():
    assert quantize_color("red", PALETTE_4) == red


def test_none_passthrough():
    assert quantize_color(None, PALETTE_4) is None


def test_hex_nearest_on_bw():
    assert quantize_color("#111111", PALETTE_BW) == black
    assert quantize_color("#eeeeee", PALETTE_BW) == white


def test_unknown_name_falls_back_white():
    # not a palette definition — a runtime color request; unknowns -> white
    assert quantize_color("notacolor", PALETTE_4) == white


def test_shorthand_hex_3digit():
    # #f00 should expand to #ff0000 -> red on a 4-color device
    assert quantize_color("#f00", PALETTE_4) == red
    assert quantize_color("#fff", PALETTE_BW) == white
    assert quantize_color("#000", PALETTE_BW) == black


def test_get_palette_accepts_3digit_hex():
    assert get_palette(["#000", "#fff", "#f00"]) == [black, white, red]


def test_get_palette_from_names():
    assert get_palette(["black", "white", "red"]) == [black, white, red]


def test_get_palette_from_hex():
    assert get_palette(["#000000", "#ffffff"]) == [(0, 0, 0, 255), (255, 255, 255, 255)]


def test_get_palette_from_rgba_tuples():
    assert get_palette([(0, 0, 0), (255, 255, 255, 255)]) == [(0, 0, 0, 255), (255, 255, 255, 255)]


def test_get_palette_shorthand():
    assert get_palette("bw") == PALETTE_BW


def test_get_palette_rejects_bad_color():
    with pytest.raises(ValueError):
        get_palette(["definitely-not-a-color"])


def test_get_palette_rejects_empty():
    with pytest.raises(ValueError):
        get_palette([])


def test_get_palette_rejects_unknown_name():
    with pytest.raises(ValueError):
        get_palette("nope")


def test_palette_applied_during_render(bw_ctx):
    # a red fill on a black/white device must come out black
    el = {"type": "rectangle", "x_start": 0, "y_start": 0, "x_end": 9, "y_end": 9, "fill": "red"}
    img = render([el], 10, 10, background="white", context=bw_ctx)
    assert img.getpixel((5, 5)) == (0, 0, 0)


def test_custom_palette_list():
    img_ctx_red = quantize_color("orange", get_palette(["black", "white", "red"]))
    # orange nearest among {black,white,red} -> red
    assert img_ctx_red == red


def test_css_named_colors():
    # Test that standard X11/CSS named colors are recognized and parsed correctly
    assert quantize_color("papayawhip", PALETTE_BW) == white
    assert quantize_color("darkgreen", PALETTE_BW) == black
    assert get_palette(["chartreuse"]) == [(127, 255, 0, 255)]

