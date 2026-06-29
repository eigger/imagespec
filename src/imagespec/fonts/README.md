# Bundled fonts

Drop the default font(s) here so the package can render text without the host
application supplying one.

Expected (referenced as `RenderContext.default_font`):

- `NotoSansKR-Regular.ttf`  ← copy from `hass-gicisky/custom_components/gicisky/fonts/`

Optional / commonly referenced by existing payloads:

- `ppb.ttf`  ← niimbot's default; copy if you want niimbot payloads to render unchanged.

Font name resolution order (see `context.py`):
1. `RenderContext.font_resolver(name)` (host-supplied, e.g. `www/fonts`)
2. a file of the same basename in this folder
3. `default_font` in this folder

> These binary files are intentionally **not** committed yet — copy them in
> before packaging/publishing.
