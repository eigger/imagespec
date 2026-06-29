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
