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
        # --- 1. Header (Title, Icons, Date/Time) ---
        {"type": "icon", "x": 20, "y": 15, "value": "mdi:palette-outline", "size": 24, "color": "blue"},
        {
            "type": "text",
            "x": 55,
            "y": 12,
            "value": "imagespec Elements Showcase",
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
        # --- 2. Card A: System Monitor (Left) ---
        {
            "type": "rectangle",
            "x_start": 15,
            "y_start": 60,
            "x_end": 215,
            "y_end": 265,
            "outline": "black",
            "width": 1,
            "radius": 8,
        },
        {"type": "text", "x": 25, "y": 68, "value": "System Monitor", "size": 12, "color": "black"},
        # CPU Gauge
        {
            "type": "gauge",
            "x": 70,
            "y": 120,
            "radius": 25,
            "progress": 72,
            "fill": "green",
            "outline": "black",
            "width": 5,
        },
        {"type": "text", "x": 70, "y": 155, "value": "CPU LOAD: 72%", "size": 9, "anchor": "ma"},
        # Storage Progress
        {"type": "text", "x": 135, "y": 95, "value": "Storage", "size": 10},
        {
            "type": "progress_bar",
            "x_start": 135,
            "y_start": 110,
            "x_end": 205,
            "y_end": 130,
            "progress": 60,
            "fill": "orange",
            "outline": "black",
            "width": 1,
            "radius": 4,
            "show_percentage": True,
        },
        # Memory Sparkline
        {"type": "text", "x": 25, "y": 178, "value": "Memory Usage (24h)", "size": 9, "color": "gray"},
        {
            "type": "sparkline",
            "x": 25,
            "y": 195,
            "width": 180,
            "height": 40,
            "values": [40, 42, 38, 55, 60, 52, 48, 62, 70, 64],
            "fill": "yellow",
            "color": "red",
            "width_line": 2,
            "dot_last": True,
        },
        # --- 3. Card B: Energy & Usage (Center) ---
        {
            "type": "rectangle",
            "x_start": 225,
            "y_start": 60,
            "x_end": 425,
            "y_end": 265,
            "outline": "black",
            "width": 1,
            "radius": 8,
        },
        {"type": "text", "x": 235, "y": 68, "value": "Energy & Usage", "size": 12, "color": "black"},
        # Pie Chart
        {
            "type": "pie",
            "x": 280,
            "y": 120,
            "radius": 24,
            "values": "Gas,30,orange;Water,25,blue;Elec,45,red",
            "inner_radius": 10,
            "outline": "black",
        },
        {"type": "text", "x": 280, "y": 152, "value": "Utility Ratio", "size": 9, "anchor": "ma"},
        # Small Sparkline
        {"type": "text", "x": 330, "y": 98, "value": "Power (24h)", "size": 8, "color": "gray"},
        {
            "type": "sparkline",
            "x": 330,
            "y": 110,
            "width": 85,
            "height": 30,
            "values": [12, 15, 8, 24, 32, 19, 45, 28, 50, 35],
            "fill": "yellow",
            "color": "red",
            "width_line": 2,
            "dot_last": True,
        },
        # Bar Diagram
        {
            "type": "diagram",
            "x": 225,
            "y": 165,
            "width": 190,
            "height": 85,
            "margin": 15,
            "bars": {"values": "Jan,45;Feb,75;Mar,60", "color": "blue", "legend_color": "black", "legend_size": 9},
        },
        # --- 4. Card C: Vector Elements (Right) ---
        {
            "type": "rectangle",
            "x_start": 435,
            "y_start": 60,
            "x_end": 625,
            "y_end": 265,
            "outline": "black",
            "width": 1,
            "radius": 8,
        },
        {"type": "text", "x": 445, "y": 68, "value": "Vector Elements", "size": 12, "color": "black"},
        # Shapes Row 1
        {"type": "circle", "x": 470, "y": 120, "radius": 15, "outline": "blue", "width": 2},
        {"type": "ellipse", "x_start": 505, "y_start": 105, "x_end": 555, "y_end": 135, "outline": "red", "width": 2},
        {"type": "polygon", "points": "570,135;585,105;600,135", "fill": "yellow", "outline": "black", "width": 1},
        # Shapes Row 2
        {
            "type": "arc",
            "x_start": 455,
            "y_start": 180,
            "x_end": 485,
            "y_end": 210,
            "start_angle": 0,
            "end_angle": 180,
            "outline": "red",
            "width": 2,
        },
        {
            "type": "rectangle_pattern",
            "x_start": 510,
            "y_start": 180,
            "x_size": 3,
            "y_size": 3,
            "x_repeat": 5,
            "y_repeat": 5,
            "x_offset": 2,
            "y_offset": 2,
            "fill": "black",
        },
        {
            "type": "line",
            "x_start": 555,
            "y_start": 195,
            "x_end": 605,
            "y_end": 195,
            "fill": "red",
            "width": 2,
            "dash": [4, 4],
        },
        # --- 5. Card D: Access & Schedule (Bottom) ---
        {
            "type": "rectangle",
            "x_start": 15,
            "y_start": 275,
            "x_end": 625,
            "y_end": 375,
            "outline": "black",
            "width": 1,
            "radius": 8,
        },
        {"type": "text", "x": 25, "y": 282, "value": "Access Control & Schedule", "size": 12, "color": "black"},
        # QR Code & Barcode
        {"type": "qrcode", "x": 25, "y": 292, "data": "https://github.com/eigger/imagespec", "boxsize": 2},
        {
            "type": "barcode",
            "x": 105,
            "y": 305,
            "data": "1234",
            "module_width": 0.15,
            "module_height": 2.0,
            "quiet_zone": 0.5,
            "write_text": False,
        },
        # Text Fit Box
        {
            "type": "text_fit",
            "x": 215,
            "y": 292,
            "width": 185,
            "height": 70,
            "value": "Guest network is active. Scan QR to connect or use passcode.",
            "size": 12,
            "max_lines": 3,
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
            "y": 292,
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
