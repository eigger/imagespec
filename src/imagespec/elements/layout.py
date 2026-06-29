"""Layout containers: group.

A ``group`` renders its child elements onto a transparent sub-canvas, then
composites that at an offset. This gives reusable, relocatable sub-layouts:
children use coordinates relative to the group's top-left, the group clips to its
``width × height``, and it can optionally rotate the whole sub-layout.
"""

from __future__ import annotations

import logging

from PIL import Image

from ..registry import element, get_handler
from ..state import RenderState
from ..utils import require, should_show

_LOGGER = logging.getLogger(__name__)


@element("group")
def group(state: RenderState, element: dict) -> None:
    require(element, ["elements"], "group")
    ox = element.get("x", 0)
    oy = element.get("y", 0)
    gw = element.get("width", state.canvas_width)
    gh = element.get("height", state.canvas_height)
    rotate = int(element.get("rotate", 0) or 0)

    sub = Image.new("RGBA", (gw, gh), (0, 0, 0, 0))
    substate = RenderState(img=sub, canvas_width=gw, canvas_height=gh, context=state.context)

    for child in element["elements"]:
        if not isinstance(child, dict):
            continue
        if not should_show(child):
            continue
        handler = get_handler(child.get("type", ""))
        if handler is None:
            _LOGGER.warning("group: unknown element type '%s' — skipping.", child.get("type"))
            continue
        handler(substate, child)

    result = substate.img
    if rotate in (90, 180, 270):
        result = result.rotate(-rotate, expand=True)

    state.img.alpha_composite(result, (ox, oy))
