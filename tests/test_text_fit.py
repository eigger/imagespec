"""text_fit: box-constrained text (shrink / ellipsis / wrap)."""

from __future__ import annotations

import pytest

from imagespec import RenderError, render
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
