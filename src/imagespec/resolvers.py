"""Optional font resolvers for :class:`~imagespec.context.RenderContext`.

These are convenience helpers — the core works fine with ``font_resolver=None``
(bundled fonts only) or any callable you write yourself.

``caching_resolver`` addresses the "do I bundle every font or require the
internet?" trade-off: fonts are fetched from the web **once**, cached to disk,
and reused offline thereafter. Bundle only the essentials; download the rest on
first use.
"""

from __future__ import annotations

import io
import logging
import os
import tempfile

import requests
from PIL import ImageFont

from .context import FontResolver

_LOGGER = logging.getLogger(__name__)

MAX_FONT_BYTES = 50 * 1024 * 1024


def _is_font(data: bytes) -> bool:
    try:
        ImageFont.truetype(io.BytesIO(data), 10)
    except (OSError, ValueError):
        return False
    return True


def chain_resolvers(*resolvers: FontResolver | None) -> FontResolver:
    """Combine resolvers; the first to return a path wins.

    Example: prefer a host directory, then fall back to downloading::

        chain_resolvers(www_fonts_resolver, caching_resolver(cache, sources))
    """

    def resolver(name: str) -> str | None:
        for r in resolvers:
            if r is None:
                continue
            path = r(name)
            if path and os.path.exists(path):
                return path
        return None

    return resolver


def directory_resolver(directory: str) -> FontResolver:
    """Resolve a font name to ``<directory>/<basename>`` if it exists."""

    def resolver(name: str) -> str | None:
        path = os.path.join(directory, os.path.basename(name))
        return path if os.path.exists(path) else None

    return resolver


def caching_resolver(
    cache_dir: str,
    sources: dict[str, str] | None = None,
    *,
    session: requests.Session | None = None,
    timeout: float = 30,
    max_bytes: int = MAX_FONT_BYTES,
) -> FontResolver:
    """Download fonts named in ``sources`` on first use, cache them, reuse offline.

    Parameters
    ----------
    cache_dir:
        Directory to store downloaded fonts (created if missing).
    sources:
        Mapping of font name (or basename) → download URL. A payload font name
        not present here returns ``None`` (so bundled fonts are used instead).
    session, timeout:
        Optional ``requests`` session and per-request timeout.
    max_bytes:
        Largest download accepted. A response that is larger, or is not a
        loadable font (e.g. an HTML error page), is logged and not cached —
        the resolver returns ``None`` so the bundled font is used.
    """
    cache_dir = os.path.expanduser(cache_dir)
    os.makedirs(cache_dir, exist_ok=True)
    sources = sources or {}
    http = session or requests

    def resolver(name: str) -> str | None:
        base = os.path.basename(name)
        cached = os.path.join(cache_dir, base)
        if os.path.exists(cached):
            return cached
        url = sources.get(name) or sources.get(base)
        if not url:
            return None
        resp = http.get(url, timeout=timeout)
        resp.raise_for_status()
        data = resp.content
        if len(data) > max_bytes:
            _LOGGER.warning("Font %r from %s is %d bytes (limit %d) - not cached", name, url, len(data), max_bytes)
            return None
        if not _is_font(data):
            # e.g. a captive portal's HTML answered 200: caching it would break every later render
            _LOGGER.warning("Download for font %r from %s is not a usable font file - not cached", name, url)
            return None
        fd, tmp = tempfile.mkstemp(prefix=base + ".", suffix=".part", dir=cache_dir)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            try:
                os.replace(tmp, cached)  # atomic: avoid a half-written cache file
            except OSError:
                # Windows refuses to replace a file a concurrent download just
                # published (PermissionError); that file is identical, so use it.
                if not os.path.exists(cached):
                    raise
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        return cached

    return resolver


# ── Verified-license Google Fonts preset ────────────────────────────────────
# Direct download URLs from the official google/fonts GitHub repo's `ofl/`
# directory — every family there is licensed under the SIL Open Font License
# 1.1 (the directory name is google/fonts' own convention for this), so there
# is no per-font license to chase down before using these, unlike an arbitrary
# font URL. Covers scripts NotoSansKR-Regular.ttf (this package's bundled
# default) doesn't: Japanese, Simplified/Traditional Chinese, Arabic, Thai,
# plus a broader Latin/Cyrillic/Greek family.
#
# These are variable fonts (a single file covering a weight/width range); PIL
# loads them at their default instance, which is fine for `ImageFont.truetype`.
GOOGLE_FONTS_SOURCES: dict[str, str] = {
    "NotoSans-Regular.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/notosans/NotoSans%5Bwdth%2Cwght%5D.ttf",
    "NotoSansJP-Regular.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/notosansjp/NotoSansJP%5Bwght%5D.ttf",
    "NotoSansSC-Regular.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/notosanssc/NotoSansSC%5Bwght%5D.ttf",
    "NotoSansTC-Regular.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/notosanstc/NotoSansTC%5Bwght%5D.ttf",
    "NotoSansArabic-Regular.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/notosansarabic/NotoSansArabic%5Bwdth%2Cwght%5D.ttf",
    "NotoSansThai-Regular.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/notosansthai/NotoSansThai%5Bwdth%2Cwght%5D.ttf",
}


def google_fonts_resolver(
    cache_dir: str,
    families: list[str] | None = None,
    *,
    session: requests.Session | None = None,
    timeout: float = 30,
) -> FontResolver:
    """``caching_resolver`` pre-loaded with :data:`GOOGLE_FONTS_SOURCES`.

    Downloads on first use and caches to disk, same as :func:`caching_resolver`
    — this just saves looking up/typing the source URLs yourself.

    Parameters
    ----------
    cache_dir:
        Directory to store downloaded fonts (created if missing).
    families:
        Subset of :data:`GOOGLE_FONTS_SOURCES` keys to make available (e.g.
        ``["NotoSansJP-Regular.ttf"]``); ``None`` (default) makes all of them
        available — nothing is downloaded until a payload actually asks for one.

    Example
    -------
    ::

        ctx = RenderContext(font_resolver=google_fonts_resolver("~/.cache/imagespec/fonts"))
        # a payload with `"font": "NotoSansJP-Regular.ttf"` now resolves,
        # downloading once and reusing the cached file after that.
    """
    if families is None:
        sources = GOOGLE_FONTS_SOURCES
    else:
        unknown = [k for k in families if k not in GOOGLE_FONTS_SOURCES]
        if unknown:
            raise ValueError(
                f"unknown Google Fonts famil{'y' if len(unknown) == 1 else 'ies'}: {', '.join(unknown)}; "
                f"expected any of: {', '.join(GOOGLE_FONTS_SOURCES)}"
            )
        sources = {k: GOOGLE_FONTS_SOURCES[k] for k in families}
    return caching_resolver(cache_dir, sources=sources, session=session, timeout=timeout)
