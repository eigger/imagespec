"""Optional font resolvers for :class:`~imagespec.context.RenderContext`.

These are convenience helpers — the core works fine with ``font_resolver=None``
(bundled fonts only) or any callable you write yourself.

``caching_resolver`` addresses the "do I bundle every font or require the
internet?" trade-off: fonts are fetched from the web **once**, cached to disk,
and reused offline thereafter. Bundle only the essentials; download the rest on
first use.
"""

from __future__ import annotations

import os
from collections.abc import Callable

import requests

FontResolver = Callable[[str], str | None]


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
    """
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
        tmp = cached + ".part"
        with open(tmp, "wb") as f:
            f.write(resp.content)
        os.replace(tmp, cached)  # atomic: avoid a half-written cache file
        return cached

    return resolver
