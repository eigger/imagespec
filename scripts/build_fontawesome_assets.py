"""Regenerate the bundled Font Awesome Free assets in ``src/imagespec/icons/``.

Maintenance/dev tool — not shipped in the package. Downloads the three Free
webfonts (Solid/Regular/Brands) and trims upstream's ``metadata/icons.json``
(which embeds full SVG path data and is ~4.5 MB) down to just what `icon`
needs to resolve a name to a codepoint: ``name``, ``codepoint``, ``styles``
(which of the three Free webfonts contain it), and ``aliases``.

Only icons in the **Free** tier (``"free": [...]`` non-empty upstream) are
included — Pro-only icons are dropped since their fonts aren't available
under an open license.

Run from the repository root:
    python scripts/build_fontawesome_assets.py
"""

from __future__ import annotations

import json
import os
import urllib.request

FA_REF = "6.x"
RAW_BASE = f"https://raw.githubusercontent.com/FortAwesome/Font-Awesome/{FA_REF}"
ICONS_DIR = os.path.join(os.path.dirname(__file__), "..", "src", "imagespec", "icons")

FONT_FILES = {
    "fontawesome-free-solid.otf": "otfs/Font%20Awesome%206%20Free-Solid-900.otf",
    "fontawesome-free-regular.otf": "otfs/Font%20Awesome%206%20Free-Regular-400.otf",
    "fontawesome-free-brands.otf": "otfs/Font%20Awesome%206%20Brands-Regular-400.otf",
}


def _download(url: str, dest: str) -> None:
    print(f"  GET {url}")
    urllib.request.urlretrieve(url, dest)  # noqa: S310 — fixed, trusted upstream URLs


def main() -> None:
    os.makedirs(ICONS_DIR, exist_ok=True)

    print("Downloading webfonts...")
    for filename, path in FONT_FILES.items():
        _download(f"{RAW_BASE}/{path}", os.path.join(ICONS_DIR, filename))

    print("Downloading + trimming metadata...")
    meta_path = os.path.join(ICONS_DIR, "_fa_icons_raw.json")
    _download(f"{RAW_BASE}/metadata/icons.json", meta_path)
    with open(meta_path, encoding="utf-8") as f:
        raw = json.load(f)
    os.remove(meta_path)

    trimmed = []
    primary_names = set(raw)
    for name, entry in raw.items():
        free_styles = entry.get("free") or []
        if not free_styles:
            continue  # Pro-only icon — not bundled
        aliases = [a for a in entry.get("aliases", {}).get("names", []) if a not in primary_names]
        trimmed.append(
            {
                "name": name,
                "codepoint": entry["unicode"],
                "styles": free_styles,
                "aliases": aliases,
            }
        )
    trimmed.sort(key=lambda e: e["name"])

    out_path = os.path.join(ICONS_DIR, "fontawesome-free_meta.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(trimmed, f, separators=(",", ":"))
    print(f"Wrote {len(trimmed)} free icons to {out_path}")

    license_path = os.path.join(ICONS_DIR, "LICENSE-FONTAWESOME")
    _download(f"{RAW_BASE}/LICENSE.txt", license_path)
    print(f"Wrote {license_path}")


if __name__ == "__main__":
    main()
