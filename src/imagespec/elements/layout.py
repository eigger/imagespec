"""Layout containers: group.

A ``group`` renders its child elements onto a transparent sub-canvas, then
composites that at an offset. This gives reusable, relocatable sub-layouts:
children use coordinates relative to the group's top-left, the group clips to its
``width × height``, and it can optionally rotate the whole sub-layout.
"""

from __future__ import annotations

from PIL import Image

from ..dispatch import render_element
from ..exceptions import RenderError
from ..registry import element
from ..state import RenderState
from ..utils import require


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

    for idx, child in enumerate(element["elements"]):
        if not isinstance(child, dict):
            continue
        ctype = child.get("type", "")
        try:
            render_element(substate, child)
        except RenderError:
            raise  # already descriptive
        except Exception as exc:  # noqa: BLE001 — add child context, then surface
            raise RenderError(f"group: error rendering child #{idx} (type '{ctype}'): {exc}") from exc

    result = substate.img
    if rotate in (90, 180, 270):
        result = result.rotate(-rotate, expand=True)

    state.img.alpha_composite(result, (ox, oy))
