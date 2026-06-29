"""Element handlers.

Importing this package imports each handler module for its registration
side-effects (the ``@element(...)`` decorators populate the registry).

When porting a new element category, add its module to the import list below.
"""

from __future__ import annotations

from . import (
    charts,  # noqa: F401
    codes,  # noqa: F401
    layout,  # noqa: F401
    media,  # noqa: F401
    shapes,  # noqa: F401
    text,  # noqa: F401
)
