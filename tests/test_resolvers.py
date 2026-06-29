"""Optional font resolvers."""

from __future__ import annotations

import os

from imagespec import chain_resolvers, directory_resolver
from imagespec.context import BUNDLED_FONTS_DIR
from imagespec.resolvers import caching_resolver


def test_directory_resolver_hit():
    r = directory_resolver(BUNDLED_FONTS_DIR)
    assert r("ppb.ttf") == os.path.join(BUNDLED_FONTS_DIR, "ppb.ttf")


def test_directory_resolver_miss():
    assert directory_resolver(BUNDLED_FONTS_DIR)("nope.ttf") is None


def test_chain_picks_first_hit():
    r = chain_resolvers(
        directory_resolver("/no/such/dir"),
        directory_resolver(BUNDLED_FONTS_DIR),
    )
    assert r("ppb.ttf") == os.path.join(BUNDLED_FONTS_DIR, "ppb.ttf")


def test_chain_all_miss():
    r = chain_resolvers(directory_resolver("/no/such/dir"), None)
    assert r("ppb.ttf") is None


def test_caching_resolver_unknown_returns_none(tmp_path):
    r = caching_resolver(str(tmp_path), sources={})
    assert r("whatever.ttf") is None


def test_caching_resolver_uses_existing_cache(tmp_path):
    # pre-seed the cache; resolver should return it without any download
    cached = tmp_path / "Seed.ttf"
    cached.write_bytes(b"not really a font")
    r = caching_resolver(str(tmp_path), sources={"Seed.ttf": "http://example/should-not-fetch"})
    assert r("Seed.ttf") == str(cached)
