"""Exceptions for imagespec.

The core stays framework-agnostic: it raises :class:`RenderError` rather than
``homeassistant.exceptions.HomeAssistantError``. Each integration's adapter is
expected to catch ``RenderError`` and re-raise it as whatever its framework
expects (e.g. ``HomeAssistantError``).
"""

from __future__ import annotations


class RenderError(Exception):
    """Raised when a payload cannot be rendered (bad arguments, missing data, ...)."""
