"""Render context: the seam where framework-specific behaviour is injected.

The core renderer must not import Home Assistant. Anything it needs from the
host application is provided through :class:`RenderContext`:

* ``font_resolver`` — given a font name (as written in a payload), return an
  absolute path to a ``.ttf``/``.otf`` file, or ``None`` to fall back to the
  fonts bundled with this package. This is where an integration plugs in its
  ``hass.config.path("www/fonts")`` lookup.
* ``history_provider`` — given entity ids and a ``[start, end]`` window, return
  historical states for the ``plot`` element. Only required if a payload uses
  ``plot``; otherwise it can be left ``None``.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from PIL import ImageFont

from .colors import DEFAULT_PALETTE, get_palette, quantize_color
from .exceptions import RenderError

FontResolver = Callable[[str], str | None]
HistoryProvider = Callable[[Sequence[str], Any, Any], dict[str, Any]]

_PKG_DIR = os.path.dirname(__file__)
BUNDLED_FONTS_DIR = os.path.join(_PKG_DIR, "fonts")
BUNDLED_ICONS_DIR = os.path.join(_PKG_DIR, "icons")


def _bundled_font_path(name: str) -> str | None:
    path = os.path.join(BUNDLED_FONTS_DIR, os.path.basename(name))
    return path if os.path.exists(path) else None


@dataclass
class RenderContext:
    """Host-supplied capabilities and defaults for a render call."""

    font_resolver: FontResolver | None = None
    history_provider: HistoryProvider | None = None
    default_font: str = "NotoSansKR-Regular.ttf"
    icons_dir: str = BUNDLED_ICONS_DIR
    # Security: whether `dlimg` may open local/relative filesystem paths.
    # Off by default — only http(s)/data URLs are allowed unless opted in.
    allow_local_images: bool = False
    # Device color palette. Accepts a list of RGBA tuples, or a name/count
    # string ("2"/"bw", "4", "7"/"acep", ...). See colors.PALETTES.
    palette: Any = field(default_factory=lambda: DEFAULT_PALETTE)
    # Cache keyed by (resolved path, size) so repeated text elements are cheap.
    _font_cache: dict[tuple[str, int], ImageFont.FreeTypeFont] = field(default_factory=dict, repr=False)

    def __post_init__(self):
        # Allow palette to be given as a friendly name ("7", "bw", ...).
        self.palette = get_palette(self.palette)

    def color(self, value):
        """Quantize a requested color to this device's palette (or ``None``)."""
        return quantize_color(value, self.palette)

    def resolve_font_path(self, name: str | None) -> str:
        """Resolve a payload font name to an absolute file path.

        Order: injected resolver → bundled font of the same basename →
        bundled default font.
        """
        name = name or self.default_font
        if self.font_resolver is not None:
            p = self.font_resolver(name)
            if p and os.path.exists(p):
                return p
        p = _bundled_font_path(name)
        if p:
            return p
        p = _bundled_font_path(self.default_font)
        if p:
            return p
        raise RenderError(
            f"Font '{name}' could not be resolved and no bundled default ('{self.default_font}') is available."
        )

    def font(self, name: str | None, size) -> ImageFont.FreeTypeFont:
        """Return a (cached) truetype font for ``name`` at ``size``."""
        path = self.resolve_font_path(name)
        key = (path, int(size))
        cached = self._font_cache.get(key)
        if cached is None:
            cached = ImageFont.truetype(path, int(size))
            self._font_cache[key] = cached
        return cached

    def history(self, entity_ids: Sequence[str], start, end) -> dict[str, Any]:
        """Fetch historical states for the ``plot`` element."""
        if self.history_provider is None:
            raise RenderError(
                "This payload uses 'plot', which needs historical data, but the "
                "RenderContext has no history_provider configured."
            )
        return self.history_provider(entity_ids, start, end)
