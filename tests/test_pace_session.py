"""PACE review and patient bundle boundaries with fictional worker fixtures."""
from __future__ import annotations

import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import openpyxl
from pypdf import PdfReader
from reportlab.pdfgen import canvas

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
from desktop_model import DesktopSession, InputError
from extraction_profiles import applicable_fields
from pace_profile import PROFILE, profile_schema
from server import parse_schema


def fictional_pdf(record_id="S-001", first="Example", last="Person", mrn="000042", pages=1, instrument="patient_records", required_response=None):
    output = io.BytesIO()
    pdf = canvas.Canvas(output, pagesize=(612, 792), invariant=1)
    for page_index in range(pages):
        pdf.drawString(54, 730, f"Fixture identity | {record_id} | {first} | {last} | 1980-02-03 | {mrn}")
        if page_index == 0:
            pdf.drawString(54, 710, f"Fixture instrument | {instrument}")
        pdf.drawString(54, 690, "Fixture field | headaches_yn | 0")
        if required_response is not None:
            pdf.drawString(54, 670, f"Fixture required field | hit6_severity | {required_response}")
        pdf.showPage()
    pdf.save()
    return output.getvalue()


def fixture_process(workspace, data, filename, schema, rid):
    folder = workspace.assets / rid
    folder.mkdir()
    reader = PdfReader(io.BytesIO(data))
    identities, instruments, instrument_starts = [], set(), []
    required_fields, evidence, unanswered = {}, {}, []
    for page_number, page in enumerate(reader.pages, 1):
        for line in page.extract_text().splitlines():
            parts = [part.strip() for part in line.split("|")]
            if parts[0] == "Fixture identity":
                identities.append(dict(zip(("recordId", "firstName", "lastName", "dob", "mrn"), parts[1:]), page=page_number))
            elif parts[0] == "Fixture instrument" and parts[1] != "unknown":
                instruments.add(parts[1])
                instrument_starts.append({"instrument": parts[1], "page": page_number})
            elif parts[0] == "Fixture required field":
                required_fields[parts[1]] = parts[2]
                if not parts[2]:
                    unanswered.append(parts[1])
                    evidence[parts[1]] = {"mapping": "pace-unmarked-radio", "page": page_number,
                        "method": "pdf-text", "text": "Visible unanswered radio row", "region": {"x": .1, "y": .1, "width": .8, "height": .1}}
    ids = sorted({identity["recordId"] for identity in identities})
    values = {field["name"]: "" for field in schema}
    if len(ids) == 1:
        values["record_id"] = ids[0]
    active = ["record_id", "mrn", "patient_first", "patient_last", "patient_dob", "headaches_yn"]
    if identities:
        first_identity = identities[0]
        for name, key in (("mrn", "mrn"), ("patient_first", "firstName"), ("patient_last", "lastName"), ("patient_dob", "dob")):
            values[name] = first_identity[key]
    values["headaches_yn"] = "0"
    values.update(required_fields)
    active.extend(required_fields)
    return {"values": values, "evidence": evidence, "issues": [], "pipeline": [],
            "pages": [{"page": number, "width": 612, "height": 792} for number in range(1, len(reader.pages) + 1)],
            "applicableFields": active, "sourceContext": {"profile": PROFILE, "recordIds": ids,
                "identities": identities, "instruments": sorted(instruments),
                "instrumentStarts": instrument_starts, "unansweredFields": sorted(set(unanswered)), "blockingIssues": []}}


class PaceSessionTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix="quickcap-pace-session-")
        self.addCleanup(self.folder.cleanup)
        self.session = DesktopSession()
        self.addCleanup(self.session.close)
        self.session.use_pace_profile()
        processor = patch("server.Workspace.process", fixture_process)
        processor.start()
        self.addCleanup(processor.stop)

    def add(self, **kwargs):
        return self.session.add_document(fictional_pdf(**kwargs), "fictional.pdf")

    def approve(self, record):
        return self.session.review_record(record["id"], record["values"], record["applicableFields"], "Fictional reviewer", True)

    def write(self, name, **kwargs):
        path = Path(self.folder.name) / name
        path.write_bytes(fictional_pdf(**kwargs))
        return path

    def test_schema_is_canonical_and_cannot_remove_source_constraints(self):
        schema = profile_schema()
        schema[0]["required"] = False
        schema[5]["required"] = False
        schema[5]["region"] = {"page": 1, "x": 0, "y": 0, "width": 1, "height": 1}
        parsed = parse_schema(schema)
        self.assertEqual(parsed[0]["name"], "record_id")
        self.assertTrue(parsed[0]["required"])
        self.assertTrue(parsed[5]["required"])
        self.assertNotIn("region", parsed[5])
        with self.assertRaisesRegex(InputError, "complete canonical"):
            parse_schema(profile_schema()[:-1])
        altered = profile_schema()
        altered[0]["profile"] = "untrusted-profile"
        with self.assertRaisesRegex(InputError, "Only the built-in"):
            parse_schema(altered)

    def test_edits_cannot_hide_a_visible_field_or_fill_a_hidden_field(self):
        record = self.add()
        values = {**record["values"], "headaches_yn": ""}
        record = self.session.review_record(record["id"], values, record["applicableFields"], "Fictional reviewer")
        self.assertEqual(applicable_fields(self.session.workspace.schema, values, record),
                         {"record_id", "mrn", "patient_first", "patient_last", "patient_dob", "headaches_yn"})
        with self.assertRaisesRegex(InputError, "Confirm every field"):
            self.session.review_record(record["id"], values, [name for name in record["applicableFields"] if name != "headaches_yn"], "Fictional reviewer", True)
        record = self.approve(record)
        self.assertEqual(record["values"]["headaches_yn"], "")
        values = {**record["values"], "ha_prev_yn": "1"}
        record = self.session.review_record(record["id"], values, [], "Fictional reviewer")
        self.assertIn("ha_prev_yn", record["validationErrors"])
        with self.assertRaisesRegex(InputError, "Correct invalid"):
            self.approve(record)

    def test_edited_identity_and_unknown_instrument_cannot_be_approved(self):
        record = self.add()
        edited = self.session.review_record(record["id"], {**record["values"], "record_id": "S-OTHER", "mrn": "999"}, [], "Fictional reviewer")
        self.assertIn("record_id", edited["validationErrors"])
        self.assertIn("mrn", edited["validationErrors"])
        with self.assertRaises(InputError):
            self.approve(edited)
        unknown = self.add(record_id="S-002", instrument="unknown")
        self.assertIn("record_id", unknown["validationErrors"])
        with self.assertRaises(InputError):
            self.approve(unknown)

    def test_required_source_blank_needs_confirmation_again_after_reopen(self):
        record = self.add(required_response="")
        self.assertIn("hit6_severity", record["validationErrors"])
        self.assertEqual(record["sourceContext"]["unansweredFields"], ["hit6_severity"])
        with self.assertRaisesRegex(InputError, "Correct invalid or missing"):
            self.session.review_record(record["id"], record["values"], [name for name in record["applicableFields"] if name != "hit6_severity"], "Fictional reviewer", True)
        acknowledged = self.session.review_record(record["id"], record["values"], ["hit6_severity"], "Fictional reviewer")
        self.assertNotIn("hit6_severity", acknowledged["validationErrors"])
        approved = self.approve(acknowledged)
        self.assertEqual(approved["status"], "approved")
        self.assertEqual(approved["values"]["hit6_severity"], "")
        path = Path(self.folder.name) / "source-blank-project.json"
        self.session.save_project(path)
        self.session.open_project(path)
        reopened = self.session.snapshot()["records"][0]
        self.assertEqual(reopened["confirmed"], [])
        self.assertIn("hit6_severity", reopened["validationErrors"])
        with self.assertRaisesRegex(InputError, "Correct invalid or missing"):
            self.session.review_record(reopened["id"], reopened["values"], [name for name in reopened["applicableFields"] if name != "hit6_severity"], "Fictional reviewer", True)
        self.assertEqual(self.approve(reopened)["status"], "approved")

    def test_cleared_required_answer_cannot_gain_source_blank_waiver(self):
        record = self.add(required_response="6")
        changed = self.session.review_record(record["id"], {**record["values"], "hit6_severity": ""}, record["applicableFields"], "Fictional reviewer")
        self.assertEqual(changed["sourceContext"]["unansweredFields"], [])
        self.assertIn("hit6_severity", changed["validationErrors"])
        with self.assertRaisesRegex(InputError, "Correct invalid or missing"):
            self.approve(changed)

    def test_generic_required_blank_still_blocks_with_all_confirmations(self):
        self.session.set_schema([{"name": "record_id", "type": "text"}, {"name": "essential", "type": "text", "required": True}])
        output = {"values": {"record_id": "GENERIC-1", "essential": ""}, "pages": [], "evidence": {}, "issues": [], "pipeline": []}
        with patch("server.Workspace.process", return_value=output):
            record = self.session.add_document(fictional_pdf(), "generic-required.pdf")
        with self.assertRaisesRegex(InputError, "Correct invalid or missing"):
            self.session.review_record(record["id"], record["values"], ["record_id", "essential"], "Fictional reviewer", True)
        changed = self.session.review_record(record["id"], {"record_id": "GENERIC-1", "essential": "Present answer"}, [], "Fictional reviewer")
        approved = self.session.review_record(changed["id"], changed["values"], ["record_id", "essential"], "Fictional reviewer", True)
        self.assertEqual(approved["values"]["essential"], "Present answer")

    def test_switching_to_custom_fields_discards_source_profile_metadata(self):
        self.add()
        generic = {"values": {"record_id": "GENERIC-1"}, "pages": [], "evidence": {}, "issues": [], "pipeline": []}
        with patch("server.Workspace.process", return_value=generic):
            self.session.set_schema([{"name": "record_id", "type": "text"}])
        record = self.session.snapshot()["records"][0]
        self.assertIsNone(self.session.snapshot()["profile"])
        self.assertNotIn("applicableFields", record)
        self.assertNotIn("sourceContext", record)
        approved = self.session.review_record(record["id"], {"record_id": "GENERIC-1"}, ["record_id"], "Fictional reviewer", True)
        self.assertEqual(approved["status"], "approved")
        self.assertEqual(self.session.export("csv", mapped=False).decode("utf-8-sig"), "record_id\r\nGENERIC-1\r\n")

    def test_conflicting_or_missing_bundle_identity_rolls_back(self):
        first = self.write("first.pdf")
        conflict = self.write("conflict.pdf", first="Different")
        missing = self.write("missing.pdf", mrn="")
        before = self.session.snapshot()
        for paths, record_id in (([first, conflict], "S-001"), ([first, missing], "S-001"), ([first], "S-999")):
            with self.subTest(record_id=record_id, paths=paths):
                with self.assertRaisesRegex(InputError, "patient|record ID"):
                    self.session.add_patient_bundle(paths, record_id, True)
                self.assertEqual(self.session.snapshot(), before)

    def test_variable_patient_bundles_export_exact_columns_and_reopen_rechecks_sources(self):
        first = self.session.add_patient_bundle([self.write("one.pdf"), self.write("two.pdf", pages=2, instrument="hit6")], "S-001", True)
        second = self.session.add_patient_bundle([self.write("other.pdf", record_id="S-002", mrn="000043")], "S-002", True)
        self.assertEqual([len(first["pages"]), len(second["pages"])], [4, 2])
        self.approve(first)
        self.approve(second)
        self.session.use_categories_as_columns()
        self.session.set_mapping(dict(self.session.workspace.template["mappings"]), True)
        output = self.session.export("xlsx", expected_revision=self.session.workspace.template["revision"])
        workbook = openpyxl.load_workbook(io.BytesIO(output), data_only=False)
        try:
            rows = list(workbook.active.values)
            headers = rows[0]
            self.assertEqual(len(headers), 512)
            self.assertEqual(headers[:6], ("record_id", "redcap_repeat_instrument", "redcap_repeat_instance", "redcap_data_access_group", "pt_email", "mrn"))
            self.assertEqual([(row[0], row[5]) for row in rows[1:]], [("S-001", "000042"), ("S-002", "000043")])
            self.assertEqual([row[headers.index("headaches_yn")] for row in rows[1:]], ["0", "0"])
            self.assertEqual([row[headers.index("ha_prev_yn")] for row in rows[1:]], [None, None])
        finally:
            workbook.close()
        project = json.loads(self.session.project_bytes())
        project["records"][0]["applicableFields"] = ["record_id"]
        project["records"][0]["sourceContext"] = {"profile": "forged"}
        path = Path(self.folder.name) / "fictional-project.json"
        path.write_text(json.dumps(project))
        self.session.open_project(path)
        reopened = self.session.snapshot()
        self.assertEqual(reopened["profile"], PROFILE)
        self.assertEqual([record["status"] for record in reopened["records"]], ["review", "review"])
        self.assertEqual(reopened["records"][0]["sourceContext"]["recordIds"], ["S-001"])
        self.assertIn("headaches_yn", reopened["records"][0]["applicableFields"])
        self.assertEqual(reopened["records"][0]["confirmed"], [])
        self.assertFalse(reopened["template"]["confirmed"])

    def test_unknown_source_and_repeated_complete_instrument_cannot_merge(self):
        first = self.write("first.pdf")
        repeated = self.write("same-assessment.pdf", pages=2)
        unknown = self.write("unknown-assessment.pdf", instrument="unknown")
        before = self.session.snapshot()
        for second, message in ((repeated, "Repeated instrument"), (unknown, "recognized instrument header")):
            with self.subTest(second=second):
                with self.assertRaisesRegex(InputError, message):
                    self.session.add_patient_bundle([first, second], "S-001", True)
                self.assertEqual(self.session.snapshot(), before)
        def conflicting_answers(workspace, *args):
            result = fixture_process(workspace, *args)
            result["sourceContext"]["blockingIssues"].append("Conflicting source answers cannot be combined.")
            return result
        different = self.write("different-assessment.pdf", instrument="hit6")
        with patch("server.Workspace.process", conflicting_answers):
            with self.assertRaisesRegex(InputError, "Conflicting source answers"):
                self.session.add_patient_bundle([first, different], "S-001", True)
        self.assertEqual(self.session.snapshot(), before)
        accepted = self.session.add_patient_bundle([first, different], "S-001", True)
        self.assertEqual(accepted["sourceContext"]["instrumentStarts"], [
            {"instrument": "patient_records", "page": 2}, {"instrument": "hit6", "page": 3}])


if __name__ == "__main__":
    unittest.main()
