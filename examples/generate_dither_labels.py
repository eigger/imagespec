"""Generate dithering sample labels for the two target device classes:

* Electronic shelf label (ESL) — 3-color black/white/red panel.
* Label printer — 2-color black/white.

Both mix crisp content (text, QR, barcode) with charts in off-palette colors that
are dithered (``dither: true``) into halftone patterns, so chart segments stay
distinguishable on a limited-color device while text/codes stay sharp.

Run from the repository root:
    python examples/generate_dither_labels.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from imagespec import RenderContext, render
from imagespec.colors import PALETTE_BW, PALETTE_BWR


def esl_3color():
    """A grocery shelf label on a 3-color (black/white/red) ESL panel, 296x128."""
    ctx = RenderContext(palette=PALETTE_BWR)
    payload = [
        {"type": "rectangle", "x_start": 0, "y_start": 0, "x_end": 295, "y_end": 127, "outline": "black", "width": 2},
        # red header band
        {"type": "rectangle", "x_start": 2, "y_start": 2, "x_end": 293, "y_end": 24, "fill": "red", "outline": None},
        {"type": "text", "x": 8, "y": 6, "value": "WEEKLY DEAL", "size": 15, "color": "white"},
        {"type": "text", "x": 200, "y": 7, "value": "Aisle 7", "size": 12, "color": "white"},
        # product + price
        {"type": "text", "x": 8, "y": 30, "value": "Organic Coffee", "size": 18, "color": "black"},
        {"type": "text", "x": 8, "y": 52, "value": "Fair Trade · 500g", "size": 11, "color": "black"},
        {"type": "text", "x": 8, "y": 74, "value": "$12.99", "size": 34, "color": "red"},
        {"type": "text", "x": 8, "y": 112, "value": "$25.98 / kg", "size": 11, "color": "black"},
        # donut "flavor profile" in off-palette browns -> dithered halftone
        {
            "type": "pie",
            "x": 175,
            "y": 78,
            "radius": 34,
            "inner_radius": 15,
            "values": "Roast,40,#6f4e37;Acidity,30,#c8a45d;Body,30,#3b2f2f",
            "outline": "black",
            "dither": True,
        },
        {"type": "text", "x": 175, "y": 114, "value": "Flavor", "size": 10, "color": "black", "anchor": "ma"},
        # price-trend sparkline (off-palette green) -> dithered
        {
            "type": "sparkline",
            "x": 225,
            "y": 40,
            "width": 60,
            "height": 30,
            "values": [16.5, 15.9, 15.0, 14.2, 13.5, 12.99],
            "color": "#2ca02c",
            "fill": "#aec7e8",
            "width_line": 2,
            "dot_last": True,
            "dither": True,
        },
        {"type": "qrcode", "x": 232, "y": 78, "data": "https://store/p/organic-coffee", "boxsize": 1, "border": 1},
    ]
    return render(payload, width=296, height=128, background="white", dither=False, context=ctx)


def label_2color():
    """A product/shipping label on a 2-color (black/white) label printer, 360x180."""
    ctx = RenderContext(palette=PALETTE_BW)
    payload = [
        {"type": "rectangle", "x_start": 0, "y_start": 0, "x_end": 359, "y_end": 179, "outline": "black", "width": 2},
        {"type": "text", "x": 10, "y": 8, "value": "WAREHOUSE A — DAILY", "size": 16, "color": "black"},
        {"type": "line", "x_start": 10, "y_start": 30, "x_end": 350, "y_end": 30, "fill": "black", "width": 1},
        # bar chart of throughput, off-palette blue -> dithered to a BW halftone
        {
            "type": "diagram",
            "x": 8,
            "y": 38,
            "width": 200,
            "height": 95,
            "margin": 14,
            "bars": {"values": "Mon,40;Tue,72;Wed,55;Thu,88", "color": "#1f77b4", "legend_color": "black"},
            "dither": True,
        },
        # stock gauge in off-palette orange -> dithered
        {
            "type": "gauge",
            "x": 285,
            "y": 78,
            "radius": 34,
            "progress": 67,
            "fill": "#ff7f0e",
            "outline": "black",
            "width": 9,
            "show_value": True,
            "size": 18,
            "dither": True,
        },
        {"type": "text", "x": 285, "y": 116, "value": "Stock", "size": 11, "color": "black", "anchor": "ma"},
        # crisp barcode + id (never dithered); pixel-sized into a 210x34 box
        {
            "type": "barcode",
            "x": 14,
            "y": 140,
            "data": "4006381333931",
            "code": "ean13",
            "width": 210,
            "height": 34,
            "write_text": True,
        },
        {"type": "text", "x": 250, "y": 150, "value": "SKU 4471-A", "size": 13, "color": "black"},
    ]
    return render(payload, width=360, height=180, background="white", dither=False, context=ctx)


def main():
    os.makedirs("examples", exist_ok=True)
    esl_3color().save("examples/dither_esl_3color.png")
    print("Saved examples/dither_esl_3color.png")
    label_2color().save("examples/dither_label_2color.png")
    print("Saved examples/dither_label_2color.png")


if __name__ == "__main__":
    main()
