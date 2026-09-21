"""Palette dithering for limited-color (e-ink / label) panels.

Elements are drawn in full color; this module maps an RGB image onto a device
palette. Supported methods are those with medium-or-better suitability for
e-ink: error-diffusion kernels (serpentine scan) and ordered/threshold screens.

``none`` uses Pillow's C ``quantize`` path (fast default). Other methods are
implemented here — Pillow only ships working Floyd–Steinberg, and we keep a
serpentine Python FS for e-ink quality.

numpy is optional (``pip install imagespec[fast]``). With it, ordered screens
are fully vectorised and error diffusion pushes error to the rows below with
array ops; without it the same algorithms run in pure Python. Both paths are
bit-identical — every error cell receives the same float operands in the same
order — and the test-suite asserts that.
"""

from __future__ import annotations

from PIL import Image

try:
    import numpy as np
except ImportError:  # pragma: no cover - exercised by the pure-Python tests via monkeypatch
    np = None

# ── Public method names ────────────────────────────────────────────────────

DITHER_NONE = "none"
DITHER_FLOYD = "floyd"
DITHER_ATKINSON = "atkinson"
DITHER_JARVIS = "jarvis"
DITHER_STUCKI = "stucki"
DITHER_BURKES = "burkes"
DITHER_SIERRA = "sierra"
DITHER_SIERRA2 = "sierra2"
DITHER_SIERRA_LITE = "sierra-lite"
DITHER_STEVENSON_ARCE = "stevenson-arce"
DITHER_BAYER2 = "bayer2"
DITHER_BAYER4 = "bayer4"
DITHER_BAYER8 = "bayer8"
DITHER_BAYER16 = "bayer16"
DITHER_CLUSTERED4 = "clustered4"
DITHER_CLUSTERED8 = "clustered8"

DITHER_METHODS: tuple[str, ...] = (
    DITHER_NONE,
    DITHER_FLOYD,
    DITHER_ATKINSON,
    DITHER_JARVIS,
    DITHER_STUCKI,
    DITHER_BURKES,
    DITHER_SIERRA,
    DITHER_SIERRA2,
    DITHER_SIERRA_LITE,
    DITHER_STEVENSON_ARCE,
    DITHER_BAYER2,
    DITHER_BAYER4,
    DITHER_BAYER8,
    DITHER_BAYER16,
    DITHER_CLUSTERED4,
    DITHER_CLUSTERED8,
)

# Align crop origins so ordered screens keep absolute phase (see dispatch).
# Must be a multiple of every ordered matrix size we ship (currently 2/4/8/16
# and clustered 4/8 — LCM is 16). A non-multiple (e.g. align=16 with a future
# 6×6 screen) silently breaks crop phase even if align >= matrix size.
ORDERED_ORIGIN_ALIGN = 16

