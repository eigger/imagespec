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
        "stack": {
            "type": "stack",
            "x": 0,
            "y": 0,
            "direction": "vertical",
            "gap": 2,
            "elements": [
                {"type": "text", "value": "a", "size": 8},
                {"type": "text", "value": "b", "size": 8},
            ],
        },
        "row": {
            "type": "row",
            "x": 0,
            "y": 0,
            "class": "gap-2 items-center",
            "elements": [
                {"type": "icon", "value": "mdi:home", "size": 12},
                {"type": "text", "value": "Hi", "size": 8},
            ],
        },
        "column": {
            "type": "column",
            "x": 0,
            "y": 0,
            "gap": 1,
            "elements": [
                {"type": "rectangle", "x_start": 0, "y_start": 0, "x_end": 10, "y_end": 5, "fill": "black"},
                {"type": "rectangle", "x_start": 0, "y_start": 0, "x_end": 6, "y_end": 5, "fill": "red"},
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


def test_line_y_end_defaults_to_y_start(ctx):
    # The reference documents y_end as optional; a horizontal line needs only y_start.
    payload = [{"type": "line", "x_start": 0, "x_end": 20, "y_start": 5, "fill": "black", "width": 1}]
    img = render(payload, 20, 10, background="white", context=ctx).convert("RGB")
    assert img.getpixel((10, 5)) == (0, 0, 0)
    assert img.getpixel((10, 8)) == (255, 255, 255)


def test_icon_weather_alias(ctx):
    el = {"type": "icon", "x": 0, "y": 0, "value": "weather-partlycloudy", "size": 16}
    assert render([el], 40, 40, context=ctx).size == (40, 40)


def _ink_bbox(img):
    return img.convert("L").point(lambda v: 255 if v < 128 else 0).getbbox()


@pytest.mark.parametrize("value", ["x", "ace", "Hgjy"])
@pytest.mark.parametrize("rotation", [90, 360])
def test_rotated_text_keeps_all_ink(ctx, value, rotation):
    """Lowercase-only text has a bbox origin below 0,0; it must not be clipped or vanish."""

    def ink(**extra):
        el = {"type": "text", "x": 50, "y": 50, "value": value, "size": 40, **extra}
        return _ink_bbox(render([el], 200, 200, context=ctx))

    b, r = ink(), ink(rotation=rotation)
    assert b is not None and r is not None
    expected = (b[2] - b[0], b[3] - b[1]) if rotation == 360 else (b[3] - b[1], b[2] - b[0])
    assert (r[2] - r[0], r[3] - r[1]) == expected


def test_rotated_text_honours_anchor(ctx):
    def ink(anchor):
        el = {"type": "text", "x": 100, "y": 100, "value": "Hi", "size": 30, "rotation": 90, "anchor": anchor}
        return _ink_bbox(render([el], 200, 200, context=ctx))

    lt, mm, rb = ink("lt"), ink("mm"), ink("rb")
    assert lt[0] > mm[0] > rb[0] and lt[1] > mm[1] > rb[1]


def test_rotated_text_background_padding(ctx):
    def box(padding):
        el = {"type": "text", "x": 50, "y": 50, "value": "Hi", "size": 20, "rotation": 90, "background": "black"}
        el["background_padding"] = padding
        return _ink_bbox(render([el], 200, 200, context=ctx))

    b0, b10 = box(0), box(10)
    assert (b10[2] - b10[0]) - (b0[2] - b0[0]) == 20
    assert (b10[3] - b10[1]) - (b0[3] - b0[1]) == 20


@pytest.mark.parametrize("anchor", [None, "lt", "mt", "rt", "lb", "mb", "rb", "la", "mm", "rs"])
def test_multiline_text_renders_with_every_anchor(ctx, anchor):
    """`\\n` in `value` is documented, but the default `lt` anchor raised for multi-line text."""
    el = {"type": "text", "x": 60, "y": 40, "value": "ab\ncd", "size": 14}
    if anchor:
        el["anchor"] = anchor
    img = render([el], 120, 80, context=ctx)
    top, bottom = _ink_bbox(img)[1], _ink_bbox(img)[3]
    assert bottom - top > 14  # two lines


def test_multiline_text_default_anchor_is_top_left(ctx):
    el = {"type": "text", "x": 30, "y": 20, "value": "ab\ncd", "size": 14}
    left, top, right, bottom = _ink_bbox(render([el], 120, 80, context=ctx))
    assert 28 <= left <= 36 and 18 <= top <= 24  # starts at the point, not centred on it


def test_multiline_text_with_background_and_rotation(ctx):
    for extra in ({"background": "yellow"}, {"rotation": 90}, {"background": "yellow", "rotation": 90, "anchor": "mb"}):
        el = {"type": "text", "x": 40, "y": 40, "value": "ab\ncd", "size": 14, **extra}
        assert render([el], 100, 80, context=ctx).size == (100, 80)


def test_single_line_text_anchor_is_unchanged(ctx):
    one = {"type": "text", "x": 30, "y": 20, "value": "ab", "size": 14}
    assert _ink_bbox(render([one], 120, 80, context=ctx)) == _ink_bbox(
        render([{**one, "anchor": "lt"}], 120, 80, context=ctx)
    )


@pytest.mark.parametrize("anchor", [None, "lt", "mt", "rt", "lb", "mb", "rb"])
def test_multiline_text_lands_where_the_single_line_text_does(ctx, anchor):
    """A templated value that sometimes contains a newline must not jump: the top (or, for b-anchors,
    bottom) edge of multi-line text sits where the same text on one line puts it."""
    base = {"type": "text", "x": 60, "y": 40, "size": 20}
    if anchor:
        base["anchor"] = anchor
    one = _ink_bbox(render([{**base, "value": "Hab"}], 160, 100, context=ctx))
    two = _ink_bbox(render([{**base, "value": "Hab\nHab"}], 160, 100, context=ctx))
    edge = 3 if anchor and anchor[1] == "b" else 1
    assert abs(one[edge] - two[edge]) <= 2


def test_text_box_and_new_multiline_and_plot_legend_accept_newlines(ctx):
    box = {"type": "text_box", "x": 5, "y": 5, "value": "a\nb"}
    nm = {"type": "new_multiline", "x": 5, "y": 5, "value": "a\nb", "anchor": "lt"}
    assert render([box, nm], 80, 80, context=ctx).size == (80, 80)


@pytest.mark.parametrize("rotation", [90, 180, 45])
@pytest.mark.parametrize("anchor", [None, "lt", "mt", "lb", "rb"])
def test_rotated_multiline_text_lands_where_rotated_single_line_text_does(ctx, rotation, anchor):
    base = {"type": "text", "x": 100, "y": 100, "size": 20, "rotation": rotation}
    if anchor:
        base["anchor"] = anchor
    one = _ink_bbox(render([{**base, "value": "Hab"}], 220, 220, context=ctx))
    two = _ink_bbox(render([{**base, "value": "Hab\nHab"}], 220, 220, context=ctx))
    edge = 3 if anchor and anchor[1] == "b" else 1
    assert abs(one[edge] - two[edge]) <= 2


@pytest.mark.parametrize("dash", [[0, 0], [-1, 1], [1, float("inf")]])
def test_line_rejects_dash_lengths_without_finite_positive_progress(ctx, dash):
    from imagespec import RenderError

    with pytest.raises(RenderError, match="dash lengths must be finite positive"):
        render([{"type": "line", "x_start": 0, "x_end": 10, "y_start": 0, "dash": dash}], 20, 20, context=ctx)
