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


def test_plot_missing_entity_data_raises(history_ctx):
    # provider returns data only for requested ids; ask handler to require a
    # series with no data by monkeypatching the provider to an empty dict.
    history_ctx.history_provider = lambda ids, s, e: {}
    el = {"type": "plot", "data": [{"entity": "sensor.missing"}]}
    with pytest.raises(RenderError):
        render([el], 200, 100, context=history_ctx)
