"""Element handler registry.

Replaces the original monolithic ``if element["type"] == ...`` chain with a
decorator-based dispatch table. Each handler is registered for one or more
payload ``type`` strings and has the signature ``handler(state, element)``.
"""

from __future__ import annotations

from collections.abc import Callable

# Forward ref only; importing RenderState here would be circular at module load.
Handler = Callable[["RenderState", dict], None]  # noqa: F821

_HANDLERS: dict[str, Handler] = {}


def element(*names: str):
    """Register a handler function for one or more element ``type`` names."""

    def decorator(fn: Handler) -> Handler:
        for name in names:
            if name in _HANDLERS:
                raise ValueError(f"Duplicate handler registered for element type '{name}'")
            _HANDLERS[name] = fn
        return fn

    return decorator


def get_handler(name: str) -> Handler | None:
    return _HANDLERS.get(name)


def known_types() -> set[str]:
    """All element ``type`` strings the renderer currently understands."""
    return set(_HANDLERS)
