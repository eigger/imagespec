"""Auto-layout: the ``stack`` (row/column) engine and the ``class`` parser.

These assert the *layout* behaviour — drawing of each child is still the normal
element handler's job, so we only check where tiles land.
"""

from __future__ import annotations

import pytest

from imagespec import render
from imagespec.classutil import parse_class

BLACK = (0, 0, 0)
RED = (255, 0, 0)
WHITE = (255, 255, 255)


def _rect(fill, w=10, h=5):
    return {"type": "rectangle", "x_start": 0, "y_start": 0, "x_end": w - 1, "y_end": h - 1, "fill": fill}


# --------------------------------------------------------------------------- #
# class parser
# --------------------------------------------------------------------------- #


def test_parse_class_layout_tokens_use_tailwind_scale():
    # numeric units follow Tailwind's 4px-per-unit scale (gap-4 -> 16px)
    p = parse_class("flex-col gap-4 p-2 px-3 justify-between items-center")
    assert p["direction"] == "vertical"
    assert p["gap"] == 16  # 4 * 4px
    assert p["pt"] == 8 and p["pb"] == 8  # p-2 -> 8px (top/bottom)
    assert p["pl"] == 12 and p["pr"] == 12  # px-3 -> 12px, overrides p-2 on x (later wins)
    assert p["justify"] == "between"
    assert p["align"] == "center"


def test_parse_class_arbitrary_and_fraction():
    # [N]/[Npx] bypass the scale for exact pixels; `.5` is a half-step (2px)
    p = parse_class("gap-[10] px-[5px] mt-0.5")
    assert p["gap"] == 10
    assert p["pl"] == 5 and p["pr"] == 5
    assert p["mt"] == 2  # 0.5 * 4px


def test_parse_class_negative_margin():
    p = parse_class("-ml-2 -mt-[3]")
    assert p["ml"] == -8  # -(2 * 4px)
    assert p["mt"] == -3  # arbitrary, negated
    # negative padding/gap is rejected (matches Tailwind)
    assert parse_class("-p-2 -gap-4") == {}


def test_parse_class_per_child_tokens():
    p = parse_class("grow self-end mt-2 mx-1")
    assert p["grow"] == 1
    assert p["self"] == "end"
    assert p["mt"] == 8  # 2 * 4px
    assert p["ml"] == 4 and p["mr"] == 4  # 1 * 4px


def test_parse_class_ignores_styling_and_unknown():
    # styling utilities and unknown tokens are dropped; only layout survives
    assert parse_class("text-red-500 bg-blue hover:foo font-bold grow") == {"grow": 1}
    assert parse_class("") == {}
    assert parse_class(None) == {}


def test_parse_class_accepts_list():
    assert parse_class(["flex-row", "gap-2"]) == {"direction": "horizontal", "gap": 8}


# --------------------------------------------------------------------------- #
# stack engine
# --------------------------------------------------------------------------- #


def test_column_packs_children_vertically_with_gap(ctx):
    el = {"type": "column", "x": 0, "y": 0, "gap": 2, "elements": [_rect("black"), _rect("red")]}
    img = render([el], 40, 40, background="white", context=ctx)
    assert img.getpixel((2, 2)) == BLACK  # first tile at top (rows 0-4)
    assert img.getpixel((2, 5)) == WHITE  # the 2px gap is background
    assert img.getpixel((2, 9)) == RED  # second tile pushed down by height+gap (rows 7-11)


def test_row_packs_children_horizontally_with_gap(ctx):
    el = {"type": "row", "x": 0, "y": 0, "gap": 2, "elements": [_rect("black"), _rect("red")]}
    img = render([el], 40, 40, background="white", context=ctx)
    assert img.getpixel((2, 2)) == BLACK  # first tile (cols 0-9)
    assert img.getpixel((11, 2)) == WHITE  # gap column
    assert img.getpixel((13, 2)) == RED  # second tile at width+gap (cols 12-21)


def test_stack_default_direction_is_vertical(ctx):
    el = {"type": "stack", "x": 0, "y": 0, "gap": 0, "elements": [_rect("black"), _rect("red")]}
    img = render([el], 40, 40, background="white", context=ctx)
    assert img.getpixel((2, 2)) == BLACK
    assert img.getpixel((2, 7)) == RED  # stacked below, not beside


