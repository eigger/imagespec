"""Optional font resolvers."""

from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from imagespec import GOOGLE_FONTS_SOURCES, chain_resolvers, directory_resolver, google_fonts_resolver
from imagespec.context import BUNDLED_FONTS_DIR
from imagespec.resolvers import caching_resolver


def test_directory_resolver_hit():
    r = directory_resolver(BUNDLED_FONTS_DIR)
    assert r("NotoSansKR-Regular.ttf") == os.path.join(BUNDLED_FONTS_DIR, "NotoSansKR-Regular.ttf")


def test_directory_resolver_miss():
    assert directory_resolver(BUNDLED_FONTS_DIR)("nope.ttf") is None


def test_chain_picks_first_hit():
    r = chain_resolvers(
        directory_resolver("/no/such/dir"),
        directory_resolver(BUNDLED_FONTS_DIR),
    )
    assert r("NotoSansKR-Regular.ttf") == os.path.join(BUNDLED_FONTS_DIR, "NotoSansKR-Regular.ttf")


def test_chain_all_miss():
    r = chain_resolvers(directory_resolver("/no/such/dir"), None)
    assert r("NotoSansKR-Regular.ttf") is None


def test_caching_resolver_unknown_returns_none(tmp_path):
    r = caching_resolver(str(tmp_path), sources={})
    assert r("whatever.ttf") is None


def test_caching_resolver_uses_existing_cache(tmp_path):
    # pre-seed the cache; resolver should return it without any download
    cached = tmp_path / "Seed.ttf"
    cached.write_bytes(b"not really a font")
    r = caching_resolver(str(tmp_path), sources={"Seed.ttf": "http://example/should-not-fetch"})
    assert r("Seed.ttf") == str(cached)


def test_google_fonts_sources_cover_expected_scripts():
    # a sanity check on the preset table itself, not network access
    for name in (
        "NotoSans-Regular.ttf",
        "NotoSansJP-Regular.ttf",
        "NotoSansSC-Regular.ttf",
        "NotoSansTC-Regular.ttf",
        "NotoSansArabic-Regular.ttf",
        "NotoSansThai-Regular.ttf",
    ):
        assert name in GOOGLE_FONTS_SOURCES
        url = GOOGLE_FONTS_SOURCES[name]
        assert url.startswith("https://raw.githubusercontent.com/google/fonts/main/ofl/")
        assert url.endswith(".ttf")


def test_google_fonts_resolver_uses_existing_cache(tmp_path):
    # same caching behaviour as caching_resolver, pre-seeded so no network is hit
    cached = tmp_path / "NotoSansJP-Regular.ttf"
    cached.write_bytes(b"not really a font")
    r = google_fonts_resolver(str(tmp_path))
    assert r("NotoSansJP-Regular.ttf") == str(cached)


def test_google_fonts_resolver_families_filter_excludes_others(tmp_path):
    r = google_fonts_resolver(str(tmp_path), families=["NotoSansJP-Regular.ttf"])
    # not in the filtered subset, and not cached -> no source to fetch from -> None
    assert r("NotoSansArabic-Regular.ttf") is None


FONT_BYTES = Path(BUNDLED_FONTS_DIR, "NotoSansKR-Regular.ttf").read_bytes()


class FakeResponse:
    """Minimal streaming ``requests.Response`` stand-in."""

    def __init__(self, content=b"", headers=None, chunks=None):
        self._chunks = chunks if chunks is not None else [content]
        self.headers = headers or {}
        self.closed = False

    def raise_for_status(self):
        pass

    def iter_content(self, size):
        yield from self._chunks

    def close(self):
        self.closed = True


class FakeSession:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.calls = response, error, 0

    def get(self, url, timeout, stream=False):
        self.calls += 1
        if self.error:
            raise self.error
        return self.response


def _session(content):
    return FakeSession(FakeResponse(content))


