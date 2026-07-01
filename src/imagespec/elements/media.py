"""Asset-backed elements: icon (Material Design Icons / Font Awesome Free
glyph), dlimg (image)."""

from __future__ import annotations

import base64
import io
import json
import os
import urllib.parse

import requests
from PIL import Image, ImageDraw

from ..exceptions import RenderError
from ..registry import element
from ..state import RenderState
from ..utils import require

# MDI metadata is large (~3MB); load+cache once per file path.
_mdi_meta_cache: dict[str, list] = {}


def _mdi_meta(icons_dir: str) -> list:
    meta_file = os.path.join(icons_dir, "materialdesignicons-webfont_meta.json")
    cached = _mdi_meta_cache.get(meta_file)
    if cached is None:
        if not os.path.exists(meta_file):
            raise RenderError(
                f"icon: MDI metadata not found at {meta_file}. Copy "
                "materialdesignicons-webfont(.ttf/_meta.json) into the package 'icons/' dir."
            )
        with open(meta_file, encoding="utf-8") as f:
            cached = json.load(f)
        _mdi_meta_cache[meta_file] = cached
    return cached


def _map_weather_icon(icon: str) -> str:
    if icon.startswith("weather-"):
        weather_mapping = {
            "clear-night": "night",
            "partlycloudy": "partly-cloudy",
            "exceptional": "sunny-off",
        }
        clean = icon.removeprefix("weather-")
        return f"weather-{weather_mapping.get(clean, clean)}"
    return icon


def mdi_char(value: str, icons_dir: str) -> str:
    """Resolve an MDI name/alias (``mdi:home`` or ``home``) to its glyph char."""
    if value.startswith("mdi:"):
        value = value[4:]
    value = _map_weather_icon(value)
    icon_data = _mdi_meta(icons_dir)
    for ic in icon_data:
        if ic["name"] == value:
            return chr(int(ic["codepoint"], 16))
    for ic in icon_data:
        if value in ic["aliases"]:
            return chr(int(ic["codepoint"], 16))
    raise RenderError("Non valid icon used: " + value)


def mdi_font(icons_dir: str, size):
    """Load the bundled MDI webfont at ``size``."""
    from PIL import ImageFont

    font_file = os.path.join(icons_dir, "materialdesignicons-webfont.ttf")
    if not os.path.exists(font_file):
        raise RenderError(f"icon: MDI webfont not found at {font_file}.")
    return ImageFont.truetype(font_file, size)


# ── Font Awesome Free (solid/regular/brands) ───────────────────────────────
# Metadata is trimmed from upstream's metadata/icons.json (name -> codepoint,
# which of the 3 Free webfonts contain it, and aliases) by
# scripts/build_fontawesome_assets.py — Pro-only icons are not included.
_fa_meta_cache: dict[str, list] = {}
_FA_STYLE_FILES = {
    "solid": "fontawesome-free-solid.otf",
    "regular": "fontawesome-free-regular.otf",
    "brands": "fontawesome-free-brands.otf",
}
_FA_STYLE_PREFERENCE = ("solid", "regular", "brands")  # used by the generic "fa:" prefix
_FA_PREFIX_STYLE = {"fas": "solid", "far": "regular", "fab": "brands"}
_FA_PREFIXES = ("fa:", "fas:", "far:", "fab:")


def _fa_meta(icons_dir: str) -> list:
    meta_file = os.path.join(icons_dir, "fontawesome-free_meta.json")
    cached = _fa_meta_cache.get(meta_file)
    if cached is None:
        if not os.path.exists(meta_file):
            raise RenderError(
                f"icon: Font Awesome metadata not found at {meta_file}. Run "
                "scripts/build_fontawesome_assets.py to (re)generate the bundled assets."
            )
        with open(meta_file, encoding="utf-8") as f:
            cached = json.load(f)
        _fa_meta_cache[meta_file] = cached
    return cached


def _fa_lookup(name: str, icons_dir: str) -> dict:
    icon_data = _fa_meta(icons_dir)
    for ic in icon_data:
        if ic["name"] == name:
            return ic
    for ic in icon_data:
        if name in ic["aliases"]:
            return ic
    raise RenderError("Non valid Font Awesome icon used: " + name)


def fa_font(icons_dir: str, size, style: str):
    """Load one of the bundled Font Awesome Free webfonts at ``size``."""
    from PIL import ImageFont

    filename = _FA_STYLE_FILES.get(style)
    if filename is None:
        raise RenderError(f"icon: unknown Font Awesome style {style!r} (expected solid/regular/brands)")
    font_file = os.path.join(icons_dir, filename)
    if not os.path.exists(font_file):
        raise RenderError(f"icon: Font Awesome webfont not found at {font_file}.")
    return ImageFont.truetype(font_file, size)


def fa_char_and_style(value: str, icons_dir: str) -> tuple[str, str]:
    """Resolve ``fa:name`` / ``fas:name`` / ``far:name`` / ``fab:name`` to ``(glyph, style)``.

    ``fas``/``far``/``fab`` force solid/regular/brands respectively (error if the
    icon has no glyph in that style); plain ``fa:`` auto-picks the first
    available style in solid > regular > brands order.
    """
    forced_style = None
    for prefix, style in _FA_PREFIX_STYLE.items():
        if value.startswith(f"{prefix}:"):
            forced_style, value = style, value[len(prefix) + 1 :]
            break
    else:
        if value.startswith("fa:"):
            value = value[3:]
    entry = _fa_lookup(value, icons_dir)
    if forced_style is not None:
        if forced_style not in entry["styles"]:
            raise RenderError(
                f"icon: Font Awesome icon '{value}' has no {forced_style!r} style "
                f"(available: {', '.join(entry['styles'])})"
            )
        chosen = forced_style
    else:
        chosen = next((s for s in _FA_STYLE_PREFERENCE if s in entry["styles"]), entry["styles"][0])
    return chr(int(entry["codepoint"], 16)), chosen


