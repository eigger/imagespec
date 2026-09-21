"""Small shared helpers used by element handlers."""

from __future__ import annotations

from collections.abc import Iterable

from PIL import Image, ImageDraw

from .exceptions import RenderError
from .spec import Field


def require(element: dict, keys, func_name: str) -> None:
    """Raise :class:`RenderError` if any required key is missing from ``element``."""
    missing = [k for k in keys if k not in element]
    if missing:
        raise RenderError(f"Missing required argument(s) '{', '.join(missing)}' in '{func_name}'")


_FALSY_STRINGS = frozenset({"false", "0", "no", "off", "none", ""})


def should_show(element: dict) -> bool:
    """``visible`` flag, tolerant of the string forms HA templates produce.

    ``"False"``/``"off"``/``"no"``/``"none"``/``""`` and any numeric string
    equal to zero (``"0"``, ``"0.0"``) and ``None`` hide the element; any other
    value (or the key being absent) shows it.
    """
    return to_bool(element.get("visible", True))


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


_TRUTHY_STRINGS = frozenset({"true", "yes", "on"})


def to_dither(value):
    """Coerce a ``dither`` value: bool-like strings become bools, method names pass through.

    ``"False"``/``"0"``/``"off"`` → ``False``, ``"True"``/``"1"``/``"on"`` →
    ``True``; anything else (``"bayer8"``, ``True``, ``1``, ``None``) is returned
    as-is for :func:`imagespec.dither.resolve_dither_method`.
    """
    if not isinstance(value, str):
        return value
    s = value.strip().lower()
    if s in _FALSY_STRINGS:
        return False
    if s in _TRUTHY_STRINGS:
        return True
    try:
        return float(s) != 0
    except ValueError:
        return value


def coerce_element(element: dict, fields: Iterable[Field]) -> dict:
    """Return a copy of ``element`` with template strings turned into numbers/bools.

    Driven by the element's declared ``fields`` (:mod:`imagespec.spec`): number
    and integer keys go through :func:`to_number`, booleans through
    :func:`to_bool`, ``dither`` through :func:`to_dither`, and nested
    ``object``/``array`` fields recurse into their own declarations. Undeclared
    keys and child ``elements`` are left untouched (children are coerced when
    they are dispatched). Raises :class:`ValueError`
    for a non-numeric string; the render loop wraps it with the element
    index/type.

    An explicit ``None`` is **dropped** (the handler sees the key as omitted)
    unless the field accepts null — colours, ``dither``, ``any`` and fields
    declared ``nullable=True`` — so ``y: null`` or ``bars: null`` from a
    template never reaches arithmetic or ``.get`` inside a handler.
    """
    out = dict(element)
    for f in fields:
        if f.name not in element:
            continue
        value = element[f.name]
        if value is None:
            if not f.accepts_null:
                del out[f.name]
            continue
        if f.kind in ("number", "integer"):
            out[f.name] = to_number(value, f.name)
        elif f.kind == "boolean":
            out[f.name] = to_bool(value)
        elif f.kind == "dither":
            out[f.name] = to_dither(value)
        elif f.kind == "object":
            if isinstance(value, dict):
                out[f.name] = coerce_element(value, f.fields)
        elif f.kind == "array" and isinstance(value, (list, tuple)):
            if f.items in ("number", "integer"):
                out[f.name] = [to_number(v, f.name) for v in value]
            elif f.items == "object":
                out[f.name] = [coerce_element(v, f.fields) if isinstance(v, dict) else v for v in value]
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
