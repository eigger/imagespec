"""Generate a comprehensive showcase image displaying all key elements of imagespec.

Run from repository root:
    python examples/generate_showcase.py
"""

from __future__ import annotations

import os
import sys

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from imagespec import RenderContext, render
from imagespec.colors import PALETTE_7


def main():
    # Setup rendering context with a rich 7-color palette (ACeP)
    ctx = RenderContext(palette=PALETTE_7)

    # We will lay out elements inside a 640x384 e-ink dashboard style
    payload = [
        # --- Background and Layout grid ---
        {
            "type": "rectangle",
            "x_start": 0,
            "y_start": 0,
            "x_end": 639,
            "y_end": 383,
            "outline": "black",
            "width": 2,
            "radius": 12,
        },
        # Header separator
        {"type": "line", "x_start": 10, "y_start": 50, "x_end": 629, "y_end": 50, "fill": "orange", "width": 2},
        # Middle vertical separator
        {
            "type": "line",
            "x_start": 320,
            "y_start": 60,
            "x_end": 320,
            "y_end": 260,
            "fill": "black",
            "width": 1,
            "dash": [4, 4],
        },
        # Bottom separator
        {"type": "line", "x_start": 10, "y_start": 270, "x_end": 629, "y_end": 270, "fill": "black", "width": 2},
        # --- 1. Header (Title, Icons, Rich text) ---
        {"type": "icon", "x": 20, "y": 15, "value": "mdi:home-assistant", "size": 24, "color": "blue"},
        {
            "type": "text",
            "x": 55,
            "y": 12,
            "value": "Smart Home Hub Showcase",
            "size": 22,
            "color": "black",
            "font": "NotoSansKR-Regular.ttf",
        },
        {
            "type": "rich_text",
            "x": 620,
            "y": 25,
            "align": "right",
            "spans": [
                {"text": "Temp: "},
                {"text": "24.5C ", "color": "red"},
                {"icon": "mdi:thermometer", "color": "red", "size": 16},
                {"text": "  Humid: "},
                {"text": "55% ", "color": "blue"},
                {"icon": "mdi:water-percent", "color": "blue", "size": 16},
            ],
            "size": 14,
        },
        # --- 2. Left Column: Shapes, Gauges, Progress bars ---
        {"type": "text", "x": 20, "y": 65, "value": "Device Status (Left Column)", "size": 14, "color": "black"},
        # Circular gauge
        {
            "type": "gauge",
            "x": 60,
            "y": 140,
            "radius": 35,
            "progress": 72,
            "fill": "green",
            "outline": "black",
            "width": 6,
        },
        {"type": "text", "x": 60, "y": 190, "value": "CPU Use", "size": 12, "anchor": "ma"},
        # Progress bar
        {
            "type": "progress_bar",
            "x_start": 130,
            "y_start": 100,
            "x_end": 300,
            "y_end": 125,
            "progress": 60,
            "fill": "orange",
            "outline": "black",
            "width": 1,
            "radius": 4,
            "show_percentage": True,
        },
        {"type": "text", "x": 130, "y": 80, "value": "Storage Volume", "size": 11},
        # Shapes showcase
        {"type": "circle", "x": 145, "y": 165, "radius": 15, "outline": "blue", "width": 2},
        {"type": "ellipse", "x_start": 175, "y_start": 150, "x_end": 225, "y_end": 180, "outline": "red", "width": 2},
        {"type": "polygon", "points": "240,180;265,145;290,180", "fill": "yellow", "outline": "black", "width": 1},
        # Dashed line and Arc
        {
            "type": "line",
            "x_start": 130,
            "y_start": 205,
            "x_end": 300,
            "y_end": 205,
            "fill": "green",
            "width": 2,
            "dash": [6, 4],
        },
        {
            "type": "arc",
            "x_start": 130,
            "y_start": 215,
            "x_end": 170,
            "y_end": 255,
            "start_angle": 0,
            "end_angle": 180,
            "outline": "red",
            "width": 2,
        },
        # Rectangle Pattern
        {"type": "text", "x": 190, "y": 215, "value": "Pattern Fill", "size": 10},
        {
            "type": "rectangle_pattern",
            "x_start": 190,
            "y_start": 230,
            "x_size": 4,
            "y_size": 4,
            "x_repeat": 15,
            "y_repeat": 4,
            "x_offset": 2,
            "y_offset": 2,
            "fill": "black",
        },
        # --- 3. Right Column: Charts (Pie, Sparkline, Diagram) ---
        {"type": "text", "x": 340, "y": 65, "value": "Data & History (Right Column)", "size": 14, "color": "black"},
        # Sparkline
        {"type": "text", "x": 340, "y": 85, "value": "24h Power Consumption", "size": 10, "color": "orange"},
        {
            "type": "sparkline",
            "x": 340,
            "y": 100,
            "width": 140,
            "height": 45,
            "values": [12, 15, 8, 24, 32, 19, 45, 28, 50, 35],
            "fill": "yellow",
            "color": "red",
            "width_line": 2,
            "dot_last": True,
        },
        # Pie Chart
        {
            "type": "pie",
            "x": 555,
            "y": 130,
            "radius": 40,
            "values": "Gas,30,orange;Water,25,blue;Elec,45,red",
            "inner_radius": 15,
            "outline": "black",
        },
        {"type": "text", "x": 555, "y": 180, "value": "Utility Ratio", "size": 10, "anchor": "ma"},
        # Bar Diagram
        {
            "type": "diagram",
            "x": 340,
            "y": 170,
            "width": 260,
            "height": 85,
            "margin": 15,
            "bars": {"values": "Jan,45;Feb,75;Mar,60", "color": "blue", "legend_color": "black", "legend_size": 10},
        },
        # --- 4. Bottom Row: Tables, Codes, and Text fit ---
        # QR Code & Barcode
        {"type": "qrcode", "x": 20, "y": 285, "data": "https://github.com/eigger/imagespec", "boxsize": 3},
        {"type": "barcode", "x": 130, "y": 285, "data": "987654321", "module_height": 35, "font_size": 10},
        # Text Fit Box
        {
            "type": "text_fit",
            "x": 280,
            "y": 285,
            "width": 150,
            "height": 80,
            "value": "Auto-fit text shrinks to fit this box tightly without overflowing.",
            "size": 18,
            "fit": "shrink",
            "padding": 5,
            "background": "white",
            "outline": "black",
            "radius": 6,
        },
        # Simple Table
        {
            "type": "table",
            "x": 450,
            "y": 285,
            "columns": [90, 80],
            "rows": [["Sensor", "Status"], ["Living Room", "Active"], ["Kitchen", "Offline"]],
            "font_size": 9,
            "header_fill": "blue",
            "header_color": "white",
            "cell_color": "black",
            "align": "center",
            "row_height": 22,
        },
    ]

    img = render(payload, width=640, height=384, background="white", dither=False, context=ctx)
    os.makedirs("examples", exist_ok=True)
    output_path = "examples/showcase.png"
    img.save(output_path)
    print(f"Showcase image successfully generated at {output_path}")


if __name__ == "__main__":
    main()
