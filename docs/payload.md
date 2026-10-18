# Writing an imagespec payload

**English** | [한국어](payload.ko.md)

This guide explains the common image description used by integrations and other hosts. The renderer creates an image; it does not discover devices, send Bluetooth data, print a label or refresh a display. Use your integration’s payload guide for its real action name, target, accepted wrapper fields and device settings. Library examples below run locally without Home Assistant or hardware.

## Payload and host action are different

An imagespec payload is a **list of element mappings**, drawn in order. Each mapping has a `type` and that element’s properties. Coordinates are pixels from the top-left; later elements may cover earlier ones. A `group`, `stack`, `row` or `column` can contain child `elements` with its own layout rules.

```yaml
- type: text
  x: 12
  y: 12
  value: "Hello, imagespec"
  size: 22
  color: black
```

This is the payload itself, not a complete HA action. A host may place the list under a `payload` field alongside device-specific targets and output options, or accept it another way. Do not paste an invented universal action wrapper into an automation. The Python API receives the parsed list; width, height, global rotation and dithering are separate `render()` arguments, and palette/resolvers are in `RenderContext`. They are not automatically top-level payload elements or fields accepted by every HA action.

Use the [element examples](elements.md) and generated [property reference](reference.md) (English) for actual keys, required fields, defaults and nested options. The [authoring guide](authoring.md) (English) covers layout choices and complete scenes. The [JSON Schema](../schema/elements.json) can help an editor find mistakes; compare its version with the imagespec version used by your integration.

## Minimal working example

[examples/payload/minimal.yaml](../examples/payload/minimal.yaml) is a complete, offline payload for a **296 × 128** demonstration canvas with a black/white palette and no rotation. Those dimensions are an example, not a claim about your device. It contains a rectangle border, text using the bundled font, and a horizontal line. Adapt the dimensions and coordinates together for your actual device.

From this checkout, Python **3.13+** can load and render it with the optional YAML extra:

```bash
python -m pip install '.[yaml]'
python - <<'PY'
from pathlib import Path

import yaml
from imagespec import RenderContext, RenderError, render, validate

payload = yaml.safe_load(Path("examples/payload/minimal.yaml").read_text())
issues = validate(payload)
if issues:
    raise SystemExit("\n".join(map(str, issues)))

try:
    image = render(
        payload,
        width=296,
        height=128,
        rotate=0,
        rotate_mode="canvas",
        background="white",
        dither=False,
        strict=True,
        context=RenderContext(palette="bw"),
    )
except (RenderError, ValueError) as exc:
    raise SystemExit(str(exc)) from exc

image.save("/tmp/imagespec-minimal.png")
print(image.mode, image.size)
PY
```

Expected output: `RGB (296, 128)`, with only black and white pixels. The file is a preview, not device transmission. The `yaml` extra supplies PyYAML; YAML parsing is optional when a host already provides Python dictionaries. Rendering this example needs no external image, downloaded font, history provider or extra barcode dependency.

## Values, templates and visibility

Prefer ordinary YAML numbers and booleans. Declared numeric fields also accept strings such as `x: "12"` or `size: "22"`; boolean fields accept `"False"`, `"off"` and `"0"`. `visible: false` hides an element. Omitting an optional key uses its default; `null` usually acts as omission, with exceptions such as colors (`null` means no fill/outline), per-element `dither` (`null` inherits the global setting), and fields with documented special meanings. Read the reference for that field rather than assuming every `null` is interchangeable.

HA/Jinja template evaluation belongs to the **host integration**, before imagespec receives the values. imagespec converts declared numeric/boolean strings; it does not evaluate `{{ ... }}`, look up HA states, or provide a universal template syntax. A coordinate still containing a Jinja expression is not a number. Check the integration’s supported template fields, then inspect the rendered value. Ordinary text containing braces is just text unless the host renders it.

YAML indentation and quoting still matter: quote HEX colors (`"#ff0000"`) so `#` does not start a comment, and keep each mapping key on its own line. Check whether the host expects a list or a YAML string; parsing that wrapper is the host’s responsibility.

## Size, colors, rotation and dithering

The integration controls the actual model dimensions, supported colors and final device encoding. Rendering a requested color does not add that color to the hardware.

| Setting | Common behavior | Device-specific decision |
|---|---|---|
| Width / height | Positive render dimensions in pixels | Supported panel resolution or print width/label dimensions; media limits and accepted action fields |
| Palette | `RenderContext(palette="bw")`, `"bwr"`, other named palettes, or an explicit supported-color list | Actual model colors; avoid assuming every e-paper display supports red or every printer has the same width |
| Requested colors | Names or quoted HEX; final RGB pixels are mapped to the palette | Off-palette colors change appearance; compare a preview with the model palette |
| `rotate` | Global `0`, `90`, `180`, `270` degrees clockwise | Physical orientation and whether the integration exposes rotation |
| `rotate_mode="canvas"` | At 90/270, drawing surface is height × width; output stays width × height | Fixed-resolution displays |
| `rotate_mode="image"` | At 90/270, draw at width × height then rotate; output becomes height × width | Hosts that permit swapped image dimensions, such as variable-size label output |
| `dither` | `False` / `"none"`: nearest palette color; `True` / `"floyd"`: Floyd–Steinberg; named method such as `"atkinson"` or `"bayer8"` | Whether the host exposes global or per-element options and which output is readable on the device |

