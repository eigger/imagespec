"""Template-string coercion: numeric/bool keys given as strings (as HA templates
produce) render the same as native numbers, and fractional floats never hit an
int-only PIL call."""

from __future__ import annotations

import pytest
from PIL import ImageDraw

from imagespec import RenderError, render
from imagespec.utils import BOOL_KEYS, NUMERIC_KEYS, coerce_element, to_bool, to_number
from test_elements import _samples  # tests/ is on sys.path via conftest (prepend import mode)

# ── unit: helpers ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "value, expected",
    [
        ("42", 42),
        (" 42 ", 42),
        ("-7", -7),
        ("3.5", 3.5),
        ("10.0", 10),  # integral float string -> int, so int-only sites work
        ("1e2", 100),
        (42, 42),  # non-strings pass through untouched
        (3.5, 3.5),
        (None, None),
        (True, True),
    ],
)
def test_to_number(value, expected):
    result = to_number(value)
    assert result == expected and type(result) is type(expected)


def test_to_number_rejects_garbage_naming_key():
    with pytest.raises(ValueError, match="'x_start' must be a number, got 'oops'"):
        to_number("oops", "x_start")


@pytest.mark.parametrize("value", ["False", "off", "no", "none", "0", "0.0", "", 0, None, False])
def test_to_bool_falsy(value):
    assert to_bool(value) is False


@pytest.mark.parametrize("value", ["True", "on", "yes", "1", "0.5", "abc", 1, True])
def test_to_bool_truthy(value):
    assert to_bool(value) is True


def test_coerce_element_top_level_and_nested():
    el = {
        "type": "plot",
        "x_start": "2",
        "size": "10.0",
        "show_value": "False",
        "columns": ["18", "18"],
        "ylegend": {"width": "20", "position": "left"},
        "spans": [{"text": "a", "size": "14"}],
        "value": "007",  # never numeric -> untouched
        "elements": [{"type": "text", "x": "5"}],  # children coerced at their own dispatch
    }
    out = coerce_element(el)
    assert out["x_start"] == 2 and out["size"] == 10 and type(out["size"]) is int
    assert out["show_value"] is False
    assert out["columns"] == [18, 18]
    assert out["ylegend"] == {"width": 20, "position": "left"}
    assert out["spans"] == [{"text": "a", "size": 14}]
    assert out["value"] == "007"
    assert out["elements"][0]["x"] == "5"
    assert el["x_start"] == "2"  # input not mutated


def test_key_sets_are_disjoint():
    assert not (NUMERIC_KEYS & BOOL_KEYS)


# ── integration: every element, strings and fractional floats ──────────────


def _convert(el, fn):
    """Apply ``fn`` to every numeric leaf (top level, nested dicts, children)."""
    out = {}
    for k, v in el.items():
        if isinstance(v, bool):
            out[k] = v
        elif isinstance(v, (int, float)):
            out[k] = fn(v)
        elif isinstance(v, dict):
            out[k] = _convert(v, fn)
        elif isinstance(v, list) and k in ("elements", "spans", "items"):
            out[k] = [_convert(c, fn) if isinstance(c, dict) else c for c in v]
        elif isinstance(v, list) and k == "columns":
            out[k] = [fn(c) for c in v]
        else:
            out[k] = v
    return out


@pytest.mark.parametrize("name", sorted(_samples("data:,").keys()))
def test_string_numbers_render_like_native(ctx, data_url, name):
    el = _samples(data_url)[name]
    native = render([el], 40, 40, context=ctx)
    as_str = render([_convert(el, str)], 40, 40, context=ctx)
    assert as_str.tobytes() == native.tobytes(), f"{name}: string numerics changed the output"


@pytest.mark.parametrize("name", sorted(_samples("data:,").keys()))
def test_integral_float_strings_render_like_native(ctx, data_url, name):
    el = _samples(data_url)[name]
    native = render([el], 40, 40, context=ctx)
    as_str = render([_convert(el, lambda v: str(float(v)))], 40, 40, context=ctx)
    assert as_str.tobytes() == native.tobytes(), f"{name}: '10.0'-style strings changed the output"


