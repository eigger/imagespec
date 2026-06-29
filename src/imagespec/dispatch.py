"""Single-element dispatch, shared by the render loop and the ``group`` container.

Kept in its own module (importing only the registry/utils, never the element
handlers) so both :mod:`imagespec.core` and :mod:`imagespec.elements.layout` can
use it without an import cycle.
"""

from __future__ import annotations

import logging

from PIL import Image

from .registry import get_handler
from .utils import should_show

_LOGGER = logging.getLogger(__name__)


def _draw_isolated(state, element, handler, dither: bool) -> None:
    """Render one element on its own layer and map it to the palette now.

    Used for a per-element ``dither`` override: the element is drawn in isolation,
    quantized (dithered halftone or flat nearest) to the device palette, then
    composited. Because the result is already palette colors, the final
    whole-image pass in :func:`~imagespec.core.render` leaves it untouched — so
    this element keeps its chosen treatment regardless of the global ``dither``
    flag, and payload (z-)order is preserved.
    """
    from .dither import dither_to_palette

    base = state.img
    state.img = Image.new("RGBA", base.size, (0, 0, 0, 0))
    handler(state, element)  # handler may reassign state.img (rotation/composite)
    layer = state.img.convert("RGBA")
    state.img = base
    alpha = layer.split()[-1]
    quant = dither_to_palette(layer, state.context.palette, dither=dither).convert("RGBA")
    quant.putalpha(alpha)  # only the pixels the element actually drew
    base.alpha_composite(quant)


def render_element(state, element: dict) -> None:
    """Dispatch a single element: visibility, handler lookup, per-element dither.

    Raises whatever the handler raises (the caller adds element index/context).
    """
    if not should_show(element):
        return
    etype = element.get("type", "")
    handler = get_handler(etype)
    if handler is None:
        _LOGGER.warning("Unknown element type '%s' — skipping.", etype)
        return
    if "dither" in element:
        _draw_isolated(state, element, handler, bool(element["dither"]))
    else:
        handler(state, element)
