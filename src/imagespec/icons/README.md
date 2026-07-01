# Bundled icons (Material Design Icons + Font Awesome Free)

The `icon` (and `rich_text`/`legend` icon spans) element resolves a name
against one of two bundled icon sets, by prefix:

- `"mdi:home"` (or no prefix, e.g. `"home"` — kept for backward compatibility)
  → **Material Design Icons**: `materialdesignicons-webfont.ttf` +
    `materialdesignicons-webfont_meta.json`.
  Source: [Pictogrammers / Templarian MaterialDesign-Webfont](https://github.com/Templarian/MaterialDesign-Webfont/tree/master/fonts).
  Licensed under the **Apache License 2.0** (full text: [`LICENSE`](LICENSE)).
- `"fa:home"` / `"fas:home"` (solid) / `"far:star"` (regular) / `"fab:github"`
  (brands) → **Font Awesome Free**: `fontawesome-free-{solid,regular,brands}.otf`
  + `fontawesome-free_meta.json` (trimmed from upstream's metadata by
  [`scripts/build_fontawesome_assets.py`](../../../scripts/build_fontawesome_assets.py) — Pro-only icons are not included).
  Plain `"fa:"` auto-picks the first available style in solid > regular > brands
  order; a forced style (`fas:`/`far:`/`fab:`) errors if that icon has no glyph
  in it. Source: [Font Awesome Free](https://github.com/FortAwesome/Font-Awesome).
  Licensed under **SIL Open Font License 1.1** (fonts) / **CC BY 4.0** (icons)
  (full text: [`LICENSE-FONTAWESOME`](LICENSE-FONTAWESOME)). Brand icons are
  trademarks of their respective owners — see that license file's "Brand Icons"
  section before using them to represent anything other than the brand itself.

`RenderContext.icons_dir` defaults to this folder.
