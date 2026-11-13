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


def _section(lines: list[str], start: int) -> str:
    """Text from ``start`` up to the next heading (or the end)."""
    end = start
    while end < len(lines) and not lines[end].startswith("#"):
        end += 1
    return "".join(lines[start:end])


def main() -> None:
    text = DOC.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    heading_re = re.compile(r"^### `([^`]+)`(?: / `([^`]+)`(?: / `([^`]+)`)?)?\s*$")

    def missing(name: str, following: str) -> str:
        """The preview block for ``name`` unless the section already has it (keeps re-runs idempotent)."""
        if f"](../examples/elements/{name}.png)" in following:
            return ""
        return preview_block(name)

    for i, line in enumerate(lines):
        out.append(line)
        following = _section(lines, i + 1)
        match = heading_re.match(line.rstrip("\n"))
        if match:
            names = [group for group in match.groups() if group]
            block = "".join(missing(name, following) for name in names)
            if block:
                out.append(block)
        elif line.startswith("## Combined label example"):
            out.append(missing("label_combo", following))

    DOC.write_text("".join(out), encoding="utf-8", newline="\n")
    print(f"Updated {DOC.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
