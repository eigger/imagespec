#!/usr/bin/env python3
"""Export the element specs to schema/elements.json and docs/reference.md.

Both files are derived from the ``@element(..., fields=[...])`` declarations
(see ``imagespec.spec``). CI runs ``--check`` so they cannot drift.

Also refreshes schema/editor_types.json when --editor-schema is given (path to
imagespec-editor/schema.js); that list is the web editor's supported types and
must remain a subset of known_types().

Usage:
  python scripts/export_schema.py
  python scripts/export_schema.py --check
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

from imagespec import known_types  # noqa: E402
from imagespec.schema import build_json_schema, build_reference_md  # noqa: E402


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


def _sync(path: Path, content: str, check: bool, label: str) -> bool:
    """Write ``content`` to ``path``, or with ``check`` report whether it is current."""
    if check:
        if not path.exists():
            print(f"MISSING {path}", file=sys.stderr)
            return False
        if path.read_text(encoding="utf-8") != content:
            print(f"{path.relative_to(ROOT)} is stale; run: python scripts/export_schema.py", file=sys.stderr)
            return False
        print(f"OK {path.relative_to(ROOT)} ({label})")
        return True
    path.write_text(content, encoding="utf-8", newline="\n")
    print(f"Wrote {path.relative_to(ROOT)} ({label})")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--editor-schema",
        type=Path,
        help="Path to eigger.github.io/imagespec-editor/schema.js to refresh editor_types.json",
    )
    parser.add_argument("--check", action="store_true", help="Do not write; exit non-zero if a committed file is stale")
    args = parser.parse_args()

    schema_dir = ROOT / "schema"
    schema_dir.mkdir(exist_ok=True)
    ok = True

    schema = build_json_schema()
    ok &= _sync(
        schema_dir / "elements.json",
        json.dumps(schema, indent=2, ensure_ascii=False) + "\n",
        args.check,
        f"{len(schema['types'])} types, {len(schema['dither_methods'])} dither methods",
    )
    ok &= _sync(ROOT / "docs" / "reference.md", build_reference_md(), args.check, "element reference")

    types = sorted(known_types())
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
        label = f"{len(editor_types)} types"
        ok &= _sync(editor_types_path, json.dumps(editor_doc, indent=2) + "\n", args.check, label)
    elif args.check and editor_types_path.exists():
        current = json.loads(editor_types_path.read_text(encoding="utf-8"))
        editor_types = current.get("types") or []
        unknown = sorted(set(editor_types) - set(types))
        if unknown:
            print(f"ERROR: editor_types.json has unknown types: {unknown}", file=sys.stderr)
            return 1
        print(f"OK editor_types ⊆ known_types ({len(editor_types)} types)")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
