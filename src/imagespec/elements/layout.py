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

import math

from PIL import Image, ImageDraw

from ..classutil import parse_class
from ..dispatch import render_element
from ..exceptions import RenderError
from ..registry import element
from ..spec import LAYOUT_FIELDS, STRETCHABLE_TYPES, color, elements, enum, num
from ..state import RenderState
from ..utils import (
    blit,
    coerce_element,
    int_xy,
    merge_mask,
    mono_draw,
    multiline_anchor,
    require,
    subtract_mask,
    wrap_words,
)


@element(
    "group",
    doc="Container: children use coordinates relative to the group's top-left, are clipped to "
    "`width` x `height`, and the whole block can be rotated.",
    fields=[
        elements(),
        num("x", 0),
        num("y", 0),
        num("width", doc="Defaults to the canvas width"),
        num("height", doc="Defaults to the canvas height"),
        num("rotate", 0, doc="0/90/180/270, clockwise"),
    ],
)
def group(state: RenderState, element: dict) -> None:
    require(element, ["elements"], "group")
    ox = element.get("x", 0)
    oy = element.get("y", 0)
    gw = round(element.get("width", state.canvas_width))
    gh = round(element.get("height", state.canvas_height))
    rotate = int(element.get("rotate", 0) or 0)

    sub = Image.new("RGBA", (gw, gh), (0, 0, 0, 0))
    substate = RenderState(
        img=sub,
        canvas_width=gw,
        canvas_height=gh,
        context=state.context,
        dither_protected=Image.new("L", sub.size, 0),
    )

    for idx, child in enumerate(element["elements"]):
        if not isinstance(child, dict):
            continue
        ctype = child.get("type", "")
        try:
            render_element(substate, child)
        except RenderError as exc:
            exc.at(f".elements[{idx}]")  # already descriptive
            raise
        except Exception as exc:  # noqa: BLE001 — add child context, then surface
            raise RenderError(
                f"group: error rendering child #{idx} (type '{ctype}'): {exc}", path=f".elements[{idx}]"
            ) from exc

    result = substate.img
    if rotate in (90, 180, 270):
        result = result.rotate(-rotate, expand=True)

    offset = int_xy(ox, oy)
    state.img.alpha_composite(result, offset)
    if substate.dither_protected is not None:
        protected = substate.dither_protected
        if rotate in (90, 180, 270):
            protected = protected.rotate(-rotate, expand=True)
        if state.dither_protected is None:
            state.dither_protected = Image.new("L", state.img.size, 0)
        merge_mask(state.dither_protected, protected, *offset)


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


def _px(value) -> int:
    """A pixel length rounded to the nearest int (``2.6`` -> 3), matching how x/y offsets are rounded."""
    return int(round(float(value)))


def _px_or(value, default: int = 0) -> int:
    """:func:`_px`, but a non-finite value (``inf``/``nan``) gives ``default`` instead of raising."""
    try:
        return _px(value)
    except (OverflowError, ValueError):
        return default


def _resolve_padding(element: dict, cls: dict) -> tuple[int, int, int, int]:
    """Return ``(left, top, right, bottom)`` from explicit keys then ``class``.

    Precedence per side: ``padding_<side>`` > ``padding_x``/``padding_y`` >
    ``padding`` (all) > class (``pl``/``pt``/...) > 0.
    """
    pad_all = element.get("padding")

    def side(name: str, axis_key: str, cls_key: str) -> int:
        v = element.get(f"padding_{name}")
        if v is not None:
            return _px(v)
        av = element.get(axis_key)
        if av is not None:
            return _px(av)
        if pad_all is not None:
            return _px(pad_all)
        if cls_key in cls:
            return _px(cls[cls_key])
        return 0

    return (
        side("left", "padding_x", "pl"),
        side("top", "padding_y", "pt"),
        side("right", "padding_x", "pr"),
        side("bottom", "padding_y", "pb"),
    )


