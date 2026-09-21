"""Text elements: text (with optional rotation + background box), multiline,
text_box, new_multiline (fit-to-width/height autosize), table, text_fit.

``new_multiline`` auto-shrinks to a width/height; ``text_fit`` fits text into a
fixed box by shrinking the font and/or truncating with an ellipsis.
"""

from __future__ import annotations

from PIL import Image

from ..exceptions import RenderError
from ..registry import element
from ..spec import any_, array, boolean, color, enum, num, string
from ..state import RenderState
from ..utils import int_xy, mono_draw, require, wrap_words
from .media import resolve_icon


def _ellipsize_line(font, line: str, max_width: float, ellipsis: str) -> str:
    """Trim ``line`` and append ``ellipsis`` so it fits within ``max_width``."""
    if font.getlength(line + ellipsis) <= max_width:
        return line + ellipsis
    s = line
    while s and font.getlength(s + ellipsis) > max_width:
        s = s[:-1]
    return s + ellipsis


def fit_lines(text: str, font, max_width: float, max_lines: int, ellipsis: str):
    """Wrap ``text`` to ``max_width`` within ``max_lines``.

    Returns ``(lines, fits)`` where ``fits`` is False if anything had to be
    truncated (too many lines, or a line wider than ``max_width``).
    """
    all_lines = wrap_words(text, font, max_width)
    fits = True
    lines = all_lines[:max_lines]
    if len(all_lines) > max_lines:
        fits = False
        lines[-1] = _ellipsize_line(font, lines[-1], max_width, ellipsis)
    for i, ln in enumerate(lines):
        if font.getlength(ln) > max_width:
            fits = False
            lines[i] = _ellipsize_line(font, ln, max_width, ellipsis)
    return lines, fits


@element(
    "text",
    doc="Text. Without `y` it flows below the previous text/line (`y_padding` gap) and advances the "
    "cursor. `\\n` in `value` starts a new line; `max_width` word-wraps instead.",
    fields=[
        num("x", required=True),
        any_("value", required=True, doc="Text to draw (converted with `str()`)"),
        num("y", doc="Omit to place at the flow cursor"),
        num("y_padding", 10, doc="Gap below the flow cursor when `y` is omitted"),
        num("size", 20, doc="Font size in px"),
        string("font", doc="Font file name; resolved by the host, else the bundled default"),
        color("color", "black"),
        string("anchor", "lt", doc="Pillow text anchor (`lt`, `mm`, `rs`, ...); ignored with `max_width`"),
        enum("align", ("left", "center", "right"), "left", doc="Line alignment for multi-line text"),
        num("spacing", 5, doc="Extra px between lines"),
        num("stroke_width", 0),
        color("stroke_fill", "white"),
        num("rotation", 0, doc="Degrees counter-clockwise; rotated text is composited at `(x, y)`"),
        color("background", doc="Fill a box behind the text"),
        num("background_padding", 2, doc="Padding of the background box"),
        num("max_width", doc="Word-wrap to this width in px"),
    ],
)
def text(state: RenderState, element: dict) -> None:
    require(element, ["x", "value"], "text")
    d = mono_draw(state.img)
    size = element.get("size", 20)
    font = state.context.font(element.get("font"), size)

    if "y" not in element:
        akt_pos_y = state.pos_y + element.get("y_padding", 10)
    else:
        akt_pos_y = element["y"]

    color = element.get("color", "black")
    anchor = element.get("anchor", "lt")
    align = element.get("align", "left")
    spacing = element.get("spacing", 5)
    stroke_width = element.get("stroke_width", 0)
    stroke_fill = state.context.color(element.get("stroke_fill", "white"))
    text_rotation = element.get("rotation", 0)
    bg_color = element.get("background", None)
    bg_padding = element.get("background_padding", 2)

    if "max_width" in element:
        value = "\n".join(wrap_words(str(element["value"]), font, element["max_width"]))
        anchor = None
    else:
        value = str(element["value"])

    # Extent of the (unrotated) text at its anchor: drives the background box
    # and the flow cursor. textbbox ignores image content, so one call serves both.
    tbbox = d.textbbox(
        (element["x"], akt_pos_y),
        value,
        font=font,
        anchor=anchor,
        align=align,
        spacing=spacing,
        stroke_width=stroke_width,
    )

    if text_rotation != 0:
        # Render onto a temporary transparent image, rotate, then composite.
        raw = d.textbbox((0, 0), value, font=font, spacing=spacing, stroke_width=stroke_width)
        tw = raw[2] - raw[0] + stroke_width * 2
        th = raw[3] - raw[1] + stroke_width * 2
        tmp = Image.new("RGBA", (tw + 4, th + 4), (255, 255, 255, 0))
        tmp_d = mono_draw(tmp)
        if bg_color is not None:
            tmp_d.rectangle([(0, 0), (tw + 4, th + 4)], fill=state.context.color(bg_color))
        tmp_d.text(
            (2, 2),
            value,
            fill=state.context.color(color),
            font=font,
            spacing=spacing,
            stroke_width=stroke_width,
            stroke_fill=stroke_fill,
        )
        tmp = tmp.rotate(text_rotation, expand=True)
        canvas = Image.new("RGBA", state.img.size, (255, 255, 255, 0))
        canvas.paste(tmp, int_xy(element["x"], akt_pos_y))
        state.img = Image.alpha_composite(state.img, canvas)
    else:
        if bg_color is not None:
            d.rectangle(
                [(tbbox[0] - bg_padding, tbbox[1] - bg_padding), (tbbox[2] + bg_padding, tbbox[3] + bg_padding)],
                fill=state.context.color(bg_color),
            )
        d.text(
            (element["x"], akt_pos_y),
            value,
            fill=state.context.color(color),
            font=font,
            anchor=anchor,
            align=align,
            spacing=spacing,
            stroke_width=stroke_width,
            stroke_fill=stroke_fill,
        )

    state.pos_y = tbbox[3]


