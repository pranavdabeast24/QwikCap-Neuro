"""Windows acceptance with disposable processes and fictional local inputs only."""
from __future__ import annotations

import base64
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tkinter as tk
from tkinter import font as tkfont
import unittest
from unittest.mock import patch

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

from desktop_model import DesktopSession, InputError
from runtime_paths import worker_command, process_options
import pipeline


@unittest.skipUnless(os.name == "nt", "Requires native Windows behavior")
class WindowsRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="quickcap-windows-test-")
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name) / "Folder with spaces 測試 Café 😀"
        self.folder.mkdir()

    def session(self):
        session = DesktopSession()
        self.addCleanup(session.close)
        session.set_schema([{"name": "record_id", "label": "Record ID", "type": "text", "required": True}])
        return session

    def test_locked_export_preserves_destination_dirty_state_and_removes_temporary_file(self):
        from ctypes import wintypes

        session = self.session()
        record = session.add_document(b"Record ID: SYNTHETIC-LOCK", "fictional.txt")
        session.review_record(record["id"], record["values"], ["record_id"], "Fictional reviewer", True)
        target = self.folder / "fictional export.csv"
        target.write_bytes(b"previous fictional export")
        before = session.snapshot()
        self.assertTrue(before["dirty"])
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                      wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        handle = kernel.CreateFileW(str(target), 0x80000000, 0x00000001, None, 3, 0x80, None)
        self.assertNotEqual(handle, wintypes.HANDLE(-1).value, "Could not lock the disposable export")
        try:
            with self.assertRaises(InputError):
                session.export("csv", target, mapped=False)
            self.assertEqual(session.snapshot(), before)
            self.assertEqual(list(self.folder.iterdir()), [target])
        finally:
            kernel.CloseHandle(handle)
        self.assertEqual(target.read_bytes(), b"previous fictional export")
        session.export("csv", target, mapped=False)
        self.assertIn(b"SYNTHETIC-LOCK", target.read_bytes())
        self.assertTrue(session.dirty)

    def test_ascii_json_workers_round_trip_unicode_under_cp1252_stdio(self):
        value = "Fictional value 測試 Café 😀"
        label = "Fictional label 測試 Café 😀"
        environment = {**os.environ, "PYTHONUTF8": "0", "PYTHONIOENCODING": "cp1252"}
        payload = {"data": base64.b64encode(f"{label}: {value}".encode("utf-8")).decode("ascii"),
                   "filename": "Fictional form 測試 Café 😀.txt", "assetDir": str(self.folder),
                   "recordId": "synthetic-unicode", "schema": [{"name": "notes", "label": label, "type": "text"}]}
        result = subprocess.run(worker_command("document"), input=json.dumps(payload).encode("ascii"),
                                capture_output=True, env=environment, timeout=60, check=True, **process_options())
        self.assertTrue(result.stdout.isascii(), "Document worker broke the ASCII JSON wire contract")
        self.assertEqual(json.loads(result.stdout)["values"], {"notes": value})
        column = "Fictional column 測試 Café 😀"
        payload = {"operation": "inspect", "filename": "Fictional template 測試 Café 😀.csv",
                   "data": base64.b64encode((column + "\n").encode("utf-8-sig")).decode("ascii")}
        result = subprocess.run(worker_command("template"), input=json.dumps(payload).encode("ascii"),
                                capture_output=True, env=environment, timeout=60, check=True, **process_options())
        self.assertTrue(result.stdout.isascii(), "Template worker broke the ASCII JSON wire contract")
        self.assertEqual([item["name"] for item in json.loads(result.stdout)["result"]["columns"]], [column])

    def test_project_save_reopen_with_unicode_paths_and_values_under_cp1252_stdio(self):
        inputs = {"folder": str(self.folder), "value": "Fictional value 測試 Café 😀",
                  "label": "Fictional label 測試 Café 😀", "filename": "Fictional form 測試 Café 😀.txt",
                  "column": "Fictional column 測試 Café 😀"}
        script = """
import json, pathlib, sys
from desktop_model import DesktopSession
inputs = json.loads(sys.argv[1])
folder = pathlib.Path(inputs['folder'])
session = DesktopSession()
try:
    session.set_schema([{'name': 'record_id', 'label': 'Record ID', 'type': 'text'},
                        {'name': 'notes', 'label': inputs['label'], 'type': 'text'}])
    source = 'Record ID: SYNTHETIC-UNICODE\\n' + inputs['label'] + ': ' + inputs['value']
    record = session.add_document(source.encode('utf-8'), inputs['filename'])
    expected = {'record_id': 'SYNTHETIC-UNICODE', 'notes': inputs['value']}
    assert record['values'] == expected
    session.review_record(record['id'], record['values'], ['record_id', 'notes'], 'Fictional reviewer', True)
    template = folder / 'Fictional template \\u6e2c\\u8a66 Caf\\u00e9 \\U0001f600.csv'
    template.write_text('record_id,' + inputs['column'] + '\\n', encoding='utf-8-sig')
    session.import_template(template)
    mappings = {'record_id': 'record_id', inputs['column']: 'notes'}
    session.set_mapping(mappings, True)
    project = folder / 'Fictional project \\u6e2c\\u8a66 Caf\\u00e9 \\U0001f600.json'
    session.save_project(project)
    assert not session.dirty and project.read_bytes().isascii()
    session.open_project(project)
    record = session.snapshot()['records'][0]
    assert record['filename'] == inputs['filename']
    assert record['values'] == expected
    assert record['confirmed'] == [] and record['status'] == 'review'
    assert session.workspace.template['mappings'] == mappings
    assert not session.workspace.template['confirmed'] and not session.dirty
    print(json.dumps({'status': 'passed', 'records': 1}))
finally:
    session.close()
"""
        environment = {**os.environ, "PYTHONUTF8": "0", "PYTHONIOENCODING": "cp1252", "PYTHONPATH": str(APP)}
        result = subprocess.run([sys.executable, "-c", script, json.dumps(inputs)], cwd=self.folder,
                                capture_output=True, env=environment, timeout=90, **process_options())
        self.assertEqual(result.returncode, 0, result.stderr.decode("cp1252", errors="replace")[-1500:])
        self.assertEqual(json.loads(result.stdout), {"status": "passed", "records": 1})

    def test_no_ocr_keeps_manual_review_available(self):
        session = self.session()
        absent = str(self.folder / "tesseract.exe")
        with patch.dict(os.environ, {"FORMBRIDGE_TESSERACT": absent}):
            self.assertIsNone(pipeline._tesseract_path())
            record = session.add_document((APP / "samples/practice-06-scan.pdf").read_bytes(), "fictional scan.pdf")
        self.assertEqual(record["values"], {"record_id": ""})
        self.assertEqual(record["evidence"], {})
        self.assertTrue(any("Local OCR is unavailable" in issue for issue in record["issues"]))
        session.review_record(record["id"], {"record_id": "MANUAL-SYNTHETIC"}, [], "Fictional reviewer")
        reviewed = session.review_record(record["id"], {"record_id": "MANUAL-SYNTHETIC"},
                                         ["record_id"], "Fictional reviewer", True)
        self.assertEqual(reviewed["values"], {"record_id": "MANUAL-SYNTHETIC"})
        self.assertEqual(reviewed["status"], "approved")

    @unittest.skipUnless(os.environ.get("FORMBRIDGE_REQUIRE_OCR") == "1", "Operational OCR is required by the Windows acceptance job")
    def test_required_tesseract_extracts_every_scanned_fictional_answer(self):
        self.assertIsNotNone(pipeline._tesseract_path(), "Windows acceptance requires an installed Tesseract engine")
        self.assertEqual(pipeline.capabilities()["ocrEngine"], "tesseract")
        schema = json.loads((APP / "samples/sample-schema.json").read_text(encoding="utf-8"))["fields"]
        fixtures = json.loads((APP / "samples/answer-key.json").read_text(encoding="utf-8"))["records"][5:]
        self.assertEqual(len(fixtures), 5)
        for index, fixture in enumerate(fixtures):
            with self.subTest(fixture=fixture["file"]):
                result = pipeline.process_document((APP / "samples" / fixture["file"]).read_bytes(),
                                                   fixture["file"], schema, self.folder, f"synthetic-scan-{index}")
                self.assertEqual(result["values"], {key: str(value) for key, value in fixture["expected"].items()},
                                 f"Fictional scan extraction issues: {result['issues']}")
                self.assertEqual(result["issues"], [])
                self.assertTrue(result["evidence"])
                self.assertEqual({item["method"] for item in result["evidence"].values()}, {"tesseract"})
                self.assertTrue(pipeline.capabilities()["ocrOperational"])

    def test_native_windows_tk_maps_controls_with_segoe_ui(self):
        from desktop import DesktopApp

        root = tk.Tk()
        app = None
        try:
            app = DesktopApp(root)
            root.geometry("1024x700")
            root.update()
            self.assertTrue(root.winfo_viewable())
            self.assertEqual(root.minsize(), (1024, 700))
            self.assertEqual(tkfont.Font(root=root, font=root.option_get("font", "Font")).actual("family").casefold(), "segoe ui")
            self.assertTrue(app.notebook.winfo_viewable())
            self.assertEqual(len(app.notebook.tabs()), 2)
            self.assertFalse(app.snapshot["records"])
        finally:
            if app is not None:
                app.commands.put(None)
                app.thread.join(timeout=2)
                self.assertFalse(app.thread.is_alive(), "Verification left a domain thread running")
                app.session.close()
            for pending in root.tk.call("after", "info"):
                root.after_cancel(pending)
            root.destroy()


if __name__ == "__main__":
    unittest.main()
