# Dithering

`imagespec` maps every render to the device palette **once at the end** of
`render()`. The `dither` argument only chooses *how* that mapping happens.

- Off-palette fills (photos, gradients, chart colors the panel cannot show)
  become distinguishable **halftone / ordered patterns**.
- In-palette colors (black text on white, QR/barcodes) stay crisp — error
  diffusion has nothing to spread when a pixel already equals a palette entry.
- The output is always **strictly on-palette**.

> **Text guideline:** Prefer not to dither anti-aliased text. Tiny edge noise
> hurts readability on low-resolution e-ink. Built-in `text` uses `fontmode="1"`
> for this reason. Keep QR/barcodes undithered as well.

Supported methods are those with **medium-or-better e-ink suitability**
(15 dither algorithms + `none`; error diffusion with serpentine scan, plus
Bayer / clustered-dot screens).

Regenerate the comparison images:

```bash
python examples/generate_dither_methods.py
```

## Source scene

Each tile below is the same source (rainbow strip, gray ramp, shaded sphere on a
warm fill) quantized to the given palette.

![Source scene](../examples/dither_methods/source.png)

## All methods — black / white

![All dither methods on B/W](../examples/dither_methods_bw.png)

## All methods — black / white / red

![All dither methods on BWR](../examples/dither_methods_bwr.png)

## Usage

```python
from imagespec import RenderContext, render, DITHER_METHODS

ctx = RenderContext(palette="bw")

# Backward compatible
img = render(payload, 296, 128, dither=True, context=ctx)  # = "floyd"
img = render(payload, 296, 128, dither=False, context=ctx)  # = "none"

# Explicit algorithm
img = render(payload, 296, 128, dither="atkinson", context=ctx)
img = render(payload, 296, 128, dither="bayer8", context=ctx)
```

Per-element override (bool or method name) — use on **photos and charts**
(`dlimg`, `pie`, `diagram`, `plot`, `sparkline`, `progress_bar`, `gauge`) when
they use off-palette colors. Leave text/QR/barcodes without `dither`:

```yaml
- type: dlimg
  x: 0
  y: 0
  xsize: 120
  ysize: 80
  url: https://example.com/photo.png
  dither: atkinson
- type: pie
  x: 140
  y: 10
  radius: 40
  values: "A,40,orange;B,60,blue"
  dither: bayer8
- type: diagram
  x: 240
  y: 10
  width: 120
  height: 80
  bars:
    values: "Mon,10;Tue,25;Wed,15"
    color: orange
  dither: floyd
- type: text
  x: 10
  y: 100
  value: Keep me sharp
  # no dither key → follows global flag (prefer global none)
```

## Method gallery (B/W)

Individual tiles for each algorithm on a 2-color palette.

### none

Flat nearest-color snap. Best for text, icons, QR/barcodes.

![none](../examples/dither_methods/none_bw.png)

### floyd

Floyd–Steinberg error diffusion (default when `dither=True`). Good general
purpose halftone for photos and charts.

![floyd](../examples/dither_methods/floyd_bw.png)

### atkinson

Bill Atkinson’s kernel (only ¾ of the error is diffused). Preserves highlights;
popular on early Mac / e-ink UIs.

![atkinson](../examples/dither_methods/atkinson_bw.png)

### jarvis

Jarvis–Judice–Ninke — wide kernel, smoother tones, a bit heavier.

![jarvis](../examples/dither_methods/jarvis_bw.png)

### stucki

Stucki — Jarvis-like quality with a slightly different kernel.

![stucki](../examples/dither_methods/stucki_bw.png)

### burkes

Burkes — lighter than Jarvis, still smooth.

![burkes](../examples/dither_methods/burkes_bw.png)

### sierra

Sierra-3 — balanced three-row diffusion.

![sierra](../examples/dither_methods/sierra_bw.png)

### sierra2

Two-row Sierra — faster, still organic.

![sierra2](../examples/dither_methods/sierra2_bw.png)

### sierra-lite

Minimal Sierra kernel — quick, coarser grain.

![sierra-lite](../examples/dither_methods/sierra-lite_bw.png)

### stevenson-arce

Stevenson–Arce — large kernel, soft grain (medium e-ink suitability).

![stevenson-arce](../examples/dither_methods/stevenson-arce_bw.png)

### bayer2 / bayer4 / bayer8 / bayer16

Ordered Bayer matrices. Deterministic patterns; often stable under partial
e-ink refresh. Larger matrices look finer.

![bayer2](../examples/dither_methods/bayer2_bw.png)

![bayer4](../examples/dither_methods/bayer4_bw.png)

![bayer8](../examples/dither_methods/bayer8_bw.png)

![bayer16](../examples/dither_methods/bayer16_bw.png)

### clustered4 / clustered8

Clustered-dot screens (print / newspaper look). Deterministic like Bayer;
medium e-ink suitability.

![clustered4](../examples/dither_methods/clustered4_bw.png)

![clustered8](../examples/dither_methods/clustered8_bw.png)

## Choosing a method

| Goal | Suggested methods |
|------|-------------------|
| Default / photos & charts (`dlimg`, `pie`, `diagram`, `plot`, `sparkline`, `progress_bar`, `gauge`) | `floyd`, `atkinson`, `sierra` |
| Softer gradients | `jarvis`, `stucki`, `burkes` |
| Stable ordered pattern (partial refresh) | `bayer8`, `bayer4` |
| Print-like dots | `clustered8` |
| Text / QR / barcode | `none` (or omit dither) |

## API notes

- `True` ≡ `"floyd"`, `False` ≡ `"none"`.
- Aliases: `floyd-steinberg`, `fs`, `jjn`, `sierra3`, `bayer`, `ordered`,
  `clustered-dot-8`, …
- Canonical list: `from imagespec import DITHER_METHODS`.
- Error-diffusion methods use **serpentine** scanning to reduce worm artifacts
  on e-ink.
