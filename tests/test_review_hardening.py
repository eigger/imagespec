# ruff: noqa: E501
"""Regression tests for plot tick handling, early dither validation and font fallback logs."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from imagespec import RenderContext, RenderError, render
from imagespec.context import BUNDLED_FONTS_DIR

FONT = Path(BUNDLED_FONTS_DIR, "NotoSansKR-Regular.ttf").read_bytes()


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


def test_font_fallback_warns_once(caplog, monkeypatch):
    from imagespec import context as ctxmod

    monkeypatch.setattr(ctxmod, "_WARNED_FONTS", set())
    ctx = RenderContext()
    with caplog.at_level(logging.WARNING, logger="imagespec.context"):
        ctx.resolve_font_path("definitely-missing.ttf")
        ctx.resolve_font_path("definitely-missing.ttf")
    assert sum("definitely-missing.ttf" in r.getMessage() for r in caplog.records) == 1


def _tick_rows(lo, hi, tick_every, height):
    now = datetime.now(UTC)

    def history(entity_ids, start, end):
        return {
            e: [
                SimpleNamespace(state=str(lo), last_changed=(now - timedelta(hours=2)).isoformat()),
                {"state": str(hi), "last_changed": (now - timedelta(hours=1)).isoformat()},
            ]
            for e in entity_ids
        }

    payload = [
        {
            "type": "plot",
            "data": [{"entity": "sensor.a", "color": "white"}],
            "ylegend": None,
            "yaxis": {"tick_every": tick_every, "tick_width": 3, "grid": None},
            "x_start": 0,
            "y_start": 0,
            "x_end": 39,
            "y_end": height - 1,
        }
    ]
    img = render(payload, 40, height, context=RenderContext(history_provider=history))
    # yaxis (width 1) at x=0, ticks start at x=1
    return [y for y in range(height) if img.getpixel((1, y)) == (0, 0, 0)]


def test_plot_ticks_include_top_and_bottom_rows_when_capped():
    rows = _tick_rows(3, 225, 1, 10)  # 223 ticks > 10 rows: every row, incl. top
    assert rows == list(range(10))


@pytest.mark.parametrize("te", [0.1, 0.2])
def test_plot_fractional_tick_every_keeps_top_tick(te):
    rows = _tick_rows(-13, -3, te, 60)
    assert rows[0] == 0 and rows[-1] == 59


def test_plot_integer_ticks_unchanged():
    rows = _tick_rows(0, 4, 1, 41)
    assert rows == [0, 10, 20, 30, 40]


def test_describe_exception():
    from imagespec.exceptions import describe_exception

    assert describe_exception(KeyError("color")) == "KeyError: 'color'"
    assert describe_exception(ValueError("bad")) == "bad"
    assert describe_exception(TypeError("bad")) == "bad"


def test_caching_resolver_replace_race(tmp_path, monkeypatch):
    import os

    from imagespec.resolvers import caching_resolver

    class Resp:
        content = FONT

        def raise_for_status(self):
            pass

    class Http:
        def get(self, url, timeout):
            return Resp()

    def boom(src, dst):
        open(dst, "wb").write(FONT)  # a concurrent download won the race
        raise PermissionError(5, "denied")

    monkeypatch.setattr(os, "replace", boom)
    r = caching_resolver(str(tmp_path), sources={"a.ttf": "http://x/a.ttf"}, session=Http())
    assert r("a.ttf") == str(tmp_path / "a.ttf")

    def boom2(src, dst):
        raise PermissionError(5, "denied")

    monkeypatch.setattr(os, "replace", boom2)
    r = caching_resolver(str(tmp_path), sources={"b.ttf": "http://x/b.ttf"}, session=Http())
    with pytest.raises(PermissionError):
        r("b.ttf")
    assert not [p for p in os.listdir(tmp_path) if p.endswith(".part")]


def test_caching_resolver_expands_user(tmp_path, monkeypatch):
    from imagespec.resolvers import caching_resolver

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    caching_resolver("~/fonts")
    assert (tmp_path / "fonts").is_dir()


def test_plot_capped_ticks_stop_at_last_tick_row():
    assert _tick_rows(0, 23, 3, 7) == [1, 2, 3, 4, 5, 6]


# ── validate() never raises ─────────────────────────────────────────────────
def test_validate_survives_overflowing_class_tokens():
    from imagespec import validate

    validate([{"type": "row", "class": "gap-1e308", "elements": [{"type": "group", "elements": []}]}])


def test_validate_reports_excessive_nesting():
    from imagespec import validate

    node: dict = {"type": "group", "elements": []}
    for _ in range(3000):
        node = {"type": "group", "elements": [node]}
    issues = validate([node])
    assert any("nested too deeply" in str(i) for i in issues)


# ── render() argument errors ────────────────────────────────────────────────
@pytest.mark.parametrize(
    "kwargs",
    [
        {"width": "200", "height": 10},
        {"width": 0, "height": 10},
        {"width": 10, "height": 10, "rotate": 45},
        {"width": 10, "height": 10, "rotate_mode": "x"},
        {"width": 10, "height": 10, "dither": "nope"},
        {"width": 10, "height": 10, "dither": 1.5},
    ],
)
def test_render_argument_errors_are_render_errors(kwargs):
    with pytest.raises(RenderError) as ei:
        render([], context=RenderContext(), **kwargs)
    assert isinstance(ei.value, ValueError)  # backward compatible


def test_render_accepts_whole_float_size():
    assert render([], 20.0, 10.0, context=RenderContext()).size == (20, 10)


def _png_url():
    import base64
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (4, 4), "red").save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


_PNG_URL = _png_url()


# ── element input errors name the problem ───────────────────────────────────
def _r(el, w=100, h=60, ctx=None):
    return render([el], w, h, context=ctx or RenderContext())


@pytest.mark.parametrize(
    "el, match",
    [
        ({"type": "pie", "x": 30, "y": 30, "radius": 20, "values": "a,x"}, "non-numeric"),
        ({"type": "pie", "x": 30, "y": 30, "radius": 20, "values": ";"}, "at least one"),
        (
            {
                "type": "diagram",
                "x": 0,
                "y": 0,
                "width": 90,
                "height": 50,
                "bars": {"values": "a,1;b", "color": "black"},
            },
            "bad bar",
        ),
        (
            {"type": "diagram", "x": 0, "y": 0, "width": 90, "height": 50, "bars": {"values": "", "color": "black"}},
            "at least one",
        ),
        ({"type": "diagram", "x": 0, "y": 0, "width": 90, "height": 50, "bars": {"values": "a,1"}}, "'color'"),
        (
            {
                "type": "progress_bar",
                "x_start": 0,
                "y_start": 0,
                "x_end": 30,
                "y_end": 3,
                "progress": 50,
                "show_percentage": True,
            },
            "too small",
        ),
        (
            {"type": "dlimg", "url": _PNG_URL, "x": 0, "y": 0, "xsize": 10, "ysize": 0},
            "positive",
        ),
        ({"type": "plot", "data": [{"entity": "a"}], "duration": 0}, "duration"),
        ({"type": "plot", "data": [{}]}, "'entity'"),
    ],
)
def test_element_input_errors(el, match):
    with pytest.raises(RenderError, match=match):
        _r(el)


def test_dlimg_undecodable_data_names_source():
    with pytest.raises(RenderError, match=r"data URL \(text/plain\) is not a readable image \(3 bytes\)"):
        _r({"type": "dlimg", "url": "data:text/plain,abc", "x": 0, "y": 0, "xsize": 4, "ysize": 4})


def test_pie_tolerates_trailing_semicolon():
    _r({"type": "pie", "x": 30, "y": 30, "radius": 20, "values": "a,1;b,2;"})


@pytest.mark.parametrize(
    "samples",
    [
        [
            SimpleNamespace(state="1", last_changed="2026-01-01T00:00:00"),
            {"state": "3", "last_changed": "2026-01-01T01:00:00"},
        ],
        [
            {"state": 2, "last_changed": "2026-01-01T00:00:00+00:00"},
            {"state": 5, "last_changed": "2026-01-01T01:00:00+00:00"},
        ],
    ],
)
def test_plot_accepts_naive_timestamps_dict_head_and_numeric_state(samples):
    ctx = RenderContext(history_provider=lambda ids, s, e: {i: samples for i in ids})
    _r({"type": "plot", "data": [{"entity": "a"}], "duration": 10**9}, ctx=ctx)


def test_plot_empty_history_names_entity():
    ctx = RenderContext(history_provider=lambda ids, s, e: {i: [] for i in ids})
    with pytest.raises(RenderError, match="sensor.a"):
        _r({"type": "plot", "data": [{"entity": "sensor.a"}]}, ctx=ctx)


def test_render_accepts_numpy_integer_sizes():
    np = pytest.importorskip("numpy")
    assert render([], np.int64(20), np.int32(10), context=RenderContext()).size == (20, 10)


def test_render_argument_error_is_also_type_error():
    with pytest.raises(TypeError):
        render([], "20", 10, context=RenderContext())
    with pytest.raises(RenderError):
        render([], 10, 10, rotate=float("inf"), context=RenderContext())


@pytest.mark.parametrize("value", [1e-05, 1.2345678901234568e17])
def test_plot_accepts_exponent_float_states(value):
    ctx = RenderContext(
        history_provider=lambda ids, s, e: {
            i: [
                {"state": value, "last_changed": "2026-01-01T00:00:00+00:00"},
                {"state": value * 2, "last_changed": "2026-01-01T01:00:00+00:00"},
            ]
            for i in ids
        }
    )
    _r({"type": "plot", "data": [{"entity": "a"}], "duration": 10**9}, ctx=ctx)


def test_plot_treats_naive_timestamps_as_utc():
    def provider(stamp):
        return lambda ids, s, e: {
            i: [{"state": 1, "last_changed": stamp(0)}, {"state": 9, "last_changed": stamp(1)}] for i in ids
        }

    naive = provider(lambda h: f"2026-01-01T0{h}:00:00")
    aware = provider(lambda h: f"2026-01-01T0{h}:00:00+00:00")
    el = {"type": "plot", "data": [{"entity": "a", "color": "black"}], "duration": 10**9}
    assert (
        _r(el, ctx=RenderContext(history_provider=naive)).tobytes()
        == _r(el, ctx=RenderContext(history_provider=aware)).tobytes()
    )


def test_text_fit_min_size_zero_is_clamped():
    _r(
        {
            "type": "text_fit",
            "x": 0,
            "y": 0,
            "width": 3,
            "height": 2,
            "value": "a long text that cannot fit",
            "size": 5,
            "min_size": 0,
        }
    )


def test_diagram_tolerates_trailing_semicolon():
    _r({"type": "diagram", "x": 0, "y": 0, "width": 90, "height": 50, "bars": {"values": "a,1;b,2;", "color": "black"}})


def test_dlimg_http_scheme_is_case_insensitive(monkeypatch):
    seen = []
    ctx = RenderContext()
    monkeypatch.setattr(ctx, "fetch_image", lambda url, timeout: seen.append(url) or b"not an image")
    with pytest.raises(RenderError, match=r"https://example\.test/p\.png is not a readable image"):
        _r(
            {
                "type": "dlimg",
                "url": "HTTPS://user:pw@example.test/p.png?token=s3cret",
                "x": 0,
                "y": 0,
                "xsize": 4,
                "ysize": 4,
            },
            ctx=ctx,
        )
    assert seen


def test_dlimg_error_does_not_leak_credentials(monkeypatch):
    ctx = RenderContext()
    monkeypatch.setattr(ctx, "fetch_image", lambda url, timeout: b"x")
    with pytest.raises(RenderError) as ei:
        _r(
            {
                "type": "dlimg",
                "url": "https://user:pw@example.test/p.png?token=s3cret",
                "x": 0,
                "y": 0,
                "xsize": 4,
                "ysize": 4,
            },
            ctx=ctx,
        )
    assert "s3cret" not in str(ei.value) and "pw" not in str(ei.value)


def test_dlimg_fetch_failure_hides_query_and_credentials(monkeypatch):
    import requests

    ctx = RenderContext()

    def boom(url, timeout):
        raise requests.ConnectionError(f"Max retries exceeded with url: {url}")

    monkeypatch.setattr(ctx, "fetch_image", boom)
    with pytest.raises(RenderError) as ei:
        _r(
            {
                "type": "dlimg",
                "url": "https://user:pw@example.test/p.png?token=s3cret",
                "x": 0,
                "y": 0,
                "xsize": 4,
                "ysize": 4,
            },
            ctx=ctx,
        )
    msg = str(ei.value)
    assert "s3cret" not in msg and "pw@" not in msg
    assert "https://example.test/p.png" in msg and "ConnectionError" in msg


@pytest.mark.parametrize(
    "url",
    [
        "http://h:99999/x",
        "http://h:abc/x",
        "http://[::1]:8080/x?t=1",
        "http://[::1/x?t=1",
        "http://[zz]/x?t=1",
        "http://u:p@h℀x/p?t=1",
    ],
)
def test_describe_url_never_raises(url):
    from imagespec.utils import describe_url

    out = describe_url(url)
    assert "?t=1" not in out and "u:p@" not in out and "TOK" not in out
    assert not any(x in out for x in ("pa", "p＠", "ss@", "u:p"))
    assert out.startswith("http://")


def test_context_download_errors_hide_credentials():
    ctx = RenderContext(image_fetcher=lambda url: b"x" * 10, max_image_bytes=5)
    with pytest.raises(RenderError) as ei:
        ctx.fetch_image("https://user:pw@example.test/p.png?token=s3cret", timeout=1)
    assert "s3cret" not in str(ei.value) and "pw@" not in str(ei.value)


def test_plot_accepts_numpy_float32_exponent_state():
    np = pytest.importorskip("numpy")
    ctx = RenderContext(
        history_provider=lambda ids, s, e: {
            i: [
                {"state": np.float32(1e-05), "last_changed": "2026-01-01T00:00:00+00:00"},
                {"state": np.float32(2e-05), "last_changed": "2026-01-01T01:00:00+00:00"},
            ]
            for i in ids
        }
    )
    _r({"type": "plot", "data": [{"entity": "a"}], "duration": 10**9}, ctx=ctx)


def test_plot_skips_huge_int_state():
    ctx = RenderContext(
        history_provider=lambda ids, s, e: {
            i: [
                {"state": 10**400, "last_changed": "2026-01-01T00:00:00+00:00"},
                {"state": 3, "last_changed": "2026-01-01T01:00:00+00:00"},
            ]
            for i in ids
        }
    )
    _r({"type": "plot", "data": [{"entity": "a"}], "duration": 10**9}, ctx=ctx)


def test_describe_url_without_scheme_is_opaque():
    from imagespec.utils import describe_url

    assert describe_url("//u:SECRET@[x/p?t=TOK") == "<invalid url>"


@pytest.mark.parametrize(
    "url",
    [
        "http://host?email=u@example.com&token=SECRET",
        "http://host?next=/a&token=SECRET",
        "http://host?redirect=http://x/y&sig=SECRET",
        "http://host#frag@SECRET",
        "http://host#a/b&SECRET",
        "http://host?tok=a@b&sig=SECRET",
        "user:SECRET@host/x?u=http://a/b",
    ],
)
def test_describe_url_never_leaks_query_or_fragment(url):
    from imagespec.utils import describe_url

    assert "SECRET" not in describe_url(url)


def test_describe_url_normal_urls():
    from imagespec.utils import describe_url

    assert describe_url("http://host:8080/p.png?x=1") == "http://host:8080/p.png"
    assert describe_url("http://[::1]:8080/x?t=1") == "http://[::1]:8080/x"
    assert describe_url("https://user:pw@example.test/p.png?token=s3cret") == "https://example.test/p.png"
    assert describe_url("http://host?x=1") == "http://host"
