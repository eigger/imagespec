"""Shared pytest fixtures."""

from __future__ import annotations

import base64
import io

import pytest
from PIL import Image

from imagespec import RenderContext


@pytest.fixture
def ctx():
    """4-color context using the bundled fonts/icons."""
    return RenderContext(palette="4")


@pytest.fixture
def bw_ctx():
    """2-color (black/white) context."""
    return RenderContext(palette="bw")


@pytest.fixture
def history_ctx():
    """4-color context with a deterministic fake history provider for `plot`."""

    class _State:  # mimics a HA State object (only the first element is one)
        def __init__(self, value, changed):
            self.state = value
            self.last_changed = changed

    from datetime import timedelta

    def provider(entity_ids, start, end):
        result = {}
        for eid in entity_ids:
            first = _State("10", start)
            rest = [
                {"state": str(10 + (i % 6)), "last_changed": (start + timedelta(hours=i)).isoformat()}
                for i in range(1, 24)
            ]
            result[eid] = [first] + rest
        return result

    return RenderContext(palette="4", history_provider=provider)


@pytest.fixture(scope="session")
def data_url():
    """A tiny in-memory PNG as a base64 data URL (for `dlimg` without network)."""
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), (255, 0, 0)).save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
