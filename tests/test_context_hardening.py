"""Hardening tests for RenderContext font resolution and thread-safe caches."""

from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from imagespec import RenderContext, RenderError, render
from imagespec import context as ctxmod
from imagespec.context import _IMAGE_CACHE_MAX_ENTRIES, BUNDLED_FONTS_DIR, FONT_CACHE_SIZE


@pytest.mark.parametrize("bad_name", [".", "/", "..", "README.md", "OFL.txt", ""])
def test_resolve_font_path_falls_back_on_directories_and_non_font_bundled_files(monkeypatch, bad_name):
    monkeypatch.setattr(ctxmod, "_WARNED_FONTS", set())
    ctx = RenderContext()
    expected = os.path.join(BUNDLED_FONTS_DIR, "NotoSansKR-Regular.ttf")
    assert ctx.resolve_font_path(bad_name) == expected
    img = render([{"type": "text", "x": 0, "y": 0, "value": "hi", "font": bad_name}], 30, 20, context=ctx)
    assert img.size == (30, 20)


def test_resolve_font_path_skips_directory_from_font_resolver(tmp_path, monkeypatch):
    monkeypatch.setattr(ctxmod, "_WARNED_FONTS", set())
    ctx = RenderContext(font_resolver=lambda _name: str(tmp_path))
    expected = os.path.join(BUNDLED_FONTS_DIR, "NotoSansKR-Regular.ttf")
    assert ctx.resolve_font_path("any.ttf") == expected


def test_custom_default_font_resolved_via_font_resolver_is_used_as_fallback(tmp_path, caplog, monkeypatch):
    monkeypatch.setattr(ctxmod, "_WARNED_FONTS", set())
    custom_font = tmp_path / "custom.ttf"
    custom_font.write_bytes(Path(BUNDLED_FONTS_DIR, "NotoSansKR-Regular.ttf").read_bytes())

    ctx = RenderContext(
        default_font="custom.ttf",
        font_resolver=lambda name: str(custom_font) if name == "custom.ttf" else None,
    )
    with caplog.at_level(logging.WARNING, logger="imagespec.context"):
        assert ctx.resolve_font_path("missing-font.ttf") == str(custom_font)
        assert ctx.resolve_font_path(None) == str(custom_font)
    assert "missing-font.ttf" in caplog.text


def test_resolve_font_path_raises_when_default_font_also_unavailable(tmp_path):
    ctx = RenderContext(default_font="nonexistent.ttf", font_resolver=lambda _n: str(tmp_path))
    with pytest.raises(RenderError, match="nonexistent.ttf"):
        ctx.resolve_font_path("missing.ttf")


def test_render_context_font_cache_is_thread_safe_under_eviction():
    ctx = RenderContext()

    def worker(idx: int) -> None:
        # Exceed FONT_CACHE_SIZE (256) concurrently across threads to exercise LRU eviction.
        for offset in range(12):
            size = 8 + ((idx * 12 + offset) % 300)
            font = ctx.font(None, size)
            assert font.size == size

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(worker, range(32)))
    assert len(ctx._font_cache) == FONT_CACHE_SIZE


def test_render_context_image_cache_is_thread_safe_under_eviction():
    def fetcher(url: str) -> bytes:
        return url.encode()

    ctx = RenderContext(image_fetcher=fetcher, image_cache_ttl=60.0)

    def worker(idx: int) -> None:
        # Exceed _IMAGE_CACHE_MAX_ENTRIES (32) concurrently across threads.
        for j in range(10):
            url = f"https://example.test/{(idx * 10 + j) % 48}.png"
            assert ctx.fetch_image(url) == url.encode()

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(worker, range(16)))
    assert len(ctx._image_cache) == _IMAGE_CACHE_MAX_ENTRIES
