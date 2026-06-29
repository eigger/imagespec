"""Color handling for limited-palette displays.

Different devices support different palettes — 2-color (black/white),
4-color (+red/yellow), 7-color (ACeP), etc. The palette is therefore **not**
hardcoded here: it lives on :class:`~imagespec.context.RenderContext` and is
passed in per render. Any requested color (name or ``#RRGGBB``) is *quantized*
to the nearest color the device can actually show.
"""

from __future__ import annotations

import logging

_LOGGER = logging.getLogger(__name__)

# ── Canonical named colors (RGBA) ──────────────────────────────────────────
white = (255, 255, 255, 255)
black = (0, 0, 0, 255)
red = (255, 0, 0, 255)
yellow = (255, 255, 0, 255)
green = (0, 128, 0, 255)
blue = (0, 0, 255, 255)
orange = (255, 165, 0, 255)

NAMED_COLORS = {
    "white": white,
    "w": white,
    "black": black,
    "b": black,
    "red": red,
    "r": red,
    "yellow": yellow,
    "y": yellow,
    "green": green,
    "g": green,
    "blue": blue,
    "orange": orange,
    "o": orange,
}

# ── Device palettes (ordered subsets of the canonical colors) ──────────────
PALETTE_BW = [black, white]  # 2-color
PALETTE_BWR = [black, white, red]  # 3-color (BWR)
PALETTE_BWY = [black, white, yellow]  # 3-color (BWY)
PALETTE_4 = [black, white, red, yellow]  # 4-color
PALETTE_7 = [black, white, red, green, blue, yellow, orange]  # 7-color (ACeP)

# Optional shorthand aliases — never required; you can always pass an explicit
# list of colors (see get_palette).
PALETTES = {
    "2": PALETTE_BW,
    "bw": PALETTE_BW,
    "mono": PALETTE_BW,
    "3": PALETTE_BWR,
    "bwr": PALETTE_BWR,
    "bwy": PALETTE_BWY,
    "4": PALETTE_4,
    "7": PALETTE_7,
    "acep": PALETTE_7,
}

DEFAULT_PALETTE = PALETTE_4


def _normalize_color(c):
    """Resolve one palette entry to an RGBA tuple.

    Accepts a color name ("red"), a HEX string ("#ff0000"), or an
    ``(r, g, b)`` / ``(r, g, b, a)`` tuple/list.
    """
    if isinstance(c, (tuple, list)):
        if len(c) == 3:
            return (int(c[0]), int(c[1]), int(c[2]), 255)
        if len(c) == 4:
            return (int(c[0]), int(c[1]), int(c[2]), int(c[3]))
        raise ValueError(f"Invalid palette color {c!r}: expected 3 or 4 components")
    s = str(c).strip().lower()
    if s in NAMED_COLORS:
        return NAMED_COLORS[s]
    if s.startswith("#"):
        h = s.lstrip("#")
        if len(h) >= 6:
            return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)
    raise ValueError(f"Unknown palette color {c!r} (not a known name or #RRGGBB)")


def get_palette(spec):
    """Resolve a palette specification to a list of RGBA tuples.

    ``spec`` may be:

    * a shorthand name/count string — ``"2"``/``"bw"``, ``"4"``, ``"7"``/``"acep"``, ...
    * a list of colors, each a name (``"red"``), HEX (``"#ff0000"``), or
      ``(r, g, b[, a])`` tuple — e.g. ``["black", "white", "red"]``.
    """
    if isinstance(spec, str):
        key = spec.strip().lower()
        if key not in PALETTES:
            raise ValueError(f"Unknown palette '{spec}'. Use a list of colors, or one of: {sorted(PALETTES)}")
        return PALETTES[key]
    colors = [_normalize_color(c) for c in spec]
    if not colors:
        raise ValueError("palette must contain at least one color")
    return colors


def _requested_rgb(color):
    """Resolve a color name or ``#RRGGBB`` to an RGBA tuple, or ``None``."""
    if color is None:
        return None
    s = str(color).strip().lower()
    if s in NAMED_COLORS:
        return NAMED_COLORS[s]
    if s.startswith("#"):
        try:
            h = s.lstrip("#")
            if len(h) >= 6:
                return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)
        except ValueError:
            pass
        return white
    return white


def nearest_in_palette(rgba, palette):
    """Return the palette color closest to ``rgba`` (Euclidean in RGB)."""
    best = palette[0]
    best_dist = float("inf")
    for c in palette:
        dist = (rgba[0] - c[0]) ** 2 + (rgba[1] - c[1]) ** 2 + (rgba[2] - c[2]) ** 2
        if dist < best_dist:
            best_dist = dist
            best = c
    return best


def quantize_color(color, palette):
    """Map a requested color to the nearest color the device supports.

    Returns ``None`` for a ``None`` input (meaning "no fill").
    """
    rgb = _requested_rgb(color)
    if rgb is None:
        return None
    snapped = nearest_in_palette(rgb, palette)
    if _LOGGER.isEnabledFor(logging.DEBUG) and tuple(rgb) != tuple(snapped):
        _LOGGER.debug("color %s -> %s (palette size %d)", color, snapped, len(palette))
    return snapped


def get_index_color(color):
    """Back-compat shim: quantize against the default 4-color palette.

    Prefer ``RenderContext.color(...)`` inside handlers so the device's actual
    palette is used.
    """
    return quantize_color(color, DEFAULT_PALETTE)