@element(
    "text_box",
    doc="Single-line text on a rounded, filled box sized to the text.",
    fields=[
        num("x", required=True),
        num("y", required=True),
        any_("value", required=True),
        num("size", 20),
        string("font"),
        num("padding", 5),
        color("fill", "black", doc="Box colour"),
        color("color", "white", doc="Text colour"),
        color("outline", doc="Box outline colour"),
        num("width", 1, doc="Outline width"),
        num("radius", 5, doc="Box corner radius"),
    ],
)
def text_box(state: RenderState, element: dict) -> None:
    require(element, ["x", "y", "value"], "text_box")
    d = mono_draw(state.img)
    size = element.get("size", 20)
    font = state.context.font(element.get("font"), size)
    value = str(element["value"])
    padding = element.get("padding", 5)
    fill_color = state.context.color(element.get("fill", "black"))
    text_color = state.context.color(element.get("color", "white"))
    outline_color = state.context.color(element.get("outline", None))
    outline_width = element.get("width", 1)
    radius = element.get("radius", 5)
    tbbox = d.textbbox((element["x"] + padding, element["y"] + padding), value, font=font)
    box_x0, box_y0 = element["x"], element["y"]
    box_x1, box_y1 = tbbox[2] + padding, tbbox[3] + padding
    d.rounded_rectangle(
        [(box_x0, box_y0), (box_x1, box_y1)], fill=fill_color, outline=outline_color, width=outline_width, radius=radius
    )
    d.text((element["x"] + padding, element["y"] + padding), value, fill=text_color, font=font, anchor="lt")


@element(
    "multiline",
    doc="Splits `value` on `delimiter` and draws one line per part, `offset_y` apart. Without "
    "`start_y` it flows below the previous text/line.",
    fields=[
        num("x", required=True),
        any_("value", required=True),
        string("delimiter", required=True, doc='Separator between lines, e.g. `"|"`'),
        num("offset_y", required=True, doc="Line pitch in px"),
        num("start_y", doc="Omit to place at the flow cursor"),
        num("y_padding", 10, doc="Gap below the flow cursor when `start_y` is omitted"),
        num("size", 20),
        string("font"),
        color("color", "black"),
        string("anchor", "lm"),
        num("stroke_width", 0),
        color("stroke_fill", "white"),
    ],
)
def multiline(state: RenderState, element: dict) -> None:
    require(element, ["x", "value", "delimiter", "offset_y"], "multiline")
    d = mono_draw(state.img)
    size = element.get("size", 20)
    font = state.context.font(element.get("font"), size)
    color = element.get("color", "black")
    anchor = element.get("anchor", "lm")
    stroke_width = element.get("stroke_width", 0)
    stroke_fill = state.context.color(element.get("stroke_fill", "white"))

    lst = str(element["value"]).replace("\n", "").split(element["delimiter"])
    pos = element.get("start_y", state.pos_y + element.get("y_padding", 10))
    for line in lst:
        d.text(
            (element["x"], pos),
            str(line),
            fill=state.context.color(color),
            font=font,
            anchor=anchor,
            stroke_width=stroke_width,
            stroke_fill=stroke_fill,
        )
        pos += element["offset_y"]
    state.pos_y = pos


