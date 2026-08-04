"""Keep schema/elements.json and schema/editor_types.json in sync with the registry."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_elements_json_matches_known_types():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "export_schema.py"), "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_editor_types_subset_of_known_types():
    from imagespec import known_types

    path = ROOT / "schema" / "editor_types.json"
    assert path.exists(), "schema/editor_types.json missing — run scripts/export_schema.py --editor-schema ..."
    data = json.loads(path.read_text(encoding="utf-8"))
    editor_types = set(data["types"])
    unknown = editor_types - known_types()
    assert not unknown, f"editor_types not in imagespec registry: {sorted(unknown)}"


def test_elements_json_structure():
    data = json.loads((ROOT / "schema" / "elements.json").read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert data["package"] == "imagespec"
    assert isinstance(data["types"], list)
    assert data["types"] == sorted(data["types"])