def resolve_icon(value: str, icons_dir: str, size):
    """Resolve an ``icon``/``rich_text``/``legend`` icon ``value`` to ``(glyph, font)``.

    ``value`` is a Font Awesome name (``"fa:home"``, or with an explicit style —
    ``"fas:"``/``"far:"``/``"fab:"``) or a Material Design Icons name
    (``"mdi:..."``; also the default when no recognized prefix is present, for
    backward compatibility).
    """
    if value.startswith(_FA_PREFIXES):
        glyph, style = fa_char_and_style(value, icons_dir)
        return glyph, fa_font(icons_dir, size, style)
    return mdi_char(value, icons_dir), mdi_font(icons_dir, size)


@element("icon")
def icon(state: RenderState, element: dict) -> None:
    require(element, ["x", "y", "value", "size"], "icon")
    d = ImageDraw.Draw(state.img)
    d.fontmode = "1"
    glyph, font = resolve_icon(element["value"], state.context.icons_dir, element["size"])
    anchor = element.get("anchor", "la")
    stroke_width = element.get("stroke_width", 0)
    stroke_fill = state.context.color(element.get("stroke_fill", "white"))
    if "color" in element:
        fill = state.context.color(element["color"])
    elif "fill" in element:
        fill = state.context.color(element["fill"])
    else:
        fill = state.context.color("black")
    d.text(
        (element["x"], element["y"]),
        glyph,
        fill=fill,
        font=font,
        anchor=anchor,
        stroke_width=stroke_width,
        stroke_fill=stroke_fill,
    )


def _resize_image(imgdl, xsize, ysize, mode):
    """Resize per fit mode: stretch (default), fit/contain, fill."""
    target_ratio = xsize / ysize
    src_w, src_h = imgdl.size
    src_ratio = src_w / src_h if src_h else 1

    if mode == "stretch" or mode is None:
        return imgdl.resize((xsize, ysize), Image.LANCZOS)
    if mode in ("fit", "contain"):
        if src_ratio > target_ratio:
            new_w, new_h = xsize, round(xsize / src_ratio)
        else:
            new_h, new_w = ysize, round(ysize * src_ratio)
        imgdl = imgdl.resize((new_w, new_h), Image.LANCZOS)
        canvas = Image.new("RGBA", (xsize, ysize), (255, 255, 255, 0))
        canvas.paste(imgdl.convert("RGBA"), ((xsize - new_w) // 2, (ysize - new_h) // 2))
        return canvas
    if mode == "fill":
        if src_ratio > target_ratio:
            new_h, new_w = ysize, round(ysize * src_ratio)
        else:
            new_w, new_h = xsize, round(xsize / src_ratio)
        imgdl = imgdl.resize((new_w, new_h), Image.LANCZOS)
        left, top = (new_w - xsize) // 2, (new_h - ysize) // 2
        return imgdl.crop((left, top, left + xsize, top + ysize))
    return imgdl.resize((xsize, ysize), Image.LANCZOS)


@element("dlimg")
def dlimg(state: RenderState, element: dict) -> None:
    require(element, ["x", "y", "url", "xsize", "ysize"], "dlimg")
    url = element["url"]
    pos_x, pos_y = element["x"], element["y"]
    xsize, ysize = element["xsize"], element["ysize"]
    rotate2 = element.get("rotate", 0)
    fit_mode = element.get("mode", "stretch")

    if url.startswith(("http://", "https://")):
        try:
            response = requests.get(url, timeout=element.get("timeout", 30))
            response.raise_for_status()
        except requests.RequestException as exc:
            raise RenderError(f"dlimg: failed to fetch {url}: {exc}") from exc
        imgdl = Image.open(io.BytesIO(response.content))
    elif url.startswith("data:"):
        s = url[5:]
        if not s or "," not in s:
            raise RenderError("dlimg: invalid data url")
        media_type, _, raw_data = s.partition(",")
        if media_type.endswith(";base64"):
            missing_padding = "=" * (-len(raw_data) % 4)
            if missing_padding:
                raw_data += missing_padding
            try:
                data = base64.b64decode(raw_data)
            except ValueError as exc:
                raise RenderError("dlimg: invalid base64 in data url") from exc
        else:
            data = urllib.parse.unquote_to_bytes(raw_data)
        imgdl = Image.open(io.BytesIO(data))
    else:
        # Local / relative filesystem path — gated for safety.
        if not state.context.allow_local_images:
            raise RenderError(
                "dlimg: local file paths are disabled. Set RenderContext.allow_local_images=True to permit them."
            )
        imgdl = Image.open(url)

    if rotate2 != 0:
        imgdl = imgdl.rotate(-rotate2, expand=True)
    imgdl = _resize_image(imgdl, xsize, ysize, fit_mode).convert("RGBA")

    # `dither` is handled generically by the render dispatcher (it isolates and
    # quantizes any element carrying a `dither` flag), so there is nothing
    # image-specific to do here.

    # Optional circular crop (avatar style).
    if element.get("mask") == "circle" or element.get("circle"):
        from PIL import ImageChops

        circle = Image.new("L", (xsize, ysize), 0)
        ImageDraw.Draw(circle).ellipse([(0, 0), (xsize - 1, ysize - 1)], fill=255)
        imgdl.putalpha(ImageChops.multiply(imgdl.split()[-1], circle))

    temp = Image.new("RGBA", state.img.size)
    temp.paste(imgdl, (pos_x, pos_y), imgdl)
    state.img = Image.alpha_composite(state.img, temp)
