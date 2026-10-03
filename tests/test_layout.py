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


@pytest.mark.parametrize("x,y", [(5.6, 3.4), (5.5, 2.5), (-0.6, 7.2)])
def test_stack_and_group_round_a_fractional_offset_the_same_way(ctx, x, y):
    def tile_box(container):
        img = render([container], 40, 30, context=ctx)
        bbox = img.convert("L").point(lambda v: 255 if v < 128 else 0).getbbox()
        return bbox

    rect = _rect("black", 4, 4)
    group = {"type": "group", "x": x, "y": y, "elements": [rect]}
    stack = {"type": "stack", "x": x, "y": y, "elements": [rect]}
    assert tile_box(stack) == tile_box(group)


def _first_ink(el, ctx, w=60, h=40):
    img = render([el], w, h, context=ctx)
    return img.convert("L").point(lambda v: 255 if v < 128 else 0).getbbox()


@pytest.mark.parametrize("raw,expected", [(2.4, 2), (2.6, 3), (3.0, 3), ("2.6", 3)])
def test_stack_padding_rounds_to_the_nearest_pixel(ctx, raw, expected):
    row = {"type": "row", "padding": raw, "elements": [_rect("black", 4, 4)]}
    assert _first_ink(row, ctx)[:2] == (expected, expected)


@pytest.mark.parametrize("raw,expected", [(2.4, 2), (2.6, 3)])
def test_stack_gap_and_child_margin_round_to_the_nearest_pixel(ctx, raw, expected):
    gap = {"type": "row", "gap": raw, "elements": [_rect("black", 4, 4), _rect("black", 4, 4)]}
    assert _first_ink(gap, ctx)[2] == 4 + expected + 4
    margin = {"type": "row", "elements": [{**_rect("black", 4, 4), "layout": {"margin": raw}}]}
    assert _first_ink(margin, ctx)[:2] == (expected, expected)
    side = {"type": "row", "elements": [{**_rect("black", 4, 4), "layout": {"margin_left": raw}}]}
    assert _first_ink(side, ctx)[0] == expected


@pytest.mark.parametrize(
    "extra",
    [
        {"layout": {"margin": "inf"}},
        {"layout": {"margin": float("inf")}},
        {"class": "m-inf"},
        {"class": "gap-inf grow-inf p-nan ml-1e999"},
        {"rotate": "inf"},
        {"rotate": 10**400},
    ],
)
@pytest.mark.parametrize("where", ["child", "container"])
def test_validate_does_not_raise_on_infinite_layout_lengths(extra, where):
    from imagespec import validate

    child = {"type": "text_fit", "width": 5, "height": 5, "value": "a"}
    row = {"type": "row", "align": "stretch", "elements": [child]}
    (child if where == "child" else row).update(extra)
    assert isinstance(validate([row]), list)  # must not raise OverflowError/ValueError


def test_non_finite_class_tokens_are_ignored():
    p = parse_class("m-inf gap-nan p-1e999 grow-inf px-[1e999px] p-2")
    assert p == parse_class("p-2")


# --------------------------------------------------------------------------- #
# container style: background / outline / radius
# --------------------------------------------------------------------------- #

YELLOW = (255, 255, 0)


def test_stack_background_fills_the_whole_box_including_padding(ctx):
    col = {
        "type": "column",
        "x": 5,
        "y": 5,
        "width": 20,
        "height": 12,
        "padding": 4,
        "background": "yellow",
        "elements": [],
    }
    img = render([col], 40, 30, context=ctx)
    assert img.getpixel((5, 5)) == YELLOW and img.getpixel((24, 16)) == YELLOW  # corners of the box
    assert img.getpixel((4, 5)) == WHITE and img.getpixel((25, 16)) == WHITE and img.getpixel((24, 17)) == WHITE


def test_stack_background_sits_behind_the_children(ctx):
    col = {"type": "column", "width": 20, "height": 20, "background": "yellow", "elements": [_rect("black", 6, 6)]}
    img = render([col], 30, 30, context=ctx)
    assert img.getpixel((2, 2)) == BLACK and img.getpixel((10, 10)) == YELLOW


