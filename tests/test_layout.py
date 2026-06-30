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
