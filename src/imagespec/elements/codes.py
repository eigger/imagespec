"""Machine-readable codes: qrcode.

Merged behaviour: keeps gicisky's defaults while adding niimbot's ``eclevel``
(error-correction level) option. ``barcode`` and ``datamatrix`` are listed in
the README porting checklist.
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


@element("qrcode")
def qrcode_element(state: RenderState, element: dict) -> None:
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
    state.img.paste(imgqr, (pos_x, pos_y), imgqr)


@element("barcode")
def barcode(state: RenderState, element: dict) -> None:
    require(element, ["x", "y", "data"], "barcode")
    data = str(element["data"])
    pos_x, pos_y = element["x"], element["y"]
    color = element.get("color", "black")
    bgcolor = element.get("bgcolor", "white")
    code = element.get("code", "code128")
    options = {
        "module_width": float(element.get("module_width", 0.2)),
        "module_height": float(element.get("module_height", 7)),
        "quiet_zone": float(element.get("quiet_zone", 6.5)),
        "font_size": int(element.get("font_size", 5)),
        "text_distance": float(element.get("text_distance", 5.0)),
        "background": bgcolor,
        "foreground": color,
        "write_text": element.get("write_text", True),
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
    state.img.paste(imagebc, (pos_x, pos_y), imagebc)


@element("datamatrix")
def datamatrix(state: RenderState, element: dict) -> None:
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

    state.img.paste(dm_image, (pos_x, pos_y), dm_image)