# Error-diffusion kernels: ((dx, dy, weight), ...), divisor.
# Weights follow the classic literature tables (Tanner Helland / Ulichney).
# Atkinson intentionally diffuses only 6/8 of the error (sum != divisor).
_KERNELS: dict[str, tuple[tuple[tuple[int, int, int], ...], int]] = {
    DITHER_FLOYD: (
        ((1, 0, 7), (-1, 1, 3), (0, 1, 5), (1, 1, 1)),
        16,
    ),
    DITHER_ATKINSON: (
        ((1, 0, 1), (2, 0, 1), (-1, 1, 1), (0, 1, 1), (1, 1, 1), (0, 2, 1)),
        8,
    ),
    DITHER_JARVIS: (
        (
            (1, 0, 7),
            (2, 0, 5),
            (-2, 1, 3),
            (-1, 1, 5),
            (0, 1, 7),
            (1, 1, 5),
            (2, 1, 3),
            (-2, 2, 1),
            (-1, 2, 3),
            (0, 2, 5),
            (1, 2, 3),
            (2, 2, 1),
        ),
        48,
    ),
    DITHER_STUCKI: (
        (
            (1, 0, 8),
            (2, 0, 4),
            (-2, 1, 2),
            (-1, 1, 4),
            (0, 1, 8),
            (1, 1, 4),
            (2, 1, 2),
            (-2, 2, 1),
            (-1, 2, 2),
            (0, 2, 4),
            (1, 2, 2),
            (2, 2, 1),
        ),
        42,
    ),
    DITHER_BURKES: (
        (
            (1, 0, 8),
            (2, 0, 4),
            (-2, 1, 2),
            (-1, 1, 4),
            (0, 1, 8),
            (1, 1, 4),
            (2, 1, 2),
        ),
        32,
    ),
    DITHER_SIERRA: (
        (
            (1, 0, 5),
            (2, 0, 3),
            (-2, 1, 2),
            (-1, 1, 4),
            (0, 1, 5),
            (1, 1, 4),
            (2, 1, 2),
            (-1, 2, 2),
            (0, 2, 3),
            (1, 2, 2),
        ),
        32,
    ),
    DITHER_SIERRA2: (
        (
            (1, 0, 4),
            (2, 0, 3),
            (-2, 1, 1),
            (-1, 1, 2),
            (0, 1, 3),
            (1, 1, 2),
            (2, 1, 1),
        ),
        16,
    ),
    DITHER_SIERRA_LITE: (
        ((1, 0, 2), (-1, 1, 1), (0, 1, 1)),
        4,
    ),
    # Stevenson–Arce half-sample offsets (odd dx); weights sum to divisor 200.
    DITHER_STEVENSON_ARCE: (
        (
            (2, 0, 32),
            (-3, 1, 12),
            (-1, 1, 26),
            (1, 1, 30),
            (3, 1, 16),
            (-2, 2, 12),
            (0, 2, 26),
            (2, 2, 12),
            (-3, 3, 5),
            (-1, 3, 12),
            (1, 3, 12),
            (3, 3, 5),
        ),
        200,
    ),
}

# Clustered-dot threshold matrices (Ulichney-style ranks, 0 .. n²-1).
_CLUSTERED4: tuple[tuple[int, ...], ...] = (
    (12, 5, 6, 13),
    (4, 0, 1, 7),
    (11, 3, 2, 8),
    (15, 10, 9, 14),
)

_CLUSTERED8: tuple[tuple[int, ...], ...] = (
    (24, 10, 12, 26, 35, 47, 49, 37),
    (8, 0, 2, 14, 45, 59, 61, 51),
    (22, 6, 4, 16, 43, 57, 63, 53),
    (30, 20, 18, 28, 33, 41, 55, 39),
    (34, 46, 48, 36, 25, 11, 13, 27),
    (44, 58, 60, 50, 9, 1, 3, 15),
    (42, 56, 62, 52, 23, 7, 5, 17),
    (32, 40, 54, 38, 31, 21, 19, 29),
)

_ALIASES: dict[str, str] = {
    "off": DITHER_NONE,
    "false": DITHER_NONE,
    "nearest": DITHER_NONE,
    "on": DITHER_FLOYD,
    "true": DITHER_FLOYD,
    "floyd-steinberg": DITHER_FLOYD,
    "fs": DITHER_FLOYD,
    "jjn": DITHER_JARVIS,
    "jarvis-judice-ninke": DITHER_JARVIS,
    "sierra3": DITHER_SIERRA,
    "sierra-3": DITHER_SIERRA,
    "two-row-sierra": DITHER_SIERRA2,
    "sierra-2": DITHER_SIERRA2,
    "sierralite": DITHER_SIERRA_LITE,
    "stevenson": DITHER_STEVENSON_ARCE,
    "bayer": DITHER_BAYER8,
    "bayer2x2": DITHER_BAYER2,
    "bayer4x4": DITHER_BAYER4,
    "bayer8x8": DITHER_BAYER8,
    "bayer16x16": DITHER_BAYER16,
    "ordered": DITHER_BAYER8,
    "clustered": DITHER_CLUSTERED8,
    "clustered-dot": DITHER_CLUSTERED8,
    "clustered-dot-4": DITHER_CLUSTERED4,
    "clustered-dot-8": DITHER_CLUSTERED8,
}