@pytest.mark.parametrize("name", sorted(_samples("data:,").keys()))
def test_fractional_floats_do_not_raise(ctx, data_url, name):
    # int-only PIL calls (Image.new size, range(), qrcode box_size, ...) used to
    # fail on e.g. width=10.4; every element must now tolerate it.
    el = _samples(data_url)[name]
    assert render([_convert(el, lambda v: v + 0.4)], 40, 40, context=ctx).size == (40, 40)


def test_stack_padding_and_child_layout_strings(bw_ctx):
    def img(fn):
        el = {
            "type": "row",
            "x": 0,
            "y": 0,
            "width": fn(60),
            "height": fn(20),
            "gap": fn(2),
            "padding_left": fn(3),
            "padding_y": fn(1),
            "elements": [
                {"type": "rectangle", "x_start": 0, "y_start": 0, "x_end": 9, "y_end": 9, "fill": "black"},
                {
                    "type": "rectangle",
                    "x_start": 0,
                    "y_start": 0,
                    "x_end": 9,
                    "y_end": 9,
                    "fill": "black",
                    "layout": {"grow": fn(1), "margin_left": fn(4), "margin_y": fn(2)},
                },
            ],
        }
        return render([el], 60, 20, context=bw_ctx)

    assert img(str).tobytes() == img(int).tobytes()


def test_plot_string_options(history_ctx):
    el = {
        "type": "plot",
        "x_start": "2",
        "y_start": "2",
        "x_end": "197",
        "y_end": "97",
        "duration": "3600",
        "low": "0",
        "data": [{"entity": "sensor.temp", "width": "2"}],
        "ylegend": {"size": "8", "width": "20"},
        "yaxis": {"width": "1", "tick_every": "2", "grid": "5"},
        "xlegend": {"size": "8", "ticks": "3"},
    }
    assert render([el], 200, 100, context=history_ctx).size == (200, 100)


# ── bool flags ─────────────────────────────────────────────────────────────


def _drawn_texts(monkeypatch, ctx, el):
    drawn = []
    orig = ImageDraw.ImageDraw.text

    def spy(self, xy, text, *args, **kwargs):
        drawn.append(text)
        return orig(self, xy, text, *args, **kwargs)

    monkeypatch.setattr(ImageDraw.ImageDraw, "text", spy)
    render([el], 60, 20, context=ctx)
    return drawn


@pytest.mark.parametrize("flag, expect_label", [("False", False), ("off", False), ("True", True), ("1", True)])
def test_bool_flag_strings(bw_ctx, monkeypatch, flag, expect_label):
    # "False" is truthy in Python; the flag must be read as a real boolean.
    el = {"type": "progress_bar", "x_start": 0, "y_start": 0, "x_end": 59, "y_end": 19, "progress": 50}
    el["show_percentage"] = flag
    assert (_drawn_texts(monkeypatch, bw_ctx, el) == ["50%"]) is expect_label


# ── errors ─────────────────────────────────────────────────────────────────


def test_bad_numeric_string_names_key_and_element(ctx):
    el = {"type": "rectangle", "x_start": "oops", "y_start": 0, "x_end": 9, "y_end": 9}
    with pytest.raises(RenderError) as exc:
        render([{"type": "line", "x_start": 0, "x_end": 5}, el], 20, 20, context=ctx)
    msg = str(exc.value)
    assert "#1" in msg and "rectangle" in msg and "'x_start' must be a number, got 'oops'" in msg


def test_bad_numeric_string_inside_container_names_child(ctx):
    el = {"type": "group", "x": 0, "y": 0, "elements": [{"type": "circle", "x": "5", "y": "abc", "radius": 3}]}
    with pytest.raises(RenderError, match=r"child #0 \(type 'circle'\): 'y' must be a number"):
        render([el], 20, 20, context=ctx)
