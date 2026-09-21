"""Data-driven elements: diagram (bar chart), plot (history line chart),
progress_bar.

``plot`` pulls history through ``RenderContext.history_provider`` so the core
never touches a host's recorder directly.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

from PIL import ImageDraw

from ..colors import white
from ..exceptions import RenderError
from ..registry import element
from ..spec import array, boolean, color, enum, num, obj, string
from ..state import RenderState
from ..utils import is_decimal, mono_draw, require


@element(
    "pie",
    doc="Pie or donut chart. Segment colours cycle through the device palette unless given.",
    fields=[
        num("x", required=True, doc="Centre x"),
        num("y", required=True, doc="Centre y"),
        num("radius", required=True),
        string("values", required=True, doc='`"label,value[,color];..."`'),
        num("inner_radius", 0, doc="> 0 makes a donut"),
        num("start_angle", -90, doc="Degrees; -90 starts at 12 o'clock"),
        color("outline", "black"),
        color("background", "white", doc="Donut hole colour"),
    ],
)
def pie(state: RenderState, element: dict) -> None:
    """Pie or donut chart from ``"label,value[,color]; ..."`` segments."""
    require(element, ["x", "y", "radius", "values"], "pie")
    cx, cy, r = element["x"], element["y"], element["radius"]
    inner = element.get("inner_radius", 0)
    start = element.get("start_angle", -90)
    outline = state.context.color(element.get("outline", "black"))

    segments = []
    for part in str(element["values"]).split(";"):
        bits = [b.strip() for b in part.split(",")]
        if len(bits) < 2:
            raise RenderError(f"pie: bad segment {part!r} — expected 'label,value[,color]'")
        segments.append((bits[0], float(bits[1]), bits[2] if len(bits) > 2 else None))

    total = sum(v for _, v, _ in segments) or 1
    # default slice colors: every palette color except the background-ish white
    cycle = [c for c in state.context.palette if c != white] or [state.context.color("black")]

    draw = ImageDraw.Draw(state.img)
    bbox = [(cx - r, cy - r), (cx + r, cy + r)]
    angle = start
    for i, (_label, value, seg_color) in enumerate(segments):
        sweep = value / total * 360
        col = state.context.color(seg_color) if seg_color else cycle[i % len(cycle)]
        draw.pieslice(bbox, angle, angle + sweep, fill=col, outline=outline)
        angle += sweep

    if inner > 0:  # donut hole
        bg = state.context.color(element.get("background", "white"))
        draw.ellipse([(cx - inner, cy - inner), (cx + inner, cy + inner)], fill=bg, outline=outline)


@element(
    "sparkline",
    doc="Compact axis-less line chart from inline values.",
    fields=[
        num("x", required=True),
        num("y", required=True),
        num("width", required=True),
        num("height", required=True),
        array("values", "number", required=True, alt="string", doc='List of numbers, or a `"1,3,2"` string'),
        num("min", doc="Y range floor; defaults to the data minimum"),
        num("max", doc="Y range ceiling; defaults to the data maximum"),
        color("color", "black", doc="Line colour"),
        color("fill", doc="Area colour below the line"),
        num("width_line", 1),
        string("joint", doc="Pillow line joint, e.g. `curve`"),
        boolean("dot_last", doc="Mark the last value with a dot"),
        num("dot_radius", 2),
        color("dot_color", doc="Defaults to `color`"),
    ],
)
def sparkline(state: RenderState, element: dict) -> None:
    """Compact axis-less line chart from inline values (no history)."""
    require(element, ["x", "y", "width", "height", "values"], "sparkline")
    x, y = element["x"], element["y"]
    w, h = element["width"], element["height"]
    values = element["values"]
    if isinstance(values, str):
        nums = [float(v) for v in values.replace(";", ",").split(",") if v.strip() != ""]
    else:
        nums = [float(v) for v in values]
    if not nums:
        return

    lo = element.get("min", min(nums))
    hi = element.get("max", max(nums))
    if hi == lo:
        hi = lo + 1
    n = len(nums)
    pts = []
    for i, v in enumerate(nums):
        px = x + (w - 1) * (i / (n - 1) if n > 1 else 0)
        py = y + (h - 1) * (1 - (v - lo) / (hi - lo))
        pts.append((px, py))

    draw = ImageDraw.Draw(state.img)
    area = element.get("fill")
    if area and len(pts) >= 2:
        base = y + h - 1
        draw.polygon([(pts[0][0], base)] + pts + [(pts[-1][0], base)], fill=state.context.color(area))
    draw.line(
        pts,
        fill=state.context.color(element.get("color", "black")),
        width=element.get("width_line", 1),
        joint=element.get("joint"),
    )
    if element.get("dot_last"):
        lx, ly = pts[-1]
        rd = element.get("dot_radius", 2)
        dot = state.context.color(element.get("dot_color", element.get("color", "black")))
        draw.ellipse([(lx - rd, ly - rd), (lx + rd, ly + rd)], fill=dot)


@element(
    "diagram",
    doc="Bar chart with x/y axes.",
    fields=[
        num("x", required=True),
        num("y", required=True),
        num("height", required=True),
        num("width", doc="Defaults to the canvas width"),
        num("margin", 20, doc="Space reserved for the axes/labels"),
        string("font"),
        obj(
            "bars",
            doc="Bar series",
            fields=[
                string("values", required=True, doc='`"label,value;label,value"`'),
                color("color", required=True),
                num("margin", 10, doc="Gap between bars"),
                num("legend_size", 10, doc="Label font size"),
                color("legend_color", "black"),
            ],
        ),
    ],
)
def diagram(state: RenderState, element: dict) -> None:
    require(element, ["x", "y", "height"], "diagram")
    draw = mono_draw(state.img)
    pos_x, pos_y = element["x"], element["y"]
    width = element.get("width", state.canvas_width)
    height = element["height"]
    offset = element.get("margin", 20)
    black = state.context.color("black")
    draw.line(
        [(pos_x + offset, pos_y + height - offset), (pos_x + width, pos_y + height - offset)], fill=black, width=1
    )
    draw.line([(pos_x + offset, pos_y), (pos_x + offset, pos_y + height - offset)], fill=black, width=1)

    if "bars" in element:
        bars_cfg = element["bars"]
        bar_margin = bars_cfg.get("margin", 10)
        bars = bars_cfg["values"].split(";")
        barcount = len(bars)
        bar_width = math.floor((width - offset - ((barcount + 1) * bar_margin)) / barcount)
        if bar_width <= 0:
            raise RenderError(
                f"diagram: not enough width ({width}px) for {barcount} bars with "
                f"margin {bar_margin} — increase 'width' or reduce 'bars.margin'."
            )
        font = state.context.font(element.get("font"), bars_cfg.get("legend_size", 10))
        legend_color = state.context.color(bars_cfg.get("legend_color", "black"))
        bar_color = state.context.color(bars_cfg["color"])
        max_val = max(float(b.split(",", 1)[1]) for b in bars)
        if max_val <= 0:
            raise RenderError(
                f"diagram: bar values must include a positive maximum, got max {max_val} — check 'bars.values'."
            )
        height_factor = (height - offset) / max_val
        for bar_pos, bar in enumerate(bars):
            name, value = bar.split(",", 1)
            x_pos = pos_x + ((bar_margin + bar_width) * bar_pos) + offset
            draw.text(
                (x_pos + (bar_width / 2), pos_y + height - offset / 2),
                str(name),
                fill=legend_color,
                font=font,
                anchor="mm",
            )
            draw.rectangle(
                [
                    (x_pos, pos_y + height - offset - (height_factor * float(value))),
                    (x_pos + bar_width, pos_y + height - offset),
                ],
                fill=bar_color,
            )


@element(
    "progress_bar",
    doc="Linear progress bar. `progress` is clamped to 0-100.",
    fields=[
        num("x_start", required=True),
        num("y_start", required=True),
        num("x_end", required=True),
        num("y_end", required=True),
        num("progress", required=True, doc="Percent, 0-100"),
        enum("direction", ("right", "left", "up", "down"), "right", doc="Case-insensitive"),
        color("background", "white"),
        color("fill", "red"),
        color("outline", "black"),
        num("width", 1, doc="Outline width"),
        num("radius", 0),
        boolean("show_percentage", False, doc="Draw `NN%` in the middle"),
        string("font"),
    ],
)
def progress_bar(state: RenderState, element: dict) -> None:
    require(element, ["x_start", "x_end", "y_start", "y_end", "progress"], "progress_bar")
    draw = ImageDraw.Draw(state.img)
    x_start, y_start = element["x_start"], element["y_start"]
    x_end, y_end = element["x_end"], element["y_end"]
    progress = max(0.0, min(100.0, float(element["progress"])))
    direction = str(element.get("direction", "right")).lower()
    if direction not in ("right", "left", "up", "down"):
        raise RenderError(f"progress_bar: 'direction' must be right/left/up/down, got {direction!r}")
    bg_color = state.context.color(element.get("background", "white"))
    fill = state.context.color(element.get("fill", "red"))
    outline = state.context.color(element.get("outline", "black"))
    width = element.get("width", 1)
    radius = element.get("radius", 0)

    draw.rounded_rectangle(
        [(x_start, y_start), (x_end, y_end)], fill=bg_color, outline=outline, width=width, radius=radius
    )

    if direction in ("right", "left"):
        progress_width = int((x_end - x_start) * (progress / 100))
    else:
        progress_height = int((y_end - y_start) * (progress / 100))

    if direction == "right":
        draw.rounded_rectangle([(x_start, y_start), (x_start + progress_width, y_end)], fill=fill, radius=radius)
    elif direction == "left":
        draw.rounded_rectangle([(x_end - progress_width, y_start), (x_end, y_end)], fill=fill, radius=radius)
    elif direction == "up":
        draw.rounded_rectangle([(x_start, y_end - progress_height), (x_end, y_end)], fill=fill, radius=radius)
    elif direction == "down":
        draw.rounded_rectangle([(x_start, y_start), (x_end, y_start + progress_height)], fill=fill, radius=radius)

    draw.rounded_rectangle([(x_start, y_start), (x_end, y_end)], fill=None, outline=outline, width=width, radius=radius)

    if element.get("show_percentage", False):
        font_size = min(y_end - y_start - 4, x_end - x_start - 4, 20)
        font = state.context.font(element.get("font"), font_size)
        text = f"{progress:g}%"
        tb = draw.textbbox((0, 0), text, font=font)
        tx = (x_start + x_end - (tb[2] - tb[0])) / 2
        ty = (y_start + y_end - (tb[3] - tb[1])) / 2
        text_color = bg_color if progress > 50 else fill
        draw.text((tx, ty), text, font=font, fill=text_color, anchor="lt")


@element(
    "plot",
    doc="Time-series line chart over the last `duration` seconds, fed by the host's "
    "`history_provider`. `low`/`high` widen the y range but never clip data.",
    fields=[
        array(
            "data",
            "object",
            required=True,
            doc="One series per entry",
            fields=[
                string("entity", required=True, doc="Entity id passed to the history provider"),
                color("color", "black"),
                num("width", 1, doc="Line width"),
                string("joint", doc="Pillow line joint"),
                color("area_fill", doc="Fill below the line"),
            ],
        ),
        num("x_start", 0),
        num("y_start", 0),
        num("x_end", doc="Defaults to `canvas_width - 1 - x_start` (same inset on the right as on the left)"),
        num("y_end", doc="Defaults to `canvas_height - 1 - y_start` (same inset at the bottom as at the top)"),
        num("duration", 86400, doc="Window in seconds ending now"),
        num("size", 10, doc="Default legend font size"),
        string("font"),
        num("low", doc="Y axis floor (widens only)"),
        num("high", doc="Y axis ceiling (widens only)"),
        boolean("debug", False, doc="Outline the plot and data areas"),
        obj(
            "ylegend",
            nullable=True,
            doc="Min/max labels; `null` disables",
            fields=[
                num("width", -1, doc="Reserved width; -1 = measure the labels"),
                color("color", "black"),
                enum("position", ("left", "right"), "left"),
                string("font"),
                num("size", doc="Defaults to the element `size`"),
            ],
        ),
        obj(
            "yaxis",
            nullable=True,
            doc="Axis line, ticks and grid; `null` disables",
            fields=[
                num("width", 1, doc="Axis line width"),
                color("color", "black"),
                num("tick_width", 2),
                num("tick_every", 1, doc="Value step between ticks"),
                num("grid", 5, nullable=True, doc="Dotted grid spacing in px; `null` disables"),
                color("grid_color", "black"),
            ],
        ),
        obj(
            "xlegend",
            doc="Time labels along the bottom",
            fields=[
                color("color", "black"),
                num("size", doc="Defaults to the element `size`"),
                string("font"),
                string("format", "%H:%M", doc="`strftime` format"),
                num("ticks", 3, doc="Number of labels"),
            ],
        ),
    ],
)
def plot(state: RenderState, element: dict) -> None:
    require(element, ["data"], "plot")
    draw = mono_draw(state.img)
    x_start = element.get("x_start", 0)
    y_start = element.get("y_start", 0)
    x_end = element.get("x_end", state.canvas_width - 1 - x_start)
    y_end = element.get("y_end", state.canvas_height - 1 - y_start)
    width = x_end - x_start + 1
    height = y_end - y_start + 1
    duration = timedelta(seconds=element.get("duration", 60 * 60 * 24))
    end = datetime.now(UTC)
    start = end - duration
    size = element.get("size", 10)

    ylegend = element.get("ylegend", {})
    if ylegend is None:
        ylegend_width = 0
        ylegend_pos = None
    else:
        ylegend_width = ylegend.get("width", -1)
        ylegend_color = state.context.color(ylegend.get("color", "black"))
        ylegend_pos = ylegend.get("position", "left")
        if ylegend_pos not in ("left", "right", None):
            ylegend_pos = "left"
        ylegend_font = state.context.font(ylegend.get("font", element.get("font")), ylegend.get("size", size))

    yaxis = element.get("yaxis", {})
    if yaxis is None:
        yaxis_width = 0
        yaxis_tick_width = 0
    else:
        yaxis_width = yaxis.get("width", 1)
        yaxis_color = state.context.color(yaxis.get("color", "black"))
        yaxis_tick_width = yaxis.get("tick_width", 2)
        yaxis_tick_every = float(yaxis.get("tick_every", 1))
        yaxis_grid = yaxis.get("grid", 5)
        if yaxis_grid is not None:
            yaxis_grid = max(1, round(yaxis_grid))  # range() step
        yaxis_grid_color = state.context.color(yaxis.get("grid_color", "black"))

    xlegend = element.get("xlegend", None)
    xlegend_height = 0
    if xlegend is not None:
        xlegend_color = state.context.color(xlegend.get("color", "black"))
        xlegend_size = xlegend.get("size", size)
        xlegend_font = state.context.font(xlegend.get("font", element.get("font")), xlegend_size)
        xlegend_format = xlegend.get("format", "%H:%M")
        xlegend_ticks = int(xlegend.get("ticks", 3))
        xlegend_height = xlegend_size + 4

    min_v: float | None = element.get("low", None)
    max_v: float | None = element.get("high", None)
    entity_ids = [p["entity"] for p in element["data"]]
    if not entity_ids:
        raise RenderError("plot: 'data' must list at least one entity")
    all_states = state.context.history(entity_ids, start, end)

    raw_data = []
    for p in element["data"]:
        if p["entity"] not in all_states:
            raise RenderError("no recorded data found for " + p["entity"])
        states = all_states[p["entity"]]
        # The provider yields the first sample as a State-like object (with
        # .state/.last_changed attrs) and the rest as dicts; normalize the head
        # without mutating the caller's list.
        head = states[0]
        normalized = [{"state": head.state, "last_changed": str(head.last_changed)}, *states[1:]]
        states = [
            (datetime.fromisoformat(s["last_changed"]), float(s["state"])) for s in normalized if is_decimal(s["state"])
        ]
        if not states:
            raise RenderError(f"plot: no numeric samples for {p['entity']} in the requested window")
        values = [v for _, v in states]
        lo, hi = min(values), max(values)
        # `low`/`high` widen the range but never clip data; `is None` (not
        # truthiness) so an explicit `low: 0` counts.
        min_v = lo if min_v is None else min(min_v, lo)
        max_v = hi if max_v is None else max(max_v, hi)
        raw_data.append(states)

    assert min_v is not None and max_v is not None  # every series contributed a lo/hi
    max_v = math.ceil(max_v)
    min_v = math.floor(min_v)
    if max_v == min_v:
        min_v -= 1
    spread = max_v - min_v

    if ylegend is not None and ylegend_width == -1:
        ylegend_width = math.ceil(
            max(draw.textlength(str(max_v), font=ylegend_font), draw.textlength(str(min_v), font=ylegend_font))
        )

    diag_x = x_start + (ylegend_width if ylegend is not None and ylegend_pos == "left" else 0)
    diag_y = y_start
    diag_width = width - (ylegend_width if ylegend is not None else 0)
    diag_height = height - xlegend_height

    if element.get("debug", False):
        draw.rectangle([(x_start, y_start), (x_end, y_end)], fill=None, outline=state.context.color("black"), width=1)
        draw.rectangle(
            [(diag_x, diag_y), (diag_x + diag_width - 1, diag_y + diag_height - 1)],
            fill=None,
            outline=state.context.color("red"),
            width=1,
        )

    if yaxis is not None and yaxis_grid is not None:
        grid_points: list[tuple[int, int]] = []
        curr: float = min_v
        while curr <= max_v:
            curr_y = round(diag_y + (1 - ((curr - min_v) / spread)) * (diag_height - 1))
            grid_points.extend((x, curr_y) for x in range(diag_x, diag_x + diag_width, yaxis_grid))
            curr += yaxis_tick_every
        draw.point(grid_points, fill=yaxis_grid_color)

    for p, data in zip(element["data"], raw_data, strict=False):
        xy_raw = []
        for time_val, value in data:
            rel_time = (time_val - start) / duration
            rel_value = (value - min_v) / spread
            xy_raw.append(
                (round(diag_x + rel_time * (diag_width - 1)), round(diag_y + (1 - rel_value) * (diag_height - 1)))
            )
        # Collapse samples that land on the same pixel column to their mean y.
        xy: list[tuple[int, int]] = []
        ys: list[int] = []
        last_x = xy_raw[0][0]
        for x, y in xy_raw:
            if x != last_x:
                xy.append((last_x, round(sum(ys) / len(ys))))
                ys = []
                last_x = x
            ys.append(y)
        xy.append((last_x, round(sum(ys) / len(ys))))

        area_fill = p.get("area_fill", None)
        if area_fill and len(xy) >= 2:
            baseline_y = diag_y + diag_height - 1
            poly_pts = [(xy[0][0], baseline_y)] + xy + [(xy[-1][0], baseline_y)]
            draw.polygon(poly_pts, fill=state.context.color(area_fill))

        draw.line(
            xy, fill=state.context.color(p.get("color", "black")), width=p.get("width", 1), joint=p.get("joint", None)
        )

    if ylegend is not None:
        if ylegend_pos == "left":
            draw.text((x_start, y_start), str(max_v), fill=ylegend_color, font=ylegend_font, anchor="lt")
            draw.text(
                (x_start, diag_y + diag_height - 1), str(min_v), fill=ylegend_color, font=ylegend_font, anchor="ls"
            )
        elif ylegend_pos == "right":
            draw.text((x_end, y_start), str(max_v), fill=ylegend_color, font=ylegend_font, anchor="rt")
            draw.text((x_end, diag_y + diag_height - 1), str(min_v), fill=ylegend_color, font=ylegend_font, anchor="rs")

    if yaxis is not None:
        draw.rectangle(
            [(diag_x, diag_y), (diag_x + yaxis_width - 1, diag_y + diag_height - 1)], width=0, fill=yaxis_color
        )
        if yaxis_tick_width > 0:
            curr = float(min_v)
            while curr <= max_v:
                curr_y = round(diag_y + (1 - ((curr - min_v) / spread)) * (diag_height - 1))
                draw.rectangle(
                    [(diag_x + yaxis_width, curr_y), (diag_x + yaxis_width + yaxis_tick_width - 1, curr_y)],
                    width=0,
                    fill=yaxis_color,
                )
                curr += yaxis_tick_every

    if xlegend is not None:
        label_y = diag_y + diag_height + 2
        for i in range(xlegend_ticks):
            ratio = i / max(xlegend_ticks - 1, 1)
            lx = round(diag_x + ratio * (diag_width - 1))
            time_label = (start + duration * ratio).strftime(xlegend_format)
            anchor = "lt" if i == 0 else "rt" if i == xlegend_ticks - 1 else "mt"
            draw.text((lx, label_y), time_label, fill=xlegend_color, font=xlegend_font, anchor=anchor)
