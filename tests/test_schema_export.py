"""schema/elements.json and docs/reference.md are derived from the element specs,
committed, and kept current; the JSON Schema is valid and accepts/rejects the
right payloads."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from imagespec import DITHER_METHODS, known_types
from imagespec.schema import SCHEMA_VERSION, build_json_schema, build_reference_md

ROOT = Path(__file__).resolve().parents[1]


def test_export_script_check_passes():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "export_schema.py"), "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_committed_files_match_generators():
    committed = json.loads((ROOT / "schema" / "elements.json").read_text(encoding="utf-8"))
    assert committed == build_json_schema(), "schema/elements.json is stale; run scripts/export_schema.py"
    assert (ROOT / "docs" / "reference.md").read_text(encoding="utf-8") == build_reference_md(), (
        "docs/reference.md is stale; run scripts/export_schema.py"
    )


def test_editor_types_subset_of_known_types():
    path = ROOT / "schema" / "editor_types.json"
    assert path.exists(), "schema/editor_types.json missing — run scripts/export_schema.py --editor-schema ..."
    data = json.loads(path.read_text(encoding="utf-8"))
    unknown = set(data["types"]) - known_types()
    assert not unknown, f"editor_types not in imagespec registry: {sorted(unknown)}"


def test_elements_json_structure():
    data = build_json_schema()
    assert data["schema_version"] == SCHEMA_VERSION
    assert data["package"] == "imagespec"
    assert data["types"] == sorted(known_types())
    assert data["dither_methods"] == list(DITHER_METHODS)
    assert set(data["$defs"]) >= known_types() - {"row", "column"} | {"element", "stack_child"}


# ── the schema is usable ───────────────────────────────────────────────────


@pytest.fixture(scope="module")
def validator():
    schema = build_json_schema()
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _previews():
    path = ROOT / "examples" / "generate_element_previews.py"
    spec = importlib.util.spec_from_file_location("generate_element_previews", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("name", sorted(_previews().SAMPLES))
def test_every_preview_payload_validates(validator, name):
    sample = _previews().SAMPLES[name]
    payload = sample if isinstance(sample, list) else [sample]
    errors = [f"{list(e.absolute_path)}: {e.message}" for e in validator.iter_errors(payload)]
    assert not errors, errors[:3]


def test_golden_scene_payloads_validate(validator):
    from test_golden import SCENES

    for name, scene in SCENES.items():
        assert validator.is_valid(scene["payload"]), name


# Shared with tests/test_validate.py: imagespec.validate must agree with the schema here.
REJECTS = [
    ("unknown key (typo)", [{"type": "circle", "x": 1, "y": 1, "radius": 3, "fil": "red"}]),
    ("missing required x at top level", [{"type": "text", "value": "a"}]),
    ("missing required x inside group", [{"type": "group", "elements": [{"type": "text", "value": "a"}]}]),
    ("enum violation", [{"type": "dlimg", "x": 0, "y": 0, "url": "u", "xsize": 1, "ysize": 1, "mode": "zoom"}]),
    ("unknown element type", [{"type": "sprite", "x": 0, "y": 0}]),
    ("wrong scalar type", [{"type": "circle", "x": "left", "y": 1, "radius": 3}]),
    ("dither integer other than 0/1", [{"type": "circle", "x": 1, "y": 1, "radius": 3, "dither": 2}]),
    ("fit_width without width", [{"type": "new_multiline", "x": 0, "y": 0, "value": "a", "fit_width": True}]),
    (
        "fit_width with width: null",
        [{"type": "new_multiline", "x": 0, "y": 0, "value": "a", "fit_width": True, "width": None}],
    ),
    ("fit: true without height", [{"type": "new_multiline", "x": 0, "y": 0, "value": "a", "fit": True, "width": 1}]),
    ("fit outside enum/boolean", [{"type": "new_multiline", "x": 0, "y": 0, "value": "a", "fit": "both"}]),
    (
        "sparkline values neither list nor string",
        [{"type": "sparkline", "x": 0, "y": 0, "width": 9, "height": 9, "values": 7}],
    ),
]

ACCEPTS = [
    ("stack child without x/y", [{"type": "row", "elements": [{"type": "text", "value": "a"}]}]),
    ("legend items as string", [{"type": "legend", "x": 0, "y": 0, "items": "a,red;b,blue"}]),
    ("explicit null for an optional key", [{"type": "circle", "x": 1, "y": 1, "radius": 3, "fill": None}]),
    ("plot ylegend: null disables it", [{"type": "plot", "data": [{"entity": "s.a"}], "ylegend": None}]),
    ("per-element dither by name", [{"type": "circle", "x": 1, "y": 1, "radius": 3, "dither": "bayer8"}]),
    *(
        (f"per-element dither as JSON {v!r}", [{"type": "circle", "x": 1, "y": 1, "radius": 3, "dither": v}])
        for v in (1, 0, None)
    ),
    ("aliases row/column", [{"type": "column", "elements": []}, {"type": "stack", "elements": []}]),
    # null where the handler has no meaning for it = omitted (dropped before dispatch)
    ("stack child with y: null", [{"type": "row", "elements": [{"type": "text", "value": "a", "y": None}]}]),
    ("optional number null (text y)", [{"type": "text", "x": 0, "y": None, "value": "a", "size": None}]),
    ("optional object null (diagram bars)", [{"type": "diagram", "x": 0, "y": 0, "height": 20, "bars": None}]),
    (
        "optional string null (rectangle corners)",
        [{"type": "rectangle", "x_start": 0, "y_start": 0, "x_end": 1, "y_end": 1, "corners": None}],
    ),
    ("fit_width with width", [{"type": "new_multiline", "x": 0, "y": 0, "value": "a", "fit_width": True, "width": 30}]),
    (
        "fit: true with both",
        [{"type": "new_multiline", "x": 0, "y": 0, "value": "a", "fit": True, "width": 30, "height": 30}],
    ),
    ("fit off needs nothing", [{"type": "new_multiline", "x": 0, "y": 0, "value": "a", "fit_width": False}]),
    ("sparkline values as string", [{"type": "sparkline", "x": 0, "y": 0, "width": 9, "height": 9, "values": "1,3,2"}]),
]


@pytest.mark.parametrize("label, payload", REJECTS)
def test_schema_rejects(validator, label, payload):
    assert not validator.is_valid(payload), label


@pytest.mark.parametrize("label, payload", ACCEPTS)
def test_schema_accepts(validator, label, payload):
    errors = [f"{list(e.absolute_path)}: {e.message}" for e in validator.iter_errors(payload)]
    assert not errors, (label, errors[:3])