def test_stack_outline_width_and_radius(ctx):
    col = {
        "type": "column",
        "width": 20,
        "height": 20,
        "outline": "red",
        "width_outline": 2,
        "radius": 6,
        "elements": [],
    }
    img = render([col], 30, 30, context=ctx)
    assert img.getpixel((10, 0)) == RED and img.getpixel((10, 1)) == RED  # 2px border on the top edge
    assert img.getpixel((10, 2)) == WHITE  # not filled inside (no background)
    assert img.getpixel((0, 0)) == WHITE  # rounded corner is cut away


def test_stack_without_style_draws_nothing_extra(ctx):
    plain = render([{"type": "row", "width": 20, "height": 20, "elements": [_rect("black")]}], 30, 30, context=ctx)
    styled_none = render(
        [{"type": "row", "width": 20, "height": 20, "background": None, "outline": None, "elements": [_rect("black")]}],
        30,
        30,
        context=ctx,
    )
    assert plain.tobytes() == styled_none.tobytes()


def test_stack_background_rotates_with_the_stack(ctx):
    col = {"type": "column", "width": 20, "height": 10, "rotate": 90, "background": "yellow", "elements": []}
    img = render([col], 30, 30, context=ctx)
    xs = [x for x in range(30) if img.getpixel((x, 5)) == YELLOW]
    ys = [y for y in range(30) if img.getpixel((5, y)) == YELLOW]
    assert (len(xs), len(ys)) == (10, 20)  # a 20x10 box turned into 10 wide x 20 tall


def test_stack_background_validates_and_flags_unknown_colors():
    from imagespec import validate

    ok = {"type": "row", "background": "yellow", "outline": "#000", "radius": 4, "elements": []}
    assert validate([ok]) == []
    bad = {"type": "row", "background": "yelow", "elements": []}
    assert [i.path for i in validate([bad])] == ["[0].background"]


def _card(text, bg, **extra):
    return {
        "type": "row",
        "padding": 4,
        "background": bg,
        "elements": [{"type": "text", "value": text, "size": 12}],
        **extra,
    }


def test_card_without_size_hugs_its_content(ctx):
    img = render([_card("Hi", "yellow", x=5, y=5)], 100, 60, context=ctx)
    xs = [x for x in range(100) if img.getpixel((x, 10)) == YELLOW or img.getpixel((x, 10)) == BLACK]
    ys = [y for y in range(60) if img.getpixel((7, y)) == YELLOW]
    assert 5 in xs and max(xs) < 40  # nowhere near the 100px canvas width
    assert min(ys) == 5 and max(ys) < 30


def test_cards_in_a_column_do_not_swallow_each_other(ctx):
    col = {
        "type": "column",
        "width": 80,
        "height": 70,
        "padding": 3,
        "gap": 5,
        "background": "black",
        "elements": [_card("A", "yellow"), _card("B", "white")],
    }
    img = render([col], 80, 70, context=ctx)
    colors_down_the_middle = [img.getpixel((5, y)) for y in range(70)]
    assert YELLOW in colors_down_the_middle and WHITE in colors_down_the_middle  # both cards drawn
    assert colors_down_the_middle.index(YELLOW) < colors_down_the_middle.index(WHITE)


def test_cards_in_a_row_sit_side_by_side_with_the_gap(ctx):
    row = {"type": "row", "width": 120, "height": 30, "gap": 6, "elements": [_card("A", "yellow"), _card("B", "red")]}
    img = render([row], 120, 30, context=ctx)
    y = 2
    yellow_x = [x for x in range(120) if img.getpixel((x, y)) == YELLOW]
    red_x = [x for x in range(120) if img.getpixel((x, y)) == RED]
    assert yellow_x and red_x and max(yellow_x) < min(red_x)
    assert min(red_x) - max(yellow_x) - 1 == 6


def test_card_hugs_one_axis_and_honours_the_other(ctx):
    img = render([_card("Hi", "yellow", width=60)], 100, 60, context=ctx)
    assert img.getpixel((59, 3)) == YELLOW and img.getpixel((60, 3)) == WHITE  # fixed width
    ys = [y for y in range(60) if img.getpixel((2, y)) == YELLOW]
    assert max(ys) < 30  # hugged height


