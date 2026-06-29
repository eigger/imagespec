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
            "x": 70,
            "y": 110,
            "radius": 25,
            "progress": 72,
            "fill": "green",
            "outline": "black",
            "width": 5,
        },
        {"type": "text", "x": 70, "y": 145, "value": "CPU Use", "size": 11, "anchor": "ma"},
        # Progress bar
        {
            "type": "progress_bar",
            "x_start": 140,
            "y_start": 105,
            "x_end": 290,
            "y_end": 125,
            "progress": 60,
            "fill": "orange",
            "outline": "black",
            "width": 1,
            "radius": 4,
            "show_percentage": True,
        },
        {"type": "text", "x": 140, "y": 85, "value": "Storage Volume", "size": 11},
        # Labeled Vector Elements Box
        {
            "type": "rectangle",
            "x_start": 20,
            "y_start": 170,
            "x_end": 300,
            "y_end": 260,
            "outline": "black",
            "width": 1,
            "radius": 6,
        },
        {"type": "text", "x": 30, "y": 175, "value": "Vector Elements", "size": 10, "color": "black"},
        # Shapes inside the box
        {"type": "circle", "x": 55, "y": 220, "radius": 15, "outline": "blue", "width": 2},
        {"type": "ellipse", "x_start": 85, "y_start": 205, "x_end": 135, "y_end": 235, "outline": "red", "width": 2},
        {"type": "polygon", "points": "150,235;170,205;190,235", "fill": "yellow", "outline": "black", "width": 1},
        {
            "type": "arc",
            "x_start": 205,
            "y_start": 205,
            "x_end": 235,
            "y_end": 235,
            "start_angle": 0,
            "end_angle": 180,
            "outline": "red",
            "width": 2,
        },
        {
            "type": "rectangle_pattern",
            "x_start": 250,
            "y_start": 208,
            "x_size": 3,
            "y_size": 3,
            "x_repeat": 12,
            "y_repeat": 8,
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
            "x": 550,
            "y": 110,
            "radius": 30,
            "values": "Gas,30,orange;Water,25,blue;Elec,45,red",
            "inner_radius": 12,
            "outline": "black",
        },
        {"type": "text", "x": 550, "y": 150, "value": "Utility Ratio", "size": 10, "anchor": "ma"},
        # Bar Diagram
        {
            "type": "diagram",
            "x": 340,
            "y": 175,
            "width": 260,
            "height": 80,
            "margin": 15,
            "bars": {"values": "Jan,45;Feb,75;Mar,60", "color": "blue", "legend_color": "black", "legend_size": 10},
        },
        # --- 4. Bottom Row: Tables, Codes, and Text fit ---
        # QR Code & Barcode
        {"type": "qrcode", "x": 20, "y": 285, "data": "https://github.com/eigger/imagespec", "boxsize": 2},
        {"type": "barcode", "x": 120, "y": 285, "data": "987654321", "module_height": 35, "font_size": 10},
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
