"""`plot` element against a fake history provider."""

from __future__ import annotations

import pytest

from imagespec import RenderError, render


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
