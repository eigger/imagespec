"""Generate individual preview images for each element type in imagespec.

Creates 150x80 thumbnails demonstrating the look of every supported element,
to be embedded directly in the README.md table.
"""

from __future__ import annotations

import base64
import io
import os
import sys
from PIL import Image

# Add src to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from imagespec import RenderContext, render
from imagespec.colors import PALETTE_7

# Tiny base64 data url for a red square (for dlimg)
buf = io.BytesIO()
Image.new("RGB", (16, 16), (255, 0, 0)).save(buf, format="PNG")
RED_DATA_URL = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def get_history_context() -> RenderContext:
    """Return a context equipped with a mock history provider for plot testing."""
    class StateMock:
        def __init__(self, value, changed):
            self.state = value
            self.last_changed = changed

    from datetime import datetime, timedelta, UTC

    def mock_provider(entity_ids, start, end):
        result = {}
        for eid in entity_ids:
            first = StateMock("15", start)
            rest = [
                {"state": str(15 + (i % 8) * 2), "last_changed": (start + timedelta(hours=i * 2)).isoformat()}
                for i in range(1, 12)
            ]
            result[eid] = [first] + rest
        return result

    return RenderContext(palette=PALETTE_7, history_provider=mock_provider)


def main():
    os.makedirs("examples/elements", exist_ok=True)
    ctx = RenderContext(palette=PALETTE_7)
    history_ctx = get_history_context()

    # Individual payloads designed to look good on a 150x80 canvas
    samples = {
        "line": {
            "type": "line",
            "x_start": 15,
            "y_start": 40,
            "x_end": 135,
            "y_end": 40,
            "fill": "red",
            "width": 3,
            "dash": [8, 4],
        },
        "rectangle": {
            "type": "rectangle",
            "x_start": 15,
            "y_start": 15,
            "x_end": 135,
            "y_end": 65,
            "outline": "blue",
            "width": 2,
            "radius": 8,
        },
        "rectangle_pattern": {
            "type": "rectangle_pattern",
            "x_start": 10,
            "x_size": 10,
            "y_start": 10,
            "y_size": 10,
            "x_repeat": 9,
            "y_repeat": 4,
            "x_offset": 5,
            "y_offset": 5,
            "fill": "orange",
        },
        "circle": {
            "type": "circle",
            "x": 75,
            "y": 40,
            "radius": 30,
            "fill": "yellow",
            "outline": "black",
            "width": 2,
        },
        "ellipse": {
            "type": "ellipse",
            "x_start": 15,
            "y_start": 20,
            "x_end": 135,
            "y_end": 60,
            "fill": "green",
            "outline": "black",
            "width": 2,
        },
        "arc": {
            "type": "arc",
            "x_start": 25,
            "y_start": 10,
            "x_end": 125,
            "y_end": 70,
            "start_angle": -180,
            "end_angle": 0,
            "outline": "red",
            "width": 3,
        },
        "polygon": {
            "type": "polygon",
            "points": "20,65;75,15;130,65",
            "fill": "blue",
            "outline": "black",
            "width": 2,
        },
        "gauge": {
            "type": "gauge",
            "x": 75,
            "y": 42,
            "radius": 28,
            "progress": 68,
            "fill": "red",
            "outline": "black",
            "width": 6,
        },
        "text": {
            "type": "text",
            "x": 75,
            "y": 40,
            "value": "Hello Spec",
            "size": 18,
            "color": "blue",
            "anchor": "mm",
        },
        "text_box": {
            "type": "text_box",
            "x": 15,
            "y": 20,
            "value": "Status: OK",
            "size": 16,
            "fill": "green",
            "color": "white",
            "radius": 6,
        },
        "multiline": {
            "type": "multiline",
            "x": 20,
            "start_y": 12,
            "value": "Coffee;Tea;Water",
            "delimiter": ";",
            "offset_y": 20,
            "size": 13,
            "color": "black",
        },
        "new_multiline": {
            "type": "new_multiline",
            "x": 15,
            "y": 15,
            "value": "Shrunk To\nFit Width",
            "size": 24,
            "width": 120,
            "fit": "width",
            "color": "red",
        },
        "text_fit": {
            "type": "text_fit",
            "x": 10,
            "y": 10,
            "width": 130,
            "height": 60,
            "value": "This text will wrap and shrink to fit perfectly inside this container.",
            "size": 16,
            "fit": "shrink",
            "outline": "black",
            "padding": 5,
        },
        "table": {
            "type": "table",
            "x": 15,
            "y": 12,
            "columns": [60, 60],
            "rows": [["Item", "Qty"], ["A", "10"], ["B", "5"]],
            "font_size": 9,
            "header": True,
            "header_fill": "black",
            "header_color": "white",
            "row_height": 18,
        },
        "qrcode": {
            "type": "qrcode",
            "x": 52,
            "y": 17,
            "data": "imagespec",
            "boxsize": 2,
            "border": 1,
        },
        "barcode": {
            "type": "barcode",
            "x": 23,
            "y": -10,
            "data": "123",
            "module_width": 0.1,
            "module_height": 1.8,
            "quiet_zone": 1.0,
            "font_size": 5,
            "text_distance": 3.0,
            "write_text": True,
        },
        "datamatrix": {
            "type": "datamatrix",
            "x": 54,
            "y": 19,
            "data": "DM",
            "boxsize": 3,
        },
        "icon": {
            "type": "icon",
            "x": 75,
            "y": 40,
            "value": "mdi:weather-sunny",
            "size": 52,
            "color": "orange",
            "anchor": "mm",
        },
        "dlimg": {
            "type": "dlimg",
            "x": 45,
            "y": 10,
            "url": RED_DATA_URL,
            "xsize": 60,
            "ysize": 60,
            "circle": True,
        },
        "diagram": {
            "type": "diagram",
            "x": 10,
            "y": 10,
            "width": 130,
            "height": 60,
            "margin": 10,
            "bars": {"values": "X,30;Y,75;Z,50", "color": "blue"},
        },
        "progress_bar": {
            "type": "progress_bar",
            "x_start": 15,
            "y_start": 25,
            "x_end": 135,
            "y_end": 55,
            "progress": 70,
            "fill": "orange",
            "outline": "black",
            "radius": 4,
            "show_percentage": True,
        },
        "pie": {
            "type": "pie",
            "x": 75,
            "y": 40,
            "radius": 30,
            "values": "A,40,red;B,60,blue",
            "inner_radius": 14,
            "outline": "black",
        },
        "sparkline": {
            "type": "sparkline",
            "x": 10,
            "y": 15,
            "width": 130,
            "height": 50,
            "values": [10, 40, 20, 80, 50, 95, 30],
            "fill": "yellow",
            "color": "red",
            "width_line": 2,
            "dot_last": True,
        },
        "rich_text": {
            "type": "rich_text",
            "x": 75,
            "y": 40,
            "align": "center",
            "spans": [{"text": "Alert: "}, {"icon": "mdi:fire", "color": "orange", "size": 18}, {"text": " Active", "color": "red"}],
            "size": 14,
        },
        "group": {
            "type": "group",
            "x": 15,
            "y": 10,
            "width": 120,
            "height": 60,
            "elements": [
                {"type": "rectangle", "x_start": 0, "y_start": 0, "x_end": 119, "y_end": 59, "fill": "yellow"},
                {"type": "text", "x": 60, "y": 30, "value": "Group Box", "anchor": "mm", "size": 14},
            ],
        },
        "plot": {
            "type": "plot",
            "x_start": 10,
            "y_start": 10,
            "x_end": 140,
            "y_end": 70,
            "data": [{"entity": "sensor.temp", "color": "red", "area_fill": "yellow"}],
            "ylegend": None,
            "xlegend": None,
            "yaxis": None,
        },
    }

    for name, el in samples.items():
        # Select appropriate context for the plot element
        active_ctx = history_ctx if name == "plot" else ctx
        try:
            img = render([el], width=150, height=80, background="white", dither=False, context=active_ctx)
            output_file = f"examples/elements/{name}.png"
            img.save(output_file)
            print(f"Generated preview for '{name}' at {output_file}")
        except Exception as e:
            print(f"Failed to generate preview for '{name}': {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