def resolve_dither_method(dither: bool | str | int | None) -> str:
    """Normalize a ``dither`` flag/name to a canonical method id.

    Accepts JSON-friendly values hosts often send:

    * ``True`` / ``1`` → ``"floyd"``
    * ``False`` / ``0`` / ``None`` → ``"none"``
    * method name (or alias) string
    """
    if dither is None:
        return DITHER_NONE
    if isinstance(dither, bool):
        return DITHER_FLOYD if dither else DITHER_NONE
    if isinstance(dither, int):
        return DITHER_FLOYD if dither else DITHER_NONE
    if isinstance(dither, str):
        key = dither.strip().lower().replace("_", "-")
        key = _ALIASES.get(key, key)
        if key in DITHER_METHODS:
            return key
        known = ", ".join(DITHER_METHODS)
        raise ValueError(f"unknown dither method {dither!r}; expected one of: {known}")
    raise TypeError(f"dither must be bool, str, int, or None, got {type(dither).__name__}")


def _palette_rgbs(palette) -> list[tuple[int, int, int]]:
    return [tuple(c[:3]) for c in palette]  # type: ignore[misc]


def _palette_image(palette) -> Image.Image:
    """Build a 'P'-mode image whose palette is ``palette`` (list of RGBA/RGB)."""
    rgbs = _palette_rgbs(palette)
    flat: list[int] = []
    for c in rgbs:
        flat.extend(c)
    pad = list(rgbs[0])
    while len(flat) < 768:
        flat.extend(pad)
    pal_img = Image.new("P", (1, 1))
    pal_img.putpalette(flat)
    return pal_img


def _nearest(r: float, g: float, b: float, palette: list[tuple[int, int, int]]) -> tuple[int, int, int]:
    best = palette[0]
    best_d = float("inf")
    for pr, pg, pb in palette:
        d = (r - pr) * (r - pr) + (g - pg) * (g - pg) + (b - pb) * (b - pb)
        if d < best_d:
            best_d = d
            best = (pr, pg, pb)
    return best


def _bayer_matrix(order: int) -> list[list[int]]:
    """Build a Bayer threshold matrix of size ``order`` × ``order`` (power of two)."""
    if order < 2 or order & (order - 1):
        raise ValueError(f"Bayer order must be a power of two >= 2, got {order}")
    matrix: list[list[int]] = [[0, 2], [3, 1]]
    size = 2
    while size < order:
        n = size * 2
        nxt = [[0] * n for _ in range(n)]
        for y in range(size):
            for x in range(size):
                v = matrix[y][x] * 4
                nxt[y][x] = v
                nxt[y][x + size] = v + 2
                nxt[y + size][x] = v + 3
                nxt[y + size][x + size] = v + 1
        matrix = nxt
        size = n
    return matrix


def _quantize_nearest_pillow(img: Image.Image, palette) -> Image.Image:
    """Fast flat snap via Pillow's C quantize path."""
    rgb = img.convert("RGB")
    pal_img = _palette_image(palette)
    return rgb.quantize(palette=pal_img, dither=Image.Dither.NONE).convert("RGB")


_INF = float("inf")


def _error_diffuse(
    img: Image.Image,
    palette: list[tuple[int, int, int]],
    kernel: tuple[tuple[int, int, int], ...],
    divisor: int,
    *,
    serpentine: bool = True,
) -> Image.Image:
    """Serpentine error diffusion onto ``palette`` (numpy-assisted when available)."""
    if np is not None:
        return _error_diffuse_np(img, palette, kernel, divisor, serpentine=serpentine)
    return _error_diffuse_py(img, palette, kernel, divisor, serpentine=serpentine)


def _scan_row(data, out, base, xs, er_row, eg_row, eb_row, pal, same, w):
    """Quantize one row in scan order, applying same-row taps as it goes.

    Returns the per-pixel error (three lists) for the taps that reach the rows
    below. The inner loop is the hot spot of every error-diffusion method, so it
    reads the source bytes directly and inlines the nearest-color search.
    """
    e_r = [0.0] * w
    e_g = [0.0] * w
    e_b = [0.0] * w
    for x in xs:
        i = base + x * 3
        r = data[i] + er_row[x]
        g = data[i + 1] + eg_row[x]
        b = data[i + 2] + eb_row[x]
        best = pal[0]
        best_d = _INF
        for c in pal:
            pr, pg, pb = c
            d = (r - pr) * (r - pr) + (g - pg) * (g - pg) + (b - pb) * (b - pb)
            if d < best_d:
                best_d = d
                best = c
        nr, ng, nb = best
        out[i] = nr
        out[i + 1] = ng
        out[i + 2] = nb
        er = r - nr
        eg = g - ng
        eb = b - nb
        if er == 0.0 and eg == 0.0 and eb == 0.0:
            continue
        e_r[x] = er
        e_g[x] = eg
        e_b[x] = eb
        for dx, f in same:
            nx = x + dx
            if 0 <= nx < w:
                er_row[nx] += er * f
                eg_row[nx] += eg * f
                eb_row[nx] += eb * f
    return e_r, e_g, e_b


