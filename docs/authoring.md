# Authoring guide (for LLMs & humans)

This document is **self-contained**: paste the whole file into an AI's context
(system prompt) and it has everything needed to generate valid, well-composed
`imagespec` payloads. It focuses on the **output contract**, the **layout
model**, and **common pitfalls**. For the exhaustive per-element key list, see
the *Element Reference* in [`../README.md`](../README.md); the most common
elements are also cheat-sheeted at the bottom here.

---

## 1. Output contract (read this first)

A payload is a **list (sequence) of element dicts** — author it as YAML or JSON.

- Every element is a **dict (mapping)** with a `type` string and that type's keys.
- The list is drawn in order: **later elements paint on top of earlier ones** (z-order).
- It is rendered by:
  ```python
  from imagespec import render, RenderContext
  ctx = RenderContext(palette="bwr")        # device colors (see §4)
  img = render(payload, width=296, height=128, background="white", context=ctx)
  ```
- **Coordinates are integer pixels.** Origin `(0, 0)` is the **top-left**; `x`
  grows right, `y` grows down.
- Unknown `type`s are warned-and-skipped; a missing **required** key raises a
  clear error naming the element. Keep to the documented keys.

**Do NOT** invent CSS, HTML, percentages (except where a key documents them),
or styling not listed here. Output only the payload (YAML or JSON), nothing else,
unless asked.

---

## 2. The #1 YAML pitfall — never put multiple keys on one line with `;`

YAML is **one key per line**. This is the single most common mistake:

```yaml
# ❌ BROKEN — YAML reads x as the string "10; y: 20", and y/size never exist
- type: text
  x: 10; y: 20; size: 16
  value: "Hi"

# ✅ CORRECT
- type: text
  x: 10
  y: 20
  size: 16
  value: "Hi"

# ✅ Also correct — JSON-style flow mapping on one line (note the commas + braces)
- { type: text, x: 10, y: 20, size: 16, value: "Hi" }
```

Semicolons are only valid **inside quoted string values** (some elements use
them as a data separator, e.g. `values: "Gas,30,orange;Water,25,blue"`).

---

## 3. Layout: pick the right tool

There are three ways to place things. Prefer the highest-level one that fits.

| Need | Use | Why |
|---|---|---|
| Things flow in a **row or column**, evenly spaced | **`stack`** / `row` / `column` | Auto-layout: no manual coordinates, adapts to content size |
| A **reusable/relocatable cluster** placed by absolute offset, clipped | **`group`** | Children use coords relative to the group; one `x`/`y` moves the whole thing |
| **Precise, one-off** pixel placement | plain elements with `x`/`y` | Full manual control |

**Default to `stack`/`row`/`column` for anything list-like** (labels stacked,
icon+value pairs, toolbars, key/value rows). It removes brittle hand-computed
coordinates and is the most robust for AI generation.

### Inside a stack, children need no coordinates

The stack measures each child and positions it. So **omit `x`/`y` on children**
— the stack fills them in. Set spacing with the stack's `gap`/`padding` and the
child's `margin`, not by hand-placing.

```yaml
- type: column          # vertical auto-layout
  x: 8                  # where the whole stack sits
  y: 8
  gap: 4               # px between children
  elements:
    - { type: text, value: "Line 1", size: 16 }   # no x/y
    - { type: text, value: "Line 2", size: 16 }   # auto-placed below
```

`row` = horizontal, `column` = vertical, `stack` = vertical unless
`direction: horizontal`.

### Stack options (structured keys — the canonical form)

Container:
- `direction`: `vertical` (default) | `horizontal`
- `gap`: int px between children
- `padding`: int (all sides), or `padding_x` / `padding_y` / `padding_top` / `padding_right` / `padding_bottom` / `padding_left`
- `justify` (main axis): `start` | `end` | `center` | `between` | `around` | `evenly`
- `align` (cross axis): `start` | `end` | `center`
- `x`, `y` (offset of the whole stack), `width`, `height` (box; default = canvas), `rotate` (90/180/270)