For a 296 × 128 call with `rotate=90`, canvas mode draws on 128 × 296 and returns 296 × 128; image mode draws on 296 × 128 and returns 128 × 296. At 0/180 the two modes have the same dimensions. Element rotation is separate from global canvas rotation. Since imagespec 1.1.0, elements without a type-specific `rotate` field accept clockwise `rotate: 0`, `90`, `180` or `270`. Existing type-specific rotation keeps its documented meaning: `text.rotation` is counter-clockwise, while `dlimg.rotate` is clockwise and follows EXIF orientation before resizing. Check the installed version and element reference before using these fields.

Use `DITHER_METHODS` from the installed library, or the [dithering reference](dithering.md) (English), for supported method names. Dithering simulates tones using supported palette colors; it cannot create extra physical colors. Per-element `dither` can override the global choice. Start with crisp text, QR and barcode content; use photo/chart dithering only when the result improves readability. Keep QR/barcode modules large enough for the actual print/display resolution and check scanning on the real output separately.

## Fonts, images, history and optional capabilities

- **Fonts:** the package includes `NotoSansKR-Regular.ttf` as the default. Font lookup tries the host’s `font_resolver`, a bundled font with the same basename, then the bundled default. A missing requested font can therefore fall back rather than fail. Other scripts or decorative fonts may need a host resolver and appropriate licensed files. The library does not assume an HA `www/fonts` path; that lookup is supplied by the integration. Download/cache resolvers exist for hosts that configure them, but do not imply every integration downloads fonts automatically. See [fonts and assets](../README.md#fonts--assets) (English).
- **Icons and codes:** bundled MDI and Font Awesome Free assets support their documented names. Do not assume paid Font Awesome icons are included. `datamatrix` needs the optional `datamatrix` extra (`pyStrich`); QR/barcode behavior and options are in the element reference. The `fast` extra adds optional numpy acceleration for dithering, not additional physical device capabilities.
- **Images (`dlimg`):** HTTP(S) and `data:` URLs are supported. Local paths are disabled unless the host sets `allow_local_images=True`. Host filesystem paths and public/browser-accessible URLs are not necessarily accessible from the integration. Authentication/session support requires the host’s `image_fetcher`; do not place secrets in public examples. Built-in HTTP downloads use a size cap (`max_image_bytes`, default 20 MiB) and optional host-configured TTL caching (off by default). A custom fetcher returns bytes and must enforce its own streaming memory limit if needed. These controls are Python context options, not guaranteed HA action fields.
- **History (`plot`):** a host `history_provider` is required. imagespec does not import HA recorder, read entities or fetch history automatically. Other inline-data chart elements have their own schemas. Do not add `plot` merely because an example from another integration supports history.

## Validation and troubleshooting

`validate(payload)` returns `Issue(path, message)` objects; an empty list means no declared-schema issues were found. It checks unknown types/keys, missing required values, declared kinds and relevant enums/colors. It does not prove that a font exists, an image URL responds, history is available, content fits the device, or the final device operation works. Render locally with the host’s real capabilities after validation.

`render(..., strict=True)` runs the same checks and raises `RenderError` listing issues. Without strict mode, unknown keys are generally ignored and unknown element types are logged and skipped; a preview can therefore look incomplete without an exception. Use validation to catch typos rather than relying on lenient rendering. The installed version’s `known_types()` and reference determine support, not a newer online example.

Handler failures are surfaced as `RenderError` with element context. `err.path` identifies an element or nested child (for example `[1].elements[0]`), `err.message` is the bare message and `str(err)` includes the path. Global invalid size, rotation or rotation mode can raise `ValueError`; not every error is a `RenderError` or proof of a device fault.

| Problem | First check |
|---|---|
| Blank or missing item | `visible`, type spelling/version, coordinates, clipping and later overlapping elements; run `validate()` |
| Unknown key / missing required key | Exact element property in the reference; inspect the path rather than changing unrelated elements |
| Numeric value rejected | Final host template result, missing/unavailable state and numeric fallback; imagespec does not evaluate Jinja |
| Wrong size / sideways / cropped | Actual model size, global rotation mode and element-specific geometry; preview in the same output settings |
| Color changed / weak readability | Actual palette, dithering and text/module size; previews do not verify hardware readability |
| Font or image missing | Host resolver/path, URL accessibility/authentication, supported glyphs and required assets |
| History unavailable | Whether this integration supplies a `history_provider`; use an inline-data element only if appropriate |
| Preview succeeds but device does not update | Return to the integration’s transport/device troubleshooting; image rendering and delivery are separate |

For help, use the integration’s existing Issues/support route and device-specific payload guide. Include the installed integration/imagespec versions, actual dimensions/palette/rotation, a minimal sanitized payload, the exact error and whether local rendering or device delivery failed. Remove private entity names, images, URLs, addresses and credentials. Follow the existing reporting process rather than creating a duplicate generic report. See [host integration guidance](integrating.md) (English) for developer-specific capabilities.