def _split_kernel(kernel, divisor):
    """Kernel taps with ``weight / divisor`` precomputed, split by row.

    Returns ``(same_lr, same_rl, below_lr, below_rl)``. The "below" lists are
    ordered so that adding them tap by tap reproduces the per-cell accumulation
    order of a pixel-by-pixel scan (the pixel feeding cell ``nx`` is
    ``nx - dx``, so left-to-right pixel order is descending ``dx``).
    """
    taps = [(dx, dy, weight / divisor) for dx, dy, weight in kernel]
    same_lr = [(dx, f) for dx, dy, f in taps if dy == 0]
    same_rl = [(-dx, f) for dx, f in same_lr]
    below = [(dx, dy, f) for dx, dy, f in taps if dy > 0]
    below_lr = sorted(below, key=lambda t: -t[0])
    below_rl = sorted([(-dx, dy, f) for dx, dy, f in below], key=lambda t: t[0])
    return same_lr, same_rl, below_lr, below_rl


def _error_diffuse_np(img, palette, kernel, divisor, *, serpentine=True):
    src = img.convert("RGB")
    w, h = src.size
    data = src.tobytes()
    out = bytearray(len(data))
    pal = [tuple(c) for c in palette]
    same_lr, same_rl, below_lr, below_rl = _split_kernel(kernel, divisor)
    max_dy = max((dy for _, dy, _ in kernel), default=0)
    err = np.zeros((h + max_dy, w, 3), dtype=np.float64)

    for y in range(h):
        ltr = (not serpentine) or (y % 2 == 0)
        er_row, eg_row, eb_row = err[y].T.tolist()
        xs = range(w) if ltr else range(w - 1, -1, -1)
        e_r, e_g, e_b = _scan_row(data, out, y * w * 3, xs, er_row, eg_row, eb_row, pal, same_lr if ltr else same_rl, w)
        if not below_lr:
            continue
        e = np.array([e_r, e_g, e_b], dtype=np.float64).T  # (w, 3)
        for dx, dy, f in below_lr if ltr else below_rl:
            ny = y + dy
            if ny >= h:
                continue
            if dx >= 0:  # cell nx receives e[nx - dx] * f
                err[ny, dx:w] += e[: w - dx] * f
            else:
                err[ny, : w + dx] += e[-dx:] * f
    return Image.frombytes("RGB", (w, h), bytes(out))


def _error_diffuse_py(img, palette, kernel, divisor, *, serpentine=True):
    src = img.convert("RGB")
    w, h = src.size
    data = src.tobytes()
    out = bytearray(len(data))
    pal = [tuple(c) for c in palette]
    same_lr, same_rl, below_lr, below_rl = _split_kernel(kernel, divisor)
    max_dy = max((dy for _, dy, _ in kernel), default=0)
    nbuf = max_dy + 1
    err = [([0.0] * w, [0.0] * w, [0.0] * w) for _ in range(nbuf)]
    zeros = [0.0] * w

    for y in range(h):
        ltr = (not serpentine) or (y % 2 == 0)
        er_row, eg_row, eb_row = err[y % nbuf]
        xs = range(w) if ltr else range(w - 1, -1, -1)
        e_r, e_g, e_b = _scan_row(data, out, y * w * 3, xs, er_row, eg_row, eb_row, pal, same_lr if ltr else same_rl, w)
        for dx, dy, f in below_lr if ltr else below_rl:
            ny = y + dy
            if ny >= h:
                continue
            tr, tg, tb = err[ny % nbuf]
            lo, hi = max(0, dx), min(w, w + dx)  # cells nx with 0 <= nx - dx < w
            for nx in range(lo, hi):
                sx = nx - dx
                tr[nx] += e_r[sx] * f
                tg[nx] += e_g[sx] * f
                tb[nx] += e_b[sx] * f
        # Row y is done; clear its slot before it wraps for y + nbuf.
        er_row[:] = zeros
        eg_row[:] = zeros
        eb_row[:] = zeros
    return Image.frombytes("RGB", (w, h), bytes(out))