def test_card_with_align_stretch_in_a_column_fills_the_width(ctx):
    col = {"type": "column", "width": 80, "height": 70, "align": "stretch", "elements": [_card("A", "yellow")]}
    img = render([col], 80, 70, context=ctx)
    run = [x for x in range(80) if img.getpixel((x, 2)) in (YELLOW, BLACK)]
    assert min(run) == 0 and max(run) == 79  # a row child with no width is stretched across the column


def _col_ink_height(img, x, color):
    return len([y for y in range(img.height) if img.getpixel((x, y)) == color])


def test_hugged_card_stretches_children_to_the_content_not_the_canvas(ctx):
    """Flexbox: the cross size of a hugged card is its tallest non-stretched child."""
    card = {
        "type": "row",
        "x": 5,
        "y": 5,
        "padding": 3,
        "background": "yellow",
        "outline": "black",
        "align": "stretch",
        "elements": [
            {"type": "column", "background": "red", "elements": [{"type": "text", "value": "a", "size": 10}]},
            {"type": "text", "value": "Hello", "size": 14},
        ],
    }
    img = render([card], 120, 90, context=ctx)
    plain = render([{**card, "align": "start"}], 120, 90, context=ctx)
    height = lambda im: _col_ink_height(im, 6, YELLOW) + _col_ink_height(im, 6, BLACK)  # noqa: E731
    assert height(img) < 40  # hugs "Hello" + padding, nowhere near the 85px left on the canvas
    red_col = [y for y in range(90) if img.getpixel((10, y)) == RED]
    assert len(red_col) > _col_ink_height(plain, 10, RED)  # and the red column was stretched up to it
    assert max(red_col) < 40


def test_hugged_column_of_cards_with_stretch_is_as_wide_as_the_widest_card(ctx):
    col = {
        "type": "column",
        "x": 2,
        "y": 2,
        "padding": 2,
        "gap": 3,
        "background": "black",
        "align": "stretch",
        "elements": [_card("Hi", "yellow"), _card("A longer one", "red")],
    }
    img = render([col], 200, 100, context=ctx)
    wide = max(x for x in range(200) if img.getpixel((x, 3)) == BLACK)
    assert wide < 100  # not canvas-wide
    # both cards end at the same column: the narrow one was stretched to the wide one
    right_edges = []
    for color in (YELLOW, RED):
        xs = [x for x in range(200) for y in range(100) if img.getpixel((x, y)) == color]
        right_edges.append(max(xs))
    assert abs(right_edges[0] - right_edges[1]) <= 1


def test_stretched_size_required_children_follow_the_hugged_cross_size(ctx):
    chip = {"type": "text_fit", "width": 20, "value": "a", "background": "black", "color": "white", "size": 8}
    card = {
        "type": "row",
        "padding": 2,
        "background": "yellow",
        "align": "stretch",
        "elements": [chip, {"type": "text", "value": "Hello", "size": 16}],
    }
    img = render([card], 100, 80, context=ctx)
    ys = [y for y in range(80) if img.getpixel((3, y)) == BLACK]
    assert ys and max(ys) < 40


def test_negative_margins_beyond_the_size_do_not_make_the_card_vanish(ctx):
    card = {
        "type": "row",
        "padding": 0,
        "background": "yellow",
        "elements": [{**_rect("black", 10, 10), "layout": {"margin": -20}}],
    }
    assert render([card], 30, 30, context=ctx).size == (30, 30)


def test_empty_card_hugs_to_padding_only(ctx):
    card = {"type": "row", "x": 2, "y": 2, "padding": 3, "background": "yellow", "elements": []}
    img = render([card], 30, 30, context=ctx)
    ys = [y for y in range(30) if img.getpixel((3, y)) == YELLOW]
    xs = [x for x in range(30) if img.getpixel((x, 3)) == YELLOW]
    assert (len(xs), len(ys)) == (6, 6)


@pytest.mark.parametrize("size", [{"width": 0}, {"height": 0}, {"width": -5}])
def test_zero_or_negative_card_size_draws_nothing(ctx, size):
    card = {"type": "column", "outline": "black", "elements": [], **size}
    img = render([card], 30, 30, context=ctx)
    assert img.getcolors() == [(900, WHITE)]


