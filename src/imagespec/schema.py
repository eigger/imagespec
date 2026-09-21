"""Derive the JSON Schema and the Markdown reference from the element specs.

Both are written by ``scripts/export_schema.py`` (``schema/elements.json`` and
``docs/reference.md``) and checked for staleness in CI, so the committed files
always match the registered handlers.
"""

from __future__ import annotations

from typing import Any

from .dither import DITHER_METHODS
from .registry import specs
from .spec import COMMON_FIELDS, POSITION_KEYS, UNSET, ElementSpec, Field

SCHEMA_VERSION = 2
SCHEMA_ID = "https://raw.githubusercontent.com/eigger/imagespec/main/schema/elements.json"

# Display order of categories in the reference (matches the README table).
CATEGORY_ORDER = ("shapes", "text", "codes", "media", "charts", "layout", "widgets")
CATEGORY_TITLES = {
    "shapes": "Shapes",
    "text": "Text",
    "codes": "Machine-readable codes",
    "media": "Media",
    "charts": "Charts",
    "layout": "Layout containers",
    "widgets": "Widgets",
}

_SCALAR_TYPES = {"number": "number", "integer": "integer", "boolean": "boolean", "string": "string", "color": "string"}


# ── JSON Schema ────────────────────────────────────────────────────────────


def _field_schema(f: Field) -> dict[str, Any]:
    s: dict[str, Any]
    if f.kind in _SCALAR_TYPES:
        s = {"type": _SCALAR_TYPES[f.kind]}
        if f.enum is not None:
            s["enum"] = list(f.enum)
    elif f.kind == "any":
        s = {}
    elif f.kind == "object":
        s = _object_schema(f.fields)
    elif f.kind == "array":
        item: dict[str, Any]
        if f.items == "object":
            item = _object_schema(f.fields)
        elif f.items in _SCALAR_TYPES:
            item = {"type": _SCALAR_TYPES[f.items]}
        elif f.items == "array":
            item = {"type": "array"}
        else:
            item = {}
        s = {"type": "array", "items": item}
    elif f.kind == "elements":
        target = "element" if f.positioned else "stack_child"
        s = {"type": "array", "items": {"$ref": f"#/$defs/{target}"}}
    elif f.kind == "dither":
        # Runtime (resolve_dither_method) also takes JSON 1/0 from hosts.
        s = {
            "anyOf": [
                {"type": "boolean"},
                {"type": "integer", "enum": [0, 1]},
                {"type": "string", "enum": list(DITHER_METHODS)},
            ]
        }
    else:  # pragma: no cover - guarded by Field.__post_init__
        raise ValueError(f.kind)

    if f.alt is not None:
        s = {"anyOf": [s, {"type": _SCALAR_TYPES[f.alt]}]}

    # Optional keys may be set to null explicitly (e.g. `fill: null`, `ylegend: null`).
    if not f.required:
        if "type" in s:
            s["type"] = [s["type"], "null"]
            if "enum" in s:
                s["enum"] = [*s["enum"], None]
        elif "anyOf" in s:
            s["anyOf"] = [*s["anyOf"], {"type": "null"}]

    desc = f.doc
    if f.kind == "color":
        desc = (desc + " " if desc else "") + "(colour name or #RGB/#RRGGBB; quantized to the device palette)"
    if desc:
        s["description"] = desc
    if f.default is not UNSET and f.default is not None:
        s["default"] = f.default
    return s


def _object_schema(fields: tuple[Field, ...]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {f.name: _field_schema(f) for f in fields},
        "required": [f.name for f in fields if f.required],
        "additionalProperties": False,
    }


def _element_schema(spec: ElementSpec) -> dict[str, Any]:
    props: dict[str, Any] = {}
    for f in COMMON_FIELDS:
        if f.name == "type":
            props["type"] = {"const": spec.name} if len(spec.names) == 1 else {"enum": list(spec.names)}
        else:
            props[f.name] = _field_schema(f)
    for f in spec.fields:
        props[f.name] = _field_schema(f)
    # x/y are required at the top level and inside `group`, but a stack supplies
    # them, so the per-element def leaves them optional and `$defs/element`
    # adds them back (see build_json_schema).
    schema: dict[str, Any] = {
        "type": "object",
        "description": spec.doc,
        "properties": props,
        "required": ["type", *(f.name for f in spec.fields if f.required and f.name not in POSITION_KEYS)],
        "additionalProperties": False,
    }
    return schema


def _positioned_ref(spec: ElementSpec) -> dict[str, Any]:
    pos = [f.name for f in spec.fields if f.required and f.name in POSITION_KEYS]
    ref = {"$ref": f"#/$defs/{spec.name}"}
    return {"allOf": [ref, {"required": pos}]} if pos else ref