def _ordered_dither(
    img: Image.Image,
    palette: list[tuple[int, int, int]],
    matrix: list[list[int]] | tuple[tuple[int, ...], ...],
    *,
    origin: tuple[int, int] = (0, 0),
) -> Image.Image:
    """Threshold-bias ordered dither, then snap to the nearest palette color.

    ``origin`` is the absolute top-left of ``img`` on the full canvas so cropped
    layers keep the same Bayer/clustered phase as a whole-image pass.
    """
    src = img.convert("RGB")
    w, h = src.size
    n = len(matrix)
    levels = float(n * n)
    ox, oy = origin
    if np is not None:
        arr = np.asarray(src, dtype=np.float64)  # (h, w, 3)
        tile = np.asarray(matrix, dtype=np.float64)[(np.arange(h) + oy) % n][:, (np.arange(w) + ox) % n]
        v = arr + (((tile + 0.5) / levels - 0.5) * 255.0)[..., None]
        pal = np.asarray(palette, dtype=np.float64)
        d = v[:, :, None, :] - pal[None, None, :, :]  # (h, w, k, 3)
        # same operand order as the scalar path: (dr*dr + dg*dg) + db*db
        dist = d[..., 0] * d[..., 0] + d[..., 1] * d[..., 1] + d[..., 2] * d[..., 2]
        idx = np.argmin(dist, axis=-1)  # first minimum, like the strict `<` search
        return Image.fromarray(np.asarray(palette, dtype=np.uint8)[idx], "RGB")
    px = src.load()
    out = Image.new("RGB", (w, h))
    dest = out.load()
    for y in range(h):
        row = matrix[(y + oy) % n]
        for x in range(w):
            bias = ((row[(x + ox) % n] + 0.5) / levels - 0.5) * 255.0
            r, g, b = px[x, y]
            dest[x, y] = _nearest(r + bias, g + bias, b + bias, palette)
    return out


def dither_to_palette(
    img: Image.Image,
    palette,
    *,
    dither: bool | str | int | None = True,
    origin: tuple[int, int] = (0, 0),
) -> Image.Image:
    """Return ``img`` quantized to ``palette`` (RGB), using ``dither`` method.

    ``dither`` may be:

    * ``True`` / ``False`` / ``1`` / ``0`` / ``None`` — floyd / none
    * a method name from :data:`DITHER_METHODS` (or a known alias)

    ``origin`` is only meaningful for ordered methods (Bayer / clustered) when
    ``img`` is a crop of a larger canvas.
    """
    method = resolve_dither_method(dither)
    rgbs = _palette_rgbs(palette)
    if not rgbs:
        raise ValueError("palette must contain at least one color")

    if method == DITHER_NONE:
        return _quantize_nearest_pillow(img, palette)

    kernel_spec = _KERNELS.get(method)
    if kernel_spec is not None:
        kernel, divisor = kernel_spec
        return _error_diffuse(img, rgbs, kernel, divisor, serpentine=True)

    if method == DITHER_BAYER2:
        return _ordered_dither(img, rgbs, _bayer_matrix(2), origin=origin)
    if method == DITHER_BAYER4:
        return _ordered_dither(img, rgbs, _bayer_matrix(4), origin=origin)
    if method == DITHER_BAYER8:
        return _ordered_dither(img, rgbs, _bayer_matrix(8), origin=origin)
    if method == DITHER_BAYER16:
        return _ordered_dither(img, rgbs, _bayer_matrix(16), origin=origin)
    if method == DITHER_CLUSTERED4:
        return _ordered_dither(img, rgbs, _CLUSTERED4, origin=origin)
    if method == DITHER_CLUSTERED8:
        return _ordered_dither(img, rgbs, _CLUSTERED8, origin=origin)

    raise ValueError(f"unhandled dither method {method!r}")  # pragma: no cover
