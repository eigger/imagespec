"""The render loop: turn a payload + size into a PIL image."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from PIL import Image

# Importing the elements package registers all handlers via @element(...).
from . import elements  # noqa: E402,F401  (side-effect import)
from .context import RenderContext
from .exceptions import RenderError
from .registry import get_handler
from .state import RenderState
from .utils import should_show

_LOGGER = logging.getLogger(__name__)

# Rotation strategies — device-dependent (see docstring below).
ROTATE_MODE_CANVAS = "canvas"  # gicisky / fixed-resolution e-ink panels
ROTATE_MODE_IMAGE = "image"  # niimbot / variable-size label printers
_ROTATE_MODES = (ROTATE_MODE_CANVAS, ROTATE_MODE_IMAGE)


def render(
    payload: Sequence[dict],
    width: int,
    height: int,
    *,
    rotate: int = 0,
    rotate_mode: str = ROTATE_MODE_CANVAS,
    background="white",
    dither: bool = False,
    context: RenderContext,
) -> Image.Image:
    """Render ``payload`` to an ``RGB`` :class:`PIL.Image.Image`.

    Parameters
    ----------
    payload:
        Sequence of element dicts (already parsed from YAML/JSON).
    width, height:
        Canvas dimensions you author against. ``RenderState.canvas_width`` /
        ``canvas_height`` always reflect the actual surface being drawn on, so
        element coordinates are written in this frame regardless of rotation.
    rotate:
        0/90/180/270 (always rotated back at the end via ``-rotate``).
    rotate_mode:
        How 90/270 rotation is handled — this differs by device:

        * ``"canvas"`` (default, gicisky): the **background/canvas rotates**. The
          working canvas is pre-swapped to ``(height, width)``, drawn on, then
          rotated back, so the **output stays exactly ``width × height``** — the
          right behaviour for a fixed-resolution e-ink panel.
        * ``"image"`` (niimbot): the **drawing rotates**. The canvas is created
          at ``width × height``, drawn on, then the whole image is rotated, so
          the **output dimensions swap** — fine for a variable-size label printer.

        For ``rotate`` of 0/180 the two modes are identical.
    background:
        Background color name or ``#RRGGBB`` (mapped via :func:`get_index_color`).
    dither:
        If True, Floyd–Steinberg dither the final image to ``context.palette``
        (better for photos/logos on limited-color panels). Per-image dithering is
        also available on the ``dlimg`` element.
    context:
        Host-supplied :class:`RenderContext` (fonts, history, ...).
    """
    rotate = int(rotate or 0)
    if rotate not in (0, 90, 180, 270):
        raise ValueError(f"rotate must be 0/90/180/270, got {rotate}")
    if rotate_mode not in _ROTATE_MODES:
        raise ValueError(f"rotate_mode must be one of {_ROTATE_MODES}, got {rotate_mode!r}")
    if width <= 0 or height <= 0:
        raise ValueError(f"width and height must be positive, got {width}x{height}")
    bg = context.color(background)

    if rotate in (90, 270) and rotate_mode == ROTATE_MODE_CANVAS:
        img = Image.new("RGBA", (height, width), color=bg)
    else:
        img = Image.new("RGBA", (width, height), color=bg)

    state = RenderState(
        img=img,
        canvas_width=img.width,
        canvas_height=img.height,
        context=context,
    )

    for idx, element in enumerate(payload or []):
        if not isinstance(element, dict):
            raise RenderError(f"each payload element must be a dict, got {type(element).__name__}")
        etype = element.get("type", "")
        _LOGGER.debug("type: %s", etype)
        if not should_show(element):
            continue
        handler = get_handler(etype)
        if handler is None:
            _LOGGER.warning("Unknown element type '%s' — skipping.", etype)
            continue
        try:
            handler(state, element)
        except RenderError:
            raise  # already descriptive (names the element type / missing arg)
        except Exception as exc:  # noqa: BLE001 — add element context, then surface
            raise RenderError(f"error rendering element #{idx} (type '{etype}'): {exc}") from exc

    img = state.img
    if rotate in (90, 180, 270):
        img = img.rotate(-rotate, expand=True)
    result = img.convert("RGB")
    if dither:
        from .dither import dither_to_palette

        result = dither_to_palette(result, context.palette)
    return result
