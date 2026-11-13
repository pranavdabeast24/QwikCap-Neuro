"""Companion worker behavior and source/frozen resource selection."""
import base64
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
import runtime_paths
import desktop_worker


class DesktopRuntimeTests(unittest.TestCase):
    def test_unknown_worker_cannot_dispatch(self):
        with self.assertRaises(ValueError):
            runtime_paths.worker_command("anything-else")
        self.assertEqual(desktop_worker.main(["anything-else"]), 2)

    def test_frozen_gui_resolves_separate_helper(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch.object(sys, "frozen", True, create=True), patch.object(sys, "_MEIPASS", folder, create=True):
                with self.assertRaises(RuntimeError):
                    runtime_paths.worker_command("template")
                (root / "helpers").mkdir()
                helper = root / "helpers" / ("FormbridgeWorker.exe" if sys.platform == "win32" else "FormbridgeWorker")
                helper.write_bytes(b"fixture")
                self.assertEqual(runtime_paths.worker_command("template"), [str(helper), "template"])

    def test_source_document_worker_returns_real_pdf_values(self):
        with tempfile.TemporaryDirectory() as folder:
            data = (APP / "samples/practice-01-text.pdf").read_bytes()
            schema = json.loads((APP / "samples/sample-schema.json").read_text())
            if isinstance(schema, dict):
                schema = schema.get("fields", schema.get("schema"))
            payload = {"data": base64.b64encode(data).decode(), "filename": "fictional.pdf", "schema": schema, "assetDir": folder, "recordId": "fictionalworker"}
            result = subprocess.run(runtime_paths.worker_command("document"), input=json.dumps(payload), text=True, capture_output=True, timeout=60, check=True)
            actual = json.loads(result.stdout)
            self.assertEqual(actual["values"]["record_id"], "DEMO-001")
            self.assertEqual(str(actual["values"]["age"]), "34")
            self.assertTrue((Path(folder) / "fictionalworker/page-1.png").is_file())

    def test_pythonw_parent_uses_console_python_for_piped_workers(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            console = root / "python.exe"
            with patch.object(sys, "executable", str(root / "pythonw.exe")):
                with self.assertRaises(RuntimeError):
                    runtime_paths.worker_command("document")
                console.write_bytes(b"fixture")
                self.assertEqual(runtime_paths.worker_command("document")[0], str(console))

    def test_source_template_worker_inspects_actual_friendly_headers(self):
        payload = {"operation": "inspect", "data": base64.b64encode((APP / "spreadsheets/friendly-template.xlsx").read_bytes()).decode(), "filename": "friendly-template.xlsx"}
        result = subprocess.run(runtime_paths.worker_command("template"), input=json.dumps(payload), text=True, capture_output=True, timeout=40, check=True)
        spec = json.loads(result.stdout)["result"]
        self.assertEqual(spec["headerRow"], 3)
        self.assertEqual([c["name"] for c in spec["columns"]], ["Participant ID", "Age (years)", "Consent code", "Visit date", "Score", "Research notes"])


if __name__ == "__main__":
    unittest.main()
