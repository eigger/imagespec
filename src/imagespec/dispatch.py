"""Single-element dispatch, shared by the render loop and the ``group`` container.

Kept in its own module (importing only the registry/utils, never the element
handlers) so both :mod:`imagespec.core` and :mod:`imagespec.elements.layout` can
use it without an import cycle.
"""

from __future__ import annotations

import logging

from PIL import Image, ImageChops

from .registry import get_handler, get_spec
from .spec import COMMON_FIELDS
from .utils import blit, coerce_element, merge_mask, should_show, subtract_mask

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
    handler(state, element)  # draws into the fresh layer (a handler may also assign state.img)
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
    if state.dither_protected is None:
        state.dither_protected = Image.new("L", base.size, 0)
    protected = state.dither_protected.crop((ox, oy, right, bottom))
    protected = ImageChops.subtract(protected, alpha)
    protected = ImageChops.lighter(protected, alpha.point(lambda p: 255 if p else 0))
    state.dither_protected.paste(protected, (ox, oy))


def _draw_rotated(state, element, handler, rotation: int, dither) -> None:
    """Render one element on a transparent layer, quarter-turn its ink, then composite.

    Rotation is around the center of the element's visible alpha bounds. The source
    layer uses the current drawing surface, so pixels clipped before rotation cannot
    be recovered; the destination composite clips the rotated result as usual.
    """
    from .dither import ORDERED_ORIGIN_ALIGN, dither_to_palette

    base = state.img
    old_protected = state.dither_protected
    old_pos_y = state.pos_y
    state.img = Image.new("RGBA", base.size, (0, 0, 0, 0))
    state.dither_protected = Image.new("L", base.size, 0)
    try:
        handler(state, element)
        layer = state.img.convert("RGBA")
        additions = state.dither_protected
        new_pos_y = state.pos_y
    except Exception:
        state.img = base
        state.dither_protected = old_protected
        state.pos_y = old_pos_y
        raise
    state.img = base

    bbox = layer.getchannel("A").getbbox()
    if bbox is None:
        state.dither_protected = old_protected
        return

    left, top, right, bottom = bbox
    source = layer.crop(bbox)
    source_mask = additions.crop(bbox)
    transpose = {
        90: Image.Transpose.ROTATE_270,
        180: Image.Transpose.ROTATE_180,
        270: Image.Transpose.ROTATE_90,
    }[rotation]
    tile = source.transpose(transpose)
    tile_mask = source_mask.transpose(transpose)
    center_x, center_y = (left + right) / 2, (top + bottom) / 2
    dest_x = round(center_x - tile.width / 2)
    dest_y = round(center_y - tile.height / 2)

    if dither is not None:
        # Align the quantization crop to the global ordered-screen origin after
        # rotation, then retain the final alpha so transparent pixels stay transparent.
        ox = dest_x // ORDERED_ORIGIN_ALIGN * ORDERED_ORIGIN_ALIGN
        oy = dest_y // ORDERED_ORIGIN_ALIGN * ORDERED_ORIGIN_ALIGN
        quant_input = Image.new("RGBA", (dest_x + tile.width - ox, dest_y + tile.height - oy), (0, 0, 0, 0))
        quant_input.alpha_composite(tile, (dest_x - ox, dest_y - oy))
        alpha = quant_input.getchannel("A")
        quant = dither_to_palette(
            quant_input,
            state.context.palette,
            dither=dither,
            origin=(ox, oy),
        ).convert("RGBA")
        quant.putalpha(alpha)
        blit(base, quant, ox, oy)
        protected = old_protected.copy() if old_protected is not None else Image.new("L", base.size, 0)
        subtract_mask(protected, alpha, ox, oy)
        merge_mask(protected, alpha.point(lambda p: 255 if p else 0), ox, oy)
        state.dither_protected = protected
    else:
        blit(base, tile, dest_x, dest_y)
        coverage = tile.getchannel("A").point(lambda p: 255 if p else 0)
        if old_protected is not None:
            surviving = old_protected.copy()
            subtract_mask(surviving, coverage, dest_x, dest_y)
            state.dither_protected = surviving
        else:
            state.dither_protected = Image.new("L", base.size, 0)
        merge_mask(state.dither_protected, tile_mask, dest_x, dest_y)

    # These handlers own the flow cursor even when they intentionally write its
    # current value (for example, an explicit-y line). Do not infer ownership by
    # comparing values: the cursor may already equal the value they assign.
    if element.get("type") in {"line", "text", "multiline", "table"}:
        state.pos_y = dest_y + tile.height
    else:
        state.pos_y = new_pos_y


def render_element(state, element: dict) -> None:
    """Dispatch a single element: visibility, handler lookup, coercion, per-element dither.

    Numeric/boolean keys are coerced from template strings here (see
    :func:`~imagespec.utils.coerce_element`) so handlers can read plain numbers.
    Raises whatever the handler raises (the caller adds element index/context).
    """
    if not should_show(element):
        return
    etype = element.get("type", "")
    handler = get_handler(etype)
    if handler is None:
        _LOGGER.warning("Unknown element type '%s' — skipping.", etype)
        return
    spec = get_spec(etype)
    element = coerce_element(element, (*COMMON_FIELDS, *(spec.fields if spec else ())))
    owns_rotation = spec is not None and any(field.name == "rotate" for field in spec.fields)
    rotation_value = element.get("rotate", 0) if not owns_rotation else 0
    if not owns_rotation and (isinstance(rotation_value, bool) or rotation_value not in (0, 90, 180, 270)):
        raise ValueError(f"rotate must be 0/90/180/270 for '{etype}', got {rotation_value!r}")
    rotation = int(rotation_value)
    if rotation:
        _draw_rotated(state, element, handler, rotation, element.get("dither"))
        return
    # `dither: null` means "no per-element override" (inherit the render-wide
    # setting), the same as omitting the key — not "flat" for this element.
    if element.get("dither") is not None:
        _draw_isolated(state, element, handler, element["dither"])
    else:
        old_protected = state.dither_protected
        if old_protected is not None and old_protected.getbbox() is not None:
            # Draw to transparency so coverage is known even when an element
            # paints the same RGB value already present under a protected pixel.
            base = state.img
            state.img = Image.new("RGBA", base.size, (0, 0, 0, 0))
            state.dither_protected = Image.new("L", base.size, 0)
            handler(state, element)
            layer = state.img.convert("RGBA")
            additions = state.dither_protected
            coverage = layer.getchannel("A").point(lambda p: 255 if p else 0)
            state.img = base
            base.alpha_composite(layer)
            surviving = ImageChops.subtract(old_protected, coverage)
            state.dither_protected = ImageChops.lighter(surviving, additions)
        else:
            handler(state, element)
