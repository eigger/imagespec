#!/usr/bin/env python3
"""Export imagespec element type registry to schema/elements.json.

Also writes schema/editor_types.json when --editor-schema is given (path to
imagespec-editor/schema.js). That list is the web editor's supported types and
must remain a subset of known_types().

Usage:
  python scripts/export_schema.py
  python scripts/export_schema.py --editor-schema ../eigger.github.io/imagespec-editor/schema.js
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from imagespec import DITHER_METHODS, known_types  # noqa: E402


def extract_editor_types(schema_js: Path) -> list[str]:
    text = schema_js.read_text(encoding="utf-8")
    m = re.search(r"ELEMENT_DEFAULTS:\s*\{(.*?)\n\},", text, re.S)
    if not m:
        raise SystemExit(f"Could not parse ELEMENT_DEFAULTS from {schema_js}")
    block = m.group(1)
    types = re.findall(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:", block, re.M)
    # de-dupe preserving order
    seen: set[str] = set()
    out: list[str] = []
    for t in types:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--editor-schema",
        type=Path,
        help="Path to eigger.github.io/imagespec-editor/schema.js to refresh editor_types.json",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Do not write files; exit non-zero if committed JSON is stale",
    )
    args = parser.parse_args()

    schema_dir = ROOT / "schema"
    schema_dir.mkdir(exist_ok=True)

    types = sorted(known_types())
    dither_methods = list(DITHER_METHODS)
    elements_doc = {
        "schema_version": 1,
        "package": "imagespec",
        "types": types,
        "dither_methods": dither_methods,
    }

    elements_path = schema_dir / "elements.json"
    if args.check:
        if not elements_path.exists():
            print(f"MISSING {elements_path}", file=sys.stderr)
            return 1
        current = json.loads(elements_path.read_text(encoding="utf-8"))
        if current.get("types") != types or current.get("dither_methods") != dither_methods:
            print("schema/elements.json is stale; run: python scripts/export_schema.py", file=sys.stderr)
            print("  committed types:", current.get("types"), file=sys.stderr)
            print("  expected  types:", types, file=sys.stderr)
            print("  committed dither_methods:", current.get("dither_methods"), file=sys.stderr)
            print("  expected  dither_methods:", dither_methods, file=sys.stderr)
            return 1
        print(f"OK {elements_path} ({len(types)} types, {len(dither_methods)} dither methods)")
    else:
        elements_path.write_text(json.dumps(elements_doc, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {elements_path} ({len(types)} types, {len(dither_methods)} dither methods)")

    editor_types_path = schema_dir / "editor_types.json"
    if args.editor_schema:
        editor_types = extract_editor_types(args.editor_schema)
        unknown = sorted(set(editor_types) - set(types))
        if unknown:
            print(f"ERROR: editor types not in imagespec: {unknown}", file=sys.stderr)
            return 1
        editor_doc = {
            "schema_version": 1,
            "description": "Element types exposed by the imagespec web payload editor (subset of elements.json).",
            "types": editor_types,
        }
        if args.check:
            if not editor_types_path.exists():
                print(f"MISSING {editor_types_path}", file=sys.stderr)
                return 1
            current = json.loads(editor_types_path.read_text(encoding="utf-8"))
            if current.get("types") != editor_types:
                print("schema/editor_types.json is stale; re-run export with --editor-schema", file=sys.stderr)
                return 1
            print(f"OK {editor_types_path} ({len(editor_types)} types)")
        else:
            editor_types_path.write_text(json.dumps(editor_doc, indent=2) + "\n", encoding="utf-8")
            print(f"Wrote {editor_types_path} ({len(editor_types)} types)")
    elif args.check and editor_types_path.exists():
        current = json.loads(editor_types_path.read_text(encoding="utf-8"))
        editor_types = current.get("types") or []
        unknown = sorted(set(editor_types) - set(types))
        if unknown:
            print(f"ERROR: editor_types.json has unknown types: {unknown}", file=sys.stderr)
            return 1
        print(f"OK editor_types ⊆ known_types ({len(editor_types)} types)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
