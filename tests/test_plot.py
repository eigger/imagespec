"""`plot` element against a fake history provider."""

from __future__ import annotations

import pytest
from PIL import ImageDraw

from imagespec import RenderError, render


def _ylegend_labels(monkeypatch, ctx, **extra):
    """Render a plot with a y legend and return the strings it drew."""
    drawn = []
    orig = ImageDraw.ImageDraw.text

    def spy(self, xy, text, *args, **kwargs):
        drawn.append(text)
        return orig(self, xy, text, *args, **kwargs)

    monkeypatch.setattr(ImageDraw.ImageDraw, "text", spy)
    el = {"type": "plot", "data": [{"entity": "sensor.temp"}], "ylegend": {}, **extra}
    render([el], 200, 100, context=ctx)
    return drawn


def test_plot_low_zero_is_honoured(history_ctx, monkeypatch):
    # Regression: `low: 0` was dropped by an `or` (0 is falsy), so the axis
    # started at the data minimum (10) instead of 0.
    assert "0" in _ylegend_labels(monkeypatch, history_ctx, low=0)


def test_plot_high_zero_is_honoured(history_ctx, monkeypatch):
    # data is all positive (10..15) so `high: 0` is exceeded and must not shrink
    # the range — but it must also not crash or be treated as "unset".
    labels = _ylegend_labels(monkeypatch, history_ctx, high=0)
    assert "15" in labels and "10" in labels


def test_plot_low_high_only_widen_range(history_ctx, monkeypatch):
    labels = _ylegend_labels(monkeypatch, history_ctx, low=5, high=20)
    assert "5" in labels and "20" in labels


def test_plot_renders(history_ctx):
    el = {
        "type": "plot",
        "x_start": 2,
        "y_start": 2,
        "x_end": 197,
        "y_end": 97,
        "data": [{"entity": "sensor.temp", "color": "red", "area_fill": "yellow"}],
        "ylegend": {},
        "xlegend": {},
        "yaxis": {},
    }
    assert render([el], 200, 100, context=history_ctx).size == (200, 100)


def test_plot_multiple_series(history_ctx):
    el = {"type": "plot", "data": [{"entity": "sensor.a", "color": "red"}, {"entity": "sensor.b", "color": "black"}]}
    assert render([el], 200, 100, context=history_ctx).size == (200, 100)


def test_plot_default_y_end_uses_y_start_not_x_start(history_ctx):
    # Regression: the default y_end must derive from y_start, not x_start. A
    # large x_start used to wrongly collapse the plot's vertical extent.
    el = {
        "type": "plot",
        "x_start": 60,
        "data": [{"entity": "sensor.temp", "color": "red"}],
        "ylegend": None,
        "yaxis": None,
    }
    img = render([el], 200, 100, context=history_ctx)
    # with a full-height plot the line reaches into the lower half of the canvas
    lower_half_drawn = any(img.getpixel((x, y)) != (255, 255, 255) for y in range(60, 100) for x in range(60, 140))
    assert lower_half_drawn


def test_plot_missing_entity_data_raises(history_ctx):
    # provider returns data only for requested ids; ask handler to require a
    # series with no data by monkeypatching the provider to an empty dict.
    history_ctx.history_provider = lambda ids, s, e: {}
    el = {"type": "plot", "data": [{"entity": "sensor.missing"}]}
    with pytest.raises(RenderError):
        render([el], 200, 100, context=history_ctx)
