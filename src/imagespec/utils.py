"""Small shared helpers used by element handlers."""

from __future__ import annotations

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
    value = element.get("visible", True)
    if isinstance(value, str):
        s = value.strip().lower()
        if s in _FALSY_STRINGS:
            return False
        try:
            return float(s) != 0
        except ValueError:
            return True
    return bool(value)


def int_xy(x, y) -> tuple[int, int]:
    """Round a coordinate pair to ints for PIL ``paste``/``alpha_composite``.

    Drawing calls accept floats but paste offsets do not, so elements that
    composite a sub-image (rotated text, ``group``, ``dlimg``, codes) would
    otherwise fail on ``x: 5.5`` while the plain drawing path accepts it.
    """
    return int(round(float(x))), int(round(float(y)))


def get_wrapped_text(text: str, font, line_length: int) -> str:
    """Word-wrap ``text`` so each line fits within ``line_length`` pixels."""
    lines = [""]
    for word in text.split():
        line = f"{lines[-1]} {word}".strip()
        if font.getlength(line) <= line_length:
            lines[-1] = line
        else:
            lines.append(word)
    return "\n".join(lines)


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


def min_max(data):
    if not data:
        raise RenderError("data error, something is not in range of the recorder")
    mi, ma = data[0], data[0]
    for d in data[1:]:
        mi = min(mi, d)
        ma = max(ma, d)
    return mi, ma
