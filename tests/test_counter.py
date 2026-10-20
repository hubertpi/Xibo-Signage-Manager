"""Unit tests for counter image generation."""
import sys
import unittest
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "xibo_signage_manager"))
from counter import render_counter_png
from PIL import Image


class CounterTests(unittest.TestCase):
    def test_png_dimensions(self):
        image = Image.open(BytesIO(render_counter_png(932)))
        self.assertEqual(image.size, (1120, 400))
        self.assertEqual(image.format, "PNG")
        self.assertEqual(image.getpixel((0, 0)), (255, 255, 255))

    def test_variable_digits(self):
        for n in (0, 1, 932, 123456):
            self.assertGreater(len(render_counter_png(n)), 3000)

    def test_negative_is_invalid(self):
        with self.assertRaises(ValueError):
            render_counter_png(-1)
