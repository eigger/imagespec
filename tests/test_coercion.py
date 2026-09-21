"""Template-string coercion: numeric/bool keys given as strings (as HA templates
produce) render the same as native numbers, and fractional floats never hit an
int-only PIL call."""

from __future__ import annotations

import pytest
from PIL import ImageDraw

from imagespec import RenderError, render
from imagespec.registry import get_spec
from imagespec.spec import COMMON_FIELDS
from imagespec.utils import coerce_element, to_bool, to_number
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


def _fields(etype):
    return (*COMMON_FIELDS, *get_spec(etype).fields)


def test_coerce_element_top_level_and_nested():
    el = {
        "type": "plot",
        "x_start": "2",
        "size": "10.0",
        "debug": "False",
        "visible": "true",
        "ylegend": {"width": "20", "position": "left"},
        "data": [{"entity": "sensor.a", "width": "2"}],
        "layout": {"grow": "1", "margin_x": "3"},
    }
    out = coerce_element(el, _fields("plot"))
    assert out["x_start"] == 2 and out["size"] == 10 and type(out["size"]) is int
    assert out["debug"] is False and out["visible"] is True
    assert out["ylegend"] == {"width": 20, "position": "left"}
    assert out["data"] == [{"entity": "sensor.a", "width": 2}]
    assert out["layout"] == {"grow": 1, "margin_x": 3}
    assert el["x_start"] == "2"  # input not mutated


def test_coerce_element_only_touches_declared_keys():
    el = {"type": "text", "x": "5", "value": "007", "unknown_key": "42", "spans": [{"size": "9"}]}
    out = coerce_element(el, _fields("text"))
    assert out["x"] == 5
    assert out["value"] == "007"  # `any` kind: never coerced
    assert out["unknown_key"] == "42"  # undeclared: untouched
    assert out["spans"] == [{"size": "9"}]  # not a `text` field


def test_coerce_element_children_left_for_their_own_dispatch():
    el = {"type": "group", "x": "1", "elements": [{"type": "text", "x": "5", "value": "a"}]}
    out = coerce_element(el, _fields("group"))
    assert out["x"] == 1 and out["elements"][0]["x"] == "5"


def test_coerce_element_numeric_array_and_table_rows():
    el = {"type": "table", "x": 0, "y": 0, "columns": ["18", "18.0"], "rows": [["1", "2"]]}
    out = coerce_element(el, _fields("table"))
    assert out["columns"] == [18, 18]
    assert out["rows"] == [["1", "2"]]  # cells are strings by design


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


def test_group_and_stack_round_fractional_size_alike(bw_ctx):
    # both containers size their canvas the same way (round, not truncate)
    def extent(kind):
        el = {"type": kind, "x": 0, "y": 0, "width": 10.6, "height": 10.6}
        el["elements"] = [{"type": "rectangle", "x_start": 0, "y_start": 0, "x_end": 30, "y_end": 30, "fill": "black"}]
        img = render([el], 20, 20, context=bw_ctx)
        return sum(1 for x in range(20) if img.getpixel((x, 0)) == (0, 0, 0))

    assert extent("group") == extent("stack") == 11


def test_plot_fractional_grid_does_not_raise(history_ctx):
    el = {"type": "plot", "data": [{"entity": "sensor.temp"}], "yaxis": {"grid": 5.5, "tick_every": 1.5}}
    assert render([el], 200, 100, context=history_ctx).size == (200, 100)
    el["yaxis"]["grid"] = "5.5"
    assert render([el], 200, 100, context=history_ctx).size == (200, 100)


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
