"""text_fit: box-constrained text (shrink / ellipsis / wrap)."""

from __future__ import annotations

import pytest
from PIL import ImageFont

from imagespec import RenderContext, RenderError, render
from imagespec.elements.text import fit_lines


def test_fit_lines_short_text_fits(ctx):
    font = ctx.font(None, 16)
    lines, fits = fit_lines("hi", font, 200, 1, "…")
    assert lines == ["hi"] and fits is True


def test_fit_lines_single_line_ellipsized(ctx):
    font = ctx.font(None, 16)
    lines, fits = fit_lines("this is a very long sentence that cannot fit", font, 60, 1, "…")
    assert len(lines) == 1
    assert fits is False
    assert lines[0].endswith("…")
    assert font.getlength(lines[0]) <= 60


def test_fit_lines_wraps_up_to_max_lines(ctx):
    font = ctx.font(None, 16)
    lines, fits = fit_lines("alpha beta gamma delta epsilon zeta eta theta", font, 70, 2, "…")
    assert len(lines) <= 2
    assert fits is False
    assert lines[-1].endswith("…")


def test_fit_lines_long_unbreakable_word(ctx):
    font = ctx.font(None, 16)
    lines, fits = fit_lines("supercalifragilisticexpialidocious", font, 50, 1, "…")
    assert fits is False
    assert lines[0].endswith("…")
    assert font.getlength(lines[0]) <= 50


@pytest.mark.parametrize("fit", ["shrink", "ellipsis", "shrink_ellipsis"])
def test_text_fit_renders_each_mode(ctx, fit):
    el = {
        "type": "text_fit",
        "x": 2,
        "y": 2,
        "width": 60,
        "height": 24,
        "value": "a fairly long label value",
        "size": 16,
        "min_size": 6,
        "fit": fit,
    }
    assert render([el], 80, 40, context=ctx).size == (80, 40)


def test_text_fit_with_chip_background(ctx):
    el = {
        "type": "text_fit",
        "x": 2,
        "y": 2,
        "width": 60,
        "height": 24,
        "value": "label",
        "size": 14,
        "background": "black",
        "color": "white",
        "outline": "black",
        "radius": 4,
        "align": "center",
        "valign": "middle",
    }
    assert render([el], 80, 40, context=ctx).size == (80, 40)


def test_text_fit_invalid_fit_raises(ctx):
    el = {"type": "text_fit", "x": 0, "y": 0, "width": 40, "height": 20, "value": "x", "fit": "bogus"}
    with pytest.raises(RenderError):
        render([el], 40, 20, context=ctx)


def test_text_fit_shrink_keeps_within_box(ctx):
    # A long value forced into a small box with shrink should not be ellipsized
    # when min_size is low enough to fit it on the allowed lines.
    el = {
        "type": "text_fit",
        "x": 0,
        "y": 0,
        "width": 50,
        "height": 40,
        "value": "wrap me please",
        "size": 20,
        "min_size": 4,
        "max_lines": 3,
        "fit": "shrink",
    }
    # mainly a smoke assertion that shrink path completes and renders
    assert render([el], 60, 50, context=ctx).size == (60, 50)


def test_wrap_words_overlong_first_word_has_no_empty_leading_line(ctx):
    # The old `text` wrapper started from [""] and pushed an over-wide first word
    # onto a *second* line, leaving a blank first line (and a blank row of pixels).
    from imagespec.utils import wrap_words

    font = ctx.font(None, 12)
    assert wrap_words("Supercalifragilistic word", font, 30) == ["Supercalifragilistic", "word"]
    assert wrap_words("", font, 30) == []


def test_text_max_width_overlong_first_word_starts_at_top(bw_ctx):
    from imagespec import render

    wide = {"type": "text", "x": 0, "y": 0, "value": "Supercalifragilistic", "size": 12, "max_width": 30}
    # max_width switches the anchor to Pillow's default ("la"); match it explicitly
    plain = {"type": "text", "x": 0, "y": 0, "value": "Supercalifragilistic", "size": 12, "anchor": "la"}
    a = render([wide], 150, 40, context=bw_ctx)
    b = render([plain], 150, 40, context=bw_ctx)
    assert a.tobytes() == b.tobytes()  # no phantom empty first line shifting the text down