def test_caching_resolver_rejects_non_font_download(tmp_path, caplog):
    r = caching_resolver(str(tmp_path), {"f.ttf": "https://x/f"}, session=_session(b"<html>portal</html>"))
    assert r("f.ttf") is None
    assert list(tmp_path.iterdir()) == []  # nothing cached, so a later good download can succeed
    assert "not a usable font" in caplog.text


def test_caching_resolver_rejects_oversized_download(tmp_path, caplog):
    r = caching_resolver(str(tmp_path), {"f.ttf": "https://x/f"}, session=_session(FONT_BYTES), max_bytes=1000)
    assert r("f.ttf") is None
    assert list(tmp_path.iterdir()) == []
    assert "exceeds 1000 bytes" in caplog.text


def test_caching_resolver_allows_concurrent_cold_downloads(tmp_path):
    barrier = threading.Barrier(2)

    class Session:
        @staticmethod
        def get(url, timeout, stream=False):
            barrier.wait(timeout=2)
            return FakeResponse(FONT_BYTES)

    resolver = caching_resolver(str(tmp_path), {"font.ttf": "https://example.test/font.ttf"}, session=Session())
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(resolver, ["font.ttf", "font.ttf"]))
    assert results == [str(tmp_path / "font.ttf")] * 2
    assert (tmp_path / "font.ttf").read_bytes() == FONT_BYTES
    assert sorted(p.name for p in tmp_path.iterdir()) == ["font.ttf"]


def test_google_fonts_resolver_rejects_unknown_family(tmp_path):
    import pytest

    from imagespec.resolvers import google_fonts_resolver

    with pytest.raises(ValueError, match="Nope.ttf"):
        google_fonts_resolver(str(tmp_path), families=["Nope.ttf"])


def test_caching_resolver_stops_streaming_past_the_limit(tmp_path):
    consumed = []

    def endless():
        while True:
            consumed.append(1)
            yield b"x" * 1024

    resp = FakeResponse(chunks=endless())
    r = caching_resolver(str(tmp_path), {"f.ttf": "https://x/f"}, session=FakeSession(resp), max_bytes=4096)
    assert r("f.ttf") is None
    assert len(consumed) <= 6 and resp.closed  # aborted early, nothing buffered beyond the cap
    assert list(tmp_path.iterdir()) == []


def test_caching_resolver_rejects_declared_oversize_without_reading(tmp_path):
    resp = FakeResponse(chunks=[], headers={"Content-Length": "999999"})
    r = caching_resolver(str(tmp_path), {"f.ttf": "https://x/f"}, session=FakeSession(resp), max_bytes=1000)
    assert r("f.ttf") is None and resp.closed


def test_caching_resolver_remembers_failures_for_the_ttl(tmp_path):
    import requests

    session = FakeSession(error=requests.ConnectionError("offline"))
    r = caching_resolver(str(tmp_path), {"f.ttf": "https://x/f"}, session=session, failure_ttl=60)
    assert r("f.ttf") is None and r("f.ttf") is None
    assert session.calls == 1  # second render did not wait on the network again


def test_caching_resolver_retries_after_the_ttl(tmp_path, monkeypatch):
    import requests

    import imagespec.resolvers as mod

    now = [1000.0]
    monkeypatch.setattr(mod.time, "monotonic", lambda: now[0])
    session = FakeSession(error=requests.ConnectionError("offline"))
    r = caching_resolver(str(tmp_path), {"f.ttf": "https://x/f"}, session=session, failure_ttl=60)
    r("f.ttf")
    now[0] += 61
    session.error, session.response = None, FakeResponse(FONT_BYTES)
    assert r("f.ttf") == str(tmp_path / "f.ttf")
    assert session.calls == 2


def test_caching_resolver_ttl_zero_retries_every_call(tmp_path):
    import requests

    session = FakeSession(error=requests.ConnectionError("offline"))
    r = caching_resolver(str(tmp_path), {"f.ttf": "https://x/f"}, session=session, failure_ttl=0)
    r("f.ttf")
    r("f.ttf")
    assert session.calls == 2
