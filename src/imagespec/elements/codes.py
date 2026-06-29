"""Machine-readable codes: qrcode, barcode, datamatrix.

Merged behaviour: keeps gicisky's defaults while adding niimbot's ``eclevel``
(error-correction level) option on ``qrcode``. ``datamatrix`` needs the optional
``pyStrich`` dependency (``imagespec[datamatrix]``).
"""

from __future__ import annotations

from io import BytesIO

import barcode as barcode_lib
import qrcode
from barcode.writer import ImageWriter
from PIL import Image

from ..exceptions import RenderError
from ..registry import element
from ..state import RenderState
from ..utils import require

_ERROR_CORRECTION = {
    "l": qrcode.constants.ERROR_CORRECT_L,
    "m": qrcode.constants.ERROR_CORRECT_M,
    "q": qrcode.constants.ERROR_CORRECT_Q,
    "h": qrcode.constants.ERROR_CORRECT_H,
}


def _fit_square_code(img: Image.Image, width, height) -> Image.Image:
    """Scale a square 2D code (QR/DataMatrix) to fit a ``width``×``height`` box.

    Square aspect is preserved (the code fits *within* the box). NEAREST keeps
    modules crisp (pure 2-color); when enlarging, an integer scale factor is used
    so every module stays the same size — important for scanner reliability.
    """
    if width is None and height is None:
        return img
    target = min(int(v) for v in (width, height) if v is not None)
    side = img.size[0]
    if target == side:
        return img
    if target > side:
        scale = target // side  # integer upscale -> uniform modules, fits the box
        return img.resize((side * scale, side * scale), Image.NEAREST)
    return img.resize((target, target), Image.NEAREST)  # shrink to fit


@element("qrcode")
def qrcode_element(state: RenderState, element: dict) -> None:
    """QR code.

    Size by either ``boxsize`` (pixels per module) or, for predictable layout, a
    pixel ``width``/``height`` box — the code is scaled (square, crisp) to fit it.
    """
    require(element, ["x", "y", "data"], "qrcode")
    data = str(element["data"])
    pos_x = element["x"]
    pos_y = element["y"]
    color = element.get("color", "black")
    bgcolor = element.get("bgcolor", "white")
    border = element.get("border", 1)
    boxsize = element.get("boxsize", 2)
    eclevel = str(element.get("eclevel", "h")).lower()

    qr = qrcode.QRCode(
        version=1,
        error_correction=_ERROR_CORRECTION.get(eclevel, qrcode.constants.ERROR_CORRECT_H),
        box_size=boxsize,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)
    # Quantize to the device palette so a QR stays legible on limited-color panels.
    fill = state.context.color(color)
    back = state.context.color(bgcolor)
    imgqr = qr.make_image(fill_color=fill, back_color=back).convert("RGBA")
    imgqr = _fit_square_code(imgqr, element.get("width"), element.get("height"))
    state.img.paste(imgqr, (pos_x, pos_y), imgqr)


def _hex(rgba) -> str:
    """RGBA tuple -> ``#rrggbb`` string (what python-barcode's writer expects)."""
    r, g, b = (rgba or (0, 0, 0, 255))[:3]
    return f"#{r:02x}{g:02x}{b:02x}"


@element("barcode")
def barcode(state: RenderState, element: dict) -> None:
    """Linear barcode.

    Sizing: the easy path is pixel-based — give ``width`` and/or ``height`` and
    the barcode is scaled to fit that box at ``(x, y)`` (predictable layout, like
    ``dlimg``/``icon``). Without them it falls back to python-barcode's physical
    millimetre options (``module_width``/``module_height``/``quiet_zone`` at
    ``dpi``), whose pixel size depends on the DPI and is harder to place.
    """
    require(element, ["x", "y", "data"], "barcode")
    data = str(element["data"])
    pos_x, pos_y = element["x"], element["y"]
    code = element.get("code", "code128")
    options = {
        "module_width": float(element.get("module_width", 0.2)),
        "module_height": float(element.get("module_height", 7)),
        "quiet_zone": float(element.get("quiet_zone", 6.5)),
        "font_size": int(element.get("font_size", 5)),
        "text_distance": float(element.get("text_distance", 5.0)),
        "background": _hex(state.context.color(element.get("bgcolor", "white"))),
        "foreground": _hex(state.context.color(element.get("color", "black"))),
        "write_text": element.get("write_text", True),
        "dpi": int(element.get("dpi", 300)),
    }
    try:
        barcode_format = barcode_lib.get_barcode_class(code)
    except Exception as exc:  # barcode raises BarcodeNotFoundError
        raise RenderError(f"barcode: unknown code type '{code}'") from exc
    buffer = BytesIO()
    try:
        barcode_format(data, writer=ImageWriter()).write(buffer, options=options)
    except Exception as exc:
        raise RenderError(f"barcode: cannot encode {data!r} as {code}: {exc}") from exc
    buffer.seek(0)
    imagebc = Image.open(buffer).convert("RGBA")

    # Pixel-exact sizing: scale the native render to fit `width`/`height` (NEAREST
    # keeps bars pure black/white — no gray edges to dither into noise).
    target_w = element.get("width")
    target_h = element.get("height")
    if target_w is not None or target_h is not None:
        w0, h0 = imagebc.size
        if target_w is not None and target_h is not None:
            new_size = (int(target_w), int(target_h))
        elif target_w is not None:
            new_size = (int(target_w), max(1, round(h0 * (int(target_w) / w0))))
        else:
            new_size = (max(1, round(w0 * (int(target_h) / h0))), int(target_h))
        imagebc = imagebc.resize(new_size, Image.NEAREST)

    state.img.paste(imagebc, (pos_x, pos_y), imagebc)


@element("datamatrix")
def datamatrix(state: RenderState, element: dict) -> None:
    """DataMatrix 2D code.

    Size by ``boxsize`` (pixels per cell) or a pixel ``width``/``height`` box —
    like ``qrcode``, the code is scaled (square, crisp) to fit it.
    """
    require(element, ["x", "y", "data"], "datamatrix")
    try:
        from pystrich.datamatrix import DataMatrixEncoder
    except ImportError as exc:
        raise RenderError(
            "datamatrix requires 'pyStrich'. Install imagespec with the "
            "'datamatrix' extra (pip install imagespec[datamatrix])."
        ) from exc
    data = str(element["data"])
    pos_x, pos_y = element["x"], element["y"]
    color = element.get("color", "black")
    bgcolor = element.get("bgcolor", "white")
    boxsize = element.get("boxsize", 2)

    encoder = DataMatrixEncoder(data)
    dm_image = Image.open(BytesIO(encoder.get_imagedata(cellsize=boxsize))).convert("RGBA")

    if color != "black" or bgcolor != "white":
        target_color = state.context.color(color)
        target_bg = state.context.color(bgcolor)
        new_data = [target_color if px[0] < 128 else target_bg for px in dm_image.getdata()]
        dm_image.putdata(new_data)

    dm_image = _fit_square_code(dm_image, element.get("width"), element.get("height"))
    state.img.paste(dm_image, (pos_x, pos_y), dm_image)