def test_items_center_aligns_cross_axis(ctx):
    # narrow child centred horizontally in a 40px-wide column
    el = {"type": "column", "x": 0, "y": 0, "align": "center", "elements": [_rect("black", w=10)]}
    img = render([el], 40, 40, background="white", context=ctx)
    assert img.getpixel((20, 2)) == BLACK  # centred (cross-free 30 -> offset 15, cols 15-24)
    assert img.getpixel((2, 2)) == WHITE  # left edge empty


def test_class_string_drives_layout(ctx):
    # configured purely through a Tailwind-like class; gap-[2] = exact 2px
    el = {"type": "stack", "x": 0, "y": 0, "class": "flex-row gap-[2]", "elements": [_rect("black"), _rect("red")]}
    img = render([el], 40, 40, background="white", context=ctx)
    assert img.getpixel((2, 2)) == BLACK
    assert img.getpixel((13, 2)) == RED  # second tile at width(10)+gap(2)=12, cols 12-21


def test_class_gap_uses_tailwind_scale(ctx):
    # gap-2 (no brackets) = 2 * 4px = 8px between the two 10px-wide tiles
    el = {"type": "row", "x": 0, "y": 0, "class": "gap-2", "elements": [_rect("black"), _rect("red")]}
    img = render([el], 40, 40, background="white", context=ctx)
    assert img.getpixel((2, 2)) == BLACK  # cols 0-9
    assert img.getpixel((15, 2)) == WHITE  # 8px gap region (cols 10-17) is empty
    assert img.getpixel((19, 2)) == RED  # second tile at 10+8=18, cols 18-27


def test_negative_margin_nudges_tile(ctx):
    # -ml pulls the second tile back over the first (overlap), clipped safely
    el = {
        "type": "row",
        "x": 0,
        "y": 0,
        "gap": 0,
        "elements": [_rect("black"), {**_rect("red"), "class": "-ml-1"}],
    }
    img = render([el], 40, 40, background="white", context=ctx)
    # second tile would start at x=10 but -ml-1 (=-4px) pulls it back to x=6
    assert img.getpixel((8, 2)) == RED


def test_explicit_key_overrides_class(ctx):
    # class says row, explicit direction says vertical -> explicit wins
    el = {
        "type": "stack",
        "x": 0,
        "y": 0,
        "class": "flex-row",
        "direction": "vertical",
        "gap": 0,
        "elements": [_rect("black"), _rect("red")],
    }
    img = render([el], 40, 40, background="white", context=ctx)
    assert img.getpixel((2, 7)) == RED  # vertical (below), proving explicit beat class


def test_child_class_margin_shifts_tile(ctx):
    # a left margin on the second row child pushes it right (ml-[4] = exact 4px)
    el = {
        "type": "row",
        "x": 0,
        "y": 0,
        "gap": 0,
        "elements": [_rect("black"), {**_rect("red"), "class": "ml-[4]"}],
    }
    img = render([el], 40, 40, background="white", context=ctx)
    assert img.getpixel((2, 2)) == BLACK  # first tile cols 0-9
    assert img.getpixel((11, 2)) == WHITE  # 4px margin gap after col 9 stays empty
    assert img.getpixel((16, 2)) == RED  # second tile starts at 10 + 4 margin


def test_padding_insets_content(ctx):
    el = {"type": "column", "x": 0, "y": 0, "padding": 5, "elements": [_rect("black")]}
    img = render([el], 40, 40, background="white", context=ctx)
    assert img.getpixel((2, 2)) == WHITE  # padding region empty
    assert img.getpixel((7, 7)) == BLACK  # content inset by 5px


def test_stack_offset_by_x_y(ctx):
    el = {"type": "column", "x": 10, "y": 10, "elements": [_rect("black")]}
    img = render([el], 40, 40, background="white", context=ctx)
    assert img.getpixel((2, 2)) == WHITE  # nothing at canvas origin
    assert img.getpixel((12, 12)) == BLACK  # whole stack translated to (10, 10)


def test_children_without_coordinates_render(ctx):
    # text requires `x`; the stack supplies a default so children need no coords
    el = {
        "type": "column",
        "x": 0,
        "y": 0,
        "gap": 1,
        "elements": [{"type": "text", "value": "A", "size": 10}, {"type": "text", "value": "B", "size": 10}],
    }
    img = render([el], 40, 40, background="white", context=ctx)
    assert any(img.getpixel((x, y)) == BLACK for x in range(40) for y in range(40))


