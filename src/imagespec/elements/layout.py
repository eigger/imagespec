"""Layout containers: group, stack (row/column).

A ``group`` renders its child elements onto a transparent sub-canvas, then
composites that at an offset. This gives reusable, relocatable sub-layouts:
children use coordinates relative to the group's top-left, the group clips to its
``width × height``, and it can optionally rotate the whole sub-layout.

A ``stack`` (aliases ``row`` / ``column``) is an *auto-layout* container: it
measures each child's drawn extent and packs them along an axis with gap,
padding, content distribution (``justify``) and cross-axis alignment
(``items`` / per-child ``self``), flexbox-style. Children therefore need no
explicit coordinates — the stack fills them in. Both the container and each
child accept a Tailwind-like ``class`` string as shorthand for these layout
props (see :mod:`imagespec.classutil`); explicit keys win over ``class``.

Both containers are purely additive: existing payloads never mention them, and
inside them the engine only *positions* children — drawing is still delegated to
the normal element handlers, so every registered element works as a child.
"""

from __future__ import annotations

from PIL import Image

from ..classutil import parse_class
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


# --------------------------------------------------------------------------- #
# stack (row / column) — flexbox-style auto-layout
# --------------------------------------------------------------------------- #


def _first(*vals):
    """First non-``None`` value (``0``/``""`` count as present)."""
    for v in vals:
        if v is not None:
            return v
    return None


def _norm_dir(value) -> str:
    s = str(value).lower()
    if s in ("horizontal", "h", "row", "x"):
        return "horizontal"
    return "vertical"


def _resolve_padding(element: dict, cls: dict) -> tuple[int, int, int, int]:
    """Return ``(left, top, right, bottom)`` from explicit keys then ``class``.

    Precedence per side: ``padding_<side>`` > ``padding_x``/``padding_y`` >
    ``padding`` (all) > class (``pl``/``pt``/...) > 0.
    """
    pad_all = element.get("padding")

    def side(name: str, axis_key: str, cls_key: str) -> int:
        v = element.get(f"padding_{name}")
        if v is not None:
            return int(v)
        av = element.get(axis_key)
        if av is not None:
            return int(av)
        if pad_all is not None:
            return int(pad_all)
        if cls_key in cls:
            return int(cls[cls_key])
        return 0

    return (
        side("left", "padding_x", "pl"),
        side("top", "padding_y", "pt"),
        side("right", "padding_x", "pr"),
        side("bottom", "padding_y", "pb"),
    )


def _child_layout(child: dict) -> dict:
    """Per-child layout props from the child's ``class`` and ``layout`` dict.

    Read from the child's ``class`` string and an optional ``layout`` sub-dict —
    never from the child's own drawing keys (so ``margin`` on a ``diagram`` or
    ``width`` on a ``sparkline`` is never mistaken for a layout instruction).
    """
    cls = parse_class(child.get("class"))
    lay = child.get("layout")
    if not isinstance(lay, dict):
        lay = {}

    grow = lay.get("grow")
    if grow is None:
        grow = cls.get("grow", 0)
    grow = int(grow or 0)

    self_align = lay.get("align") or lay.get("self") or cls.get("self")

    m_all = lay.get("margin")

    def margin(name: str, axis_key: str, cls_key: str) -> int:
        v = lay.get(f"margin_{name}")
        if v is not None:
            return int(v)
        av = lay.get(axis_key)
        if av is not None:
            return int(av)
        if m_all is not None:
            return int(m_all)
        if cls_key in cls:
            return int(cls[cls_key])
        return 0

    return {
        "grow": grow,
        "self": self_align,
        "ml": margin("left", "margin_x", "ml"),
        "mt": margin("top", "margin_y", "mt"),
        "mr": margin("right", "margin_x", "mr"),
        "mb": margin("bottom", "margin_y", "mb"),
    }


def _justify_offsets(justify: str, free: float, n: int, gap: int) -> tuple[float, float]:
    """Return ``(leading, spacing)`` along the main axis for ``justify-*``.

    ``leading`` is the offset before the first child; ``spacing`` is the full gap
    between adjacent children (base ``gap`` plus any distributed free space).
    """
    if n <= 0:
        return 0.0, 0.0
    free = max(0.0, free)  # overflow clamps to start; content just spills/clips
    if justify == "end":
        return free, gap
    if justify == "center":
        return free / 2, gap
    if justify == "between":
        return (0.0, gap) if n == 1 else (0.0, gap + free / (n - 1))
    if justify == "around":
        unit = free / n
        return unit / 2, gap + unit
    if justify == "evenly":
        unit = free / (n + 1)
        return unit, gap + unit
    return 0.0, gap  # start (default)


def _blit(canvas: Image.Image, tile: Image.Image, x: int, y: int) -> None:
    """Alpha-composite ``tile`` at ``(x, y)``, clipping to the canvas bounds.

    Plain ``alpha_composite`` rejects offsets that fall outside the destination;
    negative margins and overflow can produce those, so we crop the tile to its
    visible rectangle first (and skip it entirely if nothing is visible).
    """
    cw, ch = canvas.size
    tw, th = tile.size
    sx, sy = max(0, -x), max(0, -y)
    ex, ey = min(tw, cw - x), min(th, ch - y)
    if ex <= sx or ey <= sy:
        return  # fully off-canvas
    part = tile.crop((sx, sy, ex, ey)) if (sx, sy, ex, ey) != (0, 0, tw, th) else tile
    canvas.alpha_composite(part, (x + sx, y + sy))


