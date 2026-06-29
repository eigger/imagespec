# Migrating the components onto imagespec

This describes how `hass-gicisky` and `hass-niimbot` will later drop their own
renderers (`renderer.py` / `imagegen.py`) and call `imagespec` instead. **Not
done yet** — this is the plan to follow when the swap happens.

The strategy: keep a **thin adapter** with the same public function name each
component already exposes, so nothing else in the component changes. The
adapter's only jobs are to build a `RenderContext` (font lookup + history +
palette) and translate `imagespec.RenderError` into `HomeAssistantError`.

All 26 element types are implemented, so no payloads will regress; unknown
element types are warned-and-skipped rather than raising.

---

## 1. Declare the dependency in `manifest.json`

`imagespec` ships from GitHub. Use a PEP 508 direct reference pinned to a tag:

```json
"requirements": [
  "imagespec[datamatrix] @ git+https://github.com/eigger/imagespec.git@v0.2.0"
]
```

- The `[datamatrix]` extra pulls in `pyStrich` (only needed for the `datamatrix`
  element); drop it if a component never uses datamatrix.
- Pin to a **tag** (`@v0.2.0`), not a branch, so installs are reproducible.
- If/when published to PyPI, this simplifies to `"imagespec[datamatrix]==0.2.0"`.

**Remove the now-duplicated deps.** `qrcode[pil]`, `python-barcode` and `pyStrich`
become transitive deps of `imagespec`, so delete them from each component's
`manifest.json`. (Leaving them in causes no conflict — the existing pins
`qrcode[pil]==7.4.2`, `python-barcode==0.15.1`, `pyStrich==0.10` all satisfy
imagespec's ranges — but removing them is the point of consolidating.)

---

## 2. A shared adapter helper

Both adapters build a `RenderContext` the same way; only `default_font` and
`palette` differ. Factor it once:

```python
import os

from homeassistant.exceptions import HomeAssistantError
from homeassistant.components.recorder.history import get_significant_states

from imagespec import RenderContext, RenderError, render


def _make_context(hass, *, default_font, palette):
    def font_resolver(name):
        # check www/fonts; return None to fall back to imagespec's bundled fonts
        cand = os.path.join(hass.config.path("www/fonts"), os.path.basename(name))
        return cand if os.path.exists(cand) else None

    def history_provider(entity_ids, start, end):
        return get_significant_states(
            hass, start_time=start, entity_ids=list(entity_ids),
            significant_changes_only=False, minimal_response=True, no_attributes=False,
        )

    return RenderContext(
        font_resolver=font_resolver,
        history_provider=history_provider,
        default_font=default_font,
        palette=palette,  # list of supported colors (names/hex/rgba) or "2"/"4"/"7" shorthand
    )
```

---

## 3. gicisky — `renderer.py`

`render_image(entity_id, device, service, hass)` derives the canvas size from
`device` and uses the **`canvas`** rotation mode (fixed-resolution ESL panel):

```python
def render_image(entity_id, device, service, hass):
    try:
        return render(
            payload=service.data.get("payload", ""),
            width=device.width,
            height=device.height,
            rotate=int(service.data.get("rotate", 0)),
            rotate_mode="canvas",   # ESL panel: fixed resolution, background rotates
            background=service.data.get("background", "white"),
            context=_make_context(hass, default_font="NotoSansKR-Regular.ttf",
                                  palette=device.palette),  # "2"/"4"/"7" per model
        )
    except RenderError as err:
        raise HomeAssistantError(str(err)) from err
```

Also narrow the `from .renderer import *` in `__init__.py` to
`from .renderer import render_image` once the old helper soup is gone.

---

## 4. niimbot — `imagegen.py`

`customimage(entity_id, service, hass)` takes the canvas size from `service.data`
and uses the **`image`** rotation mode (variable-size label printer):

```python
def customimage(entity_id, service, hass):
    try:
        return render(
            payload=service.data.get("payload", ""),
            width=service.data.get("width", 400),
            height=service.data.get("height", 240),
            rotate=service.data.get("rotate", 0),
            rotate_mode="image",    # label printer: variable size, drawing rotates
            background=service.data.get("background", "white"),
            context=_make_context(hass, default_font="ppb.ttf", palette="bw"),
        )
    except RenderError as err:
        raise HomeAssistantError(str(err)) from err
```

---

## 5. Per-device specifics (don't unify these away)

| Concern | gicisky | niimbot |
|---|---|---|
| `rotate_mode` | `"canvas"` (output stays W×H) | `"image"` (output dims swap) |
| `palette` | varies by model (`"2"`/`"4"`/`"7"`) | usually `"bw"` |
| `default_font` | `NotoSansKR-Regular.ttf` | `ppb.ttf` |
| canvas size | from `device.width/height` | from `service.data["width"/"height"]` |

Colors in a payload are auto-quantized to the device `palette`, so the same
payload renders correctly on a 2/4/7-color panel without changes.

---

## 6. Optional cleanups enabled by the move

- **Delete bundled fonts** from each component that `imagespec` already ships
  (`NotoSansKR-Regular.ttf`, `ppb.ttf`, the MDI webfont + meta). Decorative fonts
  the components still need can stay in `www/fonts`, or be downloaded on demand
  via `imagespec.resolvers.caching_resolver` (download-once, cache offline).
- **Image quality**: pass `dither=True` to `render(...)`, or `"dither": true` on a
  `dlimg`, for Floyd–Steinberg dithering on limited-color panels.

---

## Swap checklist (per component)

1. Add the `imagespec[...] @ git+...@vX.Y.Z` requirement; remove qrcode/barcode/
   pyStrich.
2. Replace the body of `render_image` / `customimage` with the adapter above.
3. Delete the old rendering code and duplicated font/icon assets.
4. Smoke-test the component's existing example payloads (every element type is
   supported, so they should render unchanged).