class _InkRuler:
    """``getlength`` for wrapping that errs on the side of never clipping.

    Hinted 1-bit glyphs can come out much wider than ``font.getlength`` / ``textbbox`` predict
    (a quarter wider for "degrees" at 10px), which would leave wrapped lines clipped by the slot.
    Each word's own overhang (drawn ink minus advance) is measured once and added up: a line
    whose advance plus that overhang still fits is accepted without drawing it, one whose advance
    alone is over is rejected, and only the lines in between are really drawn and measured.
    """

    _MARGIN = 3  # kerning/rounding across word boundaries (+ _DRIFT of the advance on long lines)
    _DRIFT = 0.03

    def __init__(self, font, avail: float, *, strict: bool = False) -> None:
        self._font = font
        self._avail = avail
        self._strict = strict  # always draw: no estimate is trusted
        ascent, descent = font.getmetrics()
        self._height = ascent + descent + 8
        self._excess: dict[str, float] = {}
        self._cache: dict[str, float] = {}

    def _ink_right(self, text: str, advance: float) -> float:
        scratch = Image.new("L", (int(advance * 1.5) + 32, self._height), 0)
        mono_draw(scratch).text((0, 0), text, fill=255, font=self._font)
        ink = scratch.getbbox()
        return float(ink[2]) if ink else 0.0

    def _word_excess(self, word: str) -> float:
        if word not in self._excess:
            self._excess[word] = max(
                0.0, self._ink_right(word, self._font.getlength(word)) - self._font.getlength(word)
            )
        return self._excess[word]

    def ink_right(self, text: str) -> float:
        """Right edge of the drawn ink of ``text`` (at least its advance), cached."""
        if text not in self._cache:
            advance = self._font.getlength(text)
            self._cache[text] = max(advance, self._ink_right(text, advance))
        return self._cache[text]

    def getlength(self, text: str) -> float:
        advance = self._font.getlength(text)
        if advance > self._avail:
            return advance  # clearly over
        if (
            not self._strict
            and advance * (1 + self._DRIFT) + self._MARGIN + sum(self._word_excess(w) for w in text.split())
            <= self._avail
        ):
            return advance  # fits even with every word's hinting overhang
        return self.ink_right(text)


def _wrap_text_to(state, child: dict, avail: int) -> dict:
    """A ``text`` child whose lines are wider than ``avail`` px, word-wrapped to fit (explicit
    ``\\n`` breaks and the whitespace of lines that already fit are kept); anything else (fits,
    ``max_width`` set, rotated, ...) comes back unchanged.

    A stack clips whatever overflows it, so a long text in a narrow column used to be cut off.
    """
    if child.get("type") != "text" or child.get("max_width") is not None or avail <= 0:
        return child
    try:
        if int(float(child.get("rotation") or 0)) % 360 != 0:
            return child
        font = state.context.font(child.get("font"), float(child.get("size", 20)))
    except Exception:  # noqa: BLE001 — bad size/rotation/font: the element itself reports it
        return child
    value = str(child.get("value", ""))
    paragraphs = value.split("\n")
    ruler = _InkRuler(font, avail)

    def fits(para: str) -> bool:
        # the estimate says it fits; a paragraph is only kept whole once its drawn ink agrees
        return ruler.getlength(para) <= avail and ruler.ink_right(para) <= avail

    if all(fits(p) for p in paragraphs):
        return child
    strict = _InkRuler(font, avail, strict=True)
    lines: list[str] = []
    for para in paragraphs:
        if not para.strip() or fits(para):
            lines.append(para)  # fits (or blank): keep it as written, indentation included
            continue
        for line in wrap_words(para, ruler, avail):
            # the estimates above can be a pixel or two short for some fonts: every line that
            # was accepted without being drawn is checked once, and re-wrapped by drawing if over
            if " " in line and ruler.ink_right(line) > avail:
                lines.extend(wrap_words(line, strict, avail))
            else:
                lines.append(line)
    return {**child, "value": "\n".join(lines)}


