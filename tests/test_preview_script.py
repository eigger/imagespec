"""scripts/inject_element_previews.py must be safe to run repeatedly."""

from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "inject_element_previews.py"


def _load():
    spec = importlib.util.spec_from_file_location("inject_element_previews", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_running_twice_does_not_duplicate_previews(tmp_path, monkeypatch):
    mod = _load()
    previews = tmp_path / "elements"
    previews.mkdir()
    for name in ("text", "icon", "label_combo"):
        (previews / f"{name}.png").write_bytes(b"png")
    doc = tmp_path / "elements.md"
    doc.write_text(
        "# Elements\n\n### `text`\n\nBody.\n\n### `icon` / `text`\n\nBody.\n\n## Combined label example\n\nBody.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "DOC", doc)
    monkeypatch.setattr(mod, "PREVIEW_DIR", previews)
    monkeypatch.setattr(mod, "ROOT", tmp_path)

    mod.main()
    first = doc.read_text(encoding="utf-8")
    assert "![text preview]" in first and "![icon preview]" in first and "![label_combo preview]" in first
    mod.main()
    assert doc.read_text(encoding="utf-8") == first


def test_committed_elements_doc_is_already_up_to_date(monkeypatch, tmp_path):
    mod = _load()
    real = Path(mod.DOC)
    copy = tmp_path / "elements.md"
    copy.write_text(real.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(mod, "DOC", copy)
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    mod.main()
    assert copy.read_text(encoding="utf-8") == real.read_text(encoding="utf-8")
