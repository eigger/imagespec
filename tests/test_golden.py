"""Golden-image regression tests.

Every other test asserts *that* something renders; these assert *what* it
renders, pixel for pixel, so a change to a handler, the dither kernels or the
palette pass cannot silently alter output. Two golden sets:

* ``examples/elements/<name>.png`` — the README preview of every element, built
  from ``examples/generate_element_previews.SAMPLES``. Docs and tests share one
  source, so the previews are guaranteed to match the current renderer.
* ``tests/golden/*.png`` — targeted scenes with no doc value: each dither
  method, per-element dither phase alignment, rotation modes, and handler paths
  the previews leave uncovered.

When a change is intentional, regenerate with ``pytest --update-golden`` (or
``python examples/generate_element_previews.py`` for the previews alone) and
commit the PNGs.

Comparison is exact by default. ``IMAGESPEC_GOLDEN_TOLERANCE`` (fraction of
pixels allowed to differ, e.g. ``0.01``) loosens it for environments whose
FreeType/qrcode/barcode versions rasterise slightly differently.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest
from PIL import Image, ImageChops

from imagespec import PALETTE_BW, PALETTE_BWR, RenderContext, known_types, render
from imagespec.dither import DITHER_METHODS, dither_to_palette

ROOT = Path(__file__).resolve().parents[1]
GOLDEN_DIR = ROOT / "tests" / "golden"
TOLERANCE = float(os.environ.get("IMAGESPEC_GOLDEN_TOLERANCE", "0"))


def _load_previews_module():
    path = ROOT / "examples" / "generate_element_previews.py"
    spec = importlib.util.spec_from_file_location("generate_element_previews", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


previews = _load_previews_module()


@pytest.fixture
def check_golden(request, tmp_path):
    """Compare a rendered image against ``golden_path`` (or rewrite it)."""
    update = request.config.getoption("--update-golden")

    def _check(actual: Image.Image, golden_path: Path) -> None:
        actual = actual.convert("RGB")
        if update:
            golden_path.parent.mkdir(parents=True, exist_ok=True)
            actual.save(golden_path)
            return
        assert golden_path.exists(), f"missing golden {golden_path}; run: pytest --update-golden"
        expected = Image.open(golden_path).convert("RGB")
        assert actual.size == expected.size, f"{golden_path.name}: size {actual.size} != golden {expected.size}"
        diff = ImageChops.difference(actual, expected).convert("L").point(lambda v: 255 if v else 0)
        mismatched = diff.histogram()[255]
        fraction = mismatched / (actual.width * actual.height)
        if fraction > TOLERANCE:
            out = tmp_path / golden_path.name
            actual.save(out)
            diff.save(tmp_path / f"{golden_path.stem}.diff.png")
            pytest.fail(
                f"{golden_path.name}: {mismatched} px differ ({fraction:.2%} > {TOLERANCE:.2%}). "
                f"Actual + diff saved under {tmp_path}. If intended: pytest --update-golden"
            )

    return _check


# ── element previews (examples/elements) ───────────────────────────────────


def test_every_element_has_a_preview():
    # README preview table stays complete: a new @element(...) needs a SAMPLES entry.
    missing = known_types() - set(previews.SAMPLES)
    assert not missing, f"elements without a preview sample: {sorted(missing)}"


@pytest.mark.parametrize("name", sorted(previews.SAMPLES))
def test_element_preview_matches_renderer(check_golden, name):
    check_golden(previews.render_sample(name), Path(previews.OUT_DIR) / f"{name}.png")


# ── dither methods (tests/golden/dither_*) ─────────────────────────────────


@pytest.fixture(scope="module")
def dither_source():
    # The scene the docs use (examples/generate_dither_methods.source_scene()).
    return Image.open(ROOT / "examples" / "dither_methods" / "source.png").convert("RGB")


@pytest.mark.parametrize("palette_name", ["bw", "bwr"])
@pytest.mark.parametrize("method", DITHER_METHODS)
def test_dither_method_golden(check_golden, dither_source, method, palette_name):
    palette = PALETTE_BW if palette_name == "bw" else PALETTE_BWR
    check_golden(
        dither_to_palette(dither_source, palette, dither=method), GOLDEN_DIR / f"dither_{method}_{palette_name}.png"
    )


# ── targeted scenes (tests/golden/scene_*) ─────────────────────────────────

_GREY_RECT = {"type": "rectangle", "x_start": 13, "y_start": 7, "x_end": 90, "y_end": 50, "fill": "#808080"}

SCENES: dict[str, dict] = {
    # per-element dither: an odd offset checks the ORDERED_ORIGIN_ALIGN phase logic
    "element_dither_bayer_phase": {
        "payload": [{**_GREY_RECT, "dither": "bayer8"}, {**_GREY_RECT, "x_start": 100, "x_end": 140}],
        "palette": "bw",
    },
    "global_floyd_with_isolated_none": {
        "payload": [_GREY_RECT, {**_GREY_RECT, "x_start": 100, "x_end": 140, "dither": "none"}],
        "palette": "bw",
        "dither": "floyd",
    },
    # rotation: canvas mode keeps width×height, image mode swaps them
    "rotate90_canvas": {
        "payload": [{"type": "text", "x": 4, "y": 4, "value": "Ab", "size": 16}, {**_GREY_RECT, "fill": "red"}],
        "rotate": 90,
        "rotate_mode": "canvas",
    },
    "rotate90_image": {
        "payload": [{"type": "text", "x": 4, "y": 4, "value": "Ab", "size": 16}, {**_GREY_RECT, "fill": "red"}],
        "rotate": 90,
        "rotate_mode": "image",
    },
    # handler paths the previews leave uncovered
    "text_rotated_with_background": {
        "payload": [
            {"type": "text", "x": 20, "y": 10, "value": "Up", "size": 14, "rotation": 90, "background": "yellow"},
            {"type": "text", "x": 60, "y": 10, "value": "Wrap me please", "size": 12, "max_width": 60},
            {"type": "text", "x": 60, "y": 50, "value": "Box", "size": 12, "background": "red", "stroke_width": 1},
        ],
    },
    "progress_bar_directions": {
        "payload": [
            {
                "type": "progress_bar",
                "x_start": 5,
                "y_start": 5,
                "x_end": 70,
                "y_end": 20,
                "progress": 30,
                "direction": "left",
            },
            {
                "type": "progress_bar",
                "x_start": 80,
                "y_start": 5,
                "x_end": 95,
                "y_end": 75,
                "progress": 60,
                "direction": "up",
            },
            {
                "type": "progress_bar",
                "x_start": 105,
                "y_start": 5,
                "x_end": 120,
                "y_end": 75,
                "progress": 60,
                "direction": "down",
                "radius": 3,
            },
            {
                "type": "progress_bar",
                "x_start": 5,
                "y_start": 30,
                "x_end": 70,
                "y_end": 50,
                "progress": 25,
                "show_percentage": True,
            },
        ],
    },
    "legend_horizontal_and_shapes": {
        "payload": [
            {
                "type": "legend",
                "x": 5,
                "y": 5,
                "orientation": "horizontal",
                "size": 10,
                "items": "a,red;b,blue;c,green",
            },
            {
                "type": "legend",
                "x": 5,
                "y": 25,
                "shape": "circle",
                "size": 10,
                "items": [{"label": "c", "color": "red"}],
            },
            {
                "type": "legend",
                "x": 60,
                "y": 25,
                "shape": "line",
                "size": 10,
                "items": [{"label": "l", "color": "blue"}],
            },
        ],
    },
    "battery_percentage_and_low": {
        "payload": [
            {"type": "battery", "x": 5, "y": 5, "width": 60, "height": 24, "level": 85, "show_percentage": True},
            {
                "type": "battery",
                "x": 5,
                "y": 40,
                "width": 60,
                "height": 24,
                "level": 12,
                "low_color": "red",
                "show_percentage": True,
            },
        ],
    },
    "new_multiline_fit_height": {
        "payload": [
            {
                "type": "new_multiline",
                "x": 5,
                "y": 5,
                "value": "one\ntwo\nthree\nfour",
                "size": 30,
                "height": 60,
                "fit": "height",
            },
            {
                "type": "new_multiline",
                "x": 80,
                "y": 5,
                "value": "wide text",
                "size": 30,
                "width": 60,
                "fit_width": True,
            },
        ],
    },
    "table_align_and_no_header": {
        "payload": [
            {
                "type": "table",
                "x": 5,
                "y": 5,
                "columns": [40, 40],
                "rows": [["h1", "h2"], ["a", "b"]],
                "align": "center",
                "font_size": 9,
            },
            {
                "type": "table",
                "x": 5,
                "y": 45,
                "columns": [40, 40],
                "rows": [["x", "y"]],
                "align": "right",
                "header": False,
                "font_size": 9,
                "cell_fill": "yellow",
            },
        ],
    },
    "text_fit_modes": {
        "payload": [
            {
                "type": "text_fit",
                "x": 5,
                "y": 5,
                "width": 70,
                "height": 20,
                "value": "Too long to fit here",
                "size": 14,
                "fit": "ellipsis",
            },
            {
                "type": "text_fit",
                "x": 5,
                "y": 30,
                "width": 70,
                "height": 40,
                "value": "Two lines of shrinking text",
                "size": 14,
                "max_lines": 2,
                "fit": "shrink_ellipsis",
                "min_size": 12,
                "valign": "middle",
                "align": "center",
                "outline": "black",
            },
            {
                "type": "text_fit",
                "x": 80,
                "y": 5,
                "width": 60,
                "height": 70,
                "value": "bottom right",
                "size": 10,
                "valign": "bottom",
                "align": "right",
                "background": "yellow",
                "padding": 3,
            },
        ],
    },
    "dlimg_fill_mode_and_rotate": {
        "payload": [
            {"type": "dlimg", "x": 5, "y": 5, "url": previews.RED_DATA_URL, "xsize": 40, "ysize": 20, "mode": "fill"},
            {
                "type": "dlimg",
                "x": 60,
                "y": 5,
                "url": previews.RED_DATA_URL,
                "xsize": 40,
                "ysize": 20,
                "mode": "fit",
                "rotate": 45,
            },
            {
                "type": "dlimg",
                "x": 5,
                "y": 40,
                "url": previews.RED_DATA_URL,
                "xsize": 30,
                "ysize": 30,
                "mask": "circle",
            },
        ],
    },
    "stack_justify_and_grow": {
        "payload": [
            {
                "type": "row",
                "x": 0,
                "y": 0,
                "width": 150,
                "height": 20,
                "class": "justify-between px-2",
                "elements": [
                    {"type": "rectangle", "x_start": 0, "y_start": 0, "x_end": 10, "y_end": 10, "fill": "black"},
                    {"type": "rectangle", "x_start": 0, "y_start": 0, "x_end": 10, "y_end": 10, "fill": "red"},
                    {"type": "rectangle", "x_start": 0, "y_start": 0, "x_end": 10, "y_end": 10, "fill": "blue"},
                ],
            },
            {
                "type": "row",
                "x": 0,
                "y": 25,
                "width": 150,
                "height": 20,
                "class": "justify-evenly items-end",
                "elements": [
                    {"type": "rectangle", "x_start": 0, "y_start": 0, "x_end": 10, "y_end": 10, "fill": "black"},
                    {"type": "rectangle", "x_start": 0, "y_start": 0, "x_end": 10, "y_end": 16, "fill": "red"},
                ],
            },
            {
                "type": "row",
                "x": 0,
                "y": 50,
                "width": 150,
                "height": 20,
                "gap": 4,
                "elements": [
                    {
                        "type": "rectangle",
                        "x_start": 0,
                        "y_start": 0,
                        "x_end": 10,
                        "y_end": 10,
                        "fill": "black",
                        "class": "grow",
                    },
                    {
                        "type": "rectangle",
                        "x_start": 0,
                        "y_start": 0,
                        "x_end": 10,
                        "y_end": 10,
                        "fill": "red",
                        "class": "-ml-2 self-center",
                    },
                ],
            },
        ],
    },
    "group_rotated_and_clipped": {
        "payload": [
            {
                "type": "group",
                "x": 20,
                "y": 10,
                "width": 40,
                "height": 30,
                "rotate": 90,
                "elements": [
                    {"type": "rectangle", "x_start": 0, "y_start": 0, "x_end": 60, "y_end": 10, "fill": "red"},
                    {"type": "text", "x": 2, "y": 12, "value": "G", "size": 12},
                ],
            }
        ],
    },
}


@pytest.mark.parametrize("name", sorted(SCENES))
def test_scene_golden(check_golden, name):
    scene = SCENES[name]
    ctx = RenderContext(palette=scene.get("palette", "4"))
    img = render(
        scene["payload"],
        150,
        80,
        rotate=scene.get("rotate", 0),
        rotate_mode=scene.get("rotate_mode", "canvas"),
        dither=scene.get("dither", False),
        context=ctx,
    )
    check_golden(img, GOLDEN_DIR / f"scene_{name}.png")