def build_json_schema() -> dict[str, Any]:
    """JSON Schema (draft 2020-12) for a whole payload: an array of elements."""
    all_specs = specs()
    defs: dict[str, Any] = {
        "element": {
            "description": "Any element placed by its own coordinates (top level or inside `group`).",
            "oneOf": [_positioned_ref(s) for s in all_specs],
        },
        "stack_child": {
            "description": "Any element inside a stack/row/column, which positions it (`x`/`y` optional).",
            "oneOf": [{"$ref": f"#/$defs/{s.name}"} for s in all_specs],
        },
    }
    for s in all_specs:
        defs[s.name] = _element_schema(s)
    types = sorted(name for s in all_specs for name in s.names)
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": SCHEMA_ID,
        "title": "imagespec payload",
        "description": (
            "A list of elements rendered in order. Numeric and boolean keys also accept the string forms "
            "Home Assistant templates produce at render time; this schema describes the authored types."
        ),
        "schema_version": SCHEMA_VERSION,
        "package": "imagespec",
        "types": types,
        "dither_methods": list(DITHER_METHODS),
        "type": "array",
        "items": {"$ref": "#/$defs/element"},
        "$defs": defs,
    }


# ── Markdown reference ─────────────────────────────────────────────────────


def _type_label(f: Field) -> str:
    if f.enum is not None:
        return " \\| ".join(f"`{v}`" for v in f.enum)
    if f.kind == "array":
        label = f"array of {f.items}" if f.items != "object" else "array of objects"
        return f"{label} \\| {f.alt}" if f.alt else label
    if f.kind == "elements":
        return "array of elements"
    if f.kind == "dither":
        return "bool \\| 0/1 \\| method name"
    return f.kind


def _default_label(f: Field) -> str:
    if f.required:
        return "**required**"
    if f.default is UNSET or f.default is None:
        return ""
    if isinstance(f.default, bool):
        return "`true`" if f.default else "`false`"
    if isinstance(f.default, str):
        return f"`{f.default!r}`".replace("'", '"')
    return f"`{f.default}`"


def _field_rows(fields: tuple[Field, ...], prefix: str = "") -> list[str]:
    rows = []
    for f in fields:
        name = f"{prefix}{f.name}"
        rows.append(f"| `{name}` | {_type_label(f)} | {_default_label(f)} | {f.doc} |")
        if f.fields:
            sub = f"{name}." if f.kind == "object" else f"{name}[]."
            rows.extend(_field_rows(f.fields, sub))
    return rows


def _table(fields: tuple[Field, ...]) -> str:
    return "\n".join(["| key | type | default | description |", "|---|---|---|---|", *_field_rows(fields)])


def build_reference_md() -> str:
    """``docs/reference.md``: every element, every key, from the declarations."""
    out = [
        "# Element reference",
        "",
        "<!-- GENERATED by scripts/export_schema.py from the @element(..., fields=[...]) declarations. -->",
        "<!-- Edit the declarations next to each handler, then run: python scripts/export_schema.py -->",
        "",
        "Every key each element accepts, with its type and default. A payload is a list of these",
        "elements, rendered in order. `schema/elements.json` is the same information as JSON Schema.",
        "",
        '- **number** keys also accept numeric strings (`"42"`, `"3.5"`) as produced by templates;',
        '  **boolean** keys accept `"true"`/`"false"`/`"on"`/`"off"`/`"0"`/`"1"`.',
        "- **color** is a name (`black`, `red`, `#ff0000`, `#f00`, any CSS colour name) and is quantized",
        "  to the device palette when the image is finished.",
        "- Omitting an optional key uses the default. An explicit `null` is the same as omitting it,",
        "  except for **color** keys (`null` = no fill/outline), `dither` (`null` = no override) and",
        "  the keys whose description says what `null` does (e.g. `ylegend: null` disables the legend).",
        "",
        "See [`elements.md`](elements.md) for a rendered YAML example of every element and",
        "[`authoring.md`](authoring.md) for the layout model.",
        "",
        "## Keys accepted by every element",
        "",
        _table(COMMON_FIELDS),
        "",
    ]
    by_category: dict[str, list[ElementSpec]] = {}
    for s in specs():
        by_category.setdefault(s.category, []).append(s)
    categories = [*CATEGORY_ORDER, *sorted(c for c in by_category if c not in CATEGORY_ORDER)]
    for cat in categories:
        if cat not in by_category:
            continue
        out += [f"## {CATEGORY_TITLES.get(cat, cat.title())}", ""]
        for s in by_category[cat]:
            title = f"### `{s.name}`"
            if len(s.names) > 1:
                title += " (aliases: " + ", ".join(f"`{n}`" for n in s.names[1:]) + ")"
            out += [
                title,
                "",
                f"![{s.name} preview](../examples/elements/{s.name}.png)",
                "",
                s.doc,
                "",
                _table(s.fields),
                "",
            ]
    return "\n".join(out).rstrip("\n") + "\n"
