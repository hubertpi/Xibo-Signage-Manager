"""Regression tests for folder-managed sequencing and time prefixes."""
import pathlib
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"xibo_signage_manager"))
from slideshow import DOC_FILE, needs_playlist_sync, parse_name, rename_bulletins, pdf_pages, slideshow_payload, SLIDESHOW_STYLE

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

    def test_pdf_page_sizes_requested_and_aspect_preserved(self):
        """pdfinfo needs -f/-l to report 'Page N size' instead of 'Page size'."""
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td)
            document=root/"Newsletter.pdf"
            document.write_bytes(b"%PDF-1.4 test stub")
            renders=[]
            def run(args, **kwargs):
                if args[0]=="pdfinfo":
                    self.assertEqual(args[1:5],["-f","1","-l","100"])
                    return SimpleNamespace(stdout=(
                        "Pages:           2\\n"
                        "Page    1 size:  612 x 792 pts (letter)\\n"
                        "Page    1 rot:   0\\n"
                        "Page    2 size:  792 x 612 pts (letter)\\n"
                        "Page    2 rot:   0\\n"))
                if args[0]=="pdftoppm":
                    renders.append(args)
                    pathlib.Path(args[-1]+".jpg").write_bytes(b"test-rendered-page")
                    return SimpleNamespace()
                self.fail("Unexpected subprocess: "+str(args))
            with patch("slideshow.subprocess.run",side_effect=run):
                output=pdf_pages(document,"sha256",root/"cache")
            self.assertEqual(len(output),2)
            self.assertTrue(all(p.is_file() for p in output))
            self.assertEqual(
                [r[r.index("-scale-to-x")+1] for r in renders],
                ["1626","2608"])
            self.assertEqual(
                [r[r.index("-scale-to-y")+1] for r in renders],
                ["2104","2015"])

    def test_embedded_slideshow_clips_to_rounded_region(self):
        slides=[{"media_id":71,"duration":10},{"media_id":72,"duration":15}]
        payload=slideshow_payload(slides)
        self.assertIn('border-radius:34px', SLIDESHOW_STYLE)
        self.assertIn('overflow:hidden', SLIDESHOW_STYLE)
        self.assertIn('object-fit:contain', SLIDESHOW_STYLE)
        self.assertIn('data-url="[71]" data-ms="10000"',payload["embedHtml"])
        self.assertIn('data-url="[72]" data-ms="15000"',payload["embedHtml"])
        self.assertIn('translateX(-100%)',payload["embedScript"])
        self.assertEqual(payload["duration"],"3600")

    def test_embedded_slideshow_sync_is_idempotent(self):
        slides=[{"media_id":71,"duration":10}]
        payload=slideshow_payload(slides)
        widget={"widgetId":3,"type":"embedded","duration":3600,
                "useDuration":1,"widgetOptions":[{"option":k,"value":v}
                for k,v in payload.items()]}
        self.assertFalse(needs_playlist_sync({"isDynamic":0,"widgets":[widget]},slides))
        changed=[{"media_id":71,"duration":15}]
        self.assertTrue(needs_playlist_sync({"isDynamic":0,"widgets":[widget]},changed))


if __name__=="__main__":unittest.main()