@element(
    "new_multiline",
    doc="Multi-line text (`\\n`-separated) that can shrink its font to fit a `width` and/or `height`.",
    fields=[
        num("x", required=True),
        num("y", required=True),
        any_("value", required=True),
        num("size", 20, doc="Starting font size"),
        num("spacing", doc="Line spacing in px; defaults to `size`"),
        string("font"),
        color("color", "black"),
        string("anchor", "la"),
        enum("align", ("left", "center", "right"), "left"),
        num("stroke_width", 0),
        color("stroke_fill"),
        enum("fit", ("width", "height"), alt="boolean", doc="Which dimension to shrink to; `true` = both"),
        boolean("fit_width", doc="Shrink until the text is no wider than `width`"),
        boolean("fit_height", doc="Shrink until the text is no taller than `height`"),
        num("width", doc="Target width", required_when=[("fit_width", [True]), ("fit", ["width", True])]),
        num("height", doc="Target height", required_when=[("fit_height", [True]), ("fit", ["height", True])]),
    ],
)
def new_multiline(state: RenderState, element: dict) -> None:
    """Multiline text that can auto-shrink to fit a given width and/or height."""
    require(element, ["x", "y", "value"], "new_multiline")
    value = str(element["value"])
    d = mono_draw(state.img)
    color = element.get("color", "black")
    anchor = element.get("anchor", "la")
    size = element.get("size", 20)
    spacing = element.get("spacing", size)
    align = element.get("align", "left")
    stroke_width = element.get("stroke_width", 0)
    stroke_fill = state.context.color(element.get("stroke_fill", None))

    def rendered_size(font, spacing):
        x1, y1, x2, y2 = d.textbbox(
            (element["x"], element["y"]),
            value,
            font=font,
            anchor=anchor,
            spacing=spacing,
            align=align,
            stroke_width=stroke_width,
        )
        return x2 - x1, y2 - y1

    font = state.context.font(element.get("font"), size)
    if element.get("fit_width") or element.get("fit") in ["width", True]:
        try:
            width = float(element["width"])
        except KeyError as e:
            raise RenderError(
                f"Missing required argument {e} in 'new_multiline'; it is mandatory when text is fit to width"
            ) from e
        except ValueError as e:
            raise RenderError(f"Invalid width value {e}") from e
        rendered_width, _ = rendered_size(font, spacing)
        if rendered_width > width:
            size = size * (width / rendered_width)
            spacing = spacing * (width / rendered_width)
            font = state.context.font(element.get("font"), size)
    if element.get("fit_height") or element.get("fit") in ["height", True]:
        try:
            height = float(element["height"])
        except KeyError as e:
            raise RenderError(
                f"Missing required argument {e} in 'new_multiline'; it is mandatory when text is fit to height"
            ) from e
        except ValueError as e:
            raise RenderError(f"Invalid height value {e}") from e
        _, rendered_height = rendered_size(font, spacing)
        if rendered_height > height:
            size = size * (height / rendered_height)
            spacing = spacing * (height / rendered_height)
            font = state.context.font(element.get("font"), size)

    d.multiline_text(
        (element["x"], element["y"]),
        value,
        fill=state.context.color(color),
        font=font,
        anchor=anchor,
        spacing=spacing,
        align=align,
        stroke_width=stroke_width,
        stroke_fill=stroke_fill,
    )