def test_stack_child_error_wrapped_with_context(ctx):
    # a raw (non-RenderError) failure in a child is wrapped with stack/child context
    el = {"type": "row", "elements": [{"type": "rectangle", "x_start": "oops", "y_start": 0, "x_end": 9, "y_end": 9}]}
    with pytest.raises(Exception) as exc:
        render([el], 40, 40, context=ctx)
    msg = str(exc.value)
    assert "stack" in msg and "rectangle" in msg


# --------------------------------------------------------------------------- #
# align: stretch
# --------------------------------------------------------------------------- #


def _chip(**extra):
    return {"type": "text_fit", "width": 20, "value": "a", "background": "black", "color": "white", "size": 8, **extra}


def _black_rows(img, x):
    return [y for y in range(img.height) if img.getpixel((x, y)) == BLACK]


def test_stretch_fills_the_cross_axis_for_size_aware_children(ctx):
    row = {"type": "row", "width": 40, "height": 30, "align": "stretch", "elements": [_chip()]}
    img = render([row], 40, 30, context=ctx)
    ys = _black_rows(img, 1)
    assert ys[0] == 0 and ys[-1] >= 29 - 1  # box spans the whole 30px row


def test_start_keeps_the_natural_height(ctx):
    row = {"type": "row", "width": 40, "height": 30, "align": "start", "elements": [_chip(height=12)]}
    ys = _black_rows(render([row], 40, 30, context=ctx), 1)
    assert ys[-1] <= 12


def test_stretch_respects_an_explicit_cross_size(ctx):
    row = {"type": "row", "width": 40, "height": 30, "align": "stretch", "elements": [_chip(height=12)]}
    ys = _black_rows(render([row], 40, 30, context=ctx), 1)
    assert ys[-1] <= 12


def test_stretch_in_a_column_sizes_the_width(ctx):
    col = {
        "type": "column",
        "width": 50,
        "height": 40,
        "align": "stretch",
        "elements": [
            {"type": "text_fit", "height": 10, "value": "a", "background": "black", "color": "white", "size": 8}
        ],
    }
    img = render([col], 50, 40, context=ctx)
    assert img.getpixel((48, 1)) == BLACK


def test_stretch_per_child_override_and_margins(ctx):
    col = {
        "type": "column",
        "width": 50,
        "height": 40,
        "align": "start",
        "elements": [
            {
                "type": "text_fit",
                "height": 10,
                "value": "a",
                "background": "black",
                "color": "white",
                "size": 8,
                "layout": {"align": "stretch", "margin_x": 5},
            }
        ],
    }
    img = render([col], 50, 40, context=ctx)
    assert img.getpixel((2, 1)) == WHITE and img.getpixel((6, 1)) == BLACK
    assert img.getpixel((44, 1)) == BLACK and img.getpixel((47, 1)) == WHITE


def test_stretch_leaves_other_elements_alone(ctx):
    row = {"type": "row", "width": 40, "height": 30, "align": "stretch", "elements": [_rect("black", 10, 5)]}
    ys = _black_rows(render([row], 40, 30, context=ctx), 1)
    assert ys == list(range(5))


def test_class_tokens_drive_stretch(ctx):
    chip = {"type": "text_fit", "width": 20, "value": "a", "background": "black", "color": "white", "size": 8}
    row = {"type": "row", "width": 40, "height": 30, "class": "items-stretch", "elements": [chip]}
    assert _black_rows(render([row], 40, 30, context=ctx), 1)[-1] >= 28
    row = {"type": "row", "width": 40, "height": 30, "elements": [{**chip, "class": "self-stretch"}]}
    assert _black_rows(render([row], 40, 30, context=ctx), 1)[-1] >= 28


