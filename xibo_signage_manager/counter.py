"""Render the blue incident counter as an Xibo-ready 1120 x 400 PNG."""
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH = 1120
HEIGHT = 400
BLUE = (6, 102, 179)
CAPTION = "Days Since Last Accident"


def font_path(bold=False):
    filename = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    locations = (
        Path("/usr/share/fonts/ttf-dejavu") / filename,
        Path("/usr/share/fonts/truetype/dejavu") / filename,
    )
    for path in locations:
        if path.is_file():
            return str(path)
    raise FileNotFoundError(f"DejaVu font unavailable: {filename}")


def fit_font(draw, value, path, max_height, max_width, initial_size):
    for size in range(initial_size, 11, -1):
        font = ImageFont.truetype(path, size=size)
        left, top, right, bottom = draw.textbbox((0, 0), value, font=font)
        if right - left <= max_width and bottom - top <= max_height:
            return font
    return ImageFont.truetype(path, 12)


def render_counter_png(days: int) -> bytes:
    if days < 0:
        raise ValueError("Counter cannot be negative")
    image = Image.new("RGB", (WIDTH, HEIGHT), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    number = str(days)
    number_font = fit_font(draw, number, font_path(True), 218, WIDTH - 90, 245)
    label_font = fit_font(draw, CAPTION, font_path(False), 83, WIDTH - 60, 84)

    def centered_text(text, font, y, region_height):
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        w, h = right - left, bottom - top
        x = (WIDTH - w) / 2 - left
        yy = y + (region_height - h) / 2 - top
        draw.text((round(x), round(yy)), text, fill=BLUE, font=font)

    centered_text(number, number_font, 34, 230)
    centered_text(CAPTION, label_font, 278, 85)
    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()
