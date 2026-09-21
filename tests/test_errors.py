"""Error handling: missing required args, dlimg policy, invalid inputs."""

from __future__ import annotations

import pytest

from imagespec import RenderContext, RenderError, render


@pytest.mark.parametrize(
    "element, missing",
    [
        ({"type": "text", "y": 1}, ["x", "value"]),
        ({"type": "rectangle", "x_start": 0, "y_start": 0, "y_end": 9}, ["x_end"]),
        ({"type": "qrcode", "x": 0, "y": 0}, ["data"]),
        ({"type": "icon", "x": 0, "y": 0, "value": "mdi:home"}, ["size"]),
        ({"type": "gauge", "x": 0, "y": 0, "radius": 5}, ["progress"]),
        ({"type": "multiline", "x": 0, "value": "a,b", "delimiter": ","}, ["offset_y"]),
    ],
)
def test_missing_required_args_named_in_error(ctx, element, missing):
    with pytest.raises(RenderError) as exc:
        render([element], 20, 20, context=ctx)
    for key in missing:
        assert key in str(exc.value)


def test_dlimg_local_path_blocked_by_default(ctx):
    el = {"type": "dlimg", "x": 0, "y": 0, "url": "some/local.png", "xsize": 8, "ysize": 8}
    with pytest.raises(RenderError):
        render([el], 20, 20, context=ctx)


def test_dlimg_local_path_allowed_when_opted_in(tmp_path):
    # create a real local image and allow it
    from PIL import Image

    p = tmp_path / "x.png"
    Image.new("RGB", (4, 4), (0, 0, 0)).save(p)
    ctx = RenderContext(palette="4", allow_local_images=True)
    el = {"type": "dlimg", "x": 0, "y": 0, "url": str(p), "xsize": 8, "ysize": 8}
    assert render([el], 20, 20, context=ctx).size == (20, 20)


def test_invalid_barcode_code_raises(ctx):
    el = {"type": "barcode", "x": 0, "y": 0, "data": "123", "code": "not-a-real-symbology"}
    with pytest.raises(RenderError):
        render([el], 40, 40, context=ctx)


def test_progress_bar_bad_direction_raises(ctx):
    # used to silently draw an empty bar
    el = {"type": "progress_bar", "x_start": 0, "y_start": 0, "x_end": 19, "y_end": 9, "progress": 50}
    el["direction"] = "up!"
    with pytest.raises(RenderError, match="direction"):
        render([el], 20, 20, context=ctx)


def test_polygon_bad_points_raises(ctx):
    el = {"type": "polygon", "points": "garbage"}
    with pytest.raises(RenderError):
        render([el], 20, 20, context=ctx)


def test_handler_error_wrapped_with_element_context(ctx):
    # a non-numeric coordinate triggers a PIL/TypeError deep inside the handler;
    # the loop should surface it as a RenderError naming the element index/type.
    el = {"type": "rectangle", "x_start": "oops", "y_start": 0, "x_end": 9, "y_end": 9}
    with pytest.raises(RenderError) as exc:
        render([{"type": "line", "x_start": 0, "x_end": 5}, el], 20, 20, context=ctx)
    msg = str(exc.value)
    assert "#1" in msg and "rectangle" in msg


def test_diagram_too_small_raises(ctx):
    el = {
        "type": "diagram",
        "x": 0,
        "y": 0,
        "height": 30,
        "width": 30,
        "bars": {"values": "a,1;b,2;c,3", "color": "black", "margin": 20},
    }
    with pytest.raises(RenderError):
        render([el], 40, 40, context=ctx)


def test_plot_without_history_provider_raises(ctx):
    el = {"type": "plot", "data": [{"entity": "sensor.x"}]}
    with pytest.raises(RenderError):
        render([el], 40, 40, context=ctx)


def test_diagram_missing_required_args(ctx):
    el = {"type": "diagram", "x": 0, "bars": {"values": "a,1", "color": "black"}}
    with pytest.raises(RenderError) as exc:
        render([el], 40, 40, context=ctx)
    assert "height" in str(exc.value)


def test_diagram_accepts_float_bar_values(ctx):
    el = {
        "type": "diagram",
        "x": 0,
        "y": 0,
        "height": 35,
        "width": 60,
        "bars": {"values": "a,1.5;b,2.5", "color": "black", "margin": 4},
    }
    assert render([el], 80, 40, context=ctx).size == (80, 40)


def test_diagram_nonpositive_max_raises(ctx):
    el = {
        "type": "diagram",
        "x": 0,
        "y": 0,
        "height": 35,
        "width": 60,
        "bars": {"values": "a,0;b,0", "color": "black", "margin": 4},
    }
    with pytest.raises(RenderError):
        render([el], 80, 40, context=ctx)


