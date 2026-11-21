"""Hardening tests for RenderContext font resolution and thread-safe caches."""

from __future__ import annotations

import copy
import dataclasses
import logging
import os
import pickle
import threading
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


def test_render_context_supports_deepcopy_pickle_and_asdict():
    ctx = RenderContext()
    as_dict = dataclasses.asdict(ctx)
    assert "_lock" not in as_dict
    assert "_fetch_seq" not in as_dict
    assert "_image_cache_seq" not in as_dict

    deep_ctx = copy.deepcopy(ctx)
    assert deep_ctx._lock is not ctx._lock
    assert deep_ctx.font(None, 12).size == 12

    unpickled = pickle.loads(pickle.dumps(ctx))
    assert unpickled._lock is not ctx._lock
    assert unpickled.font(None, 12).size == 12

    # Copied/unpickled contexts also keep fetch_image functional without sharing locks.
    deep_ctx.image_cache_ttl = 10.0
    deep_ctx.image_fetcher = lambda _url: b"ok"
    assert deep_ctx.fetch_image("https://example.test/a.png") == b"ok"


def test_fetch_image_overlapping_stale_response_does_not_overwrite_newer():
    req1_started = threading.Event()
    req2_finished = threading.Event()
    calls = 0
    calls_lock = threading.Lock()

    def fetcher(_url: str) -> bytes:
        nonlocal calls
        with calls_lock:
            calls += 1
            idx = calls
        if idx == 1:
            req1_started.set()
            assert req2_finished.wait(timeout=5)
            return b"stale"
        if idx == 2:
            return b"fresh"
        return b"unexpected"

    ctx = RenderContext(image_fetcher=fetcher, image_cache_ttl=60.0)
    url = "https://example.test/race.png"

    with ThreadPoolExecutor(max_workers=2) as pool:
        fut1 = pool.submit(ctx.fetch_image, url)
        assert req1_started.wait(timeout=5)
        fut2 = pool.submit(ctx.fetch_image, url)
        assert fut2.result(timeout=5) == b"fresh"
        req2_finished.set()
        assert fut1.result(timeout=5) == b"stale"

    # Subsequent fetch must serve the newer cached response, not the late stale one.
    assert ctx.fetch_image(url) == b"fresh"
    assert calls == 2


def test_fetch_image_slow_request_beyond_ttl_does_not_refresh_ttl(monkeypatch):
    clock = 100.0
    monkeypatch.setattr(ctxmod.time, "monotonic", lambda: clock)
    calls = 0

    def slow_fetcher(_url: str) -> bytes:
        nonlocal clock, calls
        calls += 1
        if calls == 1:
            clock += 12.0  # exceeds ttl=10.0 while download is in flight
            return b"slow"
        return b"fresh"

    ctx = RenderContext(image_fetcher=slow_fetcher, image_cache_ttl=10.0)
    url = "https://example.test/slow.png"
    assert ctx.fetch_image(url) == b"slow"
    assert url not in ctx._image_cache
    assert ctx.fetch_image(url) == b"fresh"
    assert calls == 2


def test_shallow_copy_context_can_refresh_expired_image_cache(monkeypatch):
    clock = 100.0
    monkeypatch.setattr(ctxmod.time, "monotonic", lambda: clock)
    payload = b"v1"
    calls = 0

    def fetcher(_url: str) -> bytes:
        nonlocal calls
        calls += 1
        return payload

    url = "https://example.test/logo.png"
    ctx = RenderContext(image_fetcher=fetcher, image_cache_ttl=10.0)
    assert ctx.fetch_image(url) == b"v1"
    assert calls == 1

    copied = copy.copy(ctx)
    assert copied._image_cache is not ctx._image_cache
    assert copied._image_cache_seq is not ctx._image_cache_seq
    assert copied._font_cache is not ctx._font_cache
    assert copied._lock is not ctx._lock

    # Advance past TTL and refresh on the shallow copy: cache must update with v2.
    clock += 11.0
    payload = b"v2"
    assert copied.fetch_image(url) == b"v2"
    assert copied.fetch_image(url) == b"v2"
    assert calls == 2
    # Original retains its own expired v1 cache until refreshed independently.
    payload = b"v3"
    assert ctx.fetch_image(url) == b"v3"
    assert calls == 3
    assert copied.fetch_image(url) == b"v2"

    # Copying before fetching also gives independent cache/sequence state.
    fresh_orig = RenderContext(image_fetcher=fetcher, image_cache_ttl=10.0)
    fresh_copy = copy.copy(fresh_orig)
    assert fresh_copy._image_cache is not fresh_orig._image_cache
    assert fresh_copy._lock is not fresh_orig._lock
    assert fresh_orig.fetch_image(url) == b"v3"
    assert calls == 4
    clock += 11.0
    payload = b"v4"
    assert fresh_copy.fetch_image(url) == b"v4"
    assert fresh_copy.fetch_image(url) == b"v4"
    assert calls == 5
