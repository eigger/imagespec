"""Generate comparison images for dithering including gradients, font rendering, and charts.

Creates gradient, font, and chart test images, applies Floyd-Steinberg dithering with different
palettes (Black/White, Black/White/Red, ACeP 7-Color), and outputs combined
comparison images showing the visual differences.
"""

from __future__ import annotations

import os
import sys

from PIL import Image, ImageDraw, ImageFont

# Add src to sys.path so we can import imagespec without installation
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from imagespec import RenderContext, render
from imagespec.colors import PALETTE_7, PALETTE_BW, PALETTE_BWR
from imagespec.dither import dither_to_palette


def generate_source_gradient() -> Image.Image:
    """Create a 512x256 test image with smooth color gradients and a 3D shaded sphere."""
    img = Image.new("RGB", (512, 256), "white")
    draw = ImageDraw.Draw(img)

    # 1. Rainbow Gradient (Top half: 0 to 127)
    for x in range(512):
        r = int(max(0, min(255, 255 - abs(x - 170) * 1.5)))
        g = int(max(0, min(255, 255 - abs(x - 340) * 1.5)))
        b = int(max(0, min(255, 255 - (abs(x - 512) * 1.5 if x > 256 else x * 1.5))))
        draw.line([(x, 0), (x, 127)], fill=(r, g, b))

    # 2. Grayscale Gradient (Bottom half: 128 to 255)
    for x in range(512):
        gray = int((x / 511) * 255)
        draw.line([(x, 128), (x, 255)], fill=(gray, gray, gray))

    # 3. 3D Sphere in the center (shading gradient)
    cx, cy = 256, 128
    radius = 80
    for y in range(cy - radius, cy + radius):
        for x in range(cx - radius, cx + radius):
            dx = x - cx
            dy = y - cy
            dist = (dx**2 + dy**2) ** 0.5
            if dist <= radius:
                lx, ly, lz = -0.5, -0.5, 0.707
                nz = (radius**2 - dx**2 - dy**2) ** 0.5 / radius
                nx = dx / radius
                ny = dy / radius
                dot = nx * lx + ny * ly + nz * lz
                intensity = max(0.1, dot)

                r = int(255 * intensity)
                g = int(120 * intensity)
                b = int(20 * intensity)
                img.putpixel((x, y), (r, g, b))

    return img


def generate_source_text() -> Image.Image:
    """Create a 512x256 test image containing various fonts with/without anti-aliasing."""
    img = Image.new("RGB", (512, 256), "white")

    font_path = "C:\\Windows\\Fonts\\arial.ttf"
    try:
        font_title = ImageFont.truetype(font_path, 16)
        font_large = ImageFont.truetype(font_path, 36)
        font_medium = ImageFont.truetype(font_path, 20)
    except Exception:
        font_title = ImageFont.load_default()
        font_large = ImageFont.load_default()
        font_medium = ImageFont.load_default()

    # Upper Half: Anti-aliased Text (fontmode = "L")
    img_l = Image.new("L", (512, 128), 255)
    draw_l = ImageDraw.Draw(img_l)
    draw_l.fontmode = "L"

    draw_l.text((15, 10), "Anti-aliased Font (mode = 'L')", fill=0, font=font_title)
    draw_l.text((15, 30), "Quick Brown Fox", fill=0, font=font_large)
    draw_l.text((15, 80), "Small details: 0123456789 - aa/bb/cc", fill=80, font=font_medium)
    img.paste(Image.merge("RGB", (img_l, img_l, img_l)), (0, 0))

    # Add some colored text with AA
    draw_rgb = ImageDraw.Draw(img)
    draw_rgb.fontmode = "L"
    draw_rgb.text((360, 15), "Red text", fill=(255, 0, 0), font=font_medium)
    draw_rgb.text((360, 45), "Blue text", fill=(0, 0, 255), font=font_medium)
    draw_rgb.text((360, 75), "Yellow text", fill=(200, 200, 0), font=font_medium)

    # Lower Half: Aliased / Bitmap Text (fontmode = "1")
    img_1 = Image.new("L", (512, 128), 255)
    draw_1 = ImageDraw.Draw(img_1)
    draw_1.fontmode = "1"

    draw_1.text((15, 10), "Aliased / Bitmap Font (mode = '1')", fill=0, font=font_title)
    draw_1.text((15, 30), "Quick Brown Fox", fill=0, font=font_large)
    draw_1.text((15, 80), "Small details: 0123456789 - aa/bb/cc", fill=80, font=font_medium)
    img.paste(Image.merge("RGB", (img_1, img_1, img_1)), (0, 128))

    # Add some colored text without AA (drawn via temporary L image for pure mode="1")
    img_col_1 = Image.new("RGB", (150, 128), "white")
    draw_col_1 = ImageDraw.Draw(img_col_1)
    draw_col_1.fontmode = "1"
    draw_col_1.text((0, 15), "Red text", fill=(255, 0, 0), font=font_medium)
    draw_col_1.text((0, 45), "Blue text", fill=(0, 0, 255), font=font_medium)
    draw_col_1.text((0, 75), "Yellow text", fill=(200, 200, 0), font=font_medium)
    img.paste(img_col_1, (360, 128))

    return img


