"""Payload validation against the element specs, without a JSON Schema library.

:func:`validate` walks a payload the way the renderer will and reports every
problem the declarations can detect: unknown element types, keys no handler
reads (typos such as ``fil``), missing required keys, and values of the wrong
kind. It applies the same tolerance as rendering — numeric/boolean keys may be
template strings (``"42"``, ``"False"``), optional keys may be ``null`` — so a
payload that validates here renders without a contract error.

Hosts call it to surface authoring mistakes before (or instead of) rendering::

    for issue in imagespec.validate(payload):
        print(issue)          # "[2].fill: unknown key for 'circle'"

``render(..., strict=True)`` runs the same checks and raises
:class:`~imagespec.exceptions.RenderError` when any fail.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from .dither import resolve_dither_method
from .registry import get_spec, known_types
from .spec import COMMON_FIELDS, POSITION_KEYS, Field
from .utils import to_bool, to_dither, to_number

_SCALAR_LABELS = {"number": "a number", "integer": "an integer", "boolean": "a boolean", "string": "a string"}


@dataclass(frozen=True)
class Issue:
    """One validation problem: where (``[i].key.sub``) and what."""

    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


def validate(payload: Sequence[Any], *, positioned: bool = True) -> list[Issue]:
    """Check ``payload`` against the element declarations; empty list = valid.

    ``positioned=False`` validates a list of stack/row/column children, whose
    ``x``/``y`` the container supplies.
    """
    issues: list[Issue] = []
    if not isinstance(payload, (list, tuple)):
        return [Issue("", f"payload must be a list of elements, got {type(payload).__name__}")]
    for idx, element in enumerate(payload):
        _check_element(element, f"[{idx}]", positioned, issues)
    return issues


def _check_element(element: Any, path: str, positioned: bool, issues: list[Issue]) -> None:
    if not isinstance(element, dict):
        issues.append(Issue(path, f"element must be a dict, got {type(element).__name__}"))
        return
    etype = element.get("type")
    if not isinstance(etype, str) or not etype:
        issues.append(Issue(f"{path}.type", "missing element type"))
        return
    spec = get_spec(etype)
    if spec is None:
        known = ", ".join(sorted(known_types()))
        issues.append(Issue(f"{path}.type", f"unknown element type {etype!r} (known: {known})"))
        return
    fields = {f.name: f for f in (*COMMON_FIELDS, *spec.fields)}
    for key in element:
        if key not in fields:
            issues.append(Issue(f"{path}.{key}", f"unknown key for {etype!r}"))
    for f in spec.fields:
        # A stack/row/column supplies its children's x/y, so they are optional there.
        supplied = not positioned and f.name in POSITION_KEYS
        required = (f.required and not supplied) or _required_now(element, f, fields)
        _check_field(element, f, path, issues, etype, required=required)
    for f in COMMON_FIELDS:
        if f.name != "type":
            _check_field(element, f, path, issues, etype)


def _required_now(element: dict, f: Field, fields: dict[str, Field]) -> bool:
    """``f.required_when`` triggered by the element's current values (booleans coerced)."""
    for key, values in f.required_when:
        value = element.get(key)
        if value is None:
            continue
        trigger = fields.get(key)
        if trigger is not None and trigger.kind == "boolean" and isinstance(value, (str, int, float)):
            value = to_bool(value)
        if any(value == v and type(value) is type(v) for v in values):
            return True
    return False


def _check_field(
    container: dict, f: Field, path: str, issues: list[Issue], etype: str, *, required: bool | None = None
) -> None:
    key_path = f"{path}.{f.name}"
    if required is None:
        required = f.required
    if f.name not in container or container[f.name] is None:
        if required:
            issues.append(Issue(key_path, f"missing required key for {etype!r}"))
        return
    _check_value(container[f.name], f, key_path, issues, etype)


