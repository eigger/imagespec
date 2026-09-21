# imagespec

Render images from a declarative **YAML/dict spec** — shapes, text, charts,
QR/barcodes — for e-paper ESL tags and label printers.

![imagespec Showcase](https://raw.githubusercontent.com/eigger/imagespec/main/examples/showcase.png)

`imagespec` is the rendering core behind
[`hass-ble-esl`](https://github.com/eigger/hass-ble-esl) (BLE e-paper shelf
labels) and [`hass-niimbot`](https://github.com/eigger/hass-niimbot) (label
printers): both Home Assistant integrations depend on it from PyPI and keep
only a thin adapter of their own (see
[`docs/integrating.md`](docs/integrating.md)). The library has no
framework dependency, so it can be used and tested standalone. The rendering
engine was originally adapted from
[OpenEPaperLink's Home Assistant Integration](https://github.com/OpenEPaperLink/Home_Assistant_Integration)
(`imagegen` module, Apache License 2.0) and has since been substantially
rewritten and extended — see [`NOTICE`](https://github.com/eigger/imagespec/blob/main/NOTICE) for the full attribution.

## Status

Used in production by the two integrations above. Every registered element is
pinned by a golden-image test (the README previews below double as the
goldens), alongside unit tests for palettes, rotation, dithering,
template-string coercion and error handling; CI runs the suite on Python
3.13/3.14 and against the lowest supported dependency versions.

## Design

- **No framework dependency.** The core never imports Home Assistant. Anything
  host-specific is injected through `RenderContext`:
  - `font_resolver(name) -> path | None` — e.g. an integration's
    `hass.config.path("www/fonts")` lookup.
  - `history_provider(entity_ids, start, end) -> states` — for the `plot`
    element (HA recorder). Optional.
  - `palette` — the device's supported colors (see below).
- **Registry dispatch.** Each element `type` is a handler registered with
  `@element("type")` in `imagespec/elements/`, replacing the original giant
  `if/elif` chain. Adding an element = adding a function.
- **`RenderState`.** Threaded through handlers; holds the (reassignable) `img`
  and the `pos_y` flow cursor.
- **Device-dependent palette** (`RenderContext.palette`), *not* unified — panels
  support different colors. Define it as a **list of the colors the device
  supports** (names, HEX, or RGBA tuples):

  ```python
  RenderContext(palette=["black", "white", "red"])  # names
  RenderContext(palette=["#000000", "#ffffff", "#ff0000"])  # HEX
  RenderContext(palette=[(0, 0, 0), (255, 255, 255)])  # RGBA tuples
  ```

  Shorthand names are optional convenience for common panels: `"2"`/`"bw"`,
  `"3"`/`"bwr"`, `"4"`, `"7"`/`"acep"`. Any requested color in a payload is then
  quantized to the nearest color in this list — on a 2-color device `red`
  becomes black; on 4-color a blue `#1e90ff` becomes white; on 7-color it stays
  blue. Elements are drawn in full color and this mapping is applied to the whole
  image once at the end of `render()` (dithered or flat, per `dither` — see
  *Dithering*).
- **Device-dependent rotation** (`rotate_mode`), *not* unified — the two
  behaviours are physically different:
  - `"canvas"` (fixed-resolution e-ink panels, e.g. ble-esl): the drawing
    surface rotates; output stays `width×height`.
  - `"image"` (variable-size label printers, e.g. niimbot): the drawing rotates;
    output dimensions swap.

## Usage

```python
from imagespec import render, RenderContext

ctx = RenderContext(
    font_resolver=my_font_lookup,  # optional
    history_provider=my_history_lookup,  # optional, only for `plot`
)
image = render(payload, width=296, height=128, rotate=0, background="white", context=ctx)  # -> PIL.Image (RGB)
```

Run the smoke test (no fonts required):

```bash
pip install -e .
python examples/smoke_test.py
```

## Development & testing

```bash
pip install -e ".[dev,datamatrix]"   # dev pulls in numpy, so both dither paths are exercised
pytest                 # unit + golden-image tests: every element, palettes, rotation, dither, errors
pytest --update-golden # rewrite the golden PNGs after an intentional rendering change
ruff check . && ruff format --check .   # lint + format
mypy                   # type-check src/ (the package ships py.typed)
python -m build        # build sdist + wheel (bundles fonts/icons)
```

CI runs on every push/PR (`.github/workflows/ci.yml`): ruff lint+format, mypy, the test
suite on Python 3.13/3.14 (plus a lowest-pinned-dependencies job), and a build that asserts the bundled fonts/icons
are present in the wheel. Pushing a `v*` tag triggers
`.github/workflows/release.yml` to build and publish to PyPI (trusted publishing).

The test matrix (`tests/test_elements.py`) asserts it covers *every* registered
element type, so adding a new `@element(...)` without a sample fails the suite —
keeping coverage exhaustive by construction.

**Golden images** (`tests/test_golden.py`) pin the actual pixels: each element
preview in `examples/elements/` is re-rendered from
`examples/generate_element_previews.py` and compared exactly, and
`tests/golden/` holds targeted scenes (every dither method, per-element dither
phase, rotation modes, less-common handler options). A rendering change that is
intended is committed by running `pytest --update-golden` and checking in the
PNGs; an unintended one fails CI with the pixel count and a diff image.
Text in the goldens is laid out with Pillow's `BASIC` engine
(`RenderContext(layout_engine=...)`) so the same Pillow release renders them
identically on every OS; set `IMAGESPEC_GOLDEN_TOLERANCE=0.05` to allow 5 % of
pixels to differ under a different Pillow/FreeType or python-barcode release.

**Robustness built in:**

- Each handler error is wrapped with element context — you get
  `error rendering element #3 (type 'text'): ...`, not a raw PIL traceback.
- `render()` validates `rotate`/`rotate_mode`/size and rejects non-dict elements;
  unknown element types are warned-and-skipped. Unknown *keys* are ignored
  unless you pass `strict=True` (or call `imagespec.validate()` yourself).
- `dlimg` only allows `http(s)`/`data:` URLs by default; local paths require
  `RenderContext(allow_local_images=True)`. Network failures become `RenderError`.
  Downloads are streamed and abort past `max_image_bytes` (20 MB default);
  `image_cache_ttl=<seconds>` reuses a fetched image across renders (off by
  default so camera snapshots are never served stale), and `image_fetcher`
  lets the host supply its own `url -> bytes`.
- Clear errors for missing required args, invalid barcode symbology, malformed
  `polygon` points, and a `diagram` too small for its bars.
- Template-friendly input: numeric keys (`x`, `size`, `progress`, ...) accept
  strings (`"42"`, `"3.5"`) and boolean flags (`visible`, `show_percentage`, ...)
  accept `"False"`/`"off"`/`"0"`, as Home Assistant templates produce them. A
  non-numeric string fails with `'x' must be a number, got 'oops'` naming the
  element.

## Elements

> [!TIP]
> **Copy-paste examples for every element:** [`docs/elements.md`](docs/elements.md)

| Preview | Element | Module | Notes |
|:---:|---|---|---|
| ![](https://raw.githubusercontent.com/eigger/imagespec/main/examples/elements/line.png) | `line` | shapes | + dashed lines |
| ![](https://raw.githubusercontent.com/eigger/imagespec/main/examples/elements/rectangle.png) | `rectangle` | shapes | |
| ![](https://raw.githubusercontent.com/eigger/imagespec/main/examples/elements/rectangle_pattern.png) | `rectangle_pattern` | shapes | |
| ![](https://raw.githubusercontent.com/eigger/imagespec/main/examples/elements/circle.png) | `circle` | shapes | |
| ![](https://raw.githubusercontent.com/eigger/imagespec/main/examples/elements/ellipse.png) | `ellipse` | shapes | |
| ![](https://raw.githubusercontent.com/eigger/imagespec/main/examples/elements/arc.png) | `arc` | shapes | |
| ![](https://raw.githubusercontent.com/eigger/imagespec/main/examples/elements/polygon.png) | `polygon` | shapes | |
| ![](https://raw.githubusercontent.com/eigger/imagespec/main/examples/elements/gauge.png) | `gauge` | shapes | |
| ![](https://raw.githubusercontent.com/eigger/imagespec/main/examples/elements/text.png) | `text` | text | + rotation, background box |
| ![](https://raw.githubusercontent.com/eigger/imagespec/main/examples/elements/text_box.png) | `text_box` | text | |
| ![](https://raw.githubusercontent.com/eigger/imagespec/main/examples/elements/multiline.png) | `multiline` | text | |
| ![](https://raw.githubusercontent.com/eigger/imagespec/main/examples/elements/new_multiline.png) | `new_multiline` | text | fit-to-width/height autosize |
| ![](https://raw.githubusercontent.com/eigger/imagespec/main/examples/elements/text_fit.png) | `text_fit` | text | fit text into a fixed box: shrink font / ellipsis / wrap |
| ![](https://raw.githubusercontent.com/eigger/imagespec/main/examples/elements/table.png) | `table` | text | |
| ![](https://raw.githubusercontent.com/eigger/imagespec/main/examples/elements/qrcode.png) | `qrcode` | codes | `eclevel`, pixel `width`/`height` sizing |
| ![](https://raw.githubusercontent.com/eigger/imagespec/main/examples/elements/barcode.png) | `barcode` | codes | |
| ![](https://raw.githubusercontent.com/eigger/imagespec/main/examples/elements/datamatrix.png) | `datamatrix` | codes | optional dep `pyStrich` (`imagespec[datamatrix]`) |
| ![](https://raw.githubusercontent.com/eigger/imagespec/main/examples/elements/icon.png) | `icon` | media | Material Design Icons (default) **+ Font Awesome Free** (`fa:`/`fas:`/`far:`/`fab:`); needs bundled `icons/` assets |
| ![](https://raw.githubusercontent.com/eigger/imagespec/main/examples/elements/dlimg.png) | `dlimg` | media | + fit modes (stretch/fit/fill/contain) |
| ![](https://raw.githubusercontent.com/eigger/imagespec/main/examples/elements/diagram.png) | `diagram` | charts | bar chart |
| ![](https://raw.githubusercontent.com/eigger/imagespec/main/examples/elements/plot.png) | `plot` | charts | needs `history_provider`; + area_fill, xlegend |
| ![](https://raw.githubusercontent.com/eigger/imagespec/main/examples/elements/progress_bar.png) | `progress_bar` | charts | + rounded corners |
| ![](https://raw.githubusercontent.com/eigger/imagespec/main/examples/elements/pie.png) | `pie` | charts | pie / donut (`inner_radius`) |
| ![](https://raw.githubusercontent.com/eigger/imagespec/main/examples/elements/sparkline.png) | `sparkline` | charts | compact axis-less line from inline values |
| ![](https://raw.githubusercontent.com/eigger/imagespec/main/examples/elements/rich_text.png) | `rich_text` | text | inline spans: icon + text + color on one line |
| ![](https://raw.githubusercontent.com/eigger/imagespec/main/examples/elements/group.png) | `group` | layout | container: child elements at an offset, clipped, optionally rotated |
| ![](https://raw.githubusercontent.com/eigger/imagespec/main/examples/elements/column.png) | `stack` / `row` / `column` | layout | auto-layout: packs children along an axis (gap/padding/justify/align), flexbox-style, with optional Tailwind-like `class` shorthand |
| ![](https://raw.githubusercontent.com/eigger/imagespec/main/examples/elements/legend.png) | `legend` | widgets | color-swatch ↔ label rows (vertical/horizontal) for `pie`/`plot` |
| ![](https://raw.githubusercontent.com/eigger/imagespec/main/examples/elements/star_rating.png) | `star_rating` | widgets | full/half/empty stars for rating labels |
| ![](https://raw.githubusercontent.com/eigger/imagespec/main/examples/elements/battery.png) | `battery` | widgets | vector battery gauge with proportional fill |

`render(..., dither=True|"atkinson"|…)` dithers the whole output (15 algorithms
+ `none`; see [`docs/dithering.md`](docs/dithering.md)) and **any element** can
carry its own `dither` bool/method to override it just for itself.

## Payload specification

Payloads are specified as a list (sequence) of dictionary elements, which can be easily authored in YAML or JSON. Each element requires a `type` string and varying geometric/styling attributes.

> [!TIP]
> **Element-by-element YAML examples:** [`docs/elements.md`](docs/elements.md)
>
> **Generating payloads with an LLM?** See [`docs/authoring.md`](docs/authoring.md) — a
> **self-contained authoring guide** you can paste straight into an AI's context. It
> covers the output contract, the layout decision model (`stack`/`row`/`column` vs
> `group` vs absolute coordinates), the Tailwind-like `class` shorthand, common
> pitfalls (e.g. the YAML "one key per line" trap), device canvas sizes, and full
> worked examples — every example verified by actually rendering it.

### Element reference & JSON Schema

Every element's keys, types and defaults are declared once, next to its handler
(`@element("circle", fields=[num("x", required=True), ...])`), and everything
else is generated from those declarations:

- [`docs/reference.md`](docs/reference.md) — the full key reference
- [`schema/elements.json`](schema/elements.json) — JSON Schema (draft 2020-12)
  for a whole payload; use it in an editor or validator to catch typos, missing
  required keys and bad enum values before rendering
- template-string coercion (`"42"` → `42`, `"False"` → `False`) — driven by the
  declared key types
- `imagespec.validate(payload)` — the same checks at runtime, without a JSON
  Schema library: returns `[Issue(path, message), ...]` such as
  `[2].fill: unknown key for 'circle'`, tolerating template strings and `null`
  exactly as `render()` does. `render(..., strict=True)` runs it first and
  raises `RenderError` listing every issue.

`python scripts/export_schema.py` regenerates the two files; CI fails if they
drift from the declarations, and a guard test fails if a handler reads a key it
did not declare. The web payload editor in
[`eigger.github.io`](https://github.com/eigger/eigger.github.io) keeps its
supported subset in `schema/editor_types.json`.

### Common attributes
- **Colors**: names (`black`, `white`, `red`, `green`, `blue`, `orange`, `yellow`, any CSS name) or HEX (`#FF0000`, `#f00`); quantized to the device palette at the end of `render()`.
- **Coordinates**: pixels from the top-left corner `(0, 0)`.
- **Numbers and booleans** also accept the string forms Home Assistant templates produce.
- **`visible`**, **`dither`**, **`class`** / **`layout`** are accepted by every element (see the reference).

### Dithering

`imagespec` can dither full-color content onto limited palettes (2-color B/W,
3-color BWR, 7-color ACeP, …). Besides flat nearest-color mapping (`none`), it
ships **15 e-ink-oriented dither algorithms** (Floyd–Steinberg, Atkinson,
Jarvis, Stucki, Burkes, Sierra family, Stevenson–Arce, Bayer 2/4/8/16,
clustered-dot 4/8).

- `dither=False` / `"none"` (default) → flat nearest color
- `dither=True` / `"floyd"` → Floyd–Steinberg (backward compatible)
- `dither="atkinson"` / `"bayer8"` / … → any name in `DITHER_METHODS`

Per-element overrides accept the same bool or method string. Full gallery,
API notes, and per-algorithm tiles: **[`docs/dithering.md`](docs/dithering.md)**.

```bash
python examples/generate_dither_methods.py   # all-method grids + tiles
```

![All dither methods on B/W](https://raw.githubusercontent.com/eigger/imagespec/main/examples/dither_methods_bw.png)

Without dithering, colors snap to the nearest palette entry and gradients band
badly. Dithering trades spatial resolution for perceived depth.

#### 1. Gradient & 3D Shading
Dithering creates a natural halftone pattern that simulates smooth shading and eliminates color banding.
![Gradient Dithering Comparison](https://raw.githubusercontent.com/eigger/imagespec/main/examples/dither_comparison_gradient.png)

#### 2. Font Rendering (Anti-aliasing vs. Dithering)
> [!IMPORTANT]
> **Guidelines for Text:** Avoid dithering on text layers. Dithering anti-aliased font edges creates tiny dot noise, which severely degrades readability on low-resolution e-ink screens. For sharp text, use direct quantization or disable anti-aliasing (`fontmode = "1"`). The built-in `text` element enforces `fontmode = "1"` for this reason.
![Font Dithering Comparison](https://raw.githubusercontent.com/eigger/imagespec/main/examples/dither_comparison_font.png)

#### 3. Charts & Solid Fills
Dithering is useful when you have solid color regions (like pie slices or bar diagrams) in colors outside your device palette (e.g. orange on a black/white screen). Dithering simulates these colors with dot patterns to help distinguish segments, though it introduces some edge noise.
![Chart Dithering Comparison](https://raw.githubusercontent.com/eigger/imagespec/main/examples/dither_comparison_chart.png)

#### How palette mapping works
Every element is drawn in **full color**, and the whole image is mapped to
`context.palette` **once at the end** of `render()`. The `dither` flag only picks
*how* that single mapping happens:

- `dither=True` / `"floyd"` → Floyd–Steinberg (or pass another method name)
- `dither=False` / `"none"` (default) → flat nearest color

Either way the output is **strictly on-palette**. Because mapping is deferred,
in-palette colors (e.g. black text on white) stay crisp under dithering —
error diffusion spreads no error when a pixel already equals a palette color —
while the text guidance above still applies to *off-palette* text you choose to
dither.

```python
ctx = RenderContext(palette="bw")
img = render(payload, 296, 128, dither=True, context=ctx)
img = render(payload, 296, 128, dither="atkinson", context=ctx)
# orange/green/blue pie slices -> different dot patterns, not one black blob
```

#### Per-element `dither` override
Any element may carry its own `dither: true`/`false`/method name to override the
global flag just for itself — so you can dither only the parts that benefit
(photos, charts) and keep the rest flat (labels, QR codes), in a single render:

```yaml
- type: dlimg          # this photo -> halftone
  url: "https://…/photo.png"
  xsize: 100
  ysize: 100
  dither: atkinson
- type: pie            # this chart -> ordered screen
  x: 60
  y: 60
  radius: 40
  values: "Gas,30,orange;Water,25,blue;Elec,45,red"
  dither: bayer8
- type: text           # left flat regardless of the global flag
  x: 10
  y: 110
  value: "Energy mix"
```

An element with an explicit `dither` is rendered in isolation and mapped to the
palette immediately (then composited in payload order), so its choice survives
the final whole-image pass. Elements without the key follow the global `dither`
argument. (QR/barcode and black text are pure palette colors, so they stay crisp
under the global flag anyway — set `dither: false` only for *off-palette* content
you want kept solid.)

#### Device samples
Both labels below mix crisp content (text, QR, barcode) with charts authored in
off-palette colors and marked `dither: true` — the charts become halftones so
their segments stay distinguishable, while everything else stays sharp.

**Electronic shelf label — 3-color (black / white / red):**

![ESL 3-color dithering sample](https://raw.githubusercontent.com/eigger/imagespec/main/examples/dither_esl_3color.png)

**Label printer — 2-color (black / white):**

![Label printer 2-color dithering sample](https://raw.githubusercontent.com/eigger/imagespec/main/examples/dither_label_2color.png)

Regenerate them with:
```bash
python examples/generate_dither_labels.py
```

Older Floyd-vs-none comparison boards:
```bash
python examples/compare_dither.py
```

## Fonts & assets

Bundled in the package (offline baseline, ~12 MB total):

- `icons/materialdesignicons-webfont.ttf` + `_meta.json` — `icon`'s default set
  (`mdi:` prefix, or no prefix).
- `icons/fontawesome-free-{solid,regular,brands}.otf` + trimmed metadata —
  `icon`'s second set (`fa:`/`fas:`/`far:`/`fab:` prefix).
- `fonts/NotoSansKR-Regular.ttf` — the only bundled font, and the default for
  every payload (`RenderContext.default_font`).

Anything else is resolved at runtime, in order: `font_resolver` (host) →
bundled font of the same basename → bundled default. Helpers in
`imagespec.resolvers`:

- `directory_resolver(dir)` — look up fonts in a host directory (e.g. `www/fonts`).
- `caching_resolver(cache_dir, sources)` — **download on first use, cache to
  disk, reuse offline** (internet needed only once per font).
- `google_fonts_resolver(cache_dir, families=None)` — a `caching_resolver`
  preset over verified-license Google Fonts (`ofl/` directory → all SIL OFL
  1.1), covering scripts the bundled Noto Sans KR doesn't: Japanese, Simplified/
  Traditional Chinese, Arabic, Thai, plus a broader Latin/Cyrillic/Greek family.
  See `GOOGLE_FONTS_SOURCES` for the exact list.
- `chain_resolvers(a, b, ...)` — try several in order.

The package bundles only this baseline: decorative or other-script fonts are
better downloaded-and-cached (`google_fonts_resolver`/`caching_resolver`) or
served by the host (e.g. Home Assistant's `www/fonts`) through `font_resolver`.
Only fonts with a verifiable license are bundled — see *Licensing & attribution*
below.

### Licensing & attribution

`imagespec` is **MIT AND Apache-2.0** (see the `license` field in
`pyproject.toml`) — not pure MIT — because it's a combined work:

| Component | License | Source |
|---|---|---|
| imagespec's own code/modifications | MIT | [`LICENSE`](https://github.com/eigger/imagespec/blob/main/LICENSE) |
| Rendering engine origin (registry dispatch, element handlers) | Apache License 2.0 | [OpenEPaperLink Home Assistant Integration](https://github.com/OpenEPaperLink/Home_Assistant_Integration) — see [`NOTICE`](https://github.com/eigger/imagespec/blob/main/NOTICE) |
| `icons/materialdesignicons-webfont.ttf` (+ metadata) | Apache License 2.0 | [Pictogrammers / Templarian MaterialDesign-Webfont](https://github.com/Templarian/MaterialDesign-Webfont) |
| `icons/fontawesome-free-*.otf` (+ metadata) | SIL OFL 1.1 (fonts) / CC BY 4.0 (icons) | [Font Awesome Free](https://github.com/FortAwesome/Font-Awesome) |
| `fonts/NotoSansKR-Regular.ttf` | SIL Open Font License 1.1 | [Google Noto Fonts](https://fonts.google.com/noto/specimen/Noto+Sans+KR) |

The engine was originally adapted from OpenEPaperLink's code and has since been
substantially rewritten and extended (palette/color model, device-aware
rotation, dithering, new elements, ...); [`NOTICE`](https://github.com/eigger/imagespec/blob/main/NOTICE) documents this per
the Apache License's redistribution terms. Full license texts ship in the
package: [`LICENSE-APACHE-2.0`](https://github.com/eigger/imagespec/blob/main/LICENSE-APACHE-2.0) (covers the engine origin
and the MDI font), [`icons/LICENSE`](https://github.com/eigger/imagespec/blob/main/src/imagespec/icons/LICENSE) (a co-located
copy for the icons directory), [`icons/LICENSE-FONTAWESOME`](https://github.com/eigger/imagespec/blob/main/src/imagespec/icons/LICENSE-FONTAWESOME)
(Font Awesome Free — also notes brand-icon trademark restrictions), and
[`fonts/OFL.txt`](https://github.com/eigger/imagespec/blob/main/src/imagespec/fonts/OFL.txt).

## Integrating into a host

Build a `RenderContext` (palette, font lookup, history provider), call
`render()`, translate `RenderError` into the host's error type — about 60 lines.
[`docs/integrating.md`](docs/integrating.md) walks through it with a Home
Assistant adapter.