def _origin_padding(state: RenderState, child: dict, sub_w: int, sub_h: int) -> int:
    """Room around (0, 0) to measure center-origin geometry without clipping ink."""
    padding = max(sub_w, sub_h)
    try:
        radius = float(child.get("radius", 0) or 0)
        stroke = float(child.get("width", 1) or 0)
        padding = max(padding, math.ceil(max(0, radius + stroke + 2)))
    except (TypeError, ValueError, OverflowError):
        pass  # the element handler will report malformed geometry

    etype = child.get("type")
    if etype not in ("text", "multiline", "new_multiline", "icon"):
        return padding
    try:
        size = float(child.get("size", 20))
        font = state.context.font(child.get("font"), size)
        anchor = child.get("anchor", {"text": "lt", "multiline": "lm", "new_multiline": "la", "icon": "la"}[etype])
        value = str(child.get("value", ""))
        spacing = child.get("spacing", size if etype == "new_multiline" else 5)
        align = child.get("align", "left")
        stroke_width = child.get("stroke_width", 0)
        draw = ImageDraw.Draw(Image.new("L", (1, 1)))
        if etype == "multiline":
            delimiter = child.get("delimiter", "|")
            lines = value.replace("\n", "").split(delimiter)
            offset = child.get("offset_y", size)
            boxes = [
                draw.textbbox(
                    (0, i * offset), line, font=font, anchor=anchor, stroke_width=stroke_width
                )
                for i, line in enumerate(lines)
            ]
        elif etype in ("new_multiline",) or "\n" in value:
            anchor = multiline_anchor(anchor, value, always=etype == "new_multiline")
            boxes = [
                draw.multiline_textbbox(
                    (0, 0),
                    value,
                    font=font,
                    anchor=anchor,
                    spacing=spacing,
                    align=align,
                    stroke_width=stroke_width,
                )
            ]
        else:
            boxes = [draw.textbbox((0, 0), value, font=font, anchor=anchor, stroke_width=stroke_width)]
        background_padding = float(child.get("background_padding", 0) or 0)
        ink_extent = max((abs(edge) + background_padding for box in boxes for edge in box), default=0)
        rotation = abs(float(child.get("rotation", 0) or 0))
        if rotation % 360:
            width = max((box[2] - box[0] for box in boxes), default=0) + 2 * background_padding
            height = max((box[3] - box[1] for box in boxes), default=0) + 2 * background_padding
            ink_extent = max(ink_extent, math.ceil(math.hypot(width, height) + stroke_width + 2))
        return max(padding, math.ceil(ink_extent + stroke_width + 2))
    except Exception:  # noqa: BLE001 — let the element handler report invalid font/size/anchor
        return padding


def _cross_margins(lay: dict, horizontal: bool) -> int:
    """Cross-axis margins (top+bottom in a row, left+right in a column) of a child layout."""
    return lay["mt"] + lay["mb"] if horizontal else lay["ml"] + lay["mr"]


def _cross_extent(tile: dict, horizontal: bool) -> int:
    """Cross-axis size of a built tile including its margins."""
    return (tile["h"] if horizontal else tile["w"]) + _cross_margins(tile, horizontal)


def _fills_slot(child: dict, main_key: str) -> bool:
    """A card (nested stack with ``background``/``outline``) with no explicit main-axis size: `grow` makes
    its box fill the slot. Unstyled stacks draw nothing for their empty space, so there is nothing to fill."""
    styled = child.get("background") is not None or child.get("outline") is not None
    if not (styled and child.get("type") in ("stack", "row", "column") and child.get(main_key) is None):
        return False
    try:  # a 90/270 rotation swaps the axes, so width/height would grow the wrong way
        return int(float(child.get("rotate") or 0)) % 180 == 0
    except (TypeError, ValueError, OverflowError):
        return False


# Stretchable elements that can be rendered without a cross size (their width/height are optional).
_MEASURABLE = frozenset({"group", "stack", "row", "column"})


def _stretched(child: dict, lay: dict, align: str) -> bool:
    """``align: stretch`` applies to ``child``: a size-aware element (a 90/270 rotation would
    swap the axes, so those are left alone) whose own or inherited alignment is ``stretch``."""
    try:
        rotated = int(float(child.get("rotate") or 0)) % 180 != 0
    except (TypeError, ValueError, OverflowError):
        rotated = False
    return (lay["self"] or align) == "stretch" and child.get("type") in STRETCHABLE_TYPES and not rotated


