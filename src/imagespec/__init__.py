"""imagespec — render images from a declarative YAML/dict spec.

Public API:

    from imagespec import render, RenderContext

    ctx = RenderContext(font_resolver=..., history_provider=...)
    image = render(payload, width=296, height=128, rotate=0,
                   background="white", context=ctx)
"""

from __future__ import annotations

from .colors import (
    PALETTE_4,
    PALETTE_7,
    PALETTE_BW,
    PALETTE_BWR,
    PALETTES,
    get_index_color,
    get_palette,
    quantize_color,
)
from .context import RenderContext
from .core import ROTATE_MODE_CANVAS, ROTATE_MODE_IMAGE, render
from .exceptions import RenderError
from .registry import known_types
from .resolvers import caching_resolver, chain_resolvers, directory_resolver

__all__ = [
    "render",
    "RenderContext",
    "RenderError",
    "ROTATE_MODE_CANVAS",
    "ROTATE_MODE_IMAGE",
    "PALETTE_BW",
    "PALETTE_BWR",
    "PALETTE_4",
    "PALETTE_7",
    "PALETTES",
    "get_palette",
    "quantize_color",
    "get_index_color",
    "known_types",
    "caching_resolver",
    "chain_resolvers",
    "directory_resolver",
]

# Single source of truth for the version. pyproject.toml reads this via
# [tool.setuptools.dynamic]; bump it here only.
__version__ = "0.1.0"
