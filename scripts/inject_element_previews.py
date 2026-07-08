"""Insert preview images into docs/elements.md after each element heading."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "elements.md"
PREVIEW_DIR = ROOT / "examples" / "elements"


def preview_block(name: str) -> str:
    path = PREVIEW_DIR / f"{name}.png"
    if not path.exists():
        return ""
    return f"\n![{name} preview](../examples/elements/{name}.png)\n"


def main() -> None:
    text = DOC.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    heading_re = re.compile(r"^### `([^`]+)`(?: / `([^`]+)`(?: / `([^`]+)`)?)?\s*$")

    for line in lines:
        out.append(line)
        match = heading_re.match(line.rstrip("\n"))
        if match:
            names = [group for group in match.groups() if group]
            if len(names) > 1:
                block = "".join(preview_block(name) for name in names)
            else:
                block = preview_block(names[0])
            if block:
                out.append(block)
        elif line.startswith("## Combined label example"):
            out.append(preview_block("label_combo"))

    new_text = "".join(out)
    # Drop duplicate consecutive preview lines if the script is re-run.
    new_text = re.sub(r"(\n!\[[^\]]+\]\([^\)]+\))+", r"\1", new_text)
    DOC.write_text(new_text, encoding="utf-8", newline="\n")
    print(f"Updated {DOC.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