@pytest.mark.parametrize(
    "extra", [{"radius": -5}, {"radius": float("inf")}, {"width_outline": float("nan")}, {"width_outline": -2}]
)
def test_odd_radius_and_outline_widths_do_not_raise(ctx, extra):
    card = {"type": "column", "width": 20, "height": 20, "outline": "black", "elements": [], **extra}
    assert render([card], 30, 30, context=ctx).size == (30, 30)


def test_card_of_only_size_required_stretched_children_falls_back_to_the_available_cross_size(ctx):
    """Pinned: with nothing measurable the cross size is the available space (documented on width/height)."""
    chip = {"type": "text_fit", "width": 20, "value": "a", "background": "black", "color": "white", "size": 8}
    card = {"type": "row", "x": 5, "y": 5, "background": "yellow", "align": "stretch", "elements": [chip]}
    img = render([card], 60, 50, context=ctx)
    ys = [y for y in range(50) if img.getpixel((6, y)) == BLACK]
    assert min(ys) == 5 and max(ys) == 49


# --------------------------------------------------------------------------- #
# grow on cards
# --------------------------------------------------------------------------- #


def _xs(img, color, y):
    return [x for x in range(img.width) if img.getpixel((x, y)) == color]


def test_growing_card_fills_the_free_space(ctx):
    row = {
        "type": "row",
        "width": 120,
        "height": 30,
        "gap": 6,
        "elements": [_card("A", "yellow"), _card("B", "red", layout={"grow": 1})],
    }
    img = render([row], 120, 30, context=ctx)
    red = _xs(img, RED, 2)
    assert max(red) == 119  # the red card runs to the end of the row
    yellow = _xs(img, YELLOW, 2)
    assert min(red) - max(yellow) - 1 == 6  # the gap is untouched


def test_growing_cards_share_the_free_space_by_weight(ctx):
    def widths(grows):
        els = [_card("A", "yellow", layout={"grow": grows[0]}), _card("B", "red", layout={"grow": grows[1]})]
        img = render([{"type": "row", "width": 150, "height": 30, "elements": els}], 150, 30, context=ctx)
        return len(_xs(img, YELLOW, 2)), len(_xs(img, RED, 2)), img

    natural_y, natural_r, _ = widths((0, 0))
    y, r, img = widths((1, 2))
    extra_y, extra_r = y - natural_y, r - natural_r
    assert extra_y > 0 and abs(extra_r - 2 * extra_y) <= 2  # the free space is split 1:2
    assert max(_xs(img, RED, 2)) == 149  # and all of it is used


def test_growing_card_in_a_column_fills_the_height(ctx):
    col = {
        "type": "column",
        "width": 60,
        "height": 90,
        "gap": 4,
        "elements": [_card("A", "yellow"), _card("B", "red", layout={"grow": 1})],
    }
    img = render([col], 60, 90, context=ctx)
    red_rows = [y for y in range(90) if img.getpixel((2, y)) == RED]
    assert max(red_rows) == 89


def test_growing_card_with_an_explicit_size_keeps_it(ctx):
    row = {"type": "row", "width": 120, "height": 30, "elements": [_card("A", "red", width=40, layout={"grow": 1})]}
    img = render([row], 120, 30, context=ctx)
    assert max(_xs(img, RED, 2)) == 39


def test_unstyled_growing_stack_is_unchanged(ctx):
    inner = {"type": "row", "elements": [{"type": "text", "value": "A", "size": 12}], "layout": {"grow": 1}}
    row = {"type": "row", "width": 100, "height": 20, "elements": [inner, {"type": "text", "value": "Z", "size": 12}]}
    plain = {**row, "elements": [{k: v for k, v in inner.items() if k != "layout"}, row["elements"][1]]}
    a = render([row], 100, 20, context=ctx)
    b = render([plain], 100, 20, context=ctx)
    xs = lambda im: [x for x in range(100) if any(im.getpixel((x, y)) == BLACK for y in range(20))]  # noqa: E731
    assert max(xs(a)) > max(xs(b))  # grow still pushes the sibling to the end, as before


def test_growing_card_respects_margins(ctx):
    row = {
        "type": "row",
        "width": 100,
        "height": 30,
        "elements": [_card("B", "red", layout={"grow": 1, "margin_x": 5})],
    }
    img = render([row], 100, 30, context=ctx)
    red = _xs(img, RED, 2)
    assert min(red) == 5 and max(red) == 94


