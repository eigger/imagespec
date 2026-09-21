"""Small shared helpers used by element handlers."""

from __future__ import annotations

from PIL import Image, ImageDraw

from .exceptions import RenderError


def require(element: dict, keys, func_name: str) -> None:
    """Raise :class:`RenderError` if any required key is missing from ``element``."""
    missing = [k for k in keys if k not in element]
    if missing:
        raise RenderError(f"Missing required argument(s) '{', '.join(missing)}' in '{func_name}'")


_FALSY_STRINGS = frozenset({"false", "0", "no", "off", "none", ""})


def should_show(element: dict) -> bool:
    """``visible`` flag, tolerant of the string forms HA templates produce.

    ``"False"``/``"off"``/``"no"``/``"none"``/``""`` and any numeric string
    equal to zero (``"0"``, ``"0.0"``) hide the element; any other value (or the
    key being absent) shows it.
    """
    return to_bool(element.get("visible", True))


# Keys whose values are numbers in every element that uses them. Handlers read
# them straight from the dict, so :func:`coerce_element` turns the string forms
# HA templates produce ("42", "3.5") into real numbers up front, in one place.
# A key that is a string/list/color in *any* element (`value`, `values`, `data`,
# `points`, ...) must stay out of this set.
NUMERIC_KEYS = frozenset(
    {
        # position / extent
        "x", "y", "x_start", "x_end", "y_start", "y_end", "x_offset", "y_offset",
        "x_size", "y_size", "x_repeat", "y_repeat", "xsize", "ysize", "width", "height",
        "radius", "inner_radius", "start_angle", "end_angle", "rotate", "rotation",
        # text
        "size", "font_size", "spacing", "line_spacing", "offset_y", "start_y", "y_padding",
        "max_width", "max_lines", "min_size", "stroke_width", "padding", "background_padding",
        "row_height", "border_width", "width_outline", "width_line", "swatch_size", "gap",
        "legend_size",
        # stack / layout
        "padding_left", "padding_top", "padding_right", "padding_bottom", "padding_x", "padding_y",
        "margin_left", "margin_top", "margin_right", "margin_bottom", "margin_x", "margin_y",
        # values
        "progress", "level", "rating", "min", "max", "min_value", "max_value", "low", "high",
        "low_threshold", "margin", "grow", "dot_radius", "nub_width", "nub_height",
        # codes / media / plot
        "boxsize", "border", "dpi", "module_width", "module_height", "quiet_zone",
        "text_distance", "timeout", "duration", "grid", "tick_every", "tick_width", "ticks",
    }
)  # fmt: skip

# Keys holding a list of numbers (``columns: ["18", "18"]``).
NUMERIC_LIST_KEYS = frozenset({"columns", "dash"})

# Boolean flags; ``"False"``/``"off"``/... from a template must not read as True.
BOOL_KEYS = frozenset(
    {
        "show_percentage", "show_value", "dot_last", "half", "header", "write_text",
        "debug", "pie", "circle", "fit_width", "fit_height",
    }
)  # fmt: skip

# Nested dicts / lists of dicts that carry numeric keys of their own. Child
# ``elements`` are *not* listed: they are coerced when they are dispatched.
_NESTED_KEYS = frozenset({"bars", "ylegend", "yaxis", "xlegend", "layout", "spans", "items", "data"})


def to_number(value, key: str = "value"):
    """Parse a numeric string to ``int`` (if integral) or ``float``.

    Non-string values pass through untouched (``None`` included) so handlers'
    own defaults keep working. Raises :class:`ValueError` naming ``key``.
    """
    if not isinstance(value, str):
        return value
    s = value.strip()
    try:
        return int(s)
    except ValueError:
        pass
    try:
        f = float(s)
    except ValueError:
        raise ValueError(f"'{key}' must be a number, got {value!r}") from None
    return int(f) if f.is_integer() else f


def to_bool(value) -> bool:
    """``bool()`` that also understands ``"false"``/``"off"``/``"0"``/``""`` strings."""
    if isinstance(value, str):
        s = value.strip().lower()
        if s in _FALSY_STRINGS:
            return False
        try:
            return float(s) != 0
        except ValueError:
            return True
    return bool(value)


def coerce_element(element: dict) -> dict:
    """Return a copy of ``element`` with template strings turned into numbers/bools.

    Applies :data:`NUMERIC_KEYS`, :data:`NUMERIC_LIST_KEYS` and :data:`BOOL_KEYS`
    at the top level and inside the nested option dicts/lists handlers read
    (``bars``, ``ylegend``, ``spans``, ...). Raises :class:`ValueError` for a
    non-numeric string; the render loop wraps it with the element index/type.
    """
    out = dict(element)
    for key, value in element.items():
        if key in NUMERIC_KEYS:
            out[key] = to_number(value, key)
        elif key in NUMERIC_LIST_KEYS and isinstance(value, (list, tuple)):
            out[key] = [to_number(v, key) for v in value]
        elif key in BOOL_KEYS:
            out[key] = to_bool(value)
        elif key in _NESTED_KEYS:
            if isinstance(value, dict):
                out[key] = coerce_element(value)
            elif isinstance(value, (list, tuple)):
                out[key] = [coerce_element(v) if isinstance(v, dict) else v for v in value]
    return out


def int_xy(x, y) -> tuple[int, int]:
    """Round a coordinate pair to ints for PIL ``paste``/``alpha_composite``.

    Drawing calls accept floats but paste offsets do not, so elements that
    composite a sub-image (rotated text, ``group``, ``dlimg``, codes) would
    otherwise fail on ``x: 5.5`` while the plain drawing path accepts it.
    """
    return int(round(float(x))), int(round(float(y)))


def mono_draw(img: Image.Image) -> ImageDraw.ImageDraw:
    """``ImageDraw`` for ``img`` with 1-bit text rendering (no antialiasing).

    Every text-drawing handler uses this: antialiased edges would just turn
    into dither noise on a limited-palette panel.
    """
    d = ImageDraw.Draw(img)
    d.fontmode = "1"
    return d


def wrap_words(text: str, font, max_width: float) -> list[str]:
    """Greedy word-wrap to ``max_width`` pixels.

    A single word wider than ``max_width`` stays on its own line (it is never
    split), and the first line is never left empty.
    """
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


def rounded_corners(corner_string: str):
    """Translate a corner spec ("all" or "top_left,bottom_right") to a 4-tuple."""
    if corner_string == "all":
        return True, True, True, True
    corner_map = {"top_left": 0, "top_right": 1, "bottom_right": 2, "bottom_left": 3}
    result = [False] * 4
    for corner in corner_string.split(","):
        corner = corner.strip()
        if corner in corner_map:
            result[corner_map[corner]] = True
    return tuple(result)


def is_decimal(string: str) -> bool:
    if not string:
        return False
    if string.startswith("-"):
        string = string[1:]
    return len(string.split(".")) <= 2 and string.replace(".", "").isdecimal()
