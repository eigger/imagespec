# Changelog

All notable changes to imagespec. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); the project uses
[Semantic Versioning](https://semver.org/) — until 1.0, a minor bump may carry
a behaviour change, and every such change is listed under **Changed** with the
old and new behaviour.

`schema_version` in `schema/elements.json` is bumped whenever the payload
contract (keys, kinds, required-ness, `null` semantics) changes shape.

## [Unreleased]

## [0.5.0] — 2026-09-21

The payload becomes a checkable contract: every element declares its keys once,
and the JSON Schema, the reference, the template-string coercion and a runtime
validator are all derived from those declarations. Rendering output is
unchanged for valid payloads (all golden images pass byte-for-byte).

### Added

- **Element specs** ([#19]): `@element(..., fields=[num("x", required=True), ...])`
  declares each handler's keys, kinds, defaults and docs next to the code that
  reads them. `imagespec.get_spec(name)` / `imagespec.specs()` expose them.
- **`schema/elements.json`** (JSON Schema draft 2020-12, `schema_version: 2`)
  and **`docs/reference.md`** are generated from the specs by
  `scripts/export_schema.py`; CI fails if either drifts ([#19]). The schema has
  one `$def` per element with `additionalProperties: false`, so typos are
  rejected; `$defs/element` requires `x`/`y` while `$defs/stack_child` does not.
- **`imagespec.validate(payload) -> list[Issue]`** ([#20]): the same checks at
  runtime without a JSON Schema library — unknown types, undeclared keys,
  missing required keys, wrong kinds, enum and `dither` violations — with a
  path per issue (`[0].elements[2].fill: unknown key for 'circle'`). It applies
  the renderer's tolerance (template strings, `null`), so a payload that
  validates renders without a contract error.
- **`render(..., strict=True)`** ([#20]) runs `validate()` first and raises
  `RenderError` listing every issue. Default stays lenient.
- **Conditional requirements** ([#21]): `Field.required_when` — e.g.
  `new_multiline.width` is required when `fit_width` / `fit: width|true` — is
  emitted as JSON Schema `if/then`, enforced by `validate()` and shown in the
  reference.
- **Guard tests** ([#19], [#20], [#21]) parse each handler's AST: every key a
  handler reads must be declared; declared `required` ⇔ `require([...])`;
  declared defaults ⇔ `.get(key, literal)`; an optional key is never read as
  `element["key"]` without a guard. Every optional key of every preview payload
  set to `null` must validate and render.
- **Template-string coercion** ([#12]): numeric and boolean keys given as the
  strings Home Assistant templates produce (`"42"`, `"10.0"`, `"False"`) are
  converted once in dispatch, per element and per nested option dict, driven by
  the declared kinds ([#19]). Errors name the key and element
  (`'x_start' must be a number, got 'oops'`).
- **`dither`** accepts `1`/`0` and template strings (`"0"`, `"False"`) per
  element, in the schema and at runtime ([#19] review).
- **Golden-image tests** ([#13]): every element preview, every dither method and
  14 targeted scenes are compared pixel-exact; `pytest --update-golden`
  rewrites them after an intentional rendering change.
- **numpy-assisted dithering** ([#16]): optional; ordered screens ~5× and error
  diffusion up to ~2× faster, bit-identical to the pure-Python path (tested).
- **`dlimg` hardening** ([#16]): `RenderContext(max_image_bytes=...)` caps
  streamed downloads (20 MB default); `image_cache_ttl=<seconds>` reuses an
  unchanged image across renders (off by default); `image_fetcher` lets the
  host supply the download.
- **`py.typed`** shipped; `src/` is type-checked with mypy in CI ([#18]).
- `docs/integrating.md` — host integration guide ([#17]).

### Changed

- **Python ≥ 3.13** required ([#14]).
- **`null` on an optional key is the same as omitting it** ([#20] review):
  it is dropped before dispatch, so `y: null`, `size: null`, `bars: null` or a
  stack child's `x: null` no longer reach a handler as `None`. Exceptions keep
  their meaning: colour keys (`null` = no fill/outline), `dither`
  (`null` = no override), `visible` (`null` hides) and keys whose description
  says what `null` does (`ylegend`/`yaxis`/`yaxis.grid: null` disable).
- **`dither: null` per element** ([#20]) inherits the render-wide setting
  (same as omitting the key). Before, it flat-quantized that element in
  isolation — visible only when the render-wide `dither` is on.
- **`line`**: `y_end` defaults to `y_start` as documented ([#19] review);
  before, giving `y_start` without `y_end` raised `KeyError`.
- **`visible`** as a string ([#11]): `"False"`/`"off"`/`"no"`/`"0"`/`""`
  (case-insensitive) hide the element; before, any non-empty string showed it.
- **`plot` `low: 0` / `high: 0`** are honoured ([#11]); before, an explicit
  zero bound was dropped. `low`/`high` still only widen the range.
- **`progress_bar`** ([#11]): `progress` is clamped to 0–100 (the fill no
  longer paints past the outline); an unknown `direction` raises `RenderError`
  instead of drawing an empty bar.
- **`text` with `max_width`** ([#15]): a first word wider than `max_width` no
  longer leaves a blank first line.
- **Fractional coordinates** ([#11], [#12]): `x: 5.5` / `width: 10.4` render on
  every element; before, `text` (rotated), `group`, `dlimg`, `qrcode`,
  `barcode`, `datamatrix`, `rectangle_pattern` and `text_fit` raised on
  int-only PIL calls.
- **`new_multiline.fit`** is `"width"` | `"height"` | `true` in the schema and
  `validate()` ([#21]); the handler already ignored other values.
- **`sparkline.values`** as a string must be a `,`/`;`-separated list of
  numbers ([#21]); `validate()` reports `"oops"` instead of the handler dying
  in `float()`.
- The hand-written element table in the README is replaced by the generated
  `docs/reference.md` ([#19]).

### Fixed

- `plot` with `data: []` raised `TypeError`; now
  `RenderError("plot: 'data' must list at least one entity")` ([#18]).
- `multiline` without `offset_y` raised a bare `KeyError`; now a descriptive
  `RenderError` ([#11]).

### Removed

- The global `NUMERIC_KEYS` / `BOOL_KEYS` / `NUMERIC_LIST_KEYS` allow-lists from
  [#12] — superseded by the per-element specs ([#19]).
- `docs/migration.md` — replaced by `docs/integrating.md` ([#17]).

## [0.4.1] — 2026-09-19

- `datamatrix`: drop deprecated `getdata()`/`putdata()` recolour loop ([#10]).
- Pillow floor raised to 10.4; lowest-pinned-dependencies CI job ([#9]).

## [0.4.0] and earlier

Multi-algorithm palette dithering ([#6]), element schema export with CI sync
guards, rendered element previews, and the initial port of the rendering core.
See the git history.

[Unreleased]: https://github.com/eigger/imagespec/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/eigger/imagespec/compare/v0.4.1...v0.5.0
[0.4.1]: https://github.com/eigger/imagespec/compare/v0.4.0...v0.4.1
[#6]: https://github.com/eigger/imagespec/pull/6
[#9]: https://github.com/eigger/imagespec/pull/9
[#10]: https://github.com/eigger/imagespec/pull/10
[#11]: https://github.com/eigger/imagespec/pull/11
[#12]: https://github.com/eigger/imagespec/pull/12
[#13]: https://github.com/eigger/imagespec/pull/13
[#14]: https://github.com/eigger/imagespec/pull/14
[#15]: https://github.com/eigger/imagespec/pull/15
[#16]: https://github.com/eigger/imagespec/pull/16
[#17]: https://github.com/eigger/imagespec/pull/17
[#18]: https://github.com/eigger/imagespec/pull/18
[#19]: https://github.com/eigger/imagespec/pull/19
[#20]: https://github.com/eigger/imagespec/pull/20
[#21]: https://github.com/eigger/imagespec/pull/21