class _RecordingContext(RenderContext):
    def font(self, name, size):
        self.sizes.append(int(size))
        return super().font(name, size)


def _chosen_size(width, height, value, max_lines, start=60, min_size=8):
    ctx = _RecordingContext(palette="4", layout_engine=ImageFont.Layout.BASIC)
    ctx.sizes = []
    el = {
        "type": "text_fit",
        "x": 0,
        "y": 0,
        "width": width,
        "height": height,
        "value": value,
        "size": start,
        "min_size": min_size,
        "max_lines": max_lines,
    }
    render([el], max(width, 1), max(height, 1), context=ctx)
    return ctx.sizes[-1]


def _linear_size(width, height, value, max_lines, start=60, min_size=8):
    ctx = RenderContext(palette="4", layout_engine=ImageFont.Layout.BASIC)
    for size in range(start, min_size - 1, -1):
        font = ctx.font(None, size)
        ascent, descent = font.getmetrics()
        line_h = ascent + descent + 2
        lines, fits = fit_lines(value, font, width, max_lines, "…")
        if fits and line_h * len(lines) <= height:
            return size
    return min_size


def test_text_fit_shrink_is_the_largest_fitting_size_even_when_fit_is_not_monotonic():
    """Hinted advances are not monotonic in size, so a size above a failing one can still fit.

    With the FreeType in current Pillow wheels, "Hi , iii Hi WWW Temperature WWW" in a 115x104 box wraps to
    3 lines at 16 and 18 but 4 lines (too tall) at 17, so a bisection would pick 16 (or give up with
    min_size 17). Older FreeType hints differently (min-deps CI picks 17), so the assertion is "equals the
    brute-force scan" rather than a pinned size; it still guards the counterexample wherever it exists.
    """
    case = (115, 104, "Hi , iii Hi WWW Temperature WWW", 4)
    for min_size in (2, 17):
        assert _chosen_size(*case, start=20, min_size=min_size) == _linear_size(*case, start=20, min_size=min_size)


@pytest.mark.parametrize("value", ["Hi", "Temperature 21.5", "wrap me please now"])
@pytest.mark.parametrize("max_lines", [1, 3])
@pytest.mark.parametrize("width,height", [(40, 12), (90, 30), (160, 20), (300, 70), (30, 200)])
def test_text_fit_picks_the_largest_fitting_size(value, max_lines, width, height):
    assert _chosen_size(width, height, value, max_lines) == _linear_size(width, height, value, max_lines)


def test_text_fit_when_start_is_below_min_size():
    assert _chosen_size(100, 40, "abc", 1, start=6, min_size=10) == 10


@pytest.mark.parametrize("axis", ["width", "height"])
@pytest.mark.parametrize("anchor", ["la", "mm", "rs"])
@pytest.mark.parametrize("stroke_width", [0, 2])
@pytest.mark.parametrize("value", ["Temperature 21.5", "Hello World", "WWWW iii"])
def test_new_multiline_fit_never_overflows_the_target(axis, anchor, stroke_width, value):
    """Fitting scales the size once and the font truncates it to an int (and 1-bit hinting widens glyphs),
    which used to leave the drawn text a few px over the target, for any anchor and stroke."""
    ctx = RenderContext(palette="bw", layout_engine=ImageFont.Layout.BASIC)
    text = value if axis == "width" else value.replace(" ", "\n")
    for limit in range(45, 160, 11):  # above the size-1 floor even with a stroke
        el = {
            "type": "new_multiline",
            "x": 200,
            "y": 150,
            "value": text,
            "size": 40,
            "anchor": anchor,
            "stroke_width": stroke_width,
            "stroke_fill": "black",
            axis: limit,
            "fit": axis,
        }
        ink = render([el], 400, 300, context=ctx).convert("L").point(lambda p: 255 if p < 128 else 0).getbbox()
        assert ink is not None
        extent = ink[2] - ink[0] if axis == "width" else ink[3] - ink[1]
        assert extent <= limit, (value, axis, anchor, stroke_width, limit, extent)
