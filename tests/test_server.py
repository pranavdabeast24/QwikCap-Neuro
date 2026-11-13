"""Security and review invariants using only invented TXT documents.

Run from the app folder: python -m unittest discover -s tests -v
The HTTP tests bind an ephemeral loopback port and never contact the internet.
"""
from __future__ import annotations

import base64
import copy
import csv
import http.client
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch


APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
import server


def simple_schema():
    return server.parse_schema([
        {"name": "record_id", "label": "Record ID", "type": "text", "required": True},
        {"name": "visit_date", "label": "Visit date", "type": "date", "required": True},
        {"name": "age", "label": "Age", "type": "integer", "required": True, "min": 18, "max": 120},
        {"name": "consent", "label": "Consent", "type": "choice", "required": True, "choices": {"1": "Yes", "0": "No"}},
        {"name": "symptom_score", "label": "Symptom score", "type": "integer", "required": True, "min": 0, "max": 10},
        {"name": "notes", "label": "Notes", "type": "text", "required": False},
    ])


def values(identifier="TEST-001", notes="Fictional practice entry."):
    return {"record_id": identifier, "visit_date": "2026-02-12", "age": "34", "consent": "1", "symptom_score": "3", "notes": notes}


def source(identifier="TEST-001"):
    return (f"Record ID: {identifier}\nVisit date: 2026-02-12\nAge: 34\nConsent: Yes\nSymptom score: 3\nNotes: Fictional practice entry.\n").encode()


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="formbridge-test-")
        self.addCleanup(self.temp.cleanup)
        self.ws = server.Workspace(self.temp.name)
        self.ws.schema = simple_schema()
        self.record = self.ws.add(source(), "fictional.txt")

    def review(self, **overrides):
        body = {"id": self.record["id"], "values": values(), "confirmed": list(values()), "reviewer": "Synthetic Reviewer", "approve": True}
        body.update(overrides)
        self.ws.review(body)

    def test_unreviewed_document_cannot_export(self):
        self.assertEqual(self.record["status"], "review")
        with self.assertRaises(server.InputError):
            self.ws.export()

    def test_approval_requires_every_field_confirmation_and_reviewer(self):
        for overrides in ({"confirmed": ["record_id"]}, {"reviewer": "  "}, {"values": {**values(), "age": "999"}}):
            with self.subTest(overrides=overrides):
                with self.assertRaises(server.InputError):
                    self.review(**overrides)
                self.assertEqual(self.record["status"], "review")

    def test_valid_approval_exports_exact_headers_bom_and_csv_values(self):
        note = 'Café, "practice"\nLine two'
        self.review(values=values(notes=note))
        output = self.ws.export()
        self.assertTrue(output.startswith(b"\xef\xbb\xbf"))
        text = output.decode("utf-8-sig")
        self.assertTrue(text.startswith("record_id,visit_date,age,consent,symptom_score,notes\r\n"))
        self.assertEqual(list(csv.DictReader(io.StringIO(text))), [values(notes=note)])
        self.assertEqual(self.record["reviewedBy"], "Synthetic Reviewer")

    def test_saving_edit_clears_prior_approval(self):
        self.review()
        self.review(approve=False, values=values(notes="Revised fictional note."))
        self.assertEqual(self.record["status"], "review")
        self.assertEqual(self.record["reviewedBy"], "")
        with self.assertRaises(server.InputError):
            self.ws.export()

    def test_values_must_match_schema_exactly(self):
        for submitted in ({"record_id": "TEST-001"}, {**values(), "extra": "x"}, {**values(), "age": 34}):
            with self.subTest(submitted=submitted), self.assertRaises(server.InputError):
                self.review(values=submitted)

    def test_duplicate_approved_record_identifier_is_rejected(self):
        self.review()
        other = self.ws.add(source(), "another-fictional.txt")
        with self.assertRaises(server.InputError):
            self.review(id=other["id"])
        self.assertEqual(other["status"], "review")

    def test_optional_blank_remains_blank(self):
        self.review(values=values(notes=""))
        exported = list(csv.DictReader(io.StringIO(self.ws.export().decode("utf-8-sig"))))
        self.assertEqual(exported[0]["notes"], "")

    def test_remapping_is_successful_and_requires_fresh_review(self):
        self.review()
        old_id = self.record["id"]
        schema = simple_schema()
        schema[-1]["aliases"] = ["Comments"]
        self.ws.set_schema(schema)
        changed = self.ws.records[0]
        self.assertNotEqual(changed["id"], old_id)
        self.assertEqual(changed["status"], "review")
        self.assertEqual(changed["confirmed"], [])
        self.assertEqual(changed["reviewedBy"], "")
        with self.assertRaises(server.InputError):
            self.ws.export()

    def test_failed_remapping_preserves_old_schema_record_and_approval(self):
        self.review()
        before_schema, before_records = copy.deepcopy(self.ws.schema), copy.deepcopy(self.ws.records)
        schema = simple_schema()
        schema[0]["label"] = "Study identifier"
        with patch.object(self.ws, "process", side_effect=ValueError("Synthetic failure")):
            with self.assertRaises(ValueError):
                self.ws.set_schema(schema)
        self.assertEqual(self.ws.schema, before_schema)
        self.assertEqual(self.ws.records, before_records)
        self.assertIn(b"TEST-001", self.ws.export())

    def test_failed_upload_cleans_partial_preview_directory(self):
        before = {p.name for p in Path(self.temp.name).iterdir()}
        # The PDF signature passes input identification. Its malformed body
        # fails after the worker has created its per-record asset directory.
        with self.assertRaises(server.InputError):
            self.ws.add(b"%PDF-1.7\nFictional malformed PDF fixture\n", "broken-fictional.pdf")
        self.assertEqual({p.name for p in Path(self.temp.name).iterdir()}, before)
        self.assertEqual(len(self.ws.records), 1)