def generate_source_chart() -> Image.Image:
    """Create a 512x256 test image containing various charts (pie, sparkline, diagram) using imagespec rendering."""
    # Define a custom palette containing all our chart colors so they don't get quantized during initial rendering
    chart_colors = [
        "white", "black", "red", "yellow", "green", "blue", "orange",
        "#ff7f0e", "#2ca02c", "#1f77b4", "#aec7e8", "#ffbb78"
    ]
    ctx = RenderContext(palette=chart_colors)

    payload = [
        # 1. Pie/Donut Chart on the left
        {
            "type": "pie",
            "x": 120,
            "y": 128,
            "radius": 90,
            "inner_radius": 40,
            "values": "A,40,#ff7f0e;B,35,#2ca02c;C,25,#1f77b4",
            "outline": "black",
            "background": "white"
        },
        # 2. Sparkline (Line chart with fill) on the top-right
        {
            "type": "sparkline",
            "x": 260,
            "y": 30,
            "width": 235,
            "height": 90,
            "values": [10, 50, 30, 85, 40, 95, 60, 110],
            "fill": "#aec7e8",
            "color": "#1f77b4",
            "width_line": 3,
            "dot_last": True,
            "dot_color": "#1f77b4",
            "dot_radius": 5
        },
        # 3. Diagram (Bar chart) on the bottom-right
        {
            "type": "diagram",
            "x": 260,
            "y": 140,
            "width": 235,
            "height": 95,
            "margin": 15,
            "bars": {
                "values": "Mon,40;Tue,85;Wed,55",
                "color": "#ffbb78",
                "legend_color": "black",
                "legend_size": 11
            }
        }
    ]

    # Render without dithering (raw RGB image with 24-bit colors preserved)
    return render(payload, width=512, height=256, background="white", dither=False, context=ctx)


def create_comparison_layout(src: Image.Image, title: str, palettes: dict) -> Image.Image:
    """Generate a combined layout of Original, No Dither, and Dithered rows."""
    row_height = 256
    row_spacing = 80
    header_height = 80
    width = 1100
    height = header_height + (row_height + row_spacing) * 4

    canvas = Image.new("RGB", (width, height), (240, 242, 245))
    draw = ImageDraw.Draw(canvas)

    font_path = "C:\\Windows\\Fonts\\arial.ttf"
    try:
        title_font = ImageFont.truetype(font_path, 28)
        header_font = ImageFont.truetype(font_path, 20)
        label_font = ImageFont.truetype(font_path, 16)
    except Exception:
        title_font = ImageFont.load_default()
        header_font = ImageFont.load_default()
        label_font = ImageFont.load_default()

    # Draw Title
    draw.text((30, 20), title, fill=(30, 30, 30), font=title_font)

    # Row 0: Original Image
    y_pos = header_height
    draw.text((30, y_pos), "Original 24-bit Color Image", fill=(50, 50, 50), font=header_font)
    canvas.paste(src, (30, y_pos + 35))

    # Rows 1-3: Palettes
    for i, (name, palette) in enumerate(palettes.items()):
        y_pos = header_height + (row_height + row_spacing) * (i + 1)

        # Palette name header
        draw.text((30, y_pos), f"Palette: {name}", fill=(30, 30, 30), font=header_font)

        # Left Column: No Dither
        no_dither_img = dither_to_palette(src, palette, dither=False)
        canvas.paste(no_dither_img, (30, y_pos + 35))
        draw.text(
            (30, y_pos + 35 + row_height + 5),
            "Quantized (Dither = False)",
            fill=(100, 100, 100),
            font=label_font,
        )

        # Right Column: Dithered
        dither_img = dither_to_palette(src, palette, dither=True)
        canvas.paste(dither_img, (570, y_pos + 35))
        draw.text((570, y_pos + 35 + row_height + 5), "Dithered (Dither = True)", fill=(100, 100, 100), font=label_font)

    return canvas


def main():
    palettes = {
        "Black & White (2 colors)": PALETTE_BW,
        "Black, White & Red (3 colors)": PALETTE_BWR,
        "ACeP 7-Color (Black, White, Red, Green, Blue, Yellow, Orange)": PALETTE_7,
    }

    # 1. Gradient Dithering Comparison
    src_gradient = generate_source_gradient()
    canvas_gradient = create_comparison_layout(src_gradient, "Dithering Comparison Test: Gradient & Sphere", palettes)
    canvas_gradient.save("dither_comparison_gradient.png")
    print("Saved dither_comparison_gradient.png")

    # 2. Font Dithering Comparison
    src_text = generate_source_text()
    canvas_text = create_comparison_layout(src_text, "Dithering Comparison Test: Font Rendering", palettes)
    canvas_text.save("dither_comparison_font.png")
    print("Saved dither_comparison_font.png")

    # 3. Chart Dithering Comparison
    src_chart = generate_source_chart()
    canvas_chart = create_comparison_layout(src_chart, "Dithering Comparison Test: Chart Rendering", palettes)
    canvas_chart.save("dither_comparison_chart.png")
    print("Saved dither_comparison_chart.png")


if __name__ == "__main__":
    main()
