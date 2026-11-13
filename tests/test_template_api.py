"""Loopback integration tests for template mapping and approved-only exports.

Every document and workbook fixture is fictional. XLSX fixtures are the actual
blank, authored sample templates shipped with the app, never generated here.
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

import openpyxl

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
import server


RAW_HEADERS = ["record_id", "visit_date", "age", "consent", "symptom_score", "notes"]
FRIENDLY_HEADERS = ["Participant ID", "Age (years)", "Consent code", "Visit date", "Score", "Research notes"]
RAW_MAPPING = {name: name for name in RAW_HEADERS}
FRIENDLY_MAPPING = {
    "Participant ID": "record_id", "Age (years)": "age", "Consent code": "consent",
    "Visit date": "visit_date", "Score": "symptom_score", "Research notes": "notes",
}
VALUES = {"record_id": "000007", "visit_date": "2026-10-25", "age": "34", "consent": "0", "symptom_score": "0", "notes": ""}


def fictional_source(identifier="000007", notes=""):
    return (f"Record ID: {identifier}\nVisit date: 2026-10-25\nAge: 34\n"
            f"Consent: No\nSymptom score: 0\nNotes: {notes}\n").encode()


class TemplateAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="formbridge-template-api-")
        cls.httpd = server.Server(("127.0.0.1", 0), server.Workspace(cls.temp.name))
        cls.port = cls.httpd.server_port
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=2)
        cls.temp.cleanup()

    def setUp(self):
        self.assets = tempfile.TemporaryDirectory(dir=self.temp.name)
        self.addCleanup(self.assets.cleanup)
        self.httpd.workspace = server.Workspace(self.assets.name)
        # Plain text uses labels and aliases without the PDF sample's regions.
        self.httpd.workspace.schema = server.parse_schema([
            {"name": "record_id", "label": "Record ID", "type": "text", "required": True},
            {"name": "visit_date", "label": "Visit date", "type": "date", "required": True},
            {"name": "age", "label": "Age", "type": "integer", "required": True, "min": 18, "max": 120},
            {"name": "consent", "label": "Consent", "type": "choice", "required": True, "choices": {"1": "Yes", "0": "No"}},
            {"name": "symptom_score", "label": "Symptom score", "type": "integer", "required": True, "min": 0, "max": 10},
            {"name": "notes", "label": "Notes", "type": "text", "required": False},
        ])

    def request(self, method, path, body=None, headers=None, authenticated=True):
        defaults = {"Host": f"127.0.0.1:{self.port}"}
        if authenticated:
            defaults.update({"Cookie": f"formbridge_session={self.httpd.session}", "X-CSRF-Token": self.httpd.csrf})
        payload = None
        if body is not None:
            payload = body if isinstance(body, bytes) else json.dumps(body).encode()
            defaults["Content-Type"] = "application/json"
        defaults.update(headers or {})
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            connection.request(method, path, body=payload, headers=defaults)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def post(self, path, body, expected=200):
        status, _, raw = self.request("POST", path, body)
        self.assertEqual(status, expected, raw)
        return json.loads(raw)

    def state(self):
        status, _, raw = self.request("GET", "/api/state")
        self.assertEqual(status, 200, raw)
        return json.loads(raw)

    def sample(self, name="friendly"):
        return self.post("/api/template/sample", {"name": name})

    def upload(self, identifier="000007", notes=""):
        state = self.post("/api/upload", {"filename": f"fictional-{identifier}.txt", "data": base64.b64encode(fictional_source(identifier, notes)).decode()})
        record = state["records"][-1]
        self.assertEqual(record["values"], {**VALUES, "record_id": identifier, "notes": notes})
        return record

    def review(self, record, values=None, approve=True, expected=200):
        return self.post("/api/record", {
            "id": record["id"], "values": values or record["values"],
            "confirmed": RAW_HEADERS, "reviewer": "Fictional Reviewer", "approve": approve,
            "expectedRevision": record["revision"],
        }, expected)

    def mapping(self, mappings=None, confirmed=True, expected=200, revision=None):
        template = self.state()["template"]
        return self.post("/api/template/mapping", {
            "mappings": FRIENDLY_MAPPING if mappings is None else mappings, "confirmed": confirmed,
            "expectedRevision": template["revision"] if revision is None else revision,
        }, expected)

    def export(self, export_format="csv"):
        template = self.state()["template"]
        revision = f"&expectedRevision={template['revision']}" if template else ""
        return self.request("GET", f"/api/template/export?format={export_format}{revision}")

    def csv_rows(self):
        status, headers, raw = self.export()
        self.assertEqual(status, 200, raw)
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
        self.assertIn("text/csv", headers["Content-Type"])
        return list(csv.reader(io.StringIO(raw.decode("utf-8-sig"))))

    def test_authored_samples_are_blank_and_load_without_automatic_mapping(self):
        manifest = json.loads((APP / "spreadsheets/template-manifest.json").read_text())
        status, _, raw = self.request("GET", "/api/templates/samples")
        self.assertEqual(status, 200)
        self.assertEqual([item["name"] for item in json.loads(raw)], ["redcap", "friendly", "csv"])
        for name, headers in (("redcap", RAW_HEADERS), ("friendly", FRIENDLY_HEADERS), ("csv", RAW_HEADERS)):
            with self.subTest(name=name):
                expected = manifest[name]
                state = self.sample(name)
                template = state["template"]
                self.assertEqual([column["name"] for column in template["columns"]], headers)
                self.assertEqual(template["sheet"], expected["sheet"])
                self.assertEqual(template["headerRow"], expected["headerRow"])
                self.assertEqual(template["mappings"], {})
                self.assertFalse(template["confirmed"])
                self.assertFalse(state["templatePreview"]["ready"])
                self.assertNotIn("sourceData", template)
                original = self.request("GET", "/api/template/original")
                self.assertEqual(original[0], 200)
                self.assertEqual(original[2], (APP / "spreadsheets" / expected["filename"]).read_bytes())
                if name != "csv":
                    book = openpyxl.load_workbook(io.BytesIO(original[2]))
                    try:
                        sheet = book[expected["sheet"]]
                        self.assertEqual([sheet.cell(expected["headerRow"], column).value for column in range(1, 7)], headers)
                        self.assertTrue(all(cell.value is None for row in sheet.iter_rows(min_row=expected["headerRow"] + 1) for cell in row))
                    finally:
                        book.close()

    def test_txt_review_friendly_export_reopens_with_exact_values_and_types(self):
        record = self.upload()
        self.review(record)
        self.sample()
        state = self.mapping()
        self.assertTrue(state["templatePreview"]["ready"])
        self.assertEqual(state["templatePreview"]["identifierColumn"], "Participant ID")
        self.assertEqual(self.csv_rows(), [FRIENDLY_HEADERS, ["000007", "34", "0", "2026-10-25", "0", ""]])
        status, headers, raw = self.export("xlsx")
        self.assertEqual(status, 200, raw)
        self.assertIn("spreadsheetml.sheet", headers["Content-Type"])
        self.assertIn("mapped-reviewed.xlsx", headers["Content-Disposition"])
        book = openpyxl.load_workbook(io.BytesIO(raw), data_only=False)
        try:
            self.assertEqual(book.sheetnames, ["Intake"])
            sheet = book["Intake"]
            self.assertEqual([sheet.cell(3, col).value for col in range(1, 7)], FRIENDLY_HEADERS)
            self.assertEqual([sheet.cell(4, col).value for col in range(1, 7)], ["000007", 34, "0", "2026-10-25", 0, None])
            self.assertEqual([sheet.cell(4, col).data_type for col in range(1, 6)], ["s", "n", "s", "s", "n"])
            self.assertEqual(sheet["A1"].value, "Fictional research intake")
            self.assertEqual(sheet.freeze_panes, "A4")
            self.assertTrue(sheet["A3"].font.bold)
            self.assertTrue(all(cell.value is None for row in sheet.iter_rows(min_row=5) for cell in row))
        finally:
            book.close()

    def test_uploaded_authored_xlsx_respects_explicit_sheet_and_header(self):
        source = (APP / "spreadsheets/friendly-template.xlsx").read_bytes()
        state = self.post("/api/template/import", {
            "filename": "C:\\fictional\\practice.xlsx", "data": base64.b64encode(source).decode(),
            "sheet": "Intake", "headerRow": 3,
        })
        template = state["template"]
        self.assertEqual(template["name"], "practice.xlsx")
        self.assertEqual((template["sheet"], template["headerRow"]), ("Intake", 3))
        self.assertEqual([column["name"] for column in template["columns"]], FRIENDLY_HEADERS)
        self.assertEqual(template["mappings"], {})
        self.assertFalse(template["confirmed"])
        self.assertEqual(self.request("GET", "/api/template/original")[2], source)

    def test_generated_pdf_extracts_then_exports_literal_expected_record(self):
        self.httpd.workspace.schema = server.parse_schema(json.loads((APP / "samples/sample-schema.json").read_text()))
        raw_pdf = (APP / "samples/practice-01-text.pdf").read_bytes()
        state = self.post("/api/upload", {"filename": "practice-01-text.pdf", "data": base64.b64encode(raw_pdf).decode()})
        record = state["records"][0]
        self.assertEqual(record["values"], {"record_id": "DEMO-001", "visit_date": "2026-01-12", "age": "34", "consent": "1", "symptom_score": "3", "notes": "Practice entry alpha. No follow-up requested."})
        self.assertEqual(record["status"], "review")
        self.review(record)
        self.sample("redcap")
        self.mapping(RAW_MAPPING)
        self.assertEqual(self.csv_rows(), [RAW_HEADERS, ["DEMO-001", "2026-01-12", "34", "1", "3", "Practice entry alpha. No follow-up requested."]])

    def test_preview_includes_drafts_but_export_contains_only_approved_records(self):
        approved = self.upload()
        self.review(approved)
        draft = self.upload("000008", "Fictional unapproved draft.")
        self.sample()
        state = self.mapping()
        preview = state["templatePreview"]
        self.assertEqual(preview["approvedCount"], 1)
        self.assertTrue(preview["ready"])
        self.assertEqual([(row["recordId"], row["status"]) for row in preview["rows"]], [("000007", "approved"), ("000008", "review")])
        self.assertEqual(preview["rows"][1]["id"], draft["id"])
        self.assertEqual(preview["rows"][1]["values"]["Research notes"], "Fictional unapproved draft.")
        self.assertEqual(self.csv_rows(), [FRIENDLY_HEADERS, ["000007", "34", "0", "2026-10-25", "0", ""]])

    def test_missing_or_unconfirmed_mapping_blocks_export(self):
        self.review(self.upload())
        self.sample()
        self.assertEqual(self.export()[0], 400)
        state = self.mapping(confirmed=False)
        self.assertEqual(state["template"]["mappings"], FRIENDLY_MAPPING)
        self.assertFalse(state["template"]["confirmed"])
        self.assertEqual(self.export("xlsx")[0], 400)

    def test_invalid_confirmed_mappings_are_rejected_atomically(self):
        self.sample()
        before = self.state()["template"]
        cases = [
            {**FRIENDLY_MAPPING, "Research notes": "age"},
            {**FRIENDLY_MAPPING, "Participant ID": None},
            {key: value for key, value in FRIENDLY_MAPPING.items() if key != "Score"},
            {**FRIENDLY_MAPPING, "Score": "unknown_source"},
            {**FRIENDLY_MAPPING, "Unknown column": None},
        ]
        for mapping in cases:
            with self.subTest(mapping=mapping):
                self.mapping(mapping, expected=400)
                self.assertEqual(self.state()["template"], before)

    def test_explicit_blank_column_is_valid_and_discards_no_source_value(self):
        self.review(self.upload(notes="Fictional source note kept in the project."))
        self.sample()
        state = self.mapping({**FRIENDLY_MAPPING, "Research notes": None})
        self.assertTrue(state["templatePreview"]["ready"])
        self.assertEqual(state["records"][0]["values"]["notes"], "Fictional source note kept in the project.")
        self.assertEqual(self.csv_rows(), [FRIENDLY_HEADERS, ["000007", "34", "0", "2026-10-25", "0", ""]])

    def test_invalid_draft_mapping_explains_duplicate_assignment_and_missing_identifier(self):
        self.sample()
        state = self.mapping({**FRIENDLY_MAPPING, "Participant ID": "age"}, confirmed=False)
        errors = " ".join(state["templatePreview"]["errors"])
        self.assertIn("more than one destination", errors)
        self.assertIn("record identifier", errors)
        self.assertIsNone(state["templatePreview"]["identifierColumn"])
        self.assertFalse(state["templatePreview"]["ready"])

    def test_mapping_revision_must_be_current_integer_and_present(self):
        initial = self.sample()["template"]["revision"]
        saved = self.mapping()["template"]
        for revision in (initial, True, "1", None):
            with self.subTest(revision=revision):
                body = {"mappings": FRIENDLY_MAPPING, "confirmed": False}
                if revision is not None:
                    body["expectedRevision"] = revision
                self.post("/api/template/mapping", body, 409)
                self.assertEqual(self.state()["template"], saved)

    def test_record_missing_or_stale_revision_cannot_overwrite_approval(self):
        initial = self.upload()
        approved = self.review(initial)["records"][0]
        for revision in (None, initial["revision"], True):
            with self.subTest(revision=revision):
                body = {"id": initial["id"], "values": {**VALUES, "notes": "Stale fictional edit."}, "confirmed": [], "approve": False}
                if revision is not None:
                    body["expectedRevision"] = revision
                self.post("/api/record", body, 409)
                self.assertEqual(self.state()["records"][0], approved)

    def test_export_rejects_missing_or_stale_mapping_revision(self):
        self.review(self.upload())
        self.sample()
        previous = self.mapping()["template"]["revision"]
        current = self.mapping()["template"]["revision"]
        self.assertGreater(current, previous)
        for query in ("", f"&expectedRevision={previous}", "&expectedRevision=invalid"):
            with self.subTest(query=query):
                self.assertEqual(self.request("GET", f"/api/template/export?format=csv{query}")[0], 409)
        self.assertEqual(self.csv_rows(), [FRIENDLY_HEADERS, ["000007", "34", "0", "2026-10-25", "0", ""]])

    def test_bad_template_import_is_atomic_for_mapping_sources_and_approval(self):
        self.review(self.upload())
        self.sample()
        self.mapping()
        before = self.state()
        original = self.request("GET", "/api/template/original")[2]
        for body in (
            {"filename": "broken.xlsx", "data": base64.b64encode(b"Not an XLSX package").decode()},
            {"filename": "broken.xlsx", "data": "not base64!"},
            {"filename": "friendly.xlsx", "data": base64.b64encode(original).decode(), "sheet": "Missing worksheet"},
            {"filename": "friendly.xlsx", "data": base64.b64encode(original).decode(), "headerRow": 500},
        ):
            with self.subTest(body={key: value for key, value in body.items() if key != "data"}):
                self.post("/api/template/import", body, 400)
                after = self.state()
                self.assertEqual(after["template"], before["template"])
                self.assertEqual(after["records"], before["records"])
                self.assertEqual(self.request("GET", "/api/template/original")[2], original)

    def test_explicit_worksheet_configuration_clears_mapping_and_keeps_original(self):
        template = self.sample()["template"]
        saved = self.mapping()["template"]
        original = self.request("GET", "/api/template/original")[2]
        self.post("/api/template/configure", {"sheet": "Intake", "headerRow": 3}, 409)
        self.assertEqual(self.state()["template"], saved)
        state = self.post("/api/template/configure", {"sheet": "Intake", "headerRow": 3, "expectedRevision": saved["revision"]})
        changed = state["template"]
        self.assertGreater(changed["revision"], saved["revision"])
        self.assertEqual((changed["sheet"], changed["headerRow"]), ("Intake", 3))
        self.assertEqual(changed["mappings"], {})
        self.assertFalse(changed["confirmed"])
        self.assertEqual(self.request("GET", "/api/template/original")[2], original)
        self.post("/api/template/configure", {"sheet": "Intake", "headerRow": 3, "expectedRevision": template["revision"]}, 409)
        self.assertEqual(self.state()["template"], changed)

    def test_schema_edit_invalidates_mapping_confirmation_and_record_approval(self):
        self.review(self.upload())
        self.sample()
        before = self.mapping()
        fields = copy.deepcopy(before["schema"])
        fields[-1]["aliases"] = ["Fictional comments"]
        state = self.post("/api/schema", {"schema": fields})
        self.assertFalse(state["template"]["confirmed"])
        self.assertGreater(state["template"]["revision"], before["template"]["revision"])
        self.assertEqual(state["template"]["mappings"], FRIENDLY_MAPPING)
        self.assertEqual(state["records"][0]["status"], "review")
        self.assertEqual(state["records"][0]["confirmed"], [])
        self.assertNotEqual(state["records"][0]["id"], before["records"][0]["id"])
        self.assertEqual(self.export()[0], 400)

    def test_project_roundtrip_preserves_sources_values_and_associations_but_resets_gates(self):
        self.review(self.upload())
        self.sample()
        self.mapping()
        original_template = self.request("GET", "/api/template/original")[2]
        status, _, raw = self.request("GET", "/api/project")
        self.assertEqual(status, 200, raw)
        project = json.loads(raw)
        self.assertEqual(base64.b64decode(project["template"]["sourceData"]), original_template)
        self.assertEqual(project["template"]["mappings"], FRIENDLY_MAPPING)
        self.assertEqual(base64.b64decode(project["records"][0]["sourceData"]), fictional_source())
        self.assertNotIn("confirmed", project["template"])
        self.assertNotIn("status", project["records"][0])
        self.post("/api/reset", {})
        state = self.post("/api/project", project)
        self.assertEqual(state["template"]["mappings"], FRIENDLY_MAPPING)
        self.assertFalse(state["template"]["confirmed"])
        self.assertEqual(state["records"][0]["values"], VALUES)
        self.assertEqual(state["records"][0]["status"], "review")
        self.assertEqual(state["records"][0]["confirmed"], [])
        self.assertEqual(state["records"][0]["reviewedBy"], "")
        self.assertEqual(self.request("GET", "/api/template/original")[2], original_template)
        self.assertEqual(self.request("GET", f"/api/source/{state['records'][0]['id']}")[2], fictional_source())
        self.assertEqual(self.export()[0], 400)
        self.review(state["records"][0])
        self.assertEqual(self.export()[0], 400)
        self.mapping()
        self.assertEqual(self.csv_rows(), [FRIENDLY_HEADERS, ["000007", "34", "0", "2026-10-25", "0", ""]])

    def test_project_with_bad_template_is_atomic_even_after_staging_records(self):
        self.review(self.upload())
        self.sample()
        before = self.mapping()
        project = json.loads(self.request("GET", "/api/project")[2])
        project["template"]["sourceData"] = base64.b64encode(b"Not a workbook").decode()
        assets_before = {path.name for path in Path(self.assets.name).iterdir()}
        self.post("/api/project", project, 400)
        after = self.state()
        self.assertEqual(after["records"], before["records"])
        self.assertEqual(after["template"], before["template"])
        self.assertEqual({path.name for path in Path(self.assets.name).iterdir()}, assets_before)

    def test_template_routes_require_session_and_mutations_require_csrf(self):
        self.sample()
        before = self.state()["template"]
        for path in ("/api/templates/samples", "/api/template/original", "/api/template/export?format=csv"):
            with self.subTest(path=path):
                self.assertEqual(self.request("GET", path, authenticated=False)[0], 403)
        for path, body in (("/api/template/sample", {"name": "csv"}), ("/api/template/clear", {}), ("/api/template/mapping", {"mappings": FRIENDLY_MAPPING, "confirmed": True, "expectedRevision": before["revision"]})):
            with self.subTest(path=path):
                self.assertEqual(self.request("POST", path, body, headers={"X-CSRF-Token": "wrong"})[0], 403)
                self.assertEqual(self.state()["template"], before)

    def test_duplicate_json_keys_and_nonfinite_constants_are_rejected_before_mutation(self):
        for raw in (
            b'{"name":"csv","name":"redcap"}',
            b'{"name":"csv","extra":{"field":1,"field":2}}',
            b'{"name":"csv","extra":NaN}',
            b'{"name":"csv","extra":Infinity}',
            b'{"name":"csv","extra":-Infinity}',
        ):
            with self.subTest(raw=raw):
                self.post("/api/template/sample", raw, 400)
                self.assertIsNone(self.state()["template"])

    def test_transfer_encoding_and_duplicate_content_length_are_rejected(self):
        self.assertEqual(self.request("POST", "/api/template/sample", {"name": "csv"}, headers={"Transfer-Encoding": "chunked"})[0], 400)
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            connection.putrequest("POST", "/api/template/sample", skip_host=True)
            connection.putheader("Host", f"127.0.0.1:{self.port}")
            connection.putheader("Cookie", f"formbridge_session={self.httpd.session}")
            connection.putheader("X-CSRF-Token", self.httpd.csrf)
            connection.putheader("Content-Type", "application/json")
            connection.putheader("Content-Length", "14")
            connection.putheader("Content-Length", "14")
            connection.endheaders(b'{"name":"csv"}')
            response = connection.getresponse()
            self.assertEqual(response.status, 400, response.read())
        finally:
            connection.close()
        self.assertIsNone(self.state()["template"])

    def test_clearing_template_disables_template_export_and_retains_record(self):
        self.review(self.upload())
        self.sample()
        template = self.mapping()["template"]
        for body in ({}, {"expectedRevision": template["revision"] - 1}):
            self.post("/api/template/clear", body, 409)
            self.assertEqual(self.state()["template"], template)
        state = self.post("/api/template/clear", {"expectedRevision": template["revision"]})
        self.assertIsNone(state["template"])
        self.assertIsNone(state["templatePreview"])
        self.assertEqual(state["records"][0]["status"], "approved")
        self.assertEqual(self.export()[0], 400)
        self.assertEqual(self.request("GET", "/api/template/original")[0], 400)


if __name__ == "__main__":
    unittest.main()
