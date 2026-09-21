"""Declarative element specs: the single source of truth for payload keys.

Each handler declares its keys once, next to the code that reads them::

    @element("circle", doc="Circle from a centre and radius.", fields=[
        num("x", required=True, doc="centre x"),
        num("y", required=True, doc="centre y"),
        num("radius", required=True),
        color("fill", doc="interior colour; omitted = hollow"),
        color("outline", "black"),
        num("width", 1, doc="outline width"),
    ])

From these declarations the package derives:

* **coercion** — which keys are numbers/booleans, so template strings
  (``"42"``, ``"False"``) are converted before the handler runs, and which
  keys an explicit ``null`` is dropped from (= omitted) rather than passed on
  (:func:`imagespec.utils.coerce_element`);
* **JSON Schema** — ``schema/elements.json``, for editors and validators
  (``scripts/export_schema.py``);
* **documentation** — ``docs/reference.md`` (same script);
* **guard tests** — every key a handler reads must be declared, and declared
  defaults must match the handler's ``.get(key, default)`` literals.

Kinds: ``number`` (int or float), ``integer``, ``boolean``, ``string``,
``color`` (name or ``#hex``), ``any`` (handler-defined, documented in ``doc``),
``object`` (nested option dict with its own ``fields``), ``array`` (``items``
gives the item kind; ``object`` items carry ``fields``), ``elements`` (a list of
child elements, e.g. ``group``/``stack``) and ``dither`` (bool, ``0``/``1`` or a
method name).

``null``: every optional key accepts an explicit ``null`` (templates produce it
freely). For ``color`` keys it means "none" (no fill/outline); for ``dither``
"no override"; for a field declared ``nullable=True`` the handler gives it a
meaning of its own (``ylegend: null`` disables the legend). Everywhere else
``null`` is the same as omitting the key — it is dropped before dispatch, so
handlers never see ``None`` for a plain number/string/object.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

KINDS = ("number", "integer", "boolean", "string", "color", "any", "object", "array", "elements", "dither")


class _Unset:
    """Sentinel for "no documented default" (the handler decides at runtime)."""

    def __repr__(self) -> str:
        return "UNSET"


UNSET: Any = _Unset()


@dataclass(frozen=True)
class Field:
    name: str
    kind: str
    required: bool = False
    default: Any = UNSET
    doc: str = ""
    enum: tuple[Any, ...] | None = None
    # object: its own fields; array with items="object": the item's fields
    fields: tuple[Field, ...] = ()
    # array only: kind of each item ("number", "string", "any", "object", "array")
    items: str = "any"
    # a second accepted scalar kind (e.g. an array field that also takes a string,
    # or an enum that also takes a boolean)
    alt: str | None = None
    # conditionally required: ((key, accepted values), ...) — the field must be
    # present when any listed key holds one of its listed values
    required_when: tuple[tuple[str, tuple[Any, ...]], ...] = ()
    # elements only: False when the container supplies x/y itself (stack children)
    positioned: bool = True
    # an explicit null is meaningful to the handler (see the module docstring)
    nullable: bool = False

    @property
    def accepts_null(self) -> bool:
        """``None`` is passed through to the handler instead of being dropped."""
        return self.nullable or self.kind in ("color", "any", "dither")

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"field {self.name!r}: unknown kind {self.kind!r}")
        if self.required and self.default is not UNSET:
            raise ValueError(f"field {self.name!r}: a required field cannot have a default")
        if self.required and self.required_when:
            raise ValueError(f"field {self.name!r}: required and required_when are exclusive")


def _f(kind: str, name: str, default: Any = UNSET, *, required: bool = False, doc: str = "", **kw: Any) -> Field:
    return Field(name, kind, required=required, default=default, doc=doc, **kw)


def num(
    name: str,
    default: Any = UNSET,
    *,
    required: bool = False,
    doc: str = "",
    nullable: bool = False,
    required_when: Iterable[tuple[str, Iterable[Any]]] = (),
) -> Field:
    when = tuple((k, tuple(v)) for k, v in required_when)
    return _f("number", name, default, required=required, doc=doc, nullable=nullable, required_when=when)


def integer(name: str, default: Any = UNSET, *, required: bool = False, doc: str = "") -> Field:
    return _f("integer", name, default, required=required, doc=doc)


def boolean(name: str, default: Any = UNSET, *, required: bool = False, doc: str = "", nullable: bool = False) -> Field:
    return _f("boolean", name, default, required=required, doc=doc, nullable=nullable)


def string(name: str, default: Any = UNSET, *, required: bool = False, doc: str = "") -> Field:
    return _f("string", name, default, required=required, doc=doc)


def color(name: str, default: Any = UNSET, *, required: bool = False, doc: str = "") -> Field:
    return _f("color", name, default, required=required, doc=doc)


def any_(name: str, default: Any = UNSET, *, required: bool = False, doc: str = "") -> Field:
    return _f("any", name, default, required=required, doc=doc)


def enum(
    name: str,
    values: Iterable[Any],
    default: Any = UNSET,
    *,
    required: bool = False,
    doc: str = "",
    alt: str | None = None,
) -> Field:
    return _f("string", name, default, required=required, doc=doc, enum=tuple(values), alt=alt)


def obj(name: str, fields: Iterable[Field], *, required: bool = False, doc: str = "", nullable: bool = False) -> Field:
    return _f("object", name, required=required, doc=doc, fields=tuple(fields), nullable=nullable)


def array(
    name: str,
    items: str = "any",
    *,
    fields: Iterable[Field] = (),
    default: Any = UNSET,
    required: bool = False,
    doc: str = "",
    alt: str | None = None,
) -> Field:
    return _f("array", name, default, required=required, doc=doc, items=items, fields=tuple(fields), alt=alt)


def elements(
    name: str = "elements", *, positioned: bool = True, doc: str = "Child elements, rendered in order."
) -> Field:
    """Child element list. ``positioned=False`` when the container places the
    children itself, so their ``x``/``y`` are optional (stack/row/column)."""
    return _f("elements", name, required=True, doc=doc, positioned=positioned)


# Keys a non-positioning container fills in for its children.
POSITION_KEYS = frozenset({"x", "y"})


# ── shared field groups ────────────────────────────────────────────────────

# Read by an enclosing stack/row/column from each child (see layout._child_layout).
LAYOUT_FIELDS: tuple[Field, ...] = (
    num("grow", 0, doc="Share of leftover main-axis space this child takes (flex-grow)"),
    enum("align", ("start", "end", "center", "stretch"), doc="Cross-axis alignment for this child only"),
    enum("self", ("start", "end", "center", "stretch"), doc="Alias of `align`"),
    num("margin", doc="All four margins (px)"),
    num("margin_x", doc="Left and right margin"),
    num("margin_y", doc="Top and bottom margin"),
    num("margin_left"),
    num("margin_top"),
    num("margin_right"),
    num("margin_bottom"),
)

# Accepted by every element; handled by the dispatcher / containers, not the handler.
COMMON_FIELDS: tuple[Field, ...] = (
    string("type", required=True, doc="Element type"),
    boolean(
        "visible",
        True,
        nullable=True,
        doc='`false` (or `null`, or a template string such as `"False"`, `"off"`, `"0"`) skips the element',
    ),
    _f(
        "dither",
        "dither",
        doc="Per-element palette mapping: `true`/`false` (also `1`/`0` or a template string such as "
        '`"False"`) or a dither method name; overrides the render-wide setting for this element only. '
        "`null` = no override",
    ),
    string(
        "class",
        doc="Tailwind-like layout classes (`gap-2 items-center grow -ml-1 ...`), read by an enclosing stack/row/column",
    ),
    obj(
        "layout",
        LAYOUT_FIELDS,
        doc="Explicit per-child layout hints for an enclosing stack (same keys as the `class` shorthand)",
    ),
)
COMMON_NAMES = frozenset(f.name for f in COMMON_FIELDS)


@dataclass(frozen=True)
class ElementSpec:
    """Everything declared about one element type (or a set of aliases)."""

    names: tuple[str, ...]
    fields: tuple[Field, ...]
    doc: str = ""
    category: str = ""

    @property
    def name(self) -> str:
        return self.names[0]

    def field(self, name: str) -> Field | None:
        for f in self.fields:
            if f.name == name:
                return f
        return None


def walk_fields(fields: Iterable[Field], prefix: str = "") -> Iterable[tuple[str, Field]]:
    """Yield ``(dotted path, field)`` for ``fields`` and everything nested in them."""
    for f in fields:
        path = f"{prefix}{f.name}"
        yield path, f
        if f.fields:
            sub = f"{path}." if f.kind == "object" else f"{path}[]."
            yield from walk_fields(f.fields, sub)
