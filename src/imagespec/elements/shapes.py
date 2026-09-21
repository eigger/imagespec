"""Geometric primitives: line, rectangle(+pattern), circle, ellipse, arc,
polygon, gauge.

Lines may be dashed; rectangles accept per-corner rounding.
"""

from __future__ import annotations

import math

from PIL import ImageDraw

from ..exceptions import RenderError
from ..registry import element
from ..state import RenderState
from ..utils import mono_draw, require, rounded_corners


def _rounding(element: dict) -> tuple[int, tuple[bool, bool, bool, bool]]:
    """``(radius, corners)`` for ``rounded_rectangle`` from ``radius``/``corners`` keys.

    ``corners`` alone implies a 10px radius; ``radius`` alone rounds all corners.
    """
    radius = element.get("radius", 10 if "corners" in element else 0)
    if "corners" in element:
        corners = rounded_corners(element["corners"])
    elif "radius" in element:
        corners = rounded_corners("all")
    else:
        corners = (False, False, False, False)
    return radius, corners


def _draw_dashed_line(draw, x0, y0, x1, y1, dash, fill, width):
    """Draw a dashed/dotted line between two points."""
    dash_on = dash[0]
    dash_off = dash[1] if len(dash) > 1 else dash[0]
    total_len = math.hypot(x1 - x0, y1 - y0)
    if total_len == 0:
        return
    dx = (x1 - x0) / total_len
    dy = (y1 - y0) / total_len
    pos = 0
    drawing = True
    while pos < total_len:
        seg_len = dash_on if drawing else dash_off
        seg_end = min(pos + seg_len, total_len)
        if drawing:
            draw.line(
                [(x0 + dx * pos, y0 + dy * pos), (x0 + dx * seg_end, y0 + dy * seg_end)],
                fill=fill,
                width=width,
            )
        pos += seg_len
        drawing = not drawing


@element("line")
def line(state: RenderState, element: dict) -> None:
    require(element, ["x_start", "x_end"], "line")
    draw = ImageDraw.Draw(state.img)
    if "y_start" not in element:
        y_start = state.pos_y + element.get("y_padding", 0)
        y_end = y_start
    else:
        y_start = element["y_start"]
        y_end = element["y_end"]

    fill = state.context.color(element["fill"]) if "fill" in element else state.context.color("black")
    width = element.get("width", 1)
    dash = element.get("dash", None)

    if dash:
        _draw_dashed_line(draw, element["x_start"], y_start, element["x_end"], y_end, dash, fill, width)
    else:
        draw.line([(element["x_start"], y_start), (element["x_end"], y_end)], fill=fill, width=width)
    state.pos_y = y_start


@element("rectangle")
def rectangle(state: RenderState, element: dict) -> None:
    require(element, ["x_start", "x_end", "y_start", "y_end"], "rectangle")
    draw = ImageDraw.Draw(state.img)
    fill = state.context.color(element["fill"]) if "fill" in element else None
    outline = state.context.color(element["outline"]) if "outline" in element else state.context.color("black")
    width = element.get("width", 1)
    radius, corners = _rounding(element)
    draw.rounded_rectangle(
        [(element["x_start"], element["y_start"]), (element["x_end"], element["y_end"])],
        fill=fill,
        outline=outline,
        width=width,
        radius=radius,
        corners=corners,
    )


@element("rectangle_pattern")
def rectangle_pattern(state: RenderState, element: dict) -> None:
    require(
        element,
        ["x_start", "x_size", "y_start", "y_size", "x_repeat", "y_repeat", "x_offset", "y_offset"],
        "rectangle_pattern",
    )
    draw = ImageDraw.Draw(state.img)
    fill = state.context.color(element["fill"]) if "fill" in element else None
    outline = state.context.color(element["outline"]) if "outline" in element else state.context.color("black")
    width = element.get("width", 1)
    radius, corners = _rounding(element)
    for x in range(int(element["x_repeat"])):
        for y in range(int(element["y_repeat"])):
            x0 = element["x_start"] + x * (element["x_offset"] + element["x_size"])
            y0 = element["y_start"] + y * (element["y_offset"] + element["y_size"])
            draw.rounded_rectangle(
                [(x0, y0), (x0 + element["x_size"], y0 + element["y_size"])],
                fill=fill,
                outline=outline,
                width=width,
                radius=radius,
                corners=corners,
            )


