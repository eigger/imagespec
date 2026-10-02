"""Exceptions for imagespec.

The core stays framework-agnostic: it raises :class:`RenderError` rather than
``homeassistant.exceptions.HomeAssistantError``. Each integration's adapter is
expected to catch ``RenderError`` and re-raise it as whatever its framework
expects (e.g. ``HomeAssistantError``).
"""

from __future__ import annotations


class RenderError(Exception):
    """Raised when a payload cannot be rendered (bad arguments, missing data, ...).

    ``path`` locates the failing element in the payload in the same notation as
    :attr:`imagespec.Issue.path` (e.g. ``[0].elements[1]``); it is empty for errors
    that are not tied to one element. ``str(exc)`` is prefixed with it, and
    ``exc.message`` is the bare text.
    """

    def __init__(self, message: str = "", *, path: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.path = path

    def __str__(self) -> str:
        return f"{self.path}: {self.message}" if self.path else self.message

    def at(self, segment: str) -> RenderError:
        """Prepend ``segment`` (an enclosing container/index) to :attr:`path`; returns ``self``."""
        self.path = segment + self.path
        return self