@element("stack", "row", "column")
def stack(state: RenderState, element: dict) -> None:
    require(element, ["elements"], "stack")
    cls = parse_class(element.get("class"))
    etype = element.get("type")
    default_dir = "horizontal" if etype == "row" else "vertical"
    horizontal = _norm_dir(_first(element.get("direction"), cls.get("direction"), default_dir)) == "horizontal"

    gap = int(_first(element.get("gap"), cls.get("gap"), 0))
    justify = _first(element.get("justify"), element.get("justify_content"), cls.get("justify"), "start")
    align = _first(element.get("align"), element.get("align_items"), cls.get("align"), "start")

    ox = int(element.get("x", 0) or 0)
    oy = int(element.get("y", 0) or 0)
    cw = int(_first(element.get("width"), state.canvas_width))
    ch = int(_first(element.get("height"), state.canvas_height))
    rotate = int(element.get("rotate", 0) or 0)

    pl, pt, pr, pb = _resolve_padding(element, cls)
    inner_w = max(0, cw - pl - pr)
    inner_h = max(0, ch - pt - pb)

    children = [c for c in element["elements"] if isinstance(c, dict)]

    # Render each child onto its own transparent layer and measure its drawn
    # extent (alpha bbox). Children need no coordinates — default x/y to 0 for the
    # elements that require them; the bbox crop then normalises position so the
    # stack alone controls where each tile lands.
    tiles = []
    for idx, child in enumerate(children):
        eff = child
        if "x" not in eff or "y" not in eff:
            eff = {**child}
            eff.setdefault("x", 0)
            eff.setdefault("y", 0)
        sub = Image.new("RGBA", (max(1, inner_w), max(1, inner_h)), (0, 0, 0, 0))
        substate = RenderState(img=sub, canvas_width=inner_w, canvas_height=inner_h, context=state.context)
        ctype = child.get("type", "")
        try:
            render_element(substate, eff)
        except RenderError:
            raise  # already descriptive
        except Exception as exc:  # noqa: BLE001 — add child context, then surface
            raise RenderError(f"stack: error rendering child #{idx} (type '{ctype}'): {exc}") from exc
        rendered = substate.img
        bbox = rendered.getbbox()
        tile = rendered.crop(bbox) if bbox else None
        tw, th = tile.size if tile else (0, 0)
        lay = _child_layout(child)
        lay.update(img=tile, w=tw, h=th)
        tiles.append(lay)

    n = len(tiles)
    inner_main = inner_w if horizontal else inner_h
    inner_cross = inner_h if horizontal else inner_w

    def main_of(t):
        return t["w"] if horizontal else t["h"]

    def cross_of(t):
        return t["h"] if horizontal else t["w"]

    def m_main_lead(t):
        return t["ml"] if horizontal else t["mt"]

    def m_main_trail(t):
        return t["mr"] if horizontal else t["mb"]

    def m_cross_lead(t):
        return t["mt"] if horizontal else t["ml"]

    def m_cross_trail(t):
        return t["mb"] if horizontal else t["mr"]

    content_main = sum(main_of(t) + m_main_lead(t) + m_main_trail(t) for t in tiles)
    if n > 1:
        content_main += gap * (n - 1)
    free = inner_main - content_main

    # Distribute leftover main-axis space to grow children; whatever they consume
    # is removed from `free` so justify only spreads what remains.
    total_grow = sum(t["grow"] for t in tiles if t["grow"] > 0)
    grow_extra = [0] * n
    if total_grow > 0 and free > 0:
        handed = 0
        last = None
        for i, t in enumerate(tiles):
            if t["grow"] > 0:
                share = int(free * t["grow"] // total_grow)
                grow_extra[i] = share
                handed += share
                last = i
        if last is not None:
            grow_extra[last] += int(free) - handed  # rounding remainder
        free = 0

    leading, spacing = _justify_offsets(justify, free, n, gap)

    canvas = Image.new("RGBA", (max(1, cw), max(1, ch)), (0, 0, 0, 0))
    cursor = leading
    for i, t in enumerate(tiles):
        slot_main = main_of(t) + grow_extra[i]
        if t["img"] is not None:
            main_pos = cursor + m_main_lead(t)
            cfree = inner_cross - cross_of(t) - m_cross_lead(t) - m_cross_trail(t)
            a = t["self"] or align
            if a == "end":
                cross_pos = m_cross_lead(t) + max(0, cfree)
            elif a == "center":
                cross_pos = m_cross_lead(t) + max(0, cfree) / 2
            else:  # start / stretch (pixels can't stretch) -> start
                cross_pos = m_cross_lead(t)
            if horizontal:
                pos = (pl + round(main_pos), pt + round(cross_pos))
            else:
                pos = (pl + round(cross_pos), pt + round(main_pos))
            _blit(canvas, t["img"], *pos)
        cursor += m_main_lead(t) + slot_main + m_main_trail(t)
        if i < n - 1:
            cursor += spacing

    if rotate in (90, 180, 270):
        canvas = canvas.rotate(-rotate, expand=True)
    state.img.alpha_composite(canvas, (ox, oy))