class ValidationTests(unittest.TestCase):
    def test_imported_dictionary_preserves_field_names_and_codes(self):
        fields, warnings = server.schema_from_csv((APP / "samples/sample-data-dictionary.csv").read_text())
        self.assertEqual([field["name"] for field in fields], list(values()))
        self.assertEqual(fields[3]["choices"], {"1": "Yes", "0": "No"})
        self.assertEqual(fields[2]["type"], "integer")
        self.assertEqual(fields[1]["type"], "date")
        self.assertEqual(warnings, [])

    def test_checkbox_columns_expand_and_branching_requires_manual_review(self):
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["Variable / Field Name", "Field Type", "Field Label", "Choices, Calculations, OR Slider Labels", "Branching Logic (Show field only if...)", "Required Field?"])
        writer.writeheader()
        writer.writerows([{"Variable / Field Name": "study_id", "Field Type": "text", "Field Label": "Study ID"}, {"Variable / Field Name": "options", "Field Type": "checkbox", "Field Label": "Options", "Choices, Calculations, OR Slider Labels": "1, Alpha | 2, Beta"}, {"Variable / Field Name": "followup", "Field Type": "notes", "Required Field?": "y", "Branching Logic (Show field only if...)": "[options(1)]=1"}])
        fields, warnings = server.schema_from_csv(output.getvalue())
        self.assertEqual([f["name"] for f in fields], ["study_id", "options___1", "options___2", "followup"])
        self.assertEqual(fields[1]["choices"], {"0": "Unchecked", "1": "Checked"})
        self.assertFalse(fields[-1]["required"])
        self.assertTrue(any("not evaluated" in warning for warning in warnings))

    def test_custom_record_identifier_is_exported_with_its_original_name(self):
        with tempfile.TemporaryDirectory() as folder:
            ws = server.Workspace(folder)
            ws.schema = server.parse_schema([{"name": "study_id", "label": "Study ID", "type": "text"}])
            record = ws.add(b"Study ID: FICTIONAL-17", "fictional.txt")
            ws.review({"id": record["id"], "values": {"study_id": "FICTIONAL-17"}, "confirmed": ["study_id"], "reviewer": "Fictional Reviewer", "approve": True})
            self.assertEqual(ws.export().decode("utf-8-sig"), "study_id\r\nFICTIONAL-17\r\n")

    def test_hostile_schema_shapes_are_input_errors(self):
        cases = [
            None, [], [{"name": "identifier", "type": "integer"}],
            [{"name": "record_id", "type": []}],
            [{"name": "record_id", "type": {}}],
            [{"name": "record_id", "required": "false"}],
            [{"name": "record_id", "aliases": [None]}],
            [{"name": "record_id", "pattern": "(a+)+$"}],
            [{"name": "record_id"}, {"name": "record_id"}],
            [{"name": "record_id"}, {"name": "choice", "type": "choice", "choices": ["yes"]}],
            [{"name": "record_id"}, {"name": "choice", "type": "choice", "choices": {"=1+1": "Bad"}}],
            [{"name": "record_id"}, {"name": "value", "min": float("nan")}],
            [{"name": "record_id", "region": {"page": True, "x": 0, "y": 0, "width": 1, "height": 1}}],
            [{"name": "record_id", "region": {"page": 1, "x": 0.9, "y": 0, "width": 0.2, "height": 1}}],
        ]
        for raw in cases:
            with self.subTest(raw=raw), self.assertRaises(server.InputError):
                server.parse_schema(raw)

    def test_strict_ascii_numeric_grammar(self):
        for kind in ("integer", "number"):
            schema = server.parse_schema([{"name": "record_id", "type": "text"}, {"name": "value", "type": kind}])
            for bad in ("1_0", "١٢", "１２", "NaN", "Infinity", " 12 ", "=1+1"):
                with self.subTest(kind=kind, bad=bad):
                    self.assertIn("value", server.validate_values(schema, {"record_id": "TEST", "value": bad}))
            for good in ("0", "12", "-4"):
                with self.subTest(kind=kind, good=good):
                    self.assertNotIn("value", server.validate_values(schema, {"record_id": "TEST", "value": good}))
        schema[-1]["type"] = "number"
        for good in ("0.5", "-3.25", ".5", "1e2"):
            with self.subTest(good=good):
                self.assertNotIn("value", server.validate_values(schema, {"record_id": "TEST", "value": good}))

    def test_numeric_bound_does_not_round_to_float(self):
        schema = server.parse_schema([{"name": "record_id", "type": "text"}, {"name": "value", "type": "integer", "max": 9007199254740992}])
        self.assertIn("value", server.validate_values(schema, {"record_id": "TEST", "value": "9007199254740993"}))
        self.assertNotIn("value", server.validate_values(schema, {"record_id": "TEST", "value": "9007199254740992"}))

    def test_invalid_required_date_choice_formula_and_controls(self):
        schema = simple_schema()
        bad_values = {"age": ["", "17", "121", "1.5"], "symptom_score": ["-1", "11"], "visit_date": ["2026-02-30", "02/12/2026"], "consent": ["Yes", "9"], "notes": ["=1+1", " +SUM(A1)", "\t@evil", "unsafe\x00value", "x" * 4001], "record_id": ["../path", "=payload"]}
        for field, items in bad_values.items():
            for item in items:
                with self.subTest(field=field, item=item[:40]):
                    self.assertIn(field, server.validate_values(schema, {**values(), field: item}))


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="formbridge-http-test-")
        cls.server = server.Server(("127.0.0.1", 0), server.Workspace(cls.temp.name))
        cls.port = cls.server.server_port
        cls.thread = threading.Thread(target=cls.server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
        cls.temp.cleanup()

    def setUp(self):
        self.test_temp = tempfile.TemporaryDirectory(dir=self.temp.name)
        self.addCleanup(self.test_temp.cleanup)
        self.server.workspace = server.Workspace(self.test_temp.name)
        self.server.workspace.schema = simple_schema()

    def request(self, method, path, body=None, headers=None, authenticated=True):
        defaults = {"Host": f"127.0.0.1:{self.port}"}
        if authenticated:
            defaults.update({"Cookie": f"formbridge_session={self.server.session}", "X-CSRF-Token": self.server.csrf})
        payload = None
        if body is not None:
            payload = body if isinstance(body, bytes) else json.dumps(body).encode()
            defaults["Content-Type"] = "application/json"
        defaults.update(headers or {})
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=4)
        try:
            connection.request(method, path, body=payload, headers=defaults)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_state_requires_session_and_does_not_expose_original_base64(self):
        ws = self.server.workspace
        ws.add(source(), "fictional.txt")
        self.assertEqual(self.request("GET", "/api/state", authenticated=False)[0], 403)
        status, headers, body = self.request("GET", "/api/state")
        self.assertEqual(status, 200)
        parsed = json.loads(body)
        self.assertNotIn("sourceData", parsed["records"][0])
        self.assertEqual(parsed["csrfToken"], self.server.csrf)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")

    def test_foreign_host_origin_fetch_site_and_invalid_session_are_blocked(self):
        for headers in ({"Host": "attacker.invalid"}, {"Origin": "https://attacker.invalid"}, {"Origin": "null"}, {"Sec-Fetch-Site": "cross-site"}, {"Cookie": "formbridge_session=wrong"}):
            with self.subTest(headers=headers):
                self.assertEqual(self.request("GET", "/api/state", headers=headers)[0], 403)

    def test_mutations_require_csrf_and_block_foreign_origin(self):
        for headers in ({"X-CSRF-Token": ""}, {"X-CSRF-Token": "wrong"}, {"Origin": "http://evil.invalid"}):
            with self.subTest(headers=headers):
                self.assertEqual(self.request("POST", "/api/reset", {}, headers=headers)[0], 403)
        self.assertEqual(self.request("POST", "/api/reset", {})[0], 200)

    def test_absolute_form_api_target_does_not_bypass_session(self):
        status, _, _ = self.request("GET", f"http://127.0.0.1:{self.port}/api/state", authenticated=False)
        self.assertIn(status, (400, 403))

    def test_invalid_json_base64_and_schema_do_not_mutate_workspace(self):
        bad_requests = [("/api/upload", b"{"), ("/api/upload", b"[]"), ("/api/upload", {"filename": "fictional.txt", "data": "not base64!"}), ("/api/schema", {"schema": [{"name": "record_id", "type": []}]}), ("/api/upload", {"filename": "fictional.pdf", "data": base64.b64encode(b"Not a PDF").decode()})]
        for path, body in bad_requests:
            with self.subTest(path=path, body=body):
                self.assertEqual(self.request("POST", path, body)[0], 400)
                self.assertEqual(self.server.workspace.records, [])
                self.assertEqual(self.server.workspace.schema, simple_schema())

    def test_body_length_and_content_type_are_bounded(self):
        for headers, expected in (({"Content-Length": "0"}, 413), ({"Content-Length": "-1"}, 413), ({"Content-Length": str(server.MAX_BODY + 1)}, 413), ({"Content-Length": "invalid"}, 400), ({"Content-Type": "text/plain"}, 415)):
            with self.subTest(headers=headers):
                self.assertEqual(self.request("POST", "/api/reset", {}, headers=headers)[0], expected)

    def test_imported_project_cannot_forge_prior_approval(self):
        forged = {"format": "formbridge-project-v1", "schema": simple_schema(), "reviewer": "Forged Reviewer", "records": [{"filename": "fictional.txt", "sourceData": base64.b64encode(source()).decode(), "values": values(), "status": "approved", "confirmed": list(values()), "reviewedBy": "Forged Reviewer", "sourceHash": "forged"}]}
        status, _, body = self.request("POST", "/api/project", forged)
        self.assertEqual(status, 200, body)
        record = json.loads(body)["records"][0]
        self.assertEqual(record["status"], "review")
        self.assertEqual(record["confirmed"], [])
        self.assertEqual(record["reviewedBy"], "")
        self.assertNotEqual(record["sourceHash"], "forged")
        self.assertEqual(self.request("GET", "/api/export")[0], 400)

    def test_failed_project_import_is_atomic(self):
        ws = self.server.workspace
        existing = ws.add(source(), "fictional.txt")
        before = copy.deepcopy(ws.records)
        before_assets = {p.name for p in ws.assets.iterdir()}
        project = {"format": "formbridge-project-v1", "schema": simple_schema(), "records": [{"filename": "another.txt", "sourceData": base64.b64encode(source("TEST-002")).decode(), "values": values("TEST-002")}, {"filename": "bad.txt", "sourceData": "bad base64!", "values": values("TEST-003")}]}
        self.assertEqual(self.request("POST", "/api/project", project)[0], 400)
        self.assertEqual(ws.records, before)
        self.assertEqual(ws.records[0]["id"], existing["id"])
        self.assertEqual({p.name for p in ws.assets.iterdir()}, before_assets)

    def test_reset_removes_rendered_source_directories(self):
        ws = self.server.workspace
        record = ws.add(source(), "fictional.txt")
        folder = ws.assets / record["id"]
        self.assertTrue(folder.is_dir())
        self.assertEqual(self.request("POST", "/api/reset", {})[0], 200)
        self.assertFalse(folder.exists())
        self.assertEqual(ws.records, [])

    def test_saved_project_contains_sources_and_can_reload_as_draft(self):
        ws = self.server.workspace
        record = ws.add(source(), "fictional.txt")
        ws.review({"id": record["id"], "values": values(), "confirmed": list(values()), "reviewer": "Fictional Reviewer", "approve": True})
        status, _, raw = self.request("GET", "/api/project")
        self.assertEqual(status, 200)
        self.assertLessEqual(len(raw), server.MAX_BODY)
        project = json.loads(raw)
        self.assertNotIn("sourceText", project["records"][0])
        self.assertNotIn("status", project["records"][0])
        self.assertEqual(self.request("POST", "/api/reset", {})[0], 200)
        status, _, body = self.request("POST", "/api/project", project)
        self.assertEqual(status, 200, body)
        restored = json.loads(body)["records"][0]
        self.assertEqual(restored["values"], values())
        self.assertEqual(restored["status"], "review")
        self.assertEqual(restored["confirmed"], [])


if __name__ == "__main__":
    unittest.main()