def test_growing_card_rotated_90_is_left_alone(ctx):
    row = {
        "type": "row",
        "width": 120,
        "height": 60,
        "elements": [_card("R", "red", rotate=90, layout={"grow": 1}), _card("Z", "yellow")],
    }
    base = {**row, "elements": [_card("R", "red", rotate=90), _card("Z", "yellow")]}
    img, ref = render([row], 120, 60, context=ctx), render([base], 120, 60, context=ctx)
    assert len(_xs(img, RED, 2)) == len(_xs(ref, RED, 2))  # unchanged size
    assert min(_xs(img, YELLOW, 2)) > min(_xs(ref, YELLOW, 2))  # grow still pushes the sibling to the end


@pytest.mark.parametrize("pos", [{"x": 30}, {"x": -10}, {"y": 20}])
def test_growing_card_ignores_its_own_coordinates(ctx, pos):
    row = {
        "type": "row",
        "width": 120,
        "height": 30,
        "gap": 6,
        "elements": [_card("A", "yellow"), _card("B", "red", layout={"grow": 1}, **pos)],
    }
    img = render([row], 120, 30, context=ctx)
    assert max(_xs(img, RED, 2)) == 119


def test_growing_card_with_an_invisible_box_still_pushes_its_sibling(ctx):
    ghost = {
        "type": "row",
        "outline": "black",
        "width_outline": 0,
        "elements": [{"type": "text", "value": "g", "size": 12}],
        "layout": {"grow": 1},
    }
    row = {"type": "row", "width": 100, "height": 20, "elements": [ghost, _card("Z", "yellow")]}
    img = render([row], 100, 20, context=ctx)
    assert max(_xs(img, YELLOW, 2)) >= 98  # the slot was kept, so the sibling sits at the end


@pytest.mark.parametrize("y", [20, -10])
def test_growing_card_in_a_column_ignores_its_own_main_coordinate(ctx, y):
    col = {
        "type": "column",
        "width": 60,
        "height": 90,
        "gap": 4,
        "elements": [_card("A", "yellow"), _card("B", "red", y=y, layout={"grow": 1})],
    }
    img = render([col], 60, 90, context=ctx)
    assert max(y for y in range(90) if img.getpixel((2, y)) == RED) == 89


# --------------------------------------------------------------------------- #
# long text in a column wraps to the slot instead of being clipped
# --------------------------------------------------------------------------- #

LONG = "alpha beta gamma delta epsilon zeta"


def _ink(img):
    return img.convert("L").point(lambda v: 255 if v < 128 else 0).getbbox()


def test_long_text_in_a_column_wraps_inside_the_column(ctx):
    col = {"type": "column", "width": 60, "elements": [{"type": "text", "value": LONG, "size": 12}]}
    left, top, right, bottom = _ink(render([col], 200, 120, context=ctx))
    assert right <= 60 and bottom - top > 25  # several lines, all inside the 60px column


def test_the_same_text_is_clipped_in_a_row_as_before(ctx):
    row = {"type": "row", "width": 60, "elements": [{"type": "text", "value": LONG, "size": 12}]}
    left, top, right, bottom = _ink(render([row], 200, 120, context=ctx))
    assert right <= 60 and bottom - top < 16  # a single line: rows can't know their slot width


def test_text_that_fits_is_untouched(ctx):
    col = {"type": "column", "width": 150, "elements": [{"type": "text", "value": "short", "size": 12}]}
    wrapped = render([col], 200, 60, context=ctx)
    plain = render([{"type": "text", "x": 0, "y": 0, "value": "short", "size": 12}], 200, 60, context=ctx)
    assert _ink(wrapped)[2:] and _ink(wrapped)[2] - _ink(wrapped)[0] == _ink(plain)[2] - _ink(plain)[0]


def test_explicit_newlines_and_blank_lines_survive_wrapping(ctx):
    from imagespec.elements.layout import _wrap_text_to

    class _State:
        context = ctx

    child = {"type": "text", "value": "one\n\ntwo " + LONG, "size": 12}
    lines = _wrap_text_to(_State, child, 60)["value"].split("\n")
    assert lines[:3] == ["one", "", "two"] or lines[:3] == ["one", "", "two alpha"]
    assert len(lines) > 4  # the long paragraph wrapped, the original breaks are all still there


