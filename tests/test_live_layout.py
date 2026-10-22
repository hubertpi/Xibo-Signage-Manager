"""Tests for combined layout management and ICS-driven calendar rendering."""
import datetime as dt
import pathlib
import sys
import unittest
from zoneinfo import ZoneInfo
from unittest.mock import patch, Mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "xibo_signage_manager"))
from counter_widget import render_counter_markup, COUNTER_STYLE, COUNTER_SCRIPT, get_widget_option
from calendar_widget import render_calendar, CAL_STYLE, CAL_SCRIPT, events_from_ics
from layout_sync import find_parts, _clock_region_updates, CLOCK_GEOMETRY

class LiveLayoutTests(unittest.TestCase):
    def test_counter_is_svg_text_and_not_clipped_giant_html_font(self):
        text=render_counter_markup(dt.date(2024,4,1))
        self.assertIn('viewBox="0 0 1120 400"',text)
        self.assertIn('data-last-accident="2024-04-01"',text)
        self.assertIn('Days Since Last Accident',text)
        self.assertIn('<text id="xsm-days"',text)
        self.assertIn('id="xsm-safety-image"',text)
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

    def test_native_clock_regions_recenter_without_replacing_widgets(self):
        layout = {"regions": [
            {"regionId": 11, "name": "Live Time", "left": 2680, "top": 38,
             "width": 1120, "height": 160,
             "regionPlaylist": {"widgets": [{"type": "clock-digital"}]}},
            {"regionId": 14, "name": "Live Date", "left": 2680, "top": 203,
             "width": 1120, "height": 143,
             "regionPlaylist": {"widgets": [{"type": "clock-digital"}]}},
            {"regionId": 15, "name": "Live Time", "top": 0,
             "regionPlaylist": {"widgets": [{"type": "embedded"}]}},
        ]}
        updates = _clock_region_updates(layout)
        self.assertEqual([r["regionId"] for r, target in updates], [11, 14])
        self.assertEqual(
            CLOCK_GEOMETRY["Live Date"]["top"] -
            (CLOCK_GEOMETRY["Live Time"]["top"] + CLOCK_GEOMETRY["Live Time"]["height"]),
            22
        )
        self.assertEqual((CLOCK_GEOMETRY["Live Time"]["top"] +
                          CLOCK_GEOMETRY["Live Date"]["top"] +
                          CLOCK_GEOMETRY["Live Date"]["height"]) / 2, 190)
        for region, target in updates:
            region.update(target)
        self.assertEqual(_clock_region_updates(layout), [])

    def test_ics_rolling_30_days_includes_today_and_day_29(self):
        def event(uid, start, summary):
            return (
                "BEGIN:VEVENT\n"
                f"UID:{uid}\n"
                "DTSTAMP:20261001T120000Z\n"
                f"DTSTART;VALUE=DATE:{start}\n"
                f"SUMMARY:{summary}\n"
                "END:VEVENT\n"
            )
        ics = (
            "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//XSM Test//EN\n"
            + event("a@test", "20261020", "Yesterday")
            + event("b@test", "20261021", "Today")
            + event("c@test", "20261119", "Day 29")
            + event("d@test", "20261120", "Day 30")
            + "END:VCALENDAR\n"
        ).encode("utf-8")
        response = Mock()
        response.content = ics
        with patch("calendar_widget.requests.get", return_value=response):
            found = events_from_ics(
                "https://example.test/calendar.ics",
                now=dt.datetime(2026, 10, 21, 12, tzinfo=ZoneInfo("America/Chicago")),
            )
        self.assertEqual([e["name"] for e in found], ["Today", "Day 29"])

    def test_ics_empty_setting_never_fetches_network(self):
        self.assertIsNone(events_from_ics(""))

if __name__=="__main__":unittest.main()