@element("circle")
def circle(state: RenderState, element: dict) -> None:
    require(element, ["x", "y", "radius"], "circle")
    draw = ImageDraw.Draw(state.img)
    fill = state.context.color(element["fill"]) if "fill" in element else None
    outline = state.context.color(element["outline"]) if "outline" in element else state.context.color("black")
    width = element.get("width", 1)
    draw.circle((element["x"], element["y"]), element["radius"], fill=fill, outline=outline, width=width)


@element("ellipse")
def ellipse(state: RenderState, element: dict) -> None:
    require(element, ["x_start", "x_end", "y_start", "y_end"], "ellipse")
    draw = ImageDraw.Draw(state.img)
    fill = state.context.color(element["fill"]) if "fill" in element else None
    outline = state.context.color(element["outline"]) if "outline" in element else state.context.color("black")
    width = element.get("width", 1)
    draw.ellipse(
        [(element["x_start"], element["y_start"]), (element["x_end"], element["y_end"])],
        fill=fill,
        outline=outline,
        width=width,
    )


@element("arc")
def arc(state: RenderState, element: dict) -> None:
    require(element, ["x_start", "y_start", "x_end", "y_end", "start_angle", "end_angle"], "arc")
    draw = ImageDraw.Draw(state.img)
    fill = state.context.color(element.get("fill", None))
    outline = state.context.color(element.get("outline", "black"))
    width = element.get("width", 1)
    bbox = [(element["x_start"], element["y_start"]), (element["x_end"], element["y_end"])]
    if element.get("pie", False):
        draw.pieslice(
            bbox, start=element["start_angle"], end=element["end_angle"], fill=fill, outline=outline, width=width
        )
    else:
        draw.arc(bbox, start=element["start_angle"], end=element["end_angle"], fill=outline, width=width)


@element("polygon")
def polygon(state: RenderState, element: dict) -> None:
    require(element, ["points"], "polygon")
    draw = ImageDraw.Draw(state.img)
    fill = state.context.color(element.get("fill", None))
    outline = state.context.color(element.get("outline", "black"))
    width = element.get("width", 1)
    try:
        pts = []
        for pair in element["points"].split(";"):
            x_str, y_str = pair.strip().split(",")
            pts.append((float(x_str), float(y_str)))
        draw.polygon(pts, fill=fill, outline=outline, width=width)
    except Exception as e:  # noqa: BLE001
        raise RenderError(f"polygon: invalid points format '{element['points']}' — expected 'x1,y1;x2,y2;...'") from e


@element("gauge")
def gauge(state: RenderState, element: dict) -> None:
    require(element, ["x", "y", "radius", "progress"], "gauge")
    draw = ImageDraw.Draw(state.img)
    cx, cy = element["x"], element["y"]
    radius = element["radius"]
    progress = float(element["progress"])
    min_val = element.get("min_value", 0)
    max_val = element.get("max_value", 100)
    bar_width = element.get("width", 8)
    fill_color = state.context.color(element.get("fill", "black"))
    bg_color = state.context.color(element.get("background", "white"))
    outline_color = state.context.color(element.get("outline", "black"))

    start_angle = 135
    end_angle = 405  # 270° sweep
    ratio = max(0.0, min(1.0, (progress - min_val) / (max_val - min_val) if max_val != min_val else 0))
    progress_end = start_angle + ratio * 270
    bbox = [(cx - radius, cy - radius), (cx + radius, cy + radius)]

    draw.arc(bbox, start=start_angle, end=end_angle, fill=bg_color, width=bar_width)
    if ratio > 0:
        draw.arc(bbox, start=start_angle, end=progress_end, fill=fill_color, width=bar_width)
    draw.arc(
        [(cx - radius - 1, cy - radius - 1), (cx + radius + 1, cy + radius + 1)],
        start=start_angle,
        end=end_angle,
        fill=outline_color,
        width=1,
    )

    if element.get("show_value", False):
        font = state.context.font(element.get("font"), element.get("size", 16))
        d = mono_draw(state.img)
        value_color = state.context.color(element.get("color", "black"))
        display_val = f"{int(progress)}" if progress == int(progress) else f"{progress:.1f}"
        d.text((cx, cy), display_val, fill=value_color, font=font, anchor="mm")