def test_whitespace_of_lines_that_fit_is_kept(ctx):
    from imagespec.elements.layout import _wrap_text_to

    class _State:
        context = ctx

    value = "  indented\nA  B\n" + LONG
    lines = _wrap_text_to(_State, {"type": "text", "value": value, "size": 12}, 60)["value"].split("\n")
    assert lines[0] == "  indented" and lines[1] == "A  B"  # only the overflowing paragraph is reflowed


def test_a_failing_font_resolver_is_reported_with_the_child_path():
    from imagespec import RenderContext, RenderError

    def boom(name):
        raise RuntimeError("no such font")

    col = {"type": "column", "width": 60, "elements": [{"type": "text", "value": LONG, "size": 12, "font": "x.ttf"}]}
    with pytest.raises(RenderError) as exc:
        render([col], 100, 100, context=RenderContext(palette="4", font_resolver=boom))
    assert exc.value.path == "[0].elements[0]"


def test_wrapping_measures_ink_only_near_the_slot_edge(ctx, monkeypatch):
    import imagespec.elements.layout as layout

    calls = []
    real = layout.mono_draw
    monkeypatch.setattr(layout, "mono_draw", lambda im: calls.append(1) or real(im))
    words = " ".join(["lorem", "ipsum", "dolor", "sit", "amet"] * 80)
    col = {"type": "column", "width": 300, "height": 2000, "elements": [{"type": "text", "value": words, "size": 10}]}
    render([col], 320, 600, context=ctx)
    assert len(calls) < 250  # 400 words: a drawn measurement for every trial would be >> this


def test_explicit_max_width_is_left_alone(ctx):
    col = {
        "type": "column",
        "width": 60,
        "elements": [{"type": "text", "value": LONG, "size": 12, "max_width": 400}],
    }
    left, top, right, bottom = _ink(render([col], 400, 120, context=ctx))
    assert bottom - top < 16  # the element's own max_width (400px) wins: one line, clipped by the column


def test_rotated_text_is_not_wrapped_by_the_column(ctx):
    col = {"type": "column", "width": 60, "elements": [{"type": "text", "value": LONG, "size": 12, "rotation": 90}]}
    left, top, right, bottom = _ink(render([col], 400, 400, context=ctx))
    assert right - left < 16 and bottom - top > 100  # still one long rotated line


def test_wrapped_text_respects_padding_and_margins(ctx):
    col = {
        "type": "column",
        "width": 80,
        "padding": 5,
        "elements": [{"type": "text", "value": LONG, "size": 12, "layout": {"margin_x": 4}}],
    }
    left, top, right, bottom = _ink(render([col], 200, 200, context=ctx))
    assert left >= 9 and right <= 80 - 9


def test_text_wraps_inside_a_nested_card(ctx):
    card = {
        "type": "column",
        "width": 70,
        "padding": 4,
        "background": "yellow",
        "elements": [{"type": "text", "value": LONG, "size": 12}],
    }
    img = render([card], 200, 200, context=ctx)
    text_ink = [(x, y) for x in range(200) for y in range(200) if img.getpixel((x, y)) == BLACK]
    assert max(x for x, _ in text_ink) <= 70 - 4
    assert max(y for _, y in text_ink) - min(y for _, y in text_ink) > 30  # wrapped onto several lines, not clipped


@pytest.mark.parametrize("size", [8, 10, 12, 14, 16, 22, 30])
@pytest.mark.parametrize("avail", list(range(40, 160, 7)))
def test_wrapped_lines_never_overflow_the_slot_as_drawn(ctx, size, avail):
    """Measured by really drawing each line in 1-bit (hinted glyphs are wider than getlength says)."""
    from PIL import Image

    from imagespec.elements.layout import _wrap_text_to
    from imagespec.utils import mono_draw

    class _State:  # only .context is used
        context = ctx

    child = {"type": "text", "value": "Living room temperature is 21.5 degrees and humidity 40 percent", "size": size}
    wrapped = _wrap_text_to(_State, child, avail)["value"].split("\n")
    font = ctx.font(None, size)
    for line in wrapped:
        scratch = Image.new("L", (avail * 3, size * 3), 0)
        mono_draw(scratch).text((0, 0), line, fill=255, font=font)
        right = scratch.getbbox()[2]
        assert right <= avail or " " not in line, (line, right, avail)  # a single long word can't be split