def stretch_cross_key(owner: dict, child: dict) -> str | None:
    """``"height"``/``"width"`` when ``owner`` (a stack/row/column) stretches ``child`` across its
    cross axis, else ``None``. Used by ``validate()``/the schema, where that key may be omitted."""
    etype = owner.get("type")
    if etype not in ("stack", "row", "column") or not isinstance(child, dict):
        return None
    if child.get("type") not in STRETCHABLE_TYPES:
        return None
    cls = parse_class(owner.get("class"))
    default_dir = "horizontal" if etype == "row" else "vertical"
    horizontal = _norm_dir(_first(owner.get("direction"), cls.get("direction"), default_dir)) == "horizontal"
    align = _first(owner.get("align"), owner.get("align_items"), cls.get("align"), "start")
    try:
        lay = _child_layout(child)
    except (TypeError, ValueError, OverflowError):
        return None  # a bad `layout` value is reported by the normal field check
    if not _stretched(child, lay, align):
        return None
    return "height" if horizontal else "width"


def _stretch_size(child: dict, eff: dict, lay: dict, align: str, horizontal: bool, inner_cross: int) -> int | None:
    """Cross-axis size for an `align: stretch` child (``None`` = not stretched)."""
    if not _stretched(child, lay, align):
        return None
    if eff.get("height" if horizontal else "width") is not None:
        return None  # an explicit size wins
    return max(0, inner_cross - _cross_margins(lay, horizontal))


def _child_layout(child: dict) -> dict:
    """Per-child layout props from the child's ``class`` and ``layout`` dict.

    Read from the child's ``class`` string and an optional ``layout`` sub-dict —
    never from the child's own drawing keys (so ``margin`` on a ``diagram`` or
    ``width`` on a ``sparkline`` is never mistaken for a layout instruction).
    """
    cls = parse_class(child.get("class"))
    lay = child.get("layout")
    # Read from the raw child (before its own dispatch coerces it), so coerce here.
    lay = coerce_element(lay, LAYOUT_FIELDS) if isinstance(lay, dict) else {}

    grow = lay.get("grow")
    if grow is None:
        grow = cls.get("grow", 0)
    grow = int(grow or 0)

    self_align = lay.get("align") or lay.get("self") or cls.get("self")

    m_all = lay.get("margin")

    def margin(name: str, axis_key: str, cls_key: str) -> int:
        v = lay.get(f"margin_{name}")
        if v is not None:
            return _px(v)
        av = lay.get(axis_key)
        if av is not None:
            return _px(av)
        if m_all is not None:
            return _px(m_all)
        if cls_key in cls:
            return _px(cls[cls_key])
        return 0

    return {
        "grow": grow,
        "basis": lay.get("basis") if lay.get("basis") is not None else cls.get("basis"),
        "self": self_align,
        "ml": margin("left", "margin_x", "ml"),
        "mt": margin("top", "margin_y", "mt"),
        "mr": margin("right", "margin_x", "mr"),
        "mb": margin("bottom", "margin_y", "mb"),
    }


def _resolve_basis(raw, inner_main: int) -> int | None:
    """``layout.basis`` in px: a number, a numeric string, or ``"N%"`` of ``inner_main``; ``None`` if unset."""
    if raw is None:
        return None
    try:
        if isinstance(raw, str) and raw.strip().endswith("%"):
            value = inner_main * float(raw.strip()[:-1]) / 100
        elif isinstance(raw, bool):
            raise ValueError(raw)
        else:
            value = float(raw)
        return max(0, _px(value))
    except (TypeError, ValueError, OverflowError):
        raise RenderError(f"layout.basis must be a number or a percentage like '50%', got {raw!r}") from None


def basis_error(raw) -> str | None:
    """Why ``raw`` is not a usable ``layout.basis`` (``None`` if it is, or is unset); for ``validate()``."""
    try:
        _resolve_basis(raw, 100)
    except RenderError as exc:
        return exc.message
    return None


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


