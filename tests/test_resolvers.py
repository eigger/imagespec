"""Optional font resolvers."""

from __future__ import annotations

import os

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
