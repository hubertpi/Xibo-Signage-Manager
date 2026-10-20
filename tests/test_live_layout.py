"""Tests for combined layout management and ICS-driven calendar rendering."""
import datetime as dt
import pathlib
import sys
import unittest
from unittest.mock import patch, Mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "xibo_signage_manager"))
from counter_widget import render_counter_markup, COUNTER_STYLE, COUNTER_SCRIPT, get_widget_option
from calendar_widget import render_calendar, CAL_STYLE, CAL_SCRIPT, events_from_ics
from layout_sync import find_parts

class LiveLayoutTests(unittest.TestCase):
    def test_counter_is_svg_text_and_not_clipped_giant_html_font(self):
        text=render_counter_markup(dt.date(2024,4,1))
        self.assertIn('viewBox="0 0 1120 400"',text)
        self.assertIn('data-last-accident="2024-04-01"',text)
        self.assertIn('Days Since Last Accident',text)
        self.assertNotIn('<img',text)
        self.assertNotIn('<style',COUNTER_STYLE)
        self.assertIn("setInterval(update,60000)",COUNTER_SCRIPT.replace("window.",""))

    def test_calendar_renders_real_items_and_escapes_title(self):
        body=render_calendar([{"date":"2026-10-29","time":"4:00pm","name":"Safety & <Health>"}],[])
        self.assertIn("10/29/2026",body)
        self.assertIn("Safety &amp; &lt;Health&gt;",body)
        self.assertNotIn("Shop Floor ROPE Meeting",body)
        self.assertIn("Birthdays",body)
        self.assertIn("Nothing scheduled",body)
        self.assertNotIn("<style",CAL_STYLE)

    def test_calendar_unconfigured_is_explicit(self):
        text=render_calendar(None,None)
        self.assertIn("Events calendar not connected",text)
        self.assertIn("Birthdays calendar not connected",text)
        self.assertIn("10000",CAL_SCRIPT)

    def test_region_detection(self):
        l={"regions":[{"regionId":7,"name":"XSM - Bulletin Slideshow","regionPlaylist":{"playlistId":4,"widgets":[]}},
                      {"regionId":8,"name":"Events / Birthdays (10-second alternating)","regionPlaylist":{"playlistId":5,"widgets":[]}},
                      {"regionId":9,"name":"Days Since Last Accident","regionPlaylist":{"playlistId":6,"widgets":[]}}]}
        self.assertEqual(set(find_parts(l)),{"slideshow","calendar","counter"})

    def test_ics_empty_setting_never_fetches_network(self):
        self.assertIsNone(events_from_ics(""))

if __name__=="__main__":unittest.main()
