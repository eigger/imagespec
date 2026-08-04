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


def _draw_isolated(state, element, handler, dither) -> None:
    """Render one element on its own layer and map it to the palette now.

    Used for a per-element ``dither`` override: the element is drawn in isolation,
    quantized (dithered halftone or flat nearest) to the device palette, then
    composited. Because the result is already palette colors, the final
    whole-image pass in :func:`~imagespec.core.render` leaves it untouched — so
    this element keeps its chosen treatment regardless of the global ``dither``
    flag, and payload (z-)order is preserved.

    Only the opaque bounding box is quantized (aligned down to
    :data:`~imagespec.dither.ORDERED_ORIGIN_ALIGN` so Bayer/clustered phase
    matches a full-canvas pass).
    """
    from .dither import ORDERED_ORIGIN_ALIGN, dither_to_palette

    base = state.img
    state.img = Image.new("RGBA", base.size, (0, 0, 0, 0))
    handler(state, element)  # handler may reassign state.img (rotation/composite)
    layer = state.img.convert("RGBA")
    state.img = base

    bbox = layer.getbbox()
    if bbox is None:
        return

    left, top, right, bottom = bbox
    ox = (left // ORDERED_ORIGIN_ALIGN) * ORDERED_ORIGIN_ALIGN
    oy = (top // ORDERED_ORIGIN_ALIGN) * ORDERED_ORIGIN_ALIGN
    cropped = layer.crop((ox, oy, right, bottom))
    alpha = cropped.split()[-1]
    quant = dither_to_palette(
        cropped,
        state.context.palette,
        dither=dither,
        origin=(ox, oy),
    ).convert("RGBA")
    quant.putalpha(alpha)
    base.alpha_composite(quant, dest=(ox, oy))


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
        _draw_isolated(state, element, handler, element["dither"])
    else:
        handler(state, element)