@element(
    "table",
    doc="Simple grid: the first row is the header unless `header` is false.",
    fields=[
        num("x", required=True),
        num("y", required=True),
        array("columns", "number", required=True, doc="Column widths in px"),
        array("rows", "array", required=True, doc="Rows of cell values (each converted with `str()`)"),
        num("font_size", 14),
        string("font"),
        num("row_height", doc="Defaults to `font_size + 8`"),
        num("padding", 4, doc="Horizontal cell padding"),
        color("header_fill", "black"),
        color("header_color", "white"),
        color("cell_color", "black"),
        color("cell_fill", doc="Body cell background"),
        color("border_color", "black"),
        num("border_width", 1),
        enum("align", ("left", "center", "right"), "left"),
        boolean("header", True, doc="Treat the first row as a header"),
    ],
)
def table(state: RenderState, element: dict) -> None:
    require(element, ["x", "y", "columns", "rows"], "table")
    d = mono_draw(state.img)
    font_size = element.get("font_size", 14)
    font = state.context.font(element.get("font"), font_size)
    table_x, table_y = element["x"], element["y"]
    col_widths = element["columns"]
    rows = element["rows"]
    row_height = element.get("row_height", font_size + 8)
    padding = element.get("padding", 4)
    header_fill = state.context.color(element.get("header_fill", "black"))
    header_color = state.context.color(element.get("header_color", "white"))
    cell_color = state.context.color(element.get("cell_color", "black"))
    border_color = state.context.color(element.get("border_color", "black"))
    border_width = element.get("border_width", 1)
    align = element.get("align", "left")

    cur_y = table_y
    for row_idx, row in enumerate(rows):
        is_header = (row_idx == 0) and element.get("header", True)
        fill_bg = header_fill if is_header else state.context.color(element.get("cell_fill", None))
        text_color = header_color if is_header else cell_color
        cur_x = table_x
        for cell, col_w in zip(row, col_widths, strict=False):
            d.rectangle(
                [(cur_x, cur_y), (cur_x + col_w, cur_y + row_height)],
                fill=fill_bg,
                outline=border_color,
                width=border_width,
            )
            if align == "center":
                tx, ta = cur_x + col_w // 2, "mm"
            elif align == "right":
                tx, ta = cur_x + col_w - padding, "rm"
            else:
                tx, ta = cur_x + padding, "lm"
            d.text((tx, cur_y + row_height // 2), str(cell), fill=text_color, font=font, anchor=ta)
            cur_x += col_w
        cur_y += row_height
    state.pos_y = cur_y


@element(
    "rich_text",
    doc="One line of mixed spans (text and icons) with per-span size/colour/font, laid out left to "
    "right and vertically centred on `y`.",
    fields=[
        num("x", required=True),
        num("y", required=True, doc="Vertical centre of the line"),
        array(
            "spans",
            "object",
            required=True,
            doc="Each span is text (`text`) or an icon (`icon`)",
            fields=[
                any_("text", doc="Text for a text span"),
                string("icon", doc="`mdi:name` / `fa:name` for an icon span"),
                num("size", doc="Defaults to the element `size`"),
                color("color", doc="Defaults to the element `color`"),
                string("font", doc="Defaults to the element `font`"),
            ],
        ),
        num("spacing", 0, doc="Gap between spans"),
        num("size", 20),
        color("color", "black"),
        string("font"),
        enum("align", ("left", "center", "right"), "left", doc="Position of the whole line relative to `x`"),
    ],
)
def rich_text(state: RenderState, element: dict) -> None:
    """Draw inline spans (text and/or icons) left-to-right on one baseline.

    Each span is ``{"text": ...}`` or ``{"icon": "mdi:..."}`` (also accepts
    ``"fa:..."``/``"fas:..."``/``"far:..."``/``"fab:..."`` for Font Awesome) with
    optional per-span ``size``/``color``/``font``. ``element["y"]`` is the
    vertical center (spans are middle-anchored); ``align`` (left/center/right)
    positions the run relative to ``element["x"]``.
    """
    require(element, ["x", "y", "spans"], "rich_text")

    spacing = element.get("spacing", 0)
    default_size = element.get("size", 20)
    default_color = element.get("color", "black")
    default_font = element.get("font")

    measured = []  # (text, font, color)
    for sp in element["spans"]:
        size = sp.get("size", default_size)
        color = sp.get("color", default_color)
        if "icon" in sp:
            text, font = resolve_icon(sp["icon"], state.context.icons_dir, size)
        else:
            text = str(sp.get("text", ""))
            font = state.context.font(sp.get("font", default_font), size)
        measured.append((text, font, color, font.getlength(text)))

    total = sum(w for *_, w in measured) + spacing * max(0, len(measured) - 1)
    align = element.get("align", "left")
    if align == "center":
        cursor = element["x"] - total / 2
    elif align == "right":
        cursor = element["x"] - total
    else:
        cursor = element["x"]

    d = mono_draw(state.img)
    for text, font, color, w in measured:
        d.text((cursor, element["y"]), text, font=font, fill=state.context.color(color), anchor="lm")
        cursor += w + spacing


@element(
    "text_fit",
    doc="Fits text into a fixed `width` x `height` box: shrink the font, truncate with an ellipsis, "
    "or both, with word-wrap up to `max_lines`.",
    fields=[
        num("x", required=True),
        num("y", required=True),
        num("width", required=True),
        num("height", required=True),
        any_("value", required=True),
        enum("fit", ("shrink", "ellipsis", "shrink_ellipsis"), "shrink"),
        num("size", 20, doc="Starting font size"),
        num("min_size", 8, doc="Smallest size `shrink` may reach"),
        num("max_lines", 1),
        num("line_spacing", 2),
        string("ellipsis", "\u2026"),
        color("color", "black"),
        enum("align", ("left", "center", "right"), "left"),
        enum("valign", ("top", "middle", "bottom"), "top"),
        num("padding", 0),
        string("font"),
        color("background", doc="Box fill"),
        color("outline", doc="Box outline"),
        num("width_outline", 1),
        num("radius", 0, doc="Box corner radius"),
    ],
)
def text_fit(state: RenderState, element: dict) -> None:
    """Fit text into a fixed ``width × height`` box.

    ``fit`` controls overflow handling:
      * ``"shrink"`` — reduce font size (down to ``min_size``) until it fits.
      * ``"ellipsis"`` — keep size, truncate with ``…``.
      * ``"shrink_ellipsis"`` — shrink to ``min_size`` first, then ellipsize.

    Supports ``max_lines`` wrapping plus horizontal (``align``) and vertical
    (``valign``) placement, with an optional ``background``/``outline`` chip.
    """
    require(element, ["x", "y", "width", "height", "value"], "text_fit")
    x, y = element["x"], element["y"]
    box_w, box_h = element["width"], element["height"]
    value = str(element["value"])
    fit = element.get("fit", "shrink")
    if fit not in ("shrink", "ellipsis", "shrink_ellipsis"):
        raise RenderError(f"text_fit: 'fit' must be shrink/ellipsis/shrink_ellipsis, got {fit!r}")
    start_size = element.get("size", 20)
    min_size = element.get("min_size", 8)
    max_lines = max(1, int(element.get("max_lines", 1)))
    line_spacing = element.get("line_spacing", 2)
    ellipsis = element.get("ellipsis", "…")
    color = element.get("color", "black")
    align = element.get("align", "left")
    valign = element.get("valign", "top")
    padding = element.get("padding", 0)

    inner_w = box_w - 2 * padding
    inner_h = box_h - 2 * padding
    font_name = element.get("font")

    def layout(size):
        font = state.context.font(font_name, size)
        ascent, descent = font.getmetrics()
        line_h = ascent + descent + line_spacing
        lines, fits = fit_lines(value, font, inner_w, max_lines, ellipsis)
        return font, lines, fits, line_h

    if fit in ("shrink", "shrink_ellipsis"):
        chosen = None
        for size in range(int(start_size), int(min_size) - 1, -1):
            font, lines, fits, line_h = layout(size)
            if fits and line_h * len(lines) <= inner_h:
                chosen = (font, lines, line_h)
                break
        if chosen is None:
            font, lines, _, line_h = layout(min_size)
            if fit == "shrink_ellipsis":
                max_rows = max(1, inner_h // line_h)
                if len(lines) > max_rows:
                    lines = lines[:max_rows]
                    lines[-1] = _ellipsize_line(font, lines[-1], inner_w, ellipsis)
            chosen = (font, lines, line_h)
        font, lines, line_h = chosen
    else:  # ellipsis only
        font, lines, _, line_h = layout(start_size)
        max_rows = max(1, inner_h // line_h)
        if len(lines) > max_rows:
            lines = lines[:max_rows]
            lines[-1] = _ellipsize_line(font, lines[-1], inner_w, ellipsis)

    d = mono_draw(state.img)

    if "background" in element or "outline" in element:
        d.rounded_rectangle(
            [(x, y), (x + box_w, y + box_h)],
            fill=state.context.color(element.get("background")),
            outline=state.context.color(element.get("outline")),
            width=element.get("width_outline", 1),
            radius=element.get("radius", 0),
        )

    total_h = line_h * len(lines)
    if valign == "middle":
        oy = y + padding + (inner_h - total_h) // 2
    elif valign == "bottom":
        oy = y + box_h - padding - total_h
    else:
        oy = y + padding

    for i, ln in enumerate(lines):
        ly = oy + i * line_h
        if align == "center":
            lx, anchor = x + box_w // 2, "ma"
        elif align == "right":
            lx, anchor = x + box_w - padding, "ra"
        else:
            lx, anchor = x + padding, "la"
        d.text((lx, ly), ln, fill=state.context.color(color), font=font, anchor=anchor)
