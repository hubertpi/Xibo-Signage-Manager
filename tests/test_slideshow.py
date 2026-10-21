"""Regression tests for folder-managed sequencing and time prefixes."""
import pathlib
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"xibo_signage_manager"))
from slideshow import DOC_FILE, needs_playlist_sync, parse_name, rename_bulletins

class SlideFileTests(unittest.TestCase):
    def make_files(self,filenames):
        directory=tempfile.TemporaryDirectory()
        root=pathlib.Path(directory.name)
        for name in filenames:
            (root/name).write_bytes((name+" content").encode())
        with patch("slideshow.time.time",return_value=time.time()+100):
            result=rename_bulletins(root)
        return directory,root,result

    def test_insert_at_2_shifts_later_items(self):
        directory,root,items=self.make_files([
            "01 - 10s - Safety.pdf","02 - 15s - Quality.png",
            "03 - 10s - Report.jpg","0002 - 12s - Notice.pdf"])
        try:
            self.assertEqual([r["path"].name for r in items],[
                "01 - 10s - Safety.pdf","02 - 12s - Notice.pdf",
                "03 - 15s - Quality.png","04 - 10s - Report.jpg"])
            self.assertTrue((root/DOC_FILE).is_file())
            with patch("slideshow.time.time",return_value=time.time()+100):
                self.assertEqual([r["path"].name for r in rename_bulletins(root)],
                                 [r["path"].name for r in items])
        finally:directory.cleanup()

    def test_new_upload_is_appended_with_10s(self):
        directory,root,items=self.make_files(["01 - 20s - Existing.png","New.pdf"])
        try:
            self.assertEqual([r["path"].name for r in items],[
                "01 - 20s - Existing.png","02 - 10s - New.pdf"])
        finally:directory.cleanup()

    def test_four_digit_existing_move(self):
        directory,root,items=self.make_files([
            "01 - 10s - Alpha.jpg","02 - 10s - Bravo.jpg",
            "0001 - 10s - Charlie.jpg"])
        try:
            self.assertEqual([r["original"] for r in items],
                             ["Charlie.jpg","Alpha.jpg","Bravo.jpg"])
        finally:directory.cleanup()

    def test_duplicate_stems_rejected_before_mutation(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td)
            for name in ("01 - 10s - Same.jpg","02 - 15s - Same.jpg"):
                (root/name).write_bytes(b"content")
            with patch("slideshow.time.time",return_value=time.time()+100):
                with self.assertRaisesRegex(ValueError,"Duplicate"):
                    rename_bulletins(root)
            self.assertTrue((root/"01 - 10s - Same.jpg").is_file())

    def test_incomplete_copy_is_deferred(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td)
            (root/"New.png").write_bytes(b"x")
            self.assertIsNone(rename_bulletins(root))
            self.assertTrue((root/"New.png").exists())

    def test_parse_4_digit_and_default(self):
        self.assertEqual(parse_name("0002 - 15s - Update.pdf"),(2,True,15,"Update.pdf"))
        self.assertEqual(parse_name("Update.png"),(None,False,10,"Update.png"))

    def test_transition_is_required_for_existing_widgets(self):
        playlist={"isDynamic":0,"widgets":[{"widgetId":7,"mediaIds":[71],
                  "duration":10,"useDuration":1,"displayOrder":1,"widgetOptions":[]}]}
        slides=[{"media_id":71,"duration":10}]
        self.assertTrue(needs_playlist_sync(playlist,slides))
        playlist["widgets"][0]["widgetOptions"]=[{"option":k,"value":v} for k,v in {
            "transIn":"fly","transOut":"fly","transInDirection":"W",
            "transOutDirection":"W","transInDuration":"800",
            "transOutDuration":"800"}.items()]
        self.assertFalse(needs_playlist_sync(playlist,slides))

if __name__=="__main__":unittest.main()