def test_stretched_group_and_nested_stack_fill_the_cross_axis(ctx):
    fill = {"type": "rectangle", "x_start": 0, "y_start": 0, "x_end": 9, "y_end": 4, "fill": "black"}
    group = {"type": "group", "width": 12, "elements": [fill]}
    img = render(
        [{"type": "row", "width": 40, "height": 30, "align": "stretch", "elements": [group]}], 40, 30, context=ctx
    )
    assert img.getpixel((1, 1)) == BLACK  # group drawn; its box is now 30px high (content unchanged)
    inner = {"type": "column", "width": 20, "justify": "end", "elements": [_chip_col()]}
    outer = {"type": "row", "width": 40, "height": 30, "align": "stretch", "elements": [inner]}
    ys = _black_rows(render([outer], 40, 30, context=ctx), 1)
    assert ys[-1] >= 28 and ys[0] >= 18  # the stretched column spans 30px, so justify:end puts its chip at the bottom


def _chip_col():
    return {
        "type": "text_fit",
        "width": 20,
        "height": 10,
        "value": "a",
        "background": "black",
        "color": "white",
        "size": 8,
    }


def test_stretch_ignores_the_childs_own_cross_coordinate(ctx):
    row = {"type": "row", "width": 40, "height": 30, "align": "stretch", "elements": [_chip(y=5)]}
    ys = _black_rows(render([row], 40, 30, context=ctx), 1)
    assert ys[0] == 0 and ys[-1] >= 28


def test_stretch_skips_rotated_children(ctx):
    group = {"type": "group", "width": 10, "height": 10, "rotate": 90, "elements": [_rect("black", 10, 10)]}
    row = {"type": "row", "width": 40, "height": 30, "align": "stretch", "elements": [group]}
    ys = _black_rows(render([row], 40, 30, context=ctx), 1)
    assert ys == list(range(10))


def test_stretch_with_a_negative_cross_margin_still_fills(ctx):
    chip = _chip(layout={"margin_y": -3})
    row = {"type": "row", "width": 40, "height": 30, "align": "stretch", "elements": [chip]}
    ys = _black_rows(render([row], 40, 30, context=ctx), 1)
    assert ys[0] == 0 and ys[-1] >= 29


def test_stretch_sizes_sparkline_diagram_and_battery_children(ctx):
    spark = {"type": "sparkline", "width": 20, "values": [1, 3, 2], "fill": "black"}
    battery = {"type": "battery", "width": 20, "level": 100}
    for child in (spark, battery):
        row = {"type": "row", "width": 40, "height": 30, "align": "stretch", "elements": [child]}
        assert render([row], 40, 30, context=ctx).size == (40, 30)


def test_validate_accepts_an_omitted_cross_size_only_when_stretching():
    from imagespec import validate

    chip = {"type": "text_fit", "width": 20, "value": "a"}
    stretching = {"type": "row", "align": "stretch", "elements": [chip]}
    assert validate([stretching]) == []
    assert validate([{"type": "column", "class": "items-stretch", "elements": [{**chip, "height": 5}]}]) == []
    per_child = {"type": "row", "elements": [{**chip, "layout": {"align": "stretch"}}]}
    assert validate([per_child]) == []
    plain = {"type": "row", "elements": [chip]}
    assert [i.path for i in validate([plain])] == ["[0].elements[0].height"]
    # a column stretches the *width*, so a missing height is still an error there
    col = {"type": "column", "align": "stretch", "elements": [chip]}
    assert [i.path for i in validate([col])] == ["[0].elements[0].height"]
    col_ok = {"type": "column", "align": "stretch", "elements": [{"type": "text_fit", "height": 5, "value": "a"}]}
    assert validate([col_ok]) == []


def test_strict_render_accepts_a_stretched_child_without_cross_size(ctx):
    chip = {"type": "text_fit", "width": 20, "value": "a", "background": "black"}
    row = {"type": "row", "width": 40, "height": 30, "align": "stretch", "elements": [chip]}
    assert render([row], 40, 30, strict=True, context=ctx).size == (40, 30)


@pytest.mark.parametrize(
    "child",
    [
        {"type": "rectangle", "x_start": 0, "y_start": 0, "x_end": 1, "y_end": 1},
        {"type": "text_fit", "width": 5, "height": 5, "value": "a"},
    ],
    ids=["rectangle", "text_fit"],
)
def test_validate_reports_bad_layout_values_instead_of_raising(child):
    from imagespec import validate

    issues = validate([{"type": "row", "align": "stretch", "elements": [{**child, "layout": {"margin": "abc"}}]}])
    assert [i.path for i in issues] == ["[0].elements[0].layout.margin"]
