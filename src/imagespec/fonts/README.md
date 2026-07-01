# Bundled fonts

The default font the package renders text with when no `font_resolver`/payload
`font` resolves to anything else (referenced as `RenderContext.default_font`):

- `NotoSansKR-Regular.ttf` — licensed under the **SIL Open Font License 1.1**
  (full text: [`OFL.txt`](OFL.txt)), sourced from
  [Google Noto Fonts](https://fonts.google.com/noto/specimen/Noto+Sans+KR).

niimbot's `ppb.ttf` (a former second bundled font) was removed — its
license/origin could not be verified, which is a real risk for a font shipped
in a published PyPI package. If you need that look, supply your own font file
via `font_resolver` or `directory_resolver(...)`; do **not** re-add it here
without confirming its license first.

Font name resolution order (see `context.py`):
1. `RenderContext.font_resolver(name)` (host-supplied, e.g. `www/fonts`)
2. a file of the same basename in this folder
3. `default_font` in this folder
