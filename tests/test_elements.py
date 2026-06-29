"""Every element type renders without raising, and the matrix stays exhaustive."""

from __future__ import annotations

import pytest

from imagespec import known_types, render


def _samples(data_url):
    """One representative payload per element type (except `plot`, see test_plot)."""
    return {
        "line": {"type": "line", "x_start": 0, "y_start": 5, "x_end": 39, "y_end": 5},
        "rectangle": {"type": "rectangle", "x_start": 0, "y_start": 0, "x_end": 39, "y_end": 39},
        "rectangle_pattern": {
            "type": "rectangle_pattern",
            "x_start": 0,
            "x_size": 5,
            "y_start": 0,
            "y_size": 5,
            "x_repeat": 3,
            "y_repeat": 3,
            "x_offset": 2,
            "y_offset": 2,
        },
        "circle": {"type": "circle", "x": 20, "y": 20, "radius": 10},
        "ellipse": {"type": "ellipse", "x_start": 0, "y_start": 0, "x_end": 39, "y_end": 25},
        "arc": {
            "type": "arc",
            "x_start": 0,
            "y_start": 0,
            "x_end": 39,
            "y_end": 39,
            "start_angle": 0,
            "end_angle": 180,
        },
        "polygon": {"type": "polygon", "points": "0,0;39,0;20,39"},
        "gauge": {"type": "gauge", "x": 20, "y": 20, "radius": 15, "progress": 50, "show_value": True},
        "text": {"type": "text", "x": 1, "y": 1, "value": "hi", "size": 10},
        "text_box": {"type": "text_box", "x": 1, "y": 1, "value": "hi", "size": 10},
        "multiline": {"type": "multiline", "x": 1, "value": "a,b", "delimiter": ",", "offset_y": 10, "size": 8},
        "new_multiline": {
            "type": "new_multiline",
            "x": 1,
            "y": 1,
            "value": "a\nb",
            "size": 8,
            "width": 30,
            "fit": "width",
        },
        "table": {
            "type": "table",
            "x": 0,
            "y": 0,
            "columns": [18, 18],
            "rows": [["a", "b"], ["1", "2"]],
            "font_size": 8,
        },
        "text_fit": {
            "type": "text_fit",
            "x": 0,
            "y": 0,
            "width": 40,
            "height": 20,
            "value": "a long label that overflows the box",
            "size": 14,
            "fit": "shrink",
        },
        "qrcode": {"type": "qrcode", "x": 0, "y": 0, "data": "x", "boxsize": 1},
        "barcode": {"type": "barcode", "x": 0, "y": 0, "data": "123", "module_height": 3, "font_size": 3},
        "datamatrix": {"type": "datamatrix", "x": 0, "y": 0, "data": "hi", "boxsize": 1},
        "icon": {"type": "icon", "x": 0, "y": 0, "value": "mdi:home", "size": 16},
        "dlimg": {"type": "dlimg", "x": 0, "y": 0, "url": data_url, "xsize": 8, "ysize": 8},
        "diagram": {
            "type": "diagram",
            "x": 0,
            "y": 0,
            "height": 35,
            "width": 40,
            "margin": 4,
            "bars": {"values": "a,1;b,2", "color": "black", "margin": 4},
        },
        "progress_bar": {
            "type": "progress_bar",
            "x_start": 0,
            "y_start": 0,
            "x_end": 39,
            "y_end": 12,
            "progress": 50,
            "show_percentage": True,
        },
        "pie": {"type": "pie", "x": 20, "y": 20, "radius": 15, "values": "a,30;b,50;c,20", "inner_radius": 6},
        "sparkline": {
            "type": "sparkline",
            "x": 0,
            "y": 0,
            "width": 40,
            "height": 20,
            "values": "1,3,2,5,4,2,6",
            "fill": "yellow",
            "dot_last": True,
        },
        "rich_text": {
            "type": "rich_text",
            "x": 2,
            "y": 20,
            "spans": [{"text": "T "}, {"icon": "mdi:home", "size": 14}, {"text": " 23"}],
            "size": 12,
        },
        "group": {
            "type": "group",
            "x": 5,
            "y": 5,
            "width": 30,
            "height": 30,
            "elements": [
                {"type": "rectangle", "x_start": 0, "y_start": 0, "x_end": 20, "y_end": 20, "outline": "black"}
            ],
        },
        "legend": {
            "type": "legend",
            "x": 0,
            "y": 0,
            "items": [{"label": "a", "color": "black"}, {"label": "b", "color": "red"}],
            "size": 8,
        },
        "star_rating": {"type": "star_rating", "x": 0, "y": 0, "rating": 3.5, "max": 5, "size": 8},
        "battery": {"type": "battery", "x": 0, "y": 0, "width": 30, "height": 14, "level": 60},
    }


def test_matrix_is_exhaustive(data_url):
    # If a new element is registered, force a sample (and thus a test) for it.
    covered = set(_samples(data_url)) | {"plot"}
    assert covered == known_types(), f"untested element types: {known_types() - covered}"


def test_every_element_renders(ctx, data_url):
    for name, el in _samples(data_url).items():
        img = render([el], 40, 40, context=ctx)
        assert img.size == (40, 40) and img.mode == "RGB", f"{name} failed"


@pytest.mark.parametrize("mode", ["stretch", "fit", "contain", "fill"])
def test_dlimg_fit_modes(ctx, data_url, mode):
    el = {"type": "dlimg", "x": 0, "y": 0, "url": data_url, "xsize": 20, "ysize": 10, "mode": mode}
    assert render([el], 40, 40, context=ctx).size == (40, 40)


def test_icon_weather_alias(ctx):
    el = {"type": "icon", "x": 0, "y": 0, "value": "weather-partlycloudy", "size": 16}
    assert render([el], 40, 40, context=ctx).size == (40, 40)