@pytest.mark.parametrize(
    "text,size,avail",
    [("room degrees humidity", 10, 70), ("degrees office humidity", 10, 72), ("degrees Ty quick", 10, 57)],
)
def test_wrapped_lines_never_clip_at_small_sizes_where_hinting_widens_glyphs(ctx, text, size, avail):
    """Regression: 1-bit ink is up to ~25% wider than the advance for some words at 8-10px."""
    assert _clipped_lines(ctx, text, size, avail) == []


def _clipped_lines(ctx, text, size, avail):
    from PIL import Image

    from imagespec.elements.layout import _wrap_text_to
    from imagespec.utils import mono_draw

    class _State:
        context = ctx

    font = ctx.font(None, size)
    out = []
    for line in _wrap_text_to(_State, {"type": "text", "value": text, "size": size}, avail)["value"].split("\n"):
        scratch = Image.new("L", (int(font.getlength(line) * 2) + 40, size * 3), 0)
        mono_draw(scratch).text((0, 0), line, fill=255, font=font)
        box = scratch.getbbox()
        if box and box[2] > avail and " " in line.strip():  # a lone long word cannot be split
            out.append((line, box[2], avail))
    return out


def test_wrapped_lines_never_clip_random_texts(ctx):
    import random

    words = "room degrees humidity office Ty quick lorem ipsum dolor sit amet".split()
    words += "temperature living 21.5 percent WWW iii mmm a I".split()
    rnd = random.Random(11)
    bad = []
    for _ in range(300):
        size = rnd.choice([6, 8, 9, 10, 12, 16, 24])
        text = " ".join(rnd.choice(words) for _ in range(rnd.randint(3, 12)))
        avail = int(ctx.font(None, size).getlength(text) * rnd.uniform(0.3, 1.0)) + 1
        bad += _clipped_lines(ctx, text, size, avail)
    assert bad == []


def _sabotage_estimates(monkeypatch):
    """Make the fast accept path wildly optimistic, like a font whose hinting drifts past the estimate."""
    import imagespec.elements.layout as layout

    monkeypatch.setattr(layout._InkRuler, "_word_excess", lambda self, word: 0.0)
    monkeypatch.setattr(layout._InkRuler, "_DRIFT", 0.0)
    monkeypatch.setattr(layout._InkRuler, "_MARGIN", -4)
    return layout


def test_every_wrapped_line_is_verified_by_drawing_even_if_the_estimate_is_too_optimistic(ctx, monkeypatch):
    import random

    _sabotage_estimates(monkeypatch)
    words = "room degrees humidity office Ty quick lorem ipsum dolor sit amet 1 111 21.5 7 4".split()
    rnd = random.Random(5)
    bad = []
    for _ in range(200):
        size = rnd.choice([8, 10, 12, 16])
        text = " ".join(rnd.choice(words) for _ in range(rnd.randint(4, 14)))
        avail = int(ctx.font(None, size).getlength(text) * rnd.uniform(0.3, 1.0)) + 1
        bad += _clipped_lines(ctx, text, size, avail)
    assert bad == []


def test_the_verification_pass_is_what_catches_it(ctx, monkeypatch):
    """Control: without the per-line drawn check, the same sabotaged estimates do clip."""
    import random

    layout = _sabotage_estimates(monkeypatch)
    monkeypatch.setattr(layout._InkRuler, "ink_right", lambda self, text: 0.0)  # verification sees nothing
    words = "room degrees humidity office Ty quick lorem ipsum dolor sit amet 1 111 21.5 7 4".split()
    rnd = random.Random(5)
    bad = []
    for _ in range(200):
        size = rnd.choice([8, 10, 12, 16])
        text = " ".join(rnd.choice(words) for _ in range(rnd.randint(4, 14)))
        avail = int(ctx.font(None, size).getlength(text) * rnd.uniform(0.3, 1.0)) + 1
        bad += _clipped_lines(ctx, text, size, avail)
    assert bad  # proves the previous test would notice a missing verification
