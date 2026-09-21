"""Element specs are complete and consistent with the handlers that read them.

The declarations in each ``@element(..., fields=[...])`` are the source of the
JSON Schema, the generated reference and the template-string coercion, so a key
a handler reads but never declares would be invisible to all three. These tests
walk the handler source (AST) and compare it against the declarations.
"""

from __future__ import annotations

import ast
import inspect

import pytest

from imagespec import known_types
from imagespec.registry import get_handler, get_spec, specs
from imagespec.spec import COMMON_FIELDS, KINDS, LAYOUT_FIELDS, UNSET, walk_fields

# Local names that hold (part of) the payload dict inside handlers, mapped to
# the declared field path they correspond to ("" = the element itself).
_RECEIVERS = {
    "element": "",
    "eff": "",
    "child": "",
    "sp": "spans[]",
    "it": "items[]",
    "p": "data[]",
    "bars_cfg": "bars",
    "ylegend": "ylegend",
    "yaxis": "yaxis",
    "xlegend": "xlegend",
    "lay": "layout",
}


# Module-level helpers that read payload keys on a handler's behalf.
_EXTRA_READERS = {
    "stack": ["_resolve_padding"],
    "rectangle": ["_rounding"],
    "rectangle_pattern": ["_rounding"],
    "legend": ["_parse_legend_items"],
}


def _readers(spec):
    handler = get_handler(spec.name)
    module = inspect.getmodule(handler)
    return [handler, *(getattr(module, n) for n in _EXTRA_READERS.get(spec.name, ()))]


def _declared(spec) -> dict[str, object]:
    """``{path: field}`` for the spec plus the common fields."""
    return dict(walk_fields((*COMMON_FIELDS, *spec.fields)))


def _key_reads(fn) -> list[tuple[str, str, ast.AST | None]]:
    """``(receiver, key, default-node)`` for every ``recv.get("key"[, default])``,
    ``recv["key"]`` and ``"key" in recv`` in ``fn``'s source."""
    tree = ast.parse(inspect.getsource(fn))
    reads: list[tuple[str, str, ast.AST | None]] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and isinstance(node.func.value, ast.Name)
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            default = node.args[1] if len(node.args) > 1 else None
            reads.append((node.func.value.id, node.args[0].value, default))
        elif (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Name)
            and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, str)
        ):
            reads.append((node.value.id, node.slice.value, None))
        elif (
            isinstance(node, ast.Compare)
            and isinstance(node.left, ast.Constant)
            and isinstance(node.left.value, str)
            and len(node.ops) == 1
            and isinstance(node.ops[0], (ast.In, ast.NotIn))
            and isinstance(node.comparators[0], ast.Name)
        ):
            reads.append((node.comparators[0].id, node.left.value, None))
    return reads


def _path(receiver: str, key: str) -> str | None:
    prefix = _RECEIVERS.get(receiver)
    if prefix is None:
        return None  # not a payload dict (icon metadata, state rows, ...)
    return f"{prefix}.{key}" if prefix else key


# ── every element declares every key it reads ──────────────────────────────


def test_every_element_has_a_spec_with_fields():
    for name in sorted(known_types()):
        spec = get_spec(name)
        assert spec is not None and spec.fields, f"{name}: no field declarations"
        assert spec.doc, f"{name}: no doc string for the reference"


@pytest.mark.parametrize("spec", specs(), ids=lambda s: s.name)
def test_handler_reads_only_declared_keys(spec):
    declared = _declared(spec)
    undeclared = sorted(
        {
            path
            for fn in _readers(spec)
            for recv, key, _ in _key_reads(fn)
            if (path := _path(recv, key)) and path not in declared
        }
    )
    assert not undeclared, f"{spec.name} reads undeclared keys: {undeclared} — add them to its fields=[...]"


@pytest.mark.parametrize("spec", specs(), ids=lambda s: s.name)
def test_required_keys_are_enforced_by_require(spec):
    # A field declared `required` must be in the handler's require([...]) list,
    # so the documented contract and the runtime error agree.
    handler = get_handler(spec.name)
    tree = ast.parse(inspect.getsource(handler))
    required_in_code: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "require":
            required_in_code |= {c.value for c in node.args[1].elts if isinstance(c, ast.Constant)}
    declared_required = {f.name for f in spec.fields if f.required}
    assert declared_required == required_in_code, (
        f"{spec.name}: declared required {sorted(declared_required)} != require() {sorted(required_in_code)}"
    )


@pytest.mark.parametrize("spec", specs(), ids=lambda s: s.name)
def test_declared_defaults_match_handler_literals(spec):
    # element.get("k", <literal>) must agree with the documented default.
    declared = _declared(spec)
    mismatches = []
    for recv, key, default in (r for fn in _readers(spec) for r in _key_reads(fn)):
        path = _path(recv, key)
        if path is None or default is None or not isinstance(default, ast.Constant):
            continue
        field = declared.get(path)
        if field is None or field.default is UNSET:
            continue
        if field.default != default.value:
            mismatches.append(f"{path}: declared {field.default!r}, handler uses {default.value!r}")
    assert not mismatches, f"{spec.name}: " + "; ".join(mismatches)


# ── declaration hygiene ────────────────────────────────────────────────────


@pytest.mark.parametrize("spec", specs(), ids=lambda s: s.name)
def test_spec_fields_are_unique_and_well_formed(spec):
    names = [f.name for f in spec.fields]
    assert len(names) == len(set(names)), f"{spec.name}: duplicate field names"
    assert not set(names) & {f.name for f in COMMON_FIELDS}, f"{spec.name}: redeclares a common field"
    for path, f in walk_fields(spec.fields):
        assert f.kind in KINDS, path
        if f.enum is not None:
            assert f.default is UNSET or f.default in f.enum, f"{spec.name}.{path}: default not in enum"
        if f.kind == "array" and f.items == "object":
            assert f.fields, f"{spec.name}.{path}: object items need fields"


def test_layout_fields_cover_child_layout_reader():
    # layout._child_layout reads the child's `layout` dict through LAYOUT_FIELDS.
    from imagespec.elements import layout as layout_mod

    declared = {f.name for f in LAYOUT_FIELDS}
    read = {key for recv, key, _ in _key_reads(layout_mod._child_layout) if recv == "lay"}
    assert read <= declared, f"_child_layout reads undeclared layout keys: {sorted(read - declared)}"
