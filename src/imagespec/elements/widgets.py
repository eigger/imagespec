"""Small composite widgets: legend, star_rating, battery.

These fill gaps the primitive set didn't cover well:

* ``legend`` — color-swatch ↔ label rows, the companion ``pie``/``plot`` lack
  (``pie`` parses segment labels but only a legend actually draws them).
* ``star_rating`` — filled/half/empty stars for review or rating labels.
* ``battery`` — a vector battery gauge (proportional fill) for ESL status.

All are built from existing primitives/icons — no new dependencies.
"""

from __future__ import annotations

from PIL import ImageDraw

from ..exceptions import RenderError
from ..registry import element
from ..state import RenderState
from ..utils import require


def _parse_legend_items(items):
    """Normalize ``items`` to a list of ``(label, color, icon)`` triples.

    Accepts a list of dicts (``{"label": ..., "color": ..., "icon": ...}``) or a
    ``"label,color;label,color"`` string (matching the ``pie`` value syntax).
    """
    out = []
    if isinstance(items, str):
        for part in items.split(";"):
            if not part.strip():
                continue
            bits = [b.strip() for b in part.split(",")]
            if len(bits) < 2:
                raise RenderError(f"legend: bad item {part!r} — expected 'label,color'")
            out.append((bits[0], bits[1], None))
        return out
    for it in items:
        out.append((str(it.get("label", "")), it.get("color", "black"), it.get("icon")))
    return out


@element("legend")
def legend(state: RenderState, element: dict) -> None:
    """Draw a color-swatch legend (vertical or horizontal)."""
    require(element, ["x", "y", "items"], "legend")
    items = _parse_legend_items(element["items"])
    x, y = element["x"], element["y"]
    size = element.get("size", 12)
    swatch = element.get("swatch_size", size)
    gap = element.get("gap", 6)
    spacing = element.get("spacing", 4)
    orientation = element.get("orientation", "vertical")
    shape = element.get("shape", "square")
    text_color = state.context.color(element.get("color", "black"))
    font = state.context.font(element.get("font"), size)

    d = ImageDraw.Draw(state.img)
    d.fontmode = "1"
    line_h = max(swatch, size)
    cursor_x, cursor_y = x, y
    for label, color, icon in items:
        cy = cursor_y + line_h / 2
        col = state.context.color(color)
        if icon is not None:
            from .media import resolve_icon

            glyph, icon_font = resolve_icon(icon, state.context.icons_dir, swatch)
            d.text((cursor_x, cy), glyph, font=icon_font, fill=col, anchor="lm")
        elif shape == "circle":
            d.ellipse([(cursor_x, cy - swatch / 2), (cursor_x + swatch, cy + swatch / 2)], fill=col)
        elif shape == "line":
            d.line([(cursor_x, cy), (cursor_x + swatch, cy)], fill=col, width=max(2, swatch // 3))
        else:  # square
            d.rectangle([(cursor_x, cy - swatch / 2), (cursor_x + swatch, cy + swatch / 2)], fill=col)
        label_x = cursor_x + swatch + gap
        d.text((label_x, cy), label, font=font, fill=text_color, anchor="lm")
        if orientation == "horizontal":
            cursor_x = label_x + font.getlength(label) + spacing + size
        else:
            cursor_y += line_h + spacing


@element("star_rating")
def star_rating(state: RenderState, element: dict) -> None:
    """Render ``rating`` of ``max`` stars (full / optional half / empty)."""
    require(element, ["x", "y", "rating"], "star_rating")
    from .media import mdi_char, mdi_font

    rating = float(element["rating"])
    max_stars = int(element.get("max", 5))
    size = element.get("size", 16)
    spacing = element.get("spacing", 2)
    use_half = element.get("half", True)
    fill = state.context.color(element.get("color", "orange"))
    empty_fill = state.context.color(element.get("empty_color", element.get("color", "orange")))

    font = mdi_font(state.context.icons_dir, size)
    d = ImageDraw.Draw(state.img)
    d.fontmode = "1"
    x, y = element["x"], element["y"]
    for i in range(max_stars):
        threshold = i + 1
        if rating >= threshold:
            name, col = "mdi:star", fill
        elif use_half and rating >= threshold - 0.5:
            name, col = "mdi:star-half-full", fill
        else:
            name, col = "mdi:star-outline", empty_fill
        glyph = mdi_char(name, state.context.icons_dir)
        d.text((x, y), glyph, font=font, fill=col, anchor="la")
        x += size + spacing


@element("battery")
def battery(state: RenderState, element: dict) -> None:
    """Vector battery gauge with a proportional fill and terminal nub."""
    require(element, ["x", "y", "width", "height", "level"], "battery")
    x, y = element["x"], element["y"]
    w, h = element["width"], element["height"]
    level = max(0.0, min(100.0, float(element["level"])))
    outline = state.context.color(element.get("outline", "black"))
    bg = state.context.color(element.get("background", "white"))
    fill = state.context.color(element.get("fill", "black"))
    border = element.get("width_outline", 1)
    radius = element.get("radius", 2)
    pad = element.get("padding", 2)

    low_threshold = element.get("low_threshold", 20)
    if "low_color" in element and level <= low_threshold:
        fill = state.context.color(element["low_color"])

    nub_w = element.get("nub_width", max(2, w // 12))
    nub_h = element.get("nub_height", max(2, h // 2))
    body_w = w - nub_w

    d = ImageDraw.Draw(state.img)
    d.rounded_rectangle([(x, y), (x + body_w, y + h)], fill=bg, outline=outline, width=border, radius=radius)
    d.rectangle([(x + body_w, y + (h - nub_h) // 2), (x + w, y + (h + nub_h) // 2)], fill=outline)

    inner_w = body_w - 2 * pad
    fill_w = inner_w * (level / 100)
    if fill_w > 0:
        d.rounded_rectangle([(x + pad, y + pad), (x + pad + fill_w, y + h - pad)], fill=fill, radius=max(0, radius - 1))

    if element.get("show_percentage", False):
        d.fontmode = "1"
        font = state.context.font(element.get("font"), element.get("size", max(6, h - 2 * pad - 2)))
        text = f"{int(round(level))}%"
        tb = d.textbbox((0, 0), text, font=font)
        tx = x + (body_w - (tb[2] - tb[0])) / 2
        ty = y + (h - (tb[3] - tb[1])) / 2
        # use the background color over the filled portion for contrast
        d.text((tx, ty), text, font=font, fill=state.context.color(element.get("text_color", "white")), anchor="lt")
