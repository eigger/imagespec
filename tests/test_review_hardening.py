"""Regression tests for plot tick handling, early dither validation and font fallback logs."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from imagespec import RenderContext, RenderError, render


def _plot_ctx():
    now = datetime.now(UTC)

    def history(entity_ids, start, end):
        return {
            e: [
                SimpleNamespace(state="1", last_changed=(now - timedelta(hours=2)).isoformat()),
                {"state": "5000000", "last_changed": (now - timedelta(hours=1)).isoformat()},
            ]
            for e in entity_ids
        }

    return RenderContext(history_provider=history)


@pytest.mark.parametrize("bad", [0, -1, float("nan"), float("inf")])
def test_plot_rejects_non_positive_tick_every(bad):
    payload = [
        {
            "type": "plot",
            "data": [{"entity": "sensor.a"}],
            "yaxis": {"tick_every": bad},
            "x_start": 0,
            "y_start": 0,
            "x_end": 100,
            "y_end": 60,
        }
    ]
    with pytest.raises(RenderError, match="tick_every"):
        render(payload, 100, 60, context=_plot_ctx())


def test_plot_tiny_tick_every_over_wide_range_is_bounded():
    payload = [
        {
            "type": "plot",
            "data": [{"entity": "sensor.a"}],
            "yaxis": {"tick_every": 0.001},
            "x_start": 0,
            "y_start": 0,
            "x_end": 100,
            "y_end": 60,
        }
    ]
    render(payload, 100, 60, context=_plot_ctx())  # must return promptly


def test_bad_dither_fails_before_drawing():
    with pytest.raises(ValueError, match="unknown dither"):
        render([], 10, 10, dither="nope", context=RenderContext())


def test_font_fallback_warns_once(caplog):
    from imagespec import context as ctxmod

    ctxmod._WARNED_FONTS.discard("definitely-missing.ttf")
    ctx = RenderContext()
    with caplog.at_level(logging.WARNING, logger="imagespec.context"):
        ctx.resolve_font_path("definitely-missing.ttf")
        ctx.resolve_font_path("definitely-missing.ttf")
    assert sum("definitely-missing.ttf" in r.getMessage() for r in caplog.records) == 1
