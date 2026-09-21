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
* ``image_fetcher`` — optional ``url -> bytes`` used by ``dlimg`` for
  ``http(s)`` URLs instead of the built-in ``requests`` download (e.g. to reuse
  a host session or add auth). The size cap and TTL cache apply either way.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

import requests
from PIL import ImageFont

from .colors import DEFAULT_PALETTE, get_palette, resolve_color
from .exceptions import RenderError

FontResolver = Callable[[str], str | None]
HistoryProvider = Callable[[Sequence[str], Any, Any], dict[str, Any]]
ImageFetcher = Callable[[str], bytes]

_IMAGE_CACHE_MAX_ENTRIES = 32
_DOWNLOAD_CHUNK = 64 * 1024

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
    # `dlimg` http(s) downloads: hard cap on the response size (a bad URL must
    # not be able to exhaust memory), an optional host-supplied fetcher, and an
    # optional TTL cache so a label re-rendered every few minutes does not
    # re-download an unchanged logo. 0 disables the cache — the default,
    # because a camera snapshot URL must not be served stale.
    max_image_bytes: int = 20 * 1024 * 1024
    image_fetcher: ImageFetcher | None = None
    image_cache_ttl: float = 0.0
    # Device color palette. Accepts a list of RGBA tuples, or a name/count
    # string ("2"/"bw", "4", "7"/"acep", ...). See colors.PALETTES.
    palette: Any = field(default_factory=lambda: DEFAULT_PALETTE)
    # Pillow text layout engine (``ImageFont.Layout.BASIC`` / ``RAQM``). ``None``
    # keeps Pillow's default: RAQM (HarfBuzz shaping, kerning, RTL/complex
    # scripts) when libraqm is available, else BASIC. Linux wheels ship raqm,
    # Windows wheels do not, so text advances differ between them; pin BASIC
    # for pixel-identical output across platforms (the golden tests do this).
    layout_engine: int | None = None
    # Cache keyed by (resolved path, size, layout engine) so repeated text
    # elements are cheap and a later change of `layout_engine` is honoured.
    _font_cache: dict[tuple[str, int, int | None], ImageFont.FreeTypeFont] = field(default_factory=dict, repr=False)
    # url -> (monotonic fetch time, bytes); bounded, oldest entry evicted.
    _image_cache: dict[str, tuple[float, bytes]] = field(default_factory=dict, repr=False)

    def __post_init__(self):
        # Allow palette to be given as a friendly name ("7", "bw", ...).
        self.palette = get_palette(self.palette)

    def color(self, value):
        """Resolve a requested color to its **true** RGBA (or ``None``).

        Handlers always draw in full color; palette mapping (dithered or flat
        nearest, per the ``dither`` flag) happens once for the whole image at the
        end of :func:`~imagespec.core.render`.
        """
        return resolve_color(value)

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
        key = (path, int(size), self.layout_engine)
        cached = self._font_cache.get(key)
        if cached is None:
            cached = ImageFont.truetype(path, int(size), layout_engine=self.layout_engine)
            self._font_cache[key] = cached
        return cached

    def fetch_image(self, url: str, *, timeout: float = 30) -> bytes:
        """Bytes of an ``http(s)`` image for ``dlimg``: cached per ``image_cache_ttl``.

        Uses ``image_fetcher`` when set, else a streamed ``requests`` download
        that aborts once ``max_image_bytes`` is exceeded. A custom fetcher
        returns the whole body, so the cap is only checked afterwards — a
        fetcher that must bound memory has to stream and enforce it itself.
        Network errors propagate as ``requests.RequestException`` for the
        caller to wrap.
        """
        now = time.monotonic()
        if self.image_cache_ttl > 0:
            hit = self._image_cache.get(url)
            if hit is not None and now - hit[0] < self.image_cache_ttl:
                return hit[1]
        if self.image_fetcher is not None:
            data = self.image_fetcher(url)
            if len(data) > self.max_image_bytes:
                raise RenderError(f"image at {url} is {len(data)} bytes, over max_image_bytes={self.max_image_bytes}")
        else:
            data = self._download(url, timeout)
        if self.image_cache_ttl > 0:
            # Refreshing an existing (expired) url reuses its slot; only a new
            # url needs room, taking it from the oldest entry.
            if url not in self._image_cache and len(self._image_cache) >= _IMAGE_CACHE_MAX_ENTRIES:
                oldest = min(self._image_cache, key=lambda k: self._image_cache[k][0])
                del self._image_cache[oldest]
            self._image_cache[url] = (now, data)
        return data

    def _download(self, url: str, timeout: float) -> bytes:
        limit = self.max_image_bytes
        with requests.get(url, timeout=timeout, stream=True) as response:
            response.raise_for_status()
            declared = response.headers.get("Content-Length")
            if declared and declared.isdigit() and int(declared) > limit:
                raise RenderError(f"image at {url} is {declared} bytes, over max_image_bytes={limit}")
            buf = bytearray()
            for chunk in response.iter_content(_DOWNLOAD_CHUNK):
                buf += chunk
                if len(buf) > limit:
                    raise RenderError(f"image at {url} exceeds max_image_bytes={limit}; download aborted")
        return bytes(buf)

    def history(self, entity_ids: Sequence[str], start, end) -> dict[str, Any]:
        """Fetch historical states for the ``plot`` element."""
        if self.history_provider is None:
            raise RenderError(
                "This payload uses 'plot', which needs historical data, but the "
                "RenderContext has no history_provider configured."
            )
        return self.history_provider(entity_ids, start, end)
