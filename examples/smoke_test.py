"""Minimal runnable check that the core renders without Home Assistant.

Uses only font-free elements (shapes + qrcode) so it works before any fonts are
bundled. Run from the repo root:

    pip install -e .
    python examples/smoke_test.py
"""

from __future__ import annotations

from imagespec import RenderContext, render

payload = [
    {
        "type": "rectangle",
        "x_start": 2,
        "y_start": 2,
        "x_end": 293,
        "y_end": 125,
        "outline": "black",
        "width": 2,
        "radius": 8,
    },
    {
        "type": "line",
        "x_start": 10,
        "y_start": 30,
        "x_end": 286,
        "y_end": 30,
        "fill": "red",
        "width": 1,
        "dash": [4, 3],
    },
    {"type": "circle", "x": 250, "y": 70, "radius": 20, "outline": "black", "width": 2},
    {"type": "gauge", "x": 60, "y": 75, "radius": 28, "progress": 65, "fill": "red", "outline": "black", "width": 6},
    {"type": "qrcode", "x": 150, "y": 50, "data": "https://example.com", "boxsize": 2},
]

ctx = RenderContext()  # no font_resolver / history needed for this payload
img = render(payload, width=296, height=128, rotate=0, background="white", context=ctx)
img.save("smoke_test.png")
print(f"OK - wrote smoke_test.png ({img.size[0]}x{img.size[1]})")
