"""Element handler registry.

Replaces the original monolithic ``if element["type"] == ...`` chain with a
decorator-based dispatch table. Each handler is registered for one or more
payload ``type`` strings, has the signature ``handler(state, element)``, and
declares the keys it reads (see :mod:`imagespec.spec`).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING

from .spec import ElementSpec, Field

if TYPE_CHECKING:  # importing RenderState at runtime would be circular
    from .state import RenderState

Handler = Callable[["RenderState", dict], None]

_HANDLERS: dict[str, Handler] = {}
_SPECS: dict[str, ElementSpec] = {}


def element(*names: str, fields: Iterable[Field] = (), doc: str = "", category: str = ""):
    """Register a handler for one or more element ``type`` names.

    ``fields`` declares the payload keys the handler reads (:mod:`imagespec.spec`);
    ``doc`` is the one-paragraph description used in the generated reference.
    ``category`` defaults to the handler module's name (shapes, text, ...).
    """

    def decorator(fn: Handler) -> Handler:
        spec = ElementSpec(
            names=tuple(names),
            fields=tuple(fields),
            doc=doc,
            category=category or fn.__module__.rsplit(".", 1)[-1],
        )
        for name in names:
            if name in _HANDLERS:
                raise ValueError(f"Duplicate handler registered for element type '{name}'")
            _HANDLERS[name] = fn
            _SPECS[name] = spec
        return fn

    return decorator


def get_handler(name: str) -> Handler | None:
    return _HANDLERS.get(name)


def get_spec(name: str) -> ElementSpec | None:
    """Declared fields for element ``name`` (``None`` for an unknown type)."""
    return _SPECS.get(name)


def specs() -> list[ElementSpec]:
    """Every distinct spec, in registration order (aliases share one entry)."""
    seen: list[ElementSpec] = []
    for spec in _SPECS.values():
        if spec not in seen:
            seen.append(spec)
    return seen


def known_types() -> set[str]:
    """All element ``type`` strings the renderer currently understands."""
    return set(_HANDLERS)