@element(
    "stack",
    "row",
    "column",
    doc="Flexbox-style auto-layout: children need no coordinates; they are measured and packed along "
    "the main axis with `gap`, padding, `justify` and `align`. `row` and `column` fix the direction. "
    "Each child may carry `class` / `layout` hints. `background` / `outline` / `radius` draw a card "
    "behind them. Long `text` children of a `column` word-wrap to the column's width.",
    fields=[
        elements(positioned=False, doc="Child elements; their `x`/`y` are ignored (the stack positions them)"),
        enum("direction", ("horizontal", "vertical"), doc="Defaults to horizontal for `row`, vertical otherwise"),
        num("gap", 0),
        enum("justify", ("start", "end", "center", "between", "around", "evenly"), "start"),
        enum("justify_content", ("start", "end", "center", "between", "around", "evenly"), doc="Alias of `justify`"),
        enum(
            "align",
            ("start", "end", "center", "stretch"),
            "start",
            doc="Cross-axis alignment of children. `stretch` sizes `group`, `stack`/`row`/`column`, `text_fit`, "
            "`sparkline`, `diagram` and `battery` children that have no cross-axis `width`/`height` to fill it; "
            "other elements (and 90/270-rotated ones) keep their size and sit at `start`",
        ),
        enum("align_items", ("start", "end", "center", "stretch"), doc="Alias of `align`"),
        num("x", 0),
        num("y", 0),
        num(
            "width",
            doc="Defaults to the canvas width — or, with `background`/`outline`, to the content width "
            "(a card hugs its content unless sized; a card holding only `text_fit`-style children, which "
            "have no intrinsic size, needs an explicit cross size)",
        ),
        num(
            "height",
            doc="Defaults to the canvas height — or, with `background`/`outline`, to the content height "
            "(see `width` for the size-required-children caveat)",
        ),
        num("rotate", 0, doc="0/90/180/270, clockwise"),
        num("padding", doc="All sides"),
        num("padding_x"),
        num("padding_y"),
        num("padding_left"),
        num("padding_top"),
        num("padding_right"),
        num("padding_bottom"),
        color("background", doc="Fill the whole box (padding included) behind the children — a card"),
        color("outline", doc="Border colour of the box"),
        num("width_outline", 1, doc="Border width"),
        num("radius", 0, doc="Corner radius of the box"),
    ],
)
def stack(state: RenderState, element: dict) -> None:
    require(element, ["elements"], "stack")
    cls = parse_class(element.get("class"))
    etype = element.get("type")
    default_dir = "horizontal" if etype == "row" else "vertical"
    horizontal = _norm_dir(_first(element.get("direction"), cls.get("direction"), default_dir)) == "horizontal"

    gap = _px(_first(element.get("gap"), cls.get("gap"), 0))
    justify = _first(element.get("justify"), element.get("justify_content"), cls.get("justify"), "start")
    align = _first(element.get("align"), element.get("align_items"), cls.get("align"), "start")

    ox, oy = int_xy(element.get("x", 0) or 0, element.get("y", 0) or 0)  # rounded, like `group`
    cw = round(_first(element.get("width"), state.canvas_width))  # round, like `group`
    ch = round(_first(element.get("height"), state.canvas_height))
    # A styled stack (a card) without an explicit size hugs its content instead of filling the
    # parent: otherwise its background would cover the whole area and swallow its siblings.
    styled = element.get("background") is not None or element.get("outline") is not None
    hug_w = styled and element.get("width") is None
    hug_h = styled and element.get("height") is None
    rotate = int(element.get("rotate", 0) or 0)

    pl, pt, pr, pb = _resolve_padding(element, cls)
    inner_w = max(0, cw - pl - pr)
    inner_h = max(0, ch - pt - pb)

    source_idx = [i for i, c in enumerate(element["elements"]) if isinstance(c, dict)]
    children = [element["elements"][i] for i in source_idx]

    # Render each child onto its own transparent layer and measure its drawn
    # extent (alpha bbox). Children need no coordinates — default x/y to 0 for the
    # elements that require them; the bbox crop then normalises position so the
    # stack alone controls where each tile lands.
    inner_cross = inner_h if horizontal else inner_w
    cross_key = "height" if horizontal else "width"
    hug_cross_axis = hug_h if horizontal else hug_w

    def positioned(child):
        """``child`` with the x/y every element requires defaulted to 0 (the stack places it)."""
        return {**child, "x": 0, "y": 0}

    main_key = "width" if horizontal else "height"

    def render_child(idx, child, lay, stretch_size, main_size=None):
        """Render ``child`` on its own layer and crop it to its drawn extent: ``lay`` + img/w/h."""
        if main_size is None and bases[idx] is not None and _fills_slot(child, main_key):
            main_size = bases[idx]  # a card is as large as its basis
        eff = positioned(child)
        if not horizontal:  # a column's cross axis is the width: wrap long text to the slot
            eff = _wrap_text_to(state, eff, inner_w - _cross_margins(lay, horizontal))
        sub_w, sub_h = max(1, inner_w), max(1, inner_h)
        if main_size is not None:  # a growing card: its box is the whole slot along the main axis
            eff = {**eff, main_key: main_size, ("x" if horizontal else "y"): 0}  # own main coordinate is ignored
            if horizontal:
                sub_w = max(sub_w, main_size)
            else:
                sub_h = max(sub_h, main_size)
        if stretch_size is not None:
            # the child's own cross coordinate is ignored (like any stack child); a negative margin
            # can make the slot larger than the stack, so give the layer room for it
            eff = {**eff, cross_key: stretch_size, ("y" if horizontal else "x"): 0}
            if horizontal:
                sub_h = max(sub_h, stretch_size)
            else:
                sub_w = max(sub_w, stretch_size)
        # Give anchor-based elements room to draw around x/y=0 (circle, gauge,
        # middle-anchored text, ...); the crop below turns their full ink bounds
        # into the tile origin before the stack positions the tile.
        origin_pad = _origin_padding(state, child, sub_w, sub_h)
        pad_x = pad_y = origin_pad
        sub = Image.new("RGBA", (sub_w + 2 * pad_x, sub_h + 2 * pad_y), (0, 0, 0, 0))
        substate = RenderState(
            img=sub,
            canvas_width=sub_w,
            canvas_height=sub_h,
            context=state.context,
            dither_protected=Image.new("L", sub.size, 0),
        )
        ctype = child.get("type", "")
        try:
            render_element(substate, {**eff, "x": eff.get("x", 0) + pad_x, "y": eff.get("y", 0) + pad_y})
        except RenderError as exc:
            exc.at(f".elements[{source_idx[idx]}]")  # already descriptive
            raise
        except Exception as exc:  # noqa: BLE001 — add child context, then surface
            raise RenderError(
                f"stack: error rendering child #{source_idx[idx]} (type '{ctype}'): {exc}",
                path=f".elements[{source_idx[idx]}]",
            ) from exc
        rendered = substate.img
        bbox = rendered.getbbox()
        if bbox and stretch_size is not None:
            # keep the whole stretched slot on the cross axis (valign/background stay where drawn)
            bbox = (
                (bbox[0], pad_y, bbox[2], pad_y + stretch_size)
                if horizontal
                else (pad_x, bbox[1], pad_x + stretch_size, bbox[3])
            )
        tile = rendered.crop(bbox) if bbox else None
        protected = substate.dither_protected.crop(bbox) if bbox and substate.dither_protected is not None else None
        tw, th = tile.size if tile else (0, 0)
        return {
            **lay,
            "img": tile,
            "protected": protected,
            "w": tw,
            "h": th,
            "stretch": stretch_size,
            "basis": bases[idx] or 0,
        }

    lays = [_child_layout(c) for c in children]
    inner_main_now = inner_w if horizontal else inner_h  # (pre-hug: the space available)
    bases: list[int | None] = []
    for i, lay in enumerate(lays):
        try:
            bases.append(_resolve_basis(lay.get("basis"), inner_main_now))
        except RenderError as exc:
            raise exc.at(f".elements[{source_idx[i]}].layout.basis") from None
    # `align: stretch`: size-aware children without an explicit cross size fill the cross axis.
    stretches = [
        _stretch_size(c, positioned(c), lay, align, horizontal, inner_cross)
        for c, lay in zip(children, lays, strict=True)
    ]
    slots: list[dict | None] = [None] * len(children)
    if hug_cross_axis and any(st is not None for st in stretches):
        # The cross size is the content's (flexbox): measure what is not stretched first, then
        # stretch the rest to that. Containers can be measured unstretched; size-required
        # elements (text_fit, ...) have no intrinsic size, so they wait for the result.
        for i, (c, lay) in enumerate(zip(children, lays, strict=True)):
            if stretches[i] is None or c.get("type") in _MEASURABLE:
                slots[i] = render_child(i, c, lay, None)
        cross_inner = max((_cross_extent(t, horizontal) for t in slots if t is not None), default=inner_cross)
        for i, (c, lay) in enumerate(zip(children, lays, strict=True)):
            if stretches[i] is not None:
                slots[i] = render_child(i, c, lay, max(0, cross_inner - _cross_margins(lay, horizontal)))
    else:
        for i, (c, lay) in enumerate(zip(children, lays, strict=True)):
            slots[i] = render_child(i, c, lay, stretches[i])
    tiles = [t for t in slots if t is not None]

    n = len(tiles)

    def main_of(t):
        # a child's slot is at least its basis (the child itself keeps its drawn size inside it)
        return max(t["w"] if horizontal else t["h"], t["basis"])

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
    if hug_w or hug_h:
        content_cross = max((cross_of(t) + m_cross_lead(t) + m_cross_trail(t) for t in tiles), default=0)
        hug_main, hug_cross = (hug_w, hug_h) if horizontal else (hug_h, hug_w)
        extra_main = (pl + pr) if horizontal else (pt + pb)
        extra_cross = (pt + pb) if horizontal else (pl + pr)
        main_total = max(0, content_main + extra_main) if hug_main else None
        cross_total = max(0, content_cross + extra_cross) if hug_cross else None
        if horizontal:
            cw, ch = main_total if main_total is not None else cw, cross_total if cross_total is not None else ch
        else:
            ch, cw = main_total if main_total is not None else ch, cross_total if cross_total is not None else cw
        inner_w = max(0, cw - pl - pr)
        inner_h = max(0, ch - pt - pb)
        inner_cross = inner_h if horizontal else inner_w
    inner_main = inner_w if horizontal else inner_h
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
        # A growing card (styled nested stack without its own main size) fills its slot: its box,
        # not just the empty space after it, takes the extra.
        for i, (c, t) in enumerate(zip(children, tiles, strict=True)):
            if grow_extra[i] > 0 and _fills_slot(c, main_key):
                target = main_of(t) + grow_extra[i]
                tiles[i] = render_child(i, c, t, t["stretch"], target)
                # whatever the box did not take (e.g. an invisible fill) stays as slot space
                grow_extra[i] = max(0, target - main_of(tiles[i]))

    leading, spacing = _justify_offsets(justify, free, n, gap)

    canvas = Image.new("RGBA", (max(1, cw), max(1, ch)), (0, 0, 0, 0))
    protected_canvas = Image.new("L", canvas.size, 0)
    if styled and cw > 0 and ch > 0:
        mono_draw(canvas).rounded_rectangle(
            [(0, 0), (cw - 1, ch - 1)],
            fill=state.context.color(element.get("background")),
            outline=state.context.color(element.get("outline")),
            width=max(0, _px_or(element.get("width_outline", 1), 1)),
            radius=max(0, _px_or(element.get("radius", 0))),
        )
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
            else:  # start / stretch (a stretched child already spans the cross axis) -> start
                cross_pos = m_cross_lead(t)
            if horizontal:
                pos = (pl + round(main_pos), pt + round(cross_pos))
            else:
                pos = (pl + round(cross_pos), pt + round(main_pos))
            blit(canvas, t["img"], *pos)
            coverage = t["img"].getchannel("A").point(lambda p: 255 if p else 0)
            subtract_mask(protected_canvas, coverage, *pos)
            if t.get("protected") is not None:
                protected_canvas.paste(t["protected"], pos, t["protected"])
        cursor += m_main_lead(t) + slot_main + m_main_trail(t)
        if i < n - 1:
            cursor += spacing

    if rotate in (90, 180, 270):
        canvas = canvas.rotate(-rotate, expand=True)
        protected_canvas = protected_canvas.rotate(-rotate, expand=True)
    state.img.alpha_composite(canvas, (ox, oy))
    if state.dither_protected is None:
        state.dither_protected = Image.new("L", state.img.size, 0)
    merge_mask(state.dither_protected, protected_canvas, ox, oy)
