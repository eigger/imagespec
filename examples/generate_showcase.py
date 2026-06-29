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

    payload = [
        # --- Background Canvas Outline ---
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
        # --- 1. Header (Title, Icons, Rich text) ---
        {"type": "icon", "x": 20, "y": 15, "value": "mdi:home-assistant", "size": 24, "color": "blue"},
        {
            "type": "text",
            "x": 55,
            "y": 12,
            "value": "Smart Home Hub",
            "size": 22,
            "color": "black",
        },
        {
            "type": "rich_text",
            "x": 620,
            "y": 20,
            "align": "right",
            "spans": [
                {"text": "Mon, Jun 29 "},
                {"icon": "mdi:clock-outline", "color": "blue", "size": 16},
                {"text": " 19:42"},
            ],
            "size": 14,
        },

        # --- 2. Left Card: System & Climate ---
        {
            "type": "rectangle",
            "x_start": 10,
            "y_start": 60,
            "x_end": 310,
            "y_end": 265,
            "outline": "black",
            "width": 1,
            "radius": 8,
        },
        {"type": "text", "x": 20, "y": 68, "value": "System & Climate", "size": 12, "color": "black"},

        # Climate Sun Circle & Cloud Ellipse
        {"type": "circle", "x": 240, "y": 105, "radius": 10, "outline": "orange", "width": 2},
        {"type": "ellipse", "x_start": 250, "y_start": 98, "x_end": 280, "y_end": 112, "outline": "blue", "width": 2},

        # Climate text & Up polygon chevron
        {"type": "text", "x": 20, "y": 90, "value": "Living Room Temp", "size": 10, "color": "gray"},
        {
            "type": "rich_text",
            "x": 20,
            "y": 105,
            "spans": [{"text": "24.5°C ", "size": 20, "color": "red"}],
        },
        {"type": "polygon", "points": "100,120;110,105;120,120", "fill": "red", "outline": "black", "width": 1},

        # Divider line inside card
        {"type": "line", "x_start": 20, "y_start": 140, "x_end": 300, "y_end": 140, "fill": "black", "width": 1, "dash": [2, 2]},

        # CPU circular gauge
        {
            "type": "gauge",
            "x": 60,
            "y": 190,
            "radius": 22,
            "progress": 72,
            "fill": "green",
            "outline": "black",
            "width": 5,
        },
        {"type": "text", "x": 60, "y": 222, "value": "CPU", "size": 10, "anchor": "ma"},

        # Storage progress bar
        {"type": "text", "x": 130, "y": 155, "value": "Storage Volume", "size": 10},
        {
            "type": "progress_bar",
            "x_start": 130,
            "y_start": 170,
            "x_end": 290,
            "y_end": 188,
            "progress": 60,
            "fill": "orange",
            "outline": "black",
            "width": 1,
            "radius": 4,
            "show_percentage": True,
        },

        # Fan airflow Speed Arc
        {"type": "text", "x": 130, "y": 205, "value": "Airflow", "size": 10, "color": "gray"},
        {
            "type": "arc",
            "x_start": 175,
            "y_start": 205,
            "x_end": 205,
            "y_end": 235,
            "start_angle": 0,
            "end_angle": 135,
            "outline": "red",
            "width": 2,
        },

        # Signal dot matrix pattern
        {"type": "text", "x": 225, "y": 205, "value": "Signal", "size": 10, "color": "gray"},
        {
            "type": "rectangle_pattern",
            "x_start": 265,
            "y_start": 208,
            "x_size": 2,
            "y_size": 2,
            "x_repeat": 5,
            "y_repeat": 5,
            "x_offset": 2,
            "y_offset": 2,
            "fill": "black",
        },

        # --- 3. Right Card: Energy & History ---
        {
            "type": "rectangle",
            "x_start": 320,
            "y_start": 60,
            "x_end": 625,
            "y_end": 265,
            "outline": "black",
            "width": 1,
            "radius": 8,
        },
        {"type": "text", "x": 330, "y": 68, "value": "Energy & Usage", "size": 12, "color": "black"},

        # Sparkline
        {"type": "text", "x": 330, "y": 88, "value": "24h Power Consumption", "size": 9, "color": "orange"},
        {
            "type": "sparkline",
            "x": 330,
            "y": 100,
            "width": 130,
            "height": 40,
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
            "y": 110,
            "radius": 24,
            "values": "Gas,30,orange;Water,25,blue;Elec,45,red",
            "inner_radius": 10,
            "outline": "black",
        },
        {"type": "text", "x": 555, "y": 142, "value": "Utility Ratio", "size": 9, "anchor": "ma"},

        # Bar Diagram
        {
            "type": "diagram",
            "x": 330,
            "y": 160,
            "width": 280,
            "height": 90,
            "margin": 15,
            "bars": {"values": "Jan,45;Feb,75;Mar,60", "color": "blue", "legend_color": "black", "legend_size": 9},
        },

        # --- 4. Bottom Card: Access & Schedule ---
        {
            "type": "rectangle",
            "x_start": 10,
            "y_start": 275,
            "x_end": 625,
            "y_end": 373,
            "outline": "black",
            "width": 1,
            "radius": 8,
        },
        {"type": "text", "x": 20, "y": 282, "value": "Access Control & Schedule", "size": 12, "color": "black"},

        # QR Code & Barcode
        {"type": "qrcode", "x": 20, "y": 300, "data": "https://github.com/eigger/imagespec", "boxsize": 2},
        {
            "type": "barcode",
            "x": 105,
            "y": 315,
            "data": "1234",
            "module_width": 0.15,
            "module_height": 2.5,
            "quiet_zone": 0.5,
            "write_text": False,
        },

        # Text Fit Box
        {
            "type": "text_fit",
            "x": 215,
            "y": 300,
            "width": 185,
            "height": 62,
            "value": "Guest network is active. Scan QR to connect or use passcode.",
            "size": 12,
            "fit": "shrink",
            "padding": 4,
            "background": "white",
            "outline": "black",
            "radius": 4,
        },

        # Simple Table
        {
            "type": "table",
            "x": 420,
            "y": 298,
            "columns": [95, 90],
            "rows": [["Time", "Event Status"], ["08:00", "AC On (Eco)"], ["18:00", "Lights On"]],
            "font_size": 9,
            "header_fill": "blue",
            "header_color": "white",
            "cell_color": "black",
            "align": "center",
            "row_height": 20,
        },
    ]

    img = render(payload, width=640, height=384, background="white", dither=False, context=ctx)
    os.makedirs("examples", exist_ok=True)
    output_path = "examples/showcase.png"
    img.save(output_path)
    print(f"Showcase image successfully generated at {output_path}")


if __name__ == "__main__":
    main()
