"""Parse a Tailwind-like utility ``class`` string into layout props.

Only the *layout* subset that makes sense for a fixed-palette, fixed-resolution
canvas is supported: flex direction, gap, padding, content/​item alignment, plus
the per-child utilities ``grow`` / ``self-*`` / margin. Styling utilities
(colours, fonts) are intentionally **not** parsed — those stay on each element's
own keys, so there is a single source of truth and no clash with palette
quantisation. Unknown tokens are ignored (Tailwind-style), so a payload that
mixes in styling classes still parses cleanly.

**Spacing scale = real Tailwind**, not raw pixels: a numeric unit is
``N × 4px`` (Tailwind's default ``0.25rem`` step), so ``gap-2`` → 8px,
``p-4`` → 16px, ``mt-0.5`` → 2px. For exact pixels use Tailwind's *arbitrary
value* syntax — ``gap-[10]`` / ``p-[3px]`` → 10px / 3px — which bypasses the
scale. Margins may be negative (``-mt-2`` → -8px, ``-ml-[3]`` → -3px) for
fine nudges; padding/gap cannot (matches Tailwind).

The returned dict uses flat, atomic keys so both the container resolver and the
per-child resolver can pick the ones they care about:

* ``direction``           – ``"horizontal"`` / ``"vertical"``
* ``gap``                 – int px
* ``pl`` ``pt`` ``pr`` ``pb`` – padding per side (int px)
* ``justify``             – main-axis distribution
* ``align``               – cross-axis item alignment (from ``items-*``)
* ``self``                – per-child cross-axis override (from ``self-*``)
* ``grow``                – per-child main-axis grow factor (int)
* ``ml`` ``mt`` ``mr`` ``mb`` – per-child margin per side (int px, may be < 0)
"""

from __future__ import annotations

_STEP = 4  # px per spacing unit — Tailwind's 0.25rem at a 16px root

_JUSTIFY = {"start", "end", "center", "between", "around", "evenly"}
_ALIGN = {"start", "end", "center", "stretch"}

# prefix -> the side keys it sets (later tokens override earlier ones)
_PAD = {
    "p": ("pl", "pt", "pr", "pb"),
    "px": ("pl", "pr"),
    "py": ("pt", "pb"),
    "pt": ("pt",),
    "pr": ("pr",),
    "pb": ("pb",),
    "pl": ("pl",),
}
_MAR = {
    "m": ("ml", "mt", "mr", "mb"),
    "mx": ("ml", "mr"),
    "my": ("mt", "mb"),
    "mt": ("mt",),
    "mr": ("mr",),
    "mb": ("mb",),
    "ml": ("ml",),
}


def _to_float(s: str):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _space(val: str):
    """Pixels for a spacing value: ``[N]``/``[Npx]`` arbitrary, else ``N×4`` scale."""
    if len(val) >= 2 and val[0] == "[" and val[-1] == "]":
        inner = val[1:-1]
        if inner.endswith("px"):
            inner = inner[:-2]
        n = _to_float(inner)
        return None if n is None else int(round(n))
    n = _to_float(val)
    return None if n is None else int(round(n * _STEP))


def _apply(token: str, props: dict) -> None:
    # exact-match tokens first (those whose names contain a '-')
    if token == "flex-row":
        props["direction"] = "horizontal"
        return
    if token == "flex-col":
        props["direction"] = "vertical"
        return
    if token in ("grow", "flex-1"):
        props["grow"] = 1
        return

    neg = token.startswith("-")
    body = token[1:] if neg else token
    prefix, sep, val = body.partition("-")
    if not sep:
        return  # bare / unknown token — ignore

    if prefix == "justify":
        if not neg and val in _JUSTIFY:
            props["justify"] = val
    elif prefix == "items":
        if not neg and val in _ALIGN:
            props["align"] = val
    elif prefix == "self":
        if not neg and val in _ALIGN:
            props["self"] = val
    elif prefix == "grow":
        if neg:
            return
        n = _to_float(val)
        if n is not None:
            props["grow"] = int(n)
    elif prefix == "gap":
        if neg:
            return  # no negative gap
        px = _space(val)
        if px is not None:
            props["gap"] = px
    elif prefix in _PAD:
        if neg:
            return  # no negative padding (matches Tailwind)
        px = _space(val)
        if px is not None:
            for k in _PAD[prefix]:
                props[k] = px
    elif prefix in _MAR:
        px = _space(val)
        if px is not None:
            v = -px if neg else px
            for k in _MAR[prefix]:
                props[k] = v
    # anything else (text-*, bg-*, hover:*, ...) is intentionally ignored


def parse_class(value) -> dict:
    """Parse a class string (or list of strings) into a flat layout-props dict.

    Tokens are applied in order, so a later token wins on conflict
    (``"p-2 px-4"`` → left/right become 16, top/bottom stay 8). Unrecognised
    tokens are skipped.
    """
    if not value:
        return {}
    if isinstance(value, (list, tuple)):
        tokens: list[str] = []
        for v in value:
            tokens.extend(str(v).split())
    else:
        tokens = str(value).split()

    props: dict = {}
    for token in tokens:
        _apply(token, props)
    return props
