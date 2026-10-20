"""Unit tests for Xibo's real upload response shape and media reconciliation."""
import ast
import pathlib
import unittest

source = pathlib.Path("xibo_signage_manager/manager.py").read_text()
tree = ast.parse(source)
pure_names = {"media_id_from_upload", "managed_title", "find_managed_media"}
namespace = {}
for node in tree.body:
    if isinstance(node, ast.FunctionDef) and node.name in pure_names:
        compiled = compile(ast.Module(body=[node], type_ignores=[]),
                           filename="manager.py", mode="exec")
        exec(compiled, namespace)


class XiboResponseTests(unittest.TestCase):
    def test_real_nested_image_success(self):
        self.assertEqual(namespace["media_id_from_upload"](
            {"files": [{"name": "Now Hiring.jpg", "mediaId": 20}]}), 20)

    def test_real_nested_pdf_success(self):
        self.assertEqual(namespace["media_id_from_upload"](
            {"files": [{"name": "Safety.pdf", "mediaId": 21}]}), 21)

    def test_nested_duplicate_is_an_error(self):
        with self.assertRaisesRegex(ValueError, "already own media"):
            namespace["media_id_from_upload"](
                {"files": [{"error": "You already own media with this name."}]})

    def test_update_fallback_without_media_id(self):
        self.assertEqual(namespace["media_id_from_upload"](
            {"files": [{"name": "Revised.pdf"}]}, fallback=42), 42)

    def test_update_with_error_must_not_use_fallback(self):
        with self.assertRaisesRegex(ValueError, "rejected"):
            namespace["media_id_from_upload"](
                {"files": [{"error": "Forbidden"}]}, fallback=42)

    def test_adopt_existing_managed_media(self):
        items = [{"name": "Now Hiring.jpg", "mediaId": 20},
                 {"name": "XSM - Other.pdf", "mediaId": 22}]
        self.assertEqual(namespace["find_managed_media"](
            items, "Now Hiring.jpg")["mediaId"], 20)
        self.assertEqual(namespace["find_managed_media"](
            items, "Other.pdf")["mediaId"], 22)

    def test_unrelated_name_is_not_adopted(self):
        self.assertIsNone(namespace["find_managed_media"](
            [{"name": "Unrelated.jpg", "mediaId": 10}], "Other.jpg"))

    def test_prefixed_upload_title(self):
        self.assertEqual(namespace["managed_title"]("Test.pdf"), "XSM - Test.pdf")


if __name__ == "__main__":
    unittest.main()
