"""Asset-backed elements: icon (Material Design Icons glyph), dlimg (image)."""

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


@element("icon")
def icon(state: RenderState, element: dict) -> None:
    require(element, ["x", "y", "value", "size"], "icon")
    d = ImageDraw.Draw(state.img)
    d.fontmode = "1"
    glyph = mdi_char(element["value"], state.context.icons_dir)
    font = mdi_font(state.context.icons_dir, element["size"])
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

    if "http://" in url or "https://" in url:
        try:
            response = requests.get(url, timeout=element.get("timeout", 30))
            response.raise_for_status()
        except requests.RequestException as exc:
            raise RenderError(f"dlimg: failed to fetch {url}: {exc}") from exc
        imgdl = Image.open(io.BytesIO(response.content))
    elif "data:" in url:
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

    # Optional Floyd–Steinberg dithering to the device palette (keeps alpha).
    if element.get("dither"):
        from ..dither import dither_to_palette

        alpha = imgdl.split()[-1]
        imgdl = dither_to_palette(imgdl, state.context.palette).convert("RGBA")
        imgdl.putalpha(alpha)

    # Optional circular crop (avatar style).
    if element.get("mask") == "circle" or element.get("circle"):
        from PIL import ImageChops

        circle = Image.new("L", (xsize, ysize), 0)
        ImageDraw.Draw(circle).ellipse([(0, 0), (xsize - 1, ysize - 1)], fill=255)
        imgdl.putalpha(ImageChops.multiply(imgdl.split()[-1], circle))

    temp = Image.new("RGBA", state.img.size)
    temp.paste(imgdl, (pos_x, pos_y), imgdl)
    state.img = Image.alpha_composite(state.img, temp)
