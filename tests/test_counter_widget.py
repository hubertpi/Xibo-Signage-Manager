"""Unit tests: counter markup and targeted widget discovery."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "xibo_signage_manager"))
from counter_widget import render_counter_markup, counter_targets
from datetime import date

class CounterWidgetTests(unittest.TestCase):
    def test_embed_date_is_a_html_attribute(self):
        markup = render_counter_markup(date(2026, 10, 1))
        self.assertIn('data-last-accident="2026-10-01"', markup)
        self.assertIn("Days Since Last Accident", markup)
        self.assertNotIn("<img", markup)

    def test_find_widget_only_within_named_layout(self):
        def layout(name, embedded_name):
            return {"layout": name, "layoutId": 55, "regions": [
                {"regionPlaylist": {"widgets": [{"widgetId": 99,
                "type": "embedded", "widgetOptions": [
                    {"option": "name", "value": embedded_name}]}]}}]}
        layouts=[layout("Different", "XSM - Accident Counter"),
                 layout("Main Digital Bulletin - 4K Replica", "XSM - Accident Counter"),
                 layout("Main Digital Bulletin - 4K Replica", "Other")]
        result = counter_targets(layouts, "Main Digital Bulletin - 4K Replica")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][1]["widgetId"], 99)

if __name__ == "__main__":
    unittest.main()