def test_group_child_error_wrapped_with_context(ctx):
    el = {
        "type": "group",
        "x": 0,
        "y": 0,
        "elements": [{"type": "rectangle", "x_start": "oops", "y_start": 0, "x_end": 9, "y_end": 9}],
    }
    with pytest.raises(RenderError) as exc:
        render([el], 20, 20, context=ctx)
    msg = str(exc.value)
    assert "group" in msg and "rectangle" in msg


# ── dlimg fetch: size cap, TTL cache, injected fetcher ─────────────────────


def _png_bytes(color=(255, 0, 0)):
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (4, 4), color).save(buf, format="PNG")
    return buf.getvalue()


def test_dlimg_uses_injected_fetcher_and_caches_within_ttl(monkeypatch):
    calls = []

    def fetcher(url):
        calls.append(url)
        return _png_bytes()

    ctx = RenderContext(palette="4", image_fetcher=fetcher, image_cache_ttl=60)
    el = {"type": "dlimg", "x": 0, "y": 0, "url": "https://example.test/logo.png", "xsize": 8, "ysize": 8}
    render([el], 20, 20, context=ctx)
    render([el], 20, 20, context=ctx)
    assert calls == ["https://example.test/logo.png"]  # second render served from cache

    import time

    now = time.monotonic()
    monkeypatch.setattr(time, "monotonic", lambda: now + 61)
    render([el], 20, 20, context=ctx)
    assert len(calls) == 2  # expired -> refetched


def test_dlimg_cache_off_by_default():
    calls = []
    ctx = RenderContext(palette="4", image_fetcher=lambda url: (calls.append(url), _png_bytes())[1])
    el = {"type": "dlimg", "x": 0, "y": 0, "url": "https://example.test/cam.jpg", "xsize": 8, "ysize": 8}
    render([el], 20, 20, context=ctx)
    render([el], 20, 20, context=ctx)
    assert len(calls) == 2


def test_dlimg_rejects_oversized_image_from_fetcher():
    ctx = RenderContext(palette="4", image_fetcher=lambda url: _png_bytes(), max_image_bytes=10)
    el = {"type": "dlimg", "x": 0, "y": 0, "url": "https://example.test/big.png", "xsize": 8, "ysize": 8}
    with pytest.raises(RenderError, match="max_image_bytes"):
        render([el], 20, 20, context=ctx)


class _FakeResponse:
    def __init__(self, body: bytes, content_length: int | None = None):
        self._body = body
        self.headers = {} if content_length is None else {"Content-Length": str(content_length)}

    def raise_for_status(self):
        pass

    def iter_content(self, chunk):
        for i in range(0, len(self._body), chunk):
            yield self._body[i : i + chunk]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_dlimg_download_streams_and_aborts_past_limit(monkeypatch):
    import requests

    body = b"\x00" * 5000
    monkeypatch.setattr(requests, "get", lambda url, timeout, stream: _FakeResponse(body))
    ctx = RenderContext(palette="4", max_image_bytes=4096)
    with pytest.raises(RenderError, match="download aborted"):
        ctx.fetch_image("https://example.test/x.png")


def test_dlimg_download_rejects_declared_content_length(monkeypatch):
    import requests

    monkeypatch.setattr(requests, "get", lambda url, timeout, stream: _FakeResponse(b"", content_length=10**9))
    ctx = RenderContext(palette="4")
    with pytest.raises(RenderError, match="over max_image_bytes"):
        ctx.fetch_image("https://example.test/x.png")


def test_dlimg_download_success_path(monkeypatch):
    import requests

    png = _png_bytes()
    monkeypatch.setattr(requests, "get", lambda url, timeout, stream: _FakeResponse(png, content_length=len(png)))
    ctx = RenderContext(palette="4")
    el = {"type": "dlimg", "x": 0, "y": 0, "url": "https://example.test/ok.png", "xsize": 8, "ysize": 8}
    img = render([el], 20, 20, context=ctx)
    assert img.getpixel((2, 2)) == (255, 0, 0)


def test_image_cache_refresh_of_expired_url_does_not_evict_others(monkeypatch):
    import time

    from imagespec.context import _IMAGE_CACHE_MAX_ENTRIES

    ctx = RenderContext(palette="4", image_fetcher=lambda url: _png_bytes(), image_cache_ttl=10)
    urls = [f"https://example.test/{i}.png" for i in range(_IMAGE_CACHE_MAX_ENTRIES)]
    for u in urls:
        ctx.fetch_image(u)
    assert set(ctx._image_cache) == set(urls)  # full
    now = time.monotonic()
    monkeypatch.setattr(time, "monotonic", lambda: now + 11)  # everything expired
    ctx.fetch_image(urls[0])  # refresh in place
    assert set(ctx._image_cache) == set(urls)  # nothing else evicted
    ctx.fetch_image("https://example.test/new.png")  # genuinely new -> one eviction
    assert len(ctx._image_cache) == _IMAGE_CACHE_MAX_ENTRIES
    assert "https://example.test/new.png" in ctx._image_cache
