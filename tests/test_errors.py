"""Error handling: missing required args, dlimg policy, invalid inputs."""

from __future__ import annotations

import pytest

from imagespec import RenderContext, RenderError, render


@pytest.mark.parametrize(
    "element, missing",
    [
        ({"type": "text", "y": 1}, ["x", "value"]),
        ({"type": "rectangle", "x_start": 0, "y_start": 0, "y_end": 9}, ["x_end"]),
        ({"type": "qrcode", "x": 0, "y": 0}, ["data"]),
        ({"type": "icon", "x": 0, "y": 0, "value": "mdi:home"}, ["size"]),
        ({"type": "gauge", "x": 0, "y": 0, "radius": 5}, ["progress"]),
    ],
)
def test_missing_required_args_named_in_error(ctx, element, missing):
    with pytest.raises(RenderError) as exc:
        render([element], 20, 20, context=ctx)
    for key in missing:
        assert key in str(exc.value)


def test_dlimg_local_path_blocked_by_default(ctx):
    el = {"type": "dlimg", "x": 0, "y": 0, "url": "some/local.png", "xsize": 8, "ysize": 8}
    with pytest.raises(RenderError):
        render([el], 20, 20, context=ctx)


def test_dlimg_local_path_allowed_when_opted_in(tmp_path):
    # create a real local image and allow it
    from PIL import Image

    p = tmp_path / "x.png"
    Image.new("RGB", (4, 4), (0, 0, 0)).save(p)
    ctx = RenderContext(palette="4", allow_local_images=True)
    el = {"type": "dlimg", "x": 0, "y": 0, "url": str(p), "xsize": 8, "ysize": 8}
    assert render([el], 20, 20, context=ctx).size == (20, 20)


def test_invalid_barcode_code_raises(ctx):
    el = {"type": "barcode", "x": 0, "y": 0, "data": "123", "code": "not-a-real-symbology"}
    with pytest.raises(RenderError):
        render([el], 40, 40, context=ctx)


def test_polygon_bad_points_raises(ctx):
    el = {"type": "polygon", "points": "garbage"}
    with pytest.raises(RenderError):
        render([el], 20, 20, context=ctx)


def test_handler_error_wrapped_with_element_context(ctx):
    # a non-numeric coordinate triggers a PIL/TypeError deep inside the handler;
    # the loop should surface it as a RenderError naming the element index/type.
    el = {"type": "rectangle", "x_start": "oops", "y_start": 0, "x_end": 9, "y_end": 9}
    with pytest.raises(RenderError) as exc:
        render([{"type": "line", "x_start": 0, "x_end": 5}, el], 20, 20, context=ctx)
    msg = str(exc.value)
    assert "#1" in msg and "rectangle" in msg


def test_diagram_too_small_raises(ctx):
    el = {
        "type": "diagram",
        "x": 0,
        "y": 0,
        "height": 30,
        "width": 30,
        "bars": {"values": "a,1;b,2;c,3", "color": "black", "margin": 20},
    }
    with pytest.raises(RenderError):
        render([el], 40, 40, context=ctx)


def test_plot_without_history_provider_raises(ctx):
    el = {"type": "plot", "data": [{"entity": "sensor.x"}]}
    with pytest.raises(RenderError):
        render([el], 40, 40, context=ctx)


def test_diagram_missing_required_args(ctx):
    el = {"type": "diagram", "x": 0, "bars": {"values": "a,1", "color": "black"}}
    with pytest.raises(RenderError) as exc:
        render([el], 40, 40, context=ctx)
    assert "height" in str(exc.value)


def test_diagram_accepts_float_bar_values(ctx):
    el = {
        "type": "diagram",
        "x": 0,
        "y": 0,
        "height": 35,
        "width": 60,
        "bars": {"values": "a,1.5;b,2.5", "color": "black", "margin": 4},
    }
    assert render([el], 80, 40, context=ctx).size == (80, 40)


def test_diagram_nonpositive_max_raises(ctx):
    el = {
        "type": "diagram",
        "x": 0,
        "y": 0,
        "height": 35,
        "width": 60,
        "bars": {"values": "a,0;b,0", "color": "black", "margin": 4},
    }
    with pytest.raises(RenderError):
        render([el], 80, 40, context=ctx)


def test_group_child_error_wrapped_with_context(ctx):
    el = {
        "type": "group",
        "x": 0,
        "y": 0,
        "elements": [{"type": "rectangle", "x_start": "oops", "y_start": 0, "x_end": 9, "y_end": 9}],
    }
    with pytest.raises(RenderError) as exc:
        render([el], 20, 20, context=ctx)
    msg = str(exc.value)
    assert "group" in msg and "rectangle" in msg