def _check_value(value: Any, f: Field, path: str, issues: list[Issue], etype: str) -> None:
    kind = f.kind
    if f.alt is not None and _matches_scalar(value, f.alt):
        return
    alt = f" or {_SCALAR_LABELS.get(f.alt, f.alt)}" if f.alt else ""
    if kind in ("number", "integer"):
        if not _is_numberish(value, kind):
            issues.append(Issue(path, f"must be {_SCALAR_LABELS[kind]}{alt}, got {value!r}"))
    elif kind == "boolean":
        if not isinstance(value, (bool, int, float, str)):
            issues.append(Issue(path, f"must be a boolean{alt}, got {value!r}"))
    elif kind in ("string", "color"):
        if not isinstance(value, str):
            issues.append(Issue(path, f"must be a string{alt}, got {value!r}"))
        elif f.enum is not None and value not in f.enum:
            issues.append(Issue(path, f"must be one of {', '.join(map(repr, f.enum))}{alt}, got {value!r}"))
    elif kind == "object":
        if not isinstance(value, dict):
            issues.append(Issue(path, f"must be an object{alt}, got {value!r}"))
        else:
            _check_object(value, f.fields, path, issues, etype)
    elif kind == "array":
        if not isinstance(value, (list, tuple)):
            issues.append(Issue(path, f"must be an array{alt}, got {value!r}"))
        else:
            _check_items(value, f, path, issues, etype)
    elif kind == "elements":
        if not isinstance(value, (list, tuple)):
            issues.append(Issue(path, f"must be a list of elements, got {value!r}"))
        else:
            for i, child in enumerate(value):
                _check_element(child, f"{path}[{i}]", f.positioned, issues)
    elif kind == "dither":
        # Same contract as the schema: bool, 0/1, or a method name (template strings coerced).
        if isinstance(value, int) and not isinstance(value, bool) and value not in (0, 1):
            issues.append(Issue(path, f"must be true/false, 0/1 or a dither method name, got {value!r}"))
            return
        try:
            resolve_dither_method(to_dither(value))
        except (ValueError, TypeError) as exc:
            issues.append(Issue(path, str(exc)))
    # "any": handler-defined, nothing to check


def _check_object(value: dict, fields: Iterable[Field], path: str, issues: list[Issue], etype: str) -> None:
    declared = {f.name: f for f in fields}
    for key in value:
        if key not in declared:
            issues.append(Issue(f"{path}.{key}", f"unknown key for {etype!r}"))
    for f in declared.values():
        _check_field(value, f, path, issues, etype)


def _check_items(value: Sequence[Any], f: Field, path: str, issues: list[Issue], etype: str) -> None:
    for i, item in enumerate(value):
        item_path = f"{path}[{i}]"
        if f.items == "object":
            if not isinstance(item, dict):
                issues.append(Issue(item_path, f"must be an object, got {item!r}"))
            else:
                _check_object(item, f.fields, item_path, issues, etype)
        elif f.items in ("number", "integer"):
            if not _is_numberish(item, f.items):
                issues.append(Issue(item_path, f"must be {_SCALAR_LABELS[f.items]}, got {item!r}"))
        elif f.items == "string":
            if not isinstance(item, str):
                issues.append(Issue(item_path, f"must be a string, got {item!r}"))
        elif f.items == "array":
            if not isinstance(item, (list, tuple)):
                issues.append(Issue(item_path, f"must be an array, got {item!r}"))


def _is_numberish(value: Any, kind: str) -> bool:
    """Native number, or a string :func:`to_number` accepts (template output)."""
    if isinstance(value, bool):
        return False
    if isinstance(value, str):
        try:
            value = to_number(value)
        except ValueError:
            return False
    if kind == "integer":
        return isinstance(value, int) or (isinstance(value, float) and value.is_integer())
    return isinstance(value, (int, float))


def _matches_scalar(value: Any, kind: str) -> bool:
    """``value`` is acceptable as the ``alt`` kind (strict for booleans: an enum
    with ``alt="boolean"`` must not swallow arbitrary strings)."""
    if kind in ("number", "integer"):
        return _is_numberish(value, kind)
    if kind == "boolean":
        return isinstance(value, bool)
    return isinstance(value, str)
