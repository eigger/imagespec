# Integrating imagespec into a host application

imagespec renders a payload to a `PIL.Image`; everything host-specific — where
fonts live, where history comes from, which colors the device has — is injected
through `RenderContext`. A host integration is therefore a **thin adapter**: build
a context, call `render()`, translate `RenderError` into the host's own error
type. Nothing else in the host needs to know about imagespec.

This is how [`hass-ble-esl`](https://github.com/eigger/hass-ble-esl) (BLE
e-paper shelf labels) and [`hass-niimbot`](https://github.com/eigger/hass-niimbot)
(label printers) use it; their `renderer.py` files are the reference adapters
and stay around 60 lines.

---

## 1. Dependency

Published on PyPI. Pin an exact version so installs are reproducible:

```json
"requirements": ["imagespec[datamatrix]==<version you tested against>"]
```

Extras:

| extra | adds | when |
|---|---|---|
| `datamatrix` | `pyStrich` | the `datamatrix` element |
| `fast` | `numpy` | 2–6× faster dithering on large panels (output identical) |
| `yaml` | `PyYAML` | only if the host parses YAML strings itself |

`qrcode`, `python-barcode`, `pillow` and `requests` are transitive — do not pin
them again in the host.

---

## 2. What `RenderContext` needs from the host

| field | purpose | default |
|---|---|---|
| `palette` | colors the device can show — list of names/hex/RGBA, or `"bw"`/`"bwr"`/`"4"`/`"7"` | 4-color |
| `font_resolver(name) -> path \| None` | map a payload font name to a file; `None` falls back to the bundled font | bundled only |
| `history_provider(entity_ids, start, end)` | time series for `plot` | `None` → `plot` raises |
| `default_font` | used when a payload gives no `font` | `NotoSansKR-Regular.ttf` |
| `icons_dir` | directory holding the MDI / Font Awesome webfonts + metadata | bundled |
| `allow_local_images` | let `dlimg` open filesystem paths | `False` |
| `max_image_bytes` / `image_cache_ttl` / `image_fetcher` | `dlimg` download cap, optional TTL cache, host-supplied fetcher | 20 MB / off / built-in |
| `layout_engine` | Pillow text layout engine; leave `None` for the platform default | `None` |

Only `palette` is really device-specific; the rest are host conveniences.

---

## 3. A Home Assistant adapter

```python
import os

from homeassistant.components.recorder.history import get_significant_states
from homeassistant.exceptions import HomeAssistantError

from imagespec import RenderContext, RenderError, render


def _make_context(hass, *, default_font, palette):
    def font_resolver(name):
        # Bundled with the component first, then the user's www/fonts; None
        # falls back to imagespec's own bundled font.
        base = os.path.basename(name)
        for directory in (
            os.path.join(os.path.dirname(__file__), "fonts"),
            hass.config.path("www/fonts"),
        ):
            path = os.path.join(directory, base)
            if os.path.exists(path):
                return path
        return None

    def history_provider(entity_ids, start, end):
        return get_significant_states(
            hass,
            start_time=start,
            end_time=end,
            entity_ids=list(entity_ids),
            significant_changes_only=False,
            minimal_response=True,
            no_attributes=False,
        )

    return RenderContext(
        font_resolver=font_resolver,
        history_provider=history_provider,
        default_font=default_font,
        palette=palette,
    )


def render_image(device, service, hass):
    try:
        return render(
            payload=service.data.get("payload", []),
            width=device.width,
            height=device.height,
            rotate=int(service.data.get("rotate", 0)),
            rotate_mode="canvas",  # fixed-resolution ESL panel; a label printer wants "image"
            background=service.data.get("background", "white"),
            dither=service.data.get("dither", False),
            context=_make_context(hass, default_font="NotoSansKR-Regular.ttf", palette=device.palette),
        )
    except RenderError as err:
        raise HomeAssistantError(str(err)) from err
```

Notes:

- `render()` is synchronous and CPU-bound; call it from an executor
  (`hass.async_add_executor_job`) — never on the event loop.
- `history_provider` receives the raw recorder result: the first sample as a
  `State` object and the rest as dicts (`minimal_response=True`). `plot`
  normalises this itself.
- Payload values coming from templates may be strings (`"42"`, `"False"`);
  imagespec coerces numeric/boolean keys, so the adapter need not.

---

## 4. Per-device choices

| Concern | fixed-resolution panel (ESL, e-paper) | variable-size label printer |
|---|---|---|
| `rotate_mode` | `"canvas"` — output stays `width × height`, the drawing surface rotates | `"image"` — output dimensions swap |
| `palette` | per model: `"bw"`, `"bwr"`, `"4"`, `"7"` | usually `"bw"` |
| canvas size | from the device model | from the service call |
| `dither` | `"floyd"`/`"atkinson"`/… for photos on limited palettes | usually `False` for crisp text/barcodes |

Payload colors are quantized to `palette` at the end of `render()`, so one
payload renders correctly on a 2-, 4- or 7-color device without changes (a
`red` element simply becomes black on a black/white panel).

---

## 5. Errors

Everything imagespec rejects — a missing required key, a non-numeric
coordinate, an unknown barcode symbology, a failed `dlimg` download — surfaces
as `RenderError`. Errors raised by a handler's own validation name the element
type (`Missing required argument(s) 'x' in 'text'`); anything else that fails
inside a handler is wrapped with the element index and type
(`error rendering element #3 (type 'text'): ...`). Unknown element `type`s are
logged and skipped, not raised, so a payload written for a newer imagespec
degrades instead of failing. Translate `RenderError` once, at the adapter.

Unknown *keys* (a typo such as `fil: red`) are ignored by `render()`. To catch
them — and missing required keys, wrong kinds, bad enum values — before
rendering, call `imagespec.validate(payload)`; it returns a list of
`Issue(path, message)` (empty when valid) with paths like
`[0].elements[2].fill`, and accepts template strings and `null` exactly as the
renderer does. `render(..., strict=True)` does the same and raises
`RenderError` with every issue joined, which suits a "lint before publish"
mode; leave it off for the production path so a stale key never blanks a
device.

## See also

- [Element reference](reference.md) — every key, type and default; [`elements.md`](elements.md) has a rendered YAML example per element
- [Authoring guide](authoring.md) — layout model, palette, pitfalls
- [Dithering](dithering.md) — methods, per-element override, performance
