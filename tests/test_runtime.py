"""Tests for add-on startup diagnostics, Xibo 403 errors and icon."""
import ast
import pathlib
import re
import signal
import struct
import tempfile
import threading
import unittest
from types import SimpleNamespace
from urllib.parse import urljoin
from unittest.mock import Mock

ROOT = pathlib.Path(__file__).resolve().parents[1] / "xibo_signage_manager"
SOURCE = (ROOT / "manager.py").read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)

def function(name, namespace):
    node = next(node for node in TREE.body
                if isinstance(node, ast.FunctionDef) and node.name == name)
    code = compile(ast.Module(body=[node], type_ignores=[]), "manager.py", "exec")
    exec(code, namespace)
    return namespace[name]

class StartupTests(unittest.TestCase):
    def test_addon_icon_png(self):
        path = ROOT / "icon.png"
        data = path.read_bytes()
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack(">II", data[16:24]), (160, 160))

    def test_version_reads_config_in_container(self):
        version = function("addon_version", {"pathlib":pathlib,"re":re})
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / "config.yaml"
            path.write_text('version: "0.5.3"\n')
            self.assertEqual(version(path),"0.5.3")
            self.assertEqual(version(path.parent/"missing.yaml"),"unknown")

    def test_sigterm_shutdown_marks_event(self):
        stopped=threading.Event()
        due=threading.Event()
        log=Mock()
        fn=function("request_shutdown",{
            "LOG":log,"SHUTDOWN":stopped,"DUE":due,"signal":signal})
        fn(signal.SIGTERM,None)
        self.assertTrue(stopped.is_set())
        self.assertTrue(due.is_set())
        self.assertIn("Shutdown requested",log.info.call_args.args[0])

    def test_forbidden_widget_delete_is_actionable(self):
        response = SimpleNamespace(status_code=403, content=b"",
                                   raise_for_status=Mock())
        calls=[]
        ns={"requests":SimpleNamespace(request=lambda *a,**kw: (calls.append((a,kw)) or response)),
            "urljoin":urljoin,"API":"http://xibo.invalid/api/",
            "token":lambda:"test-token","TOKEN_EXPIRY":100}
        fn=function("api",ns)
        with self.assertRaisesRegex(PermissionError,"DELETE on widget 160") as ctx:
            fn("DELETE","playlist/widget/160")
        self.assertIn("delete permission",str(ctx.exception))
        self.assertEqual(calls[0][0][0],"DELETE")

    def test_explicit_success_and_stop_logs(self):
        self.assertIn("Synchronization successful:",SOURCE)
        self.assertIn("MQTT connected and Home Assistant discovery published",SOURCE)
        self.assertIn("Shutdown complete",SOURCE)

if __name__ == "__main__":
    unittest.main()