Per child (set on the child dict, under a `layout:` sub-dict to avoid clashing
with the element's own keys):
- `layout: { grow: 1 }` — take a share of leftover main-axis space (push siblings apart)
- `layout: { align: center }` — override the container's cross-axis alignment for this child
- `layout: { margin: 4 }` or `margin_x` / `margin_top` / ... — extra space around this child (may be negative to nudge)

### Optional Tailwind-like `class` shorthand

Anywhere you'd set the structured keys above, you may instead use a `class`
string (it desugars to those keys; **explicit keys win** on conflict). Only the
**layout** subset is recognized — styling/color classes are ignored, so colors
and fonts always stay on the element's own keys.

- container: `flex-row` / `flex-col`, `gap-N`, `p-N` / `px-N` / `py-N` / `pt-N` / `pr-N` / `pb-N` / `pl-N`, `justify-*`, `items-*`
- child: `grow` / `flex-1` / `grow-N`, `self-start|end|center`, `m-N` / `mx-N` / `my-N` / `mt-N` / `mr-N` / `mb-N` / `ml-N`

**Spacing scale = real Tailwind:** a unit is `N × 4px` → `gap-2` = 8px,
`p-4` = 16px, `mt-0.5` = 2px. For **exact pixels** use the arbitrary form
`gap-[10]` / `p-[3px]`. Margins may be **negative** for fine nudges
(`-mt-2` = -8px, `-ml-[3]` = -3px); padding/gap cannot.

```yaml
- type: row
  x: 8
  y: 8
  class: "gap-2 items-center"          # 8px gap, vertically centered
  elements:
    - { type: icon, value: "mdi:fire", size: 18, color: red }
    - { type: text, value: "24°C", size: 16 }
    - { type: battery, width: 30, height: 14, level: 72, class: "ml-2" }
```

---

## 4. Colors & device palette

- `RenderContext(palette=...)` is the **device's** color set. Common shorthands:
  `"bw"`/`"2"` (black/white), `"bwr"`/`"3"` (black/white/red), `"4"`, `"7"`/`"acep"`.
  You can also pass an explicit list: `["black", "white", "red"]`.
- You author colors freely (names like `"black"`, `"red"`, `"blue"`, or `#RRGGBB`);
  the final image is **quantized to the palette**. On a 2-color panel `red`
  becomes black. **Design within the device's palette** — don't rely on colors it
  can't show.
- `dither: true` (whole render, or per element) turns off-palette fills into
  halftone dot patterns so e.g. pie/bar segments stay distinguishable. **Avoid
  dithering text** — it makes edges noisy on small screens.

---

## 5. Common pitfalls checklist

- [ ] **One key per line** in YAML (no `x: 1; y: 2`). See §2.
- [ ] Inside a `stack`/`row`/`column`, **don't give children `x`/`y`** — let the stack place them.
- [ ] Outside a stack, plain elements **need** their position keys (`text` needs `x`; rectangles need `x_start`/`y_start`/`x_end`/`y_end`).
- [ ] Use **colors the palette supports**; otherwise expect quantization (or use `dither`).
- [ ] `class` numbers are the **Tailwind 4px scale** (`gap-2` = 8px), not raw pixels — use `gap-[8]` for exact px.
- [ ] Keep content inside the canvas; overflow is **clipped**, not resized.
- [ ] `class` only affects **layout**; set color/size/font on the element itself.

---

## 6. Device canvas sizes (typical)

Pass these as `width`/`height` to `render(...)`. Exact values depend on the
panel; confirm with the device.

| Device class | Typical `width × height` | Palette |
|---|---|---|
| 2.13" ESL tag | 250 × 122 | bw / bwr |
| 2.9" ESL tag | 296 × 128 | bw / bwr |
| 4.2" ESL tag | 400 × 300 | bwr / 7-color |
| Label printer (variable length) | width fixed, height per label | bw |

---

## 7. Worked examples (each verified by rendering)

### 7a. Price / shelf label — 296×128, palette `bwr`

A title, a price built from an inline `row` (so `$`, amount and `/kg` sit on one
baseline), and a barcode — all stacked with a `column`.

```yaml
- type: column
  x: 8
  y: 8
  width: 280
  height: 112
  class: "gap-2"
  elements:
    - type: text
      value: "Organic Bananas"
      size: 20
    - type: row
      class: "items-end gap-1"
      elements:
        - { type: text, value: "$", size: 22, color: red }
        - { type: text, value: "3.49", size: 40, color: red }
        - { type: text, value: "/kg", size: 16, class: "mb-[6]" }
    - type: barcode
      data: "0123456789012"
      width: 200
      height: 30
      write_text: false
```

### 7b. Weather widget — 250×122, palette `4`

An icon beside a `column` of city/temperature/condition. Note the children carry
no coordinates.

```yaml
- type: row
  x: 6
  y: 6
  class: "gap-3 items-center"
  elements:
    - { type: icon, value: "mdi:weather-partly-cloudy", size: 56 }
    - type: column
      class: "gap-1"
      elements:
        - { type: text, value: "Seoul", size: 18 }
        - { type: text, value: "21 C", size: 32 }
        - { type: text, value: "Partly cloudy", size: 14 }
```

### 7c. Dashboard rows — 296×128, palette `bwr`

A header row using `justify-between` (title left, battery right), then a metrics
row using `justify-evenly` with two centered icon+value columns.

```yaml
- type: row
  x: 6
  y: 6
  width: 284
  class: "justify-between items-center"
  elements:
    - { type: text, value: "Living Room", size: 18 }
    - { type: battery, width: 34, height: 16, level: 64 }
- type: row
  x: 6
  y: 44
  width: 284
  class: "gap-4 justify-evenly"
  elements:
    - type: column
      class: "items-center gap-1"
      elements:
        - { type: icon, value: "mdi:thermometer", size: 28, color: red }
        - { type: text, value: "23 C", size: 16 }
    - type: column
      class: "items-center gap-1"
      elements:
        - { type: icon, value: "mdi:water-percent", size: 28 }
        - { type: text, value: "45%", size: 16 }
```

---

## 8. Cheat-sheet — most-used elements

Full list & all keys: *Element Reference* in [`README.md`](../README.md) and
[`elements.md`](elements.md) (copy-paste examples per type).
`(req)` = required.

- **`text`** — `x`(req), `value`(req), `y`, `size`(=12), `color`(="black"), `font`, `anchor`. *Inside a stack, omit `x`/`y`.*
- **`rectangle`** — `x_start`/`y_start`/`x_end`/`y_end`(req), `fill`, `outline`, `width`, `radius`.
- **`line`** — `x_start`/`y_start`/`x_end`/`y_end`(req), `fill`, `width`, `dash`.
- **`icon`** — `x`/`y`(req outside a stack), `value`(req, e.g. `"mdi:home"`), `size`(=24), `color`.
- **`qrcode`** — `x`/`y`(req), `data`(req), `boxsize` **or** `width`/`height` (px box), `eclevel`.
- **`barcode`** — `x`/`y`(req), `data`(req), `code`(="code128"), `width`/`height` (px box), `write_text`.
- **`dlimg`** — `x`/`y`/`xsize`/`ysize`(req), `url`(req, http(s)/data:), `mode` (stretch/fit/fill/contain), `dither`, `circle`.
- **`progress_bar`** — `x_start`/`y_start`/`x_end`/`y_end`(req), `progress` 0–100 (req), `fill`, `background`, `radius`, `show_percentage`.
- **`battery`** — `x`/`y`/`width`/`height`(req), `level` 0–100 (req), `fill`, `low_threshold`, `low_color`, `show_percentage`.
- **`pie`** — `x`/`y`(req center), `radius`(req), `values`(req, `"label,num,color;..."`), `inner_radius` (donut).
- **`sparkline`** — `x`/`y`/`width`/`height`(req), `values`(req), `fill`, `dot_last`.
- **`text_fit`** — `x`/`y`/`width`/`height`(req), `value`(req); shrinks/wraps/ellipsizes text into the box.
- **`stack`/`row`/`column`** — `elements`(req); see §3.
- **`group`** — `elements`(req), `x`/`y` offset, `width`/`height` clip box, `rotate`.
