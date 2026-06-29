"""Text elements: text (with optional rotation + background box), multiline,
text_box, new_multiline (fit-to-width/height autosize), table, text_fit.

Merged from both sources: rotation/background box/text_box/table are gicisky;
``new_multiline`` (autosize) is niimbot. ``text_fit`` is new — fit text into a
fixed box by shrinking the font and/or truncating with an ellipsis.
"""

from __future__ import annotations

from PIL import Image, ImageDraw

from ..exceptions import RenderError
from ..registry import element
from ..state import RenderState
from ..utils import get_wrapped_text, require


def _ellipsize_line(font, line: str, max_width: float, ellipsis: str) -> str:
    """Trim ``line`` and append ``ellipsis`` so it fits within ``max_width``."""
    if font.getlength(line + ellipsis) <= max_width:
        return line + ellipsis
    s = line
    while s and font.getlength(s + ellipsis) > max_width:
        s = s[:-1]
    return s + ellipsis


def _wrap_all(text: str, font, max_width: float) -> list[str]:
    """Greedy word-wrap to ``max_width`` (a single over-long word stays one line)."""
    lines: list[str] = []
    cur = ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if cur and font.getlength(trial) > max_width:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def fit_lines(text: str, font, max_width: float, max_lines: int, ellipsis: str):
    """Wrap ``text`` to ``max_width`` within ``max_lines``.

    Returns ``(lines, fits)`` where ``fits`` is False if anything had to be
    truncated (too many lines, or a line wider than ``max_width``).
    """
    all_lines = _wrap_all(text, font, max_width)
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


@element("text")
def text(state: RenderState, element: dict) -> None:
    require(element, ["x", "value"], "text")
    d = ImageDraw.Draw(state.img)
    d.fontmode = "1"
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
        value = get_wrapped_text(str(element["value"]), font, line_length=element["max_width"])
        anchor = None
    else:
        value = str(element["value"])

    if text_rotation != 0:
        # Render onto a temporary transparent image, rotate, then composite.
        dummy = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        tbbox = dummy.textbbox((0, 0), value, font=font, spacing=spacing, stroke_width=stroke_width)
        tw = tbbox[2] - tbbox[0] + stroke_width * 2
        th = tbbox[3] - tbbox[1] + stroke_width * 2
        tmp = Image.new("RGBA", (tw + 4, th + 4), (255, 255, 255, 0))
        tmp_d = ImageDraw.Draw(tmp)
        tmp_d.fontmode = "1"
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
        canvas.paste(tmp, (element["x"], akt_pos_y))
        state.img = Image.alpha_composite(state.img, canvas)
    else:
        if bg_color is not None:
            tbbox = d.textbbox(
                (element["x"], akt_pos_y),
                value,
                font=font,
                anchor=anchor,
                align=align,
                spacing=spacing,
                stroke_width=stroke_width,
            )
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

    textbbox = ImageDraw.Draw(state.img).textbbox(
        (element["x"], akt_pos_y),
        value,
        font=font,
        anchor=anchor,
        align=align,
        spacing=spacing,
        stroke_width=stroke_width,
    )
    state.pos_y = textbbox[3]


@element("text_box")
def text_box(state: RenderState, element: dict) -> None:
    require(element, ["x", "y", "value"], "text_box")
    d = ImageDraw.Draw(state.img)
    d.fontmode = "1"
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


@element("multiline")
def multiline(state: RenderState, element: dict) -> None:
    require(element, ["x", "value", "delimiter"], "multiline")
    d = ImageDraw.Draw(state.img)
    d.fontmode = "1"
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


@element("new_multiline")
def new_multiline(state: RenderState, element: dict) -> None:
    """Multiline text that can auto-shrink to fit a given width and/or height."""
    require(element, ["x", "y", "value"], "new_multiline")
    value = str(element["value"])
    d = ImageDraw.Draw(state.img)
    d.fontmode = "1"
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


@element("table")
def table(state: RenderState, element: dict) -> None:
    require(element, ["x", "y", "columns", "rows"], "table")
    d = ImageDraw.Draw(state.img)
    d.fontmode = "1"
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


@element("rich_text")
def rich_text(state: RenderState, element: dict) -> None:
    """Draw inline spans (text and/or icons) left-to-right on one baseline.

    Each span is ``{"text": ...}`` or ``{"icon": "mdi:..."}`` with optional
    per-span ``size``/``color``/``font``. ``element["y"]`` is the vertical center
    (spans are middle-anchored); ``align`` (left/center/right) positions the run
    relative to ``element["x"]``.
    """
    require(element, ["x", "y", "spans"], "rich_text")
    from .media import mdi_char, mdi_font

    spacing = element.get("spacing", 0)
    default_size = element.get("size", 20)
    default_color = element.get("color", "black")
    default_font = element.get("font")

    measured = []  # (text, font, color)
    for sp in element["spans"]:
        size = sp.get("size", default_size)
        color = sp.get("color", default_color)
        if "icon" in sp:
            text = mdi_char(sp["icon"], state.context.icons_dir)
            font = mdi_font(state.context.icons_dir, size)
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

    d = ImageDraw.Draw(state.img)
    d.fontmode = "1"
    for text, font, color, w in measured:
        d.text((cursor, element["y"]), text, font=font, fill=state.context.color(color), anchor="lm")
        cursor += w + spacing


@element("text_fit")
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
    max_lines = max(1, element.get("max_lines", 1))
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

    d = ImageDraw.Draw(state.img)
    d.fontmode = "1"

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
