"""`plot` element against a fake history provider."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from PIL import Image, ImageDraw

from imagespec import RenderContext, RenderError, render


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


def test_plot_empty_data_is_a_payload_error(history_ctx):
    # used to reach math.ceil(None) and surface as a TypeError
    with pytest.raises(RenderError, match="at least one entity"):
        render([{"type": "plot", "data": []}], 200, 100, context=history_ctx)


def test_plot_xlegend_format_with_a_newline_renders(history_ctx):
    """`%H\\n%M` stacks the label on two lines; the t-anchored legend used to raise."""
    el = {
        "type": "plot",
        "x_start": 2,
        "y_start": 2,
        "x_end": 197,
        "y_end": 80,
        "data": [{"entity": "sensor.temp"}],
        "xlegend": {"format": "%H\n%M"},
    }
    assert render([el], 200, 100, context=history_ctx).size == (200, 100)


def test_plot_clips_pre_and_post_window_samples():
    now = datetime.now(UTC)
    samples = [
        {"state": "10", "last_changed": (now - timedelta(hours=48)).isoformat()},
        {"state": "20", "last_changed": (now - timedelta(hours=12)).isoformat()},
        {"state": "30", "last_changed": (now + timedelta(hours=12)).isoformat()},
    ]
    ctx = RenderContext(history_provider=lambda ids, s, e: {"sensor.a": samples})
    el = {
        "type": "plot",
        "x_start": 30,
        "y_start": 0,
        "x_end": 89,
        "y_end": 39,
        "duration": 86400,
        "yaxis": None,
        "ylegend": None,
        "data": [{"entity": "sensor.a", "color": "red", "area_fill": "yellow"}],
    }
    img = render([el], 100, 40, background="white", context=ctx)
    # No red or yellow pixels should ever leak left of diag_x=30 or right of diag_x+diag_width-1=89.
    assert all(img.getpixel((x, y)) == (255, 255, 255) for y in range(40) for x in range(30))
    assert all(img.getpixel((x, y)) == (255, 255, 255) for y in range(40) for x in range(90, 100))
    # Inside [30, 89], clipped segments still produce a line touching both boundaries.
    assert any(img.getpixel((30, y)) == (255, 0, 0) for y in range(40))
    assert any(img.getpixel((89, y)) == (255, 0, 0) for y in range(40))


@pytest.mark.parametrize("state", ["1e-05", "+12.5", " 15.0 "])
def test_plot_accepts_scientific_signed_and_padded_string_states(state):
    now = datetime.now(UTC)
    samples = [
        {"state": state, "last_changed": (now - timedelta(hours=2)).isoformat()},
        {"state": "20", "last_changed": (now - timedelta(hours=1)).isoformat()},
    ]
    ctx = RenderContext(history_provider=lambda ids, s, e: {"sensor.a": samples})
    assert render([{"type": "plot", "data": [{"entity": "sensor.a"}]}], 80, 40, context=ctx).size == (80, 40)


def test_plot_accepts_all_object_samples():
    now = datetime.now(UTC)
    samples = [
        SimpleNamespace(state="10", last_changed=(now - timedelta(hours=2)).isoformat()),
        SimpleNamespace(state="15", last_changed=(now - timedelta(hours=1)).isoformat()),
    ]
    ctx = RenderContext(history_provider=lambda ids, s, e: {"sensor.a": samples})
    assert render([{"type": "plot", "data": [{"entity": "sensor.a"}]}], 80, 40, context=ctx).size == (80, 40)


def test_plot_yaxis_zero_width_and_out_of_window_samples():
    now = datetime.now(UTC)
    samples = [
        {"state": "10", "last_changed": (now - timedelta(hours=72)).isoformat()},
        {"state": "15", "last_changed": (now - timedelta(hours=48)).isoformat()},
    ]
    ctx = RenderContext(history_provider=lambda ids, s, e: {"sensor.a": samples})
    el = {
        "type": "plot",
        "x_start": 0,
        "y_start": 0,
        "x_end": 79,
        "y_end": 39,
        "duration": 3600,
        "yaxis": {"width": 0, "tick_width": 0, "grid": None},
        "data": [{"entity": "sensor.a", "width": 1.5}],
    }
    assert render([el], 80, 40, context=ctx).size == (80, 40)


@pytest.mark.parametrize(
    ("x_start", "y_start", "x_end", "y_end", "ylegend_width"),
    [
        (10, 0, 15, 20, 10),  # diag_width <= 0
        (10, 0, 80, 10, 0),  # diag_height <= 0 due to xlegend_height
        (10, 0, 5, 20, 0),  # x_end < x_start
        (10, 20, 80, 5, 0),  # y_end < y_start
    ],
)
def test_plot_collapsed_area_does_not_crash(history_ctx, x_start, y_start, x_end, y_end, ylegend_width):
    el = {
        "type": "plot",
        "x_start": x_start,
        "y_start": y_start,
        "x_end": x_end,
        "y_end": y_end,
        "yaxis": {},
        "xlegend": {},
        "ylegend": {"width": ylegend_width},
        "data": [{"entity": "sensor.temp"}],
    }
    img = render([el], 90, 40, background="white", context=history_ctx)
    assert img.size == (90, 40)
    assert img.getcolors(maxcolors=1 << 24) == [(90 * 40, (255, 255, 255))]
    assert render([{**el, "debug": True}], 90, 40, background="white", context=history_ctx).size == (90, 40)


def test_clip_segment_time_handles_float_cancellation_edges():
    from imagespec.elements.charts import _clip_segment_time

    assert _clip_segment_time((-100.0, 0.1), (-1e-15, 0.9)) is None
    assert _clip_segment_time((-1e17, 0.1), (-1.0, 0.9)) is None

    clipped = _clip_segment_time((-1e17, 0.1), (2.0, 0.9))
    assert clipped is not None
    (c0_t, _), (c1_t, _) = clipped
    assert 0.0 <= c0_t <= 1.0
    assert 0.0 <= c1_t <= 1.0


def test_plot_clips_segment_joining_back_in_and_out_of_window():
    now = datetime.now(UTC)
    samples = [
        {"state": "10", "last_changed": (now - timedelta(hours=36)).isoformat()},
        {"state": "20", "last_changed": (now - timedelta(hours=12)).isoformat()},
        {"state": "15", "last_changed": (now - timedelta(hours=30)).isoformat()},
        {"state": "25", "last_changed": (now - timedelta(hours=6)).isoformat()},
    ]
    ctx = RenderContext(history_provider=lambda ids, s, e: {"sensor.a": samples})
    el = {
        "type": "plot",
        "x_start": 10,
        "y_start": 0,
        "x_end": 69,
        "y_end": 39,
        "duration": 86400,
        "yaxis": None,
        "ylegend": None,
        "data": [{"entity": "sensor.a", "color": "black"}],
    }
    img = render([el], 80, 40, background="white", context=ctx)
    assert all(img.getpixel((x, y)) == (255, 255, 255) for y in range(40) for x in range(10))
    assert any(img.getpixel((x, y)) == (0, 0, 0) for y in range(40) for x in range(10, 70))


def test_plot_out_of_window_spike_does_not_flatten_visible_y_range(monkeypatch):
    now = datetime.now(UTC)
    samples = [
        {"state": "10000", "last_changed": (now - timedelta(hours=48)).isoformat()},
        {"state": "10", "last_changed": (now - timedelta(hours=36)).isoformat()},
        {"state": "10", "last_changed": (now - timedelta(hours=23)).isoformat()},
        {"state": "20", "last_changed": (now - timedelta(hours=1)).isoformat()},
    ]
    ctx = RenderContext(palette="4", history_provider=lambda ids, s, e: {"sensor.a": samples})
    drawn: list[str] = []
    orig = ImageDraw.ImageDraw.text

    def spy(self, xy, text, *args, **kwargs):
        drawn.append(text)
        return orig(self, xy, text, *args, **kwargs)

    monkeypatch.setattr(ImageDraw.ImageDraw, "text", spy)
    el = {
        "type": "plot",
        "x_start": 0,
        "y_start": 0,
        "x_end": 99,
        "y_end": 39,
        "duration": 86400,
        "yaxis": None,
        "ylegend": {"width": 20},
        "data": [{"entity": "sensor.a", "color": "red"}],
    }
    img = render([el], 100, 40, background="white", context=ctx)
    assert "10000" not in drawn
    assert "10" in drawn and "20" in drawn
    # With 10..20 range (not 10..10000), the rising line reaches the upper half of the plot.
    assert any(img.getpixel((x, y)) == (255, 0, 0) for x in range(20, 100) for y in range(0, 15))
    assert any(img.getpixel((x, y)) == (255, 0, 0) for x in range(20, 100) for y in range(25, 40))


def test_plot_boundary_interpolated_value_included_in_y_range(monkeypatch):
    now = datetime.now(UTC)
    samples = [
        {"state": "0", "last_changed": (now - timedelta(hours=36)).isoformat()},
        {"state": "100", "last_changed": (now - timedelta(hours=12)).isoformat()},
    ]
    ctx = RenderContext(palette="4", history_provider=lambda ids, s, e: {"sensor.a": samples})
    drawn: list[str] = []
    orig = ImageDraw.ImageDraw.text

    def spy(self, xy, text, *args, **kwargs):
        drawn.append(text)
        return orig(self, xy, text, *args, **kwargs)

    monkeypatch.setattr(ImageDraw.ImageDraw, "text", spy)
    el = {
        "type": "plot",
        "duration": 86400,
        "yaxis": None,
        "ylegend": {},
        "data": [{"entity": "sensor.a", "color": "black"}],
    }
    render([el], 120, 50, context=ctx)
    assert "50" in drawn
    assert "100" in drawn
    assert "0" not in drawn


def test_plot_thick_line_is_clipped_to_plot_rectangle():
    now = datetime.now(UTC)
    samples = [
        {"state": "0", "last_changed": (now - timedelta(hours=36)).isoformat()},
        {"state": "20", "last_changed": (now + timedelta(hours=12)).isoformat()},
    ]
    ctx = RenderContext(palette="4", history_provider=lambda ids, s, e: {"sensor.a": samples})
    el = {
        "type": "plot",
        "x_start": 20,
        "y_start": 10,
        "x_end": 69,
        "y_end": 39,
        "duration": 86400,
        "yaxis": None,
        "ylegend": None,
        "data": [{"entity": "sensor.a", "color": "red", "width": 5}],
    }
    img = render([el], 90, 50, background="white", context=ctx)
    for y in range(50):
        for x in range(90):
            if not (20 <= x <= 69 and 10 <= y <= 39):
                assert img.getpixel((x, y)) == (255, 255, 255)
    assert any(img.getpixel((x, y)) == (255, 0, 0) for y in range(10, 40) for x in range(20, 70))


def test_plot_all_samples_outside_window_renders_without_crashing():
    now = datetime.now(UTC)
    samples = [
        {"state": "10", "last_changed": (now - timedelta(hours=48)).isoformat()},
        {"state": "20", "last_changed": (now - timedelta(hours=36)).isoformat()},
    ]
    ctx = RenderContext(palette="4", history_provider=lambda ids, s, e: {"sensor.a": samples})
    el = {
        "type": "plot",
        "duration": 86400,
        "yaxis": None,
        "ylegend": None,
        "data": [{"entity": "sensor.a", "color": "black"}],
    }
    img = render([el], 80, 40, background="white", context=ctx)
    assert img.getcolors(maxcolors=1 << 24) == [(80 * 40, (255, 255, 255))]


def test_plot_layer_allocation_is_clamped_to_canvas_size(history_ctx, monkeypatch):
    sizes: list[tuple[int, int]] = []
    orig_new = Image.new

    def spy_new(mode, size, color=0):
        sizes.append(size)
        return orig_new(mode, size, color)

    monkeypatch.setattr(Image, "new", spy_new)
    oversized = {
        "type": "plot",
        "x_start": 0,
        "y_start": 0,
        "x_end": 1200,
        "y_end": 900,
        "yaxis": None,
        "ylegend": None,
        "data": [{"entity": "sensor.temp"}],
    }
    assert render([oversized], 30, 20, context=history_ctx).size == (30, 20)
    assert all(w <= 30 and h <= 20 for w, h in sizes)

    sizes.clear()
    offscreen = {
        "type": "plot",
        "x_start": 100,
        "y_start": 100,
        "x_end": 500,
        "y_end": 500,
        "yaxis": None,
        "ylegend": None,
        "data": [{"entity": "sensor.temp"}],
    }
    assert render([offscreen], 30, 20, context=history_ctx).size == (30, 20)
    assert all(w <= 30 and h <= 20 for w, h in sizes)


@pytest.mark.parametrize("extra", [{"low": 100}, {"high": 0}])
def test_plot_out_of_window_fallback_does_not_invert_y_axis_with_low_or_high(monkeypatch, extra):
    now = datetime.now(UTC)
    samples = [
        {"state": "10", "last_changed": (now - timedelta(hours=48)).isoformat()},
        {"state": "15", "last_changed": (now - timedelta(hours=36)).isoformat()},
    ]
    ctx = RenderContext(palette="4", history_provider=lambda ids, s, e: {"sensor.a": samples})
    drawn: list[tuple[str, float]] = []
    orig_text = ImageDraw.ImageDraw.text

    def spy_text(self, xy, text, *args, **kwargs):
        drawn.append((text, xy[1]))
        return orig_text(self, xy, text, *args, **kwargs)

    monkeypatch.setattr(ImageDraw.ImageDraw, "text", spy_text)
    el = {
        "type": "plot",
        "duration": 86400,
        "yaxis": None,
        "ylegend": {},
        "data": [{"entity": "sensor.a"}],
        **extra,
    }
    render([el], 100, 50, context=ctx)
    y_by_label = dict(drawn)
    assert "15" in y_by_label and "10" in y_by_label
    # Upper label (15) must sit strictly above lower label (10).
    assert y_by_label["15"] < y_by_label["10"]
