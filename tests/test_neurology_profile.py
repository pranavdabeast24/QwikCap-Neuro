"""Profile extraction and approval boundaries with entirely fictional sources.

The independent authorized-train verifier checks every pilot value separately;
these tests target the safety gates and source ambiguities.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
from desktop_model import DesktopSession
from neurology_profile import (PROFILE, applicable_fields, extract, is_profile,
                               profile_schema, validate_profile_values)
from pipeline import process_document
from server import InputError, parse_schema, validate_values


def intake(name="Example Person", mrn="EX-001", dob="02/03/1980", extra=""):
    return (f"Form NEU-101\nPatient Name {name} DOB {dob} MRN {mrn} Date 04/05/2026\n"
            "Chief complaint — describe in your own words:\n"
            "Tingling in left hand.\nOccurs every morning.\nCurrent symptoms (check all that apply):\n"
            "CURRENT MEDICATIONS (INCLUDE OTC & SUPPLEMENTS)\n# Medication Dose Frequency\n"
            "1 Example medicine 20 mg Daily\n2\nALLERGIES\n"
            "No known drug allergies (NKDA) Allergies & reaction Example drug (rash)\n"
            "FAMILY HISTORY\n" + extra).encode()


def line(text, x, y, width=.1):
    words = [{"text": text, "x": x, "y": y, "width": width, "height": .01}]
    return {"text": text, "words": words, "x": x, "y": y, "width": width, "height": .01}


class NeurologyProfileTests(unittest.TestCase):
    def setUp(self):
        self.session = DesktopSession()
        self.addCleanup(self.session.close)
        self.session.use_neurology_profile()

    def add(self, **kwargs):
        return self.session.add_document(intake(**kwargs), "fictional.txt")

    def approve(self, record):
        return self.session.review_record(record["id"], record["values"], record["applicableFields"], "Synthetic reviewer", True)

    def test_explicit_profile_schema_marker_roundtrip_and_unknown_rejected(self):
        self.assertTrue(is_profile(parse_schema(json.loads(json.dumps(profile_schema())))))
        unknown = profile_schema()
        unknown[0]["profile"] = "unapproved-profile"
        with self.assertRaisesRegex(InputError, "Only the built-in"):
            parse_schema(unknown)
        incomplete = profile_schema()[:-1]
        with self.assertRaisesRegex(InputError, "complete canonical"):
            parse_schema(incomplete)
        weakened = profile_schema()
        weakened[1]["required"] = False
        self.assertTrue(parse_schema(weakened)[1]["required"])
        weakened[5]["choices"] = {"unclassified": "No classification"}
        self.assertEqual(parse_schema(weakened)[5]["choices"], profile_schema()[5]["choices"])

    def test_literal_headers_medications_and_evidence_without_inactive_values(self):
        data = intake()
        record = self.session.add_document(data, "fictional.txt")
        values = record["values"]
        self.assertEqual(values["document_id"], "DOC" + hashlib.sha256(data).hexdigest()[:24])
        self.assertEqual(values["patient_name"], "Example Person")
        self.assertEqual(values["patient_dob"], "1980-02-03")
        self.assertEqual(values["form_date"], "2026-04-05")
        self.assertEqual(values["intake_chief_complaint"], "Tingling in left hand. Occurs every morning.")
        self.assertEqual(values["intake_medications"], "Example medicine 20 mg Daily")
        self.assertEqual(values["intake_allergies"], "Example drug (rash)")
        self.assertEqual(len(record["applicableFields"]), 9)
        self.assertFalse(record["validationErrors"])
        self.assertTrue(all(not value for name, value in values.items() if name not in record["applicableFields"]))
        for name in record["applicableFields"]:
            if name == "document_id":
                continue
            proof = record["evidence"][name]
            self.assertEqual(proof["page"], 1)
            self.assertEqual(proof["method"], "plain-text")
            self.assertGreater(proof["region"]["width"], 0)
        json.dumps(record)  # Evidence occurrence lists must be serializable.

    def test_only_applicable_fields_need_confirmation_and_inactive_cannot_gain_values(self):
        record = self.add()
        record = self.approve(record)
        self.assertEqual(set(record["confirmed"]), set(record["applicableFields"]))
        csv_data = self.session.export("csv", mapped=False)
        row = list(csv.DictReader(io.StringIO(csv_data.decode("utf-8-sig"))))[0]
        self.assertEqual(row["patient_mrn"], "EX-001")
        self.assertEqual(row["hit6_total"], "")
        values = {**record["values"], "hit6_total": "36"}
        record = self.session.review_record(record["id"], values, [], "Synthetic reviewer")
        self.assertIn("hit6_total", record["validationErrors"])
        with self.assertRaises(InputError):
            self.approve(record)

    def test_missing_and_malformed_mrn_block_approval(self):
        for mrn in ("", "_INVALID"):
            with self.subTest(mrn=mrn):
                record = self.add(mrn=mrn)
                self.assertIn("patient_mrn", record["validationErrors"])
                with self.assertRaises(InputError):
                    self.approve(record)

    def test_mrn_group_identity_conflict_blocks_approval_and_export(self):
        first = self.add()
        self.approve(first)
        second = self.add(name="Different Example")
        state = self.session.snapshot()
        self.assertEqual(len(state["patientGroups"]), 1)
        self.assertTrue(state["patientGroups"][0]["conflict"])
        self.assertTrue(all(r["groupConflict"] for r in state["records"]))
        with self.assertRaisesRegex(InputError, "conflicting patient"):
            self.approve(second)
        with self.assertRaisesRegex(InputError, "Conflicting patient"):
            self.session.export("csv", mapped=False)

    def test_repeated_source_headers_conflict_even_after_manually_chosen_identity(self):
        record = self.add(extra="Patient Name Another Person DOB 02/03/1980 MRN EX-001\n")
        self.assertEqual(record["values"]["patient_name"], "")
        self.assertTrue(record["profileBlockingIssues"])
        corrected = {**record["values"], "patient_name": "Example Person"}
        record = self.session.review_record(record["id"], corrected, [], "Synthetic reviewer")
        with self.assertRaisesRegex(InputError, "within this source"):
            self.approve(record)

    def test_repeated_birth_date_and_mrn_disagreement_are_blocking_source_issues(self):
        for repeat in ("Patient Name Example Person DOB 02/04/1980 MRN EX-001\n",
                       "Patient Name Example Person DOB 02/03/1980 MRN EX-999\n",
                       "Patient Name Example Person DOB 02/30/1980 MRN EX-001\n"):
            with self.subTest(header=repeat):
                record = self.add(extra=repeat)
                self.assertTrue(record["profileBlockingIssues"])
                with self.assertRaises(InputError):
                    self.approve(record)

    def test_duplicate_source_does_not_create_second_document(self):
        record = self.add()
        with self.assertRaisesRegex(InputError, "exact source"):
            self.session.add_document(intake(), "different-filename.txt")
        self.assertEqual(len(self.session.workspace.records), 1)
        self.assertEqual(self.session.workspace.records[0]["id"], record["id"])

    def test_distinct_source_visits_keep_separate_document_rows(self):
        one = self.add()
        two = self.add(extra="Visit annotation: second source\n")
        self.assertNotEqual(one["values"]["document_id"], two["values"]["document_id"])
        self.approve(one)
        self.approve(two)
        self.assertEqual(len(self.session.workspace.approved_records()), 2)
        self.assertEqual(len(self.session.snapshot()["patientGroups"]), 1)

    def test_hash_bound_identifier_and_source_family_cannot_be_changed(self):
        record = self.add()
        edited = {**record["values"], "document_id": "DOC" + "0" * 24}
        record = self.session.review_record(record["id"], edited, [], "Synthetic reviewer")
        self.assertIn("document_id", record["validationErrors"])
        edited = {**record["values"], "instrument_family": "hit6"}
        record = self.session.review_record(record["id"], edited, [], "Synthetic reviewer")
        self.assertIn("instrument_family", record["validationErrors"])
        with self.assertRaises(InputError):
            self.approve(record)

    def test_unknown_form_stays_unclassified(self):
        record = self.session.add_document(intake().replace(b"NEU-101", b"NEU-999"), "unknown.txt")
        self.assertEqual(record["values"]["instrument_family"], "")
        self.assertEqual(set(record["applicableFields"]), {"document_id", "patient_mrn", "patient_name", "patient_dob", "form_date", "instrument_family"})
        self.assertIn("instrument_family", record["validationErrors"])
        with self.assertRaises(InputError):
            self.approve(record)

    def test_source_date_discrepancy_preserved_and_exam_calendar_validated(self):
        data = b"Form NEU-330\nPatient Name Example Person DOB 02/03/1980 MRN EX-001 Date 04/08/2026\nNIHSS exam time 04/09/2026 04:25 CT/CTA time 04/09/2026 04:32\n"
        with tempfile.TemporaryDirectory() as folder:
            record = process_document(data, "dates.txt", profile_schema(), Path(folder), "date-risk")
        self.assertEqual(record["values"]["form_date"], "2026-04-08")
        self.assertEqual(record["values"]["nihss_exam_datetime"], "2026-04-09 04:25")
        self.assertTrue(any("Both source dates are preserved" in issue for issue in record["issues"]))
        errors = validate_profile_values(profile_schema(), {**record["values"], "nihss_exam_datetime": "2026-02-30 25:99"})
        self.assertIn("nihss_exam_datetime", errors)

    def test_checkbox_points_follow_printed_columns_and_ambiguous_row_stays_blank(self):
        points = line("Points per response 6 8 10 11 13", .4, .6)
        points["words"] = [line(str(value), x, .6, .01)["words"][0] for x, value in zip((.65, .71, .77, .83, .89), (6, 8, 10, 11, 13))]
        lines = [line("Form NEU-210", .8, .05), points,
                 line("1 First question", .07, .3), line("✓", .83, .3, .01),
                 line("2 Second question", .07, .4), line("✗", .71, .4, .01), line("X", .89, .4, .01)]
        values, proof, issues = extract([{"page": 1, "method": "pdf-text", "lines": lines}], "a" * 64)
        self.assertEqual(values["hit6_q1"], "11")
        self.assertEqual(values["hit6_q2"], "")
        self.assertEqual(proof["hit6_q1"]["region"]["x"], .83)
        self.assertTrue(any("hit6_q2:" in issue for issue in issues))

    def test_generic_confirmation_and_schema_behavior_unchanged(self):
        generic = parse_schema([{"name": "record_id", "type": "text", "required": True}, {"name": "unused", "type": "text"}])
        self.assertEqual(applicable_fields(generic, {"record_id": "EX-001", "unused": ""}), {"record_id", "unused"})
        self.assertEqual(validate_values(generic, {"record_id": "EX-001", "unused": ""}), {})
        self.assertFalse(is_profile(generic))

    def test_project_reopen_preserves_opt_in_and_requires_fresh_identity_confirmation(self):
        record = self.add()
        self.approve(record)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "synthetic-project.json"
            self.session.save_project(path)
            self.session.open_project(path)
        state = self.session.snapshot()
        self.assertEqual(state["profile"], PROFILE)
        self.assertEqual(state["records"][0]["values"], record["values"])
        self.assertFalse(state["patientGroups"][0]["identityConfirmed"])
        self.assertEqual(state["records"][0]["confirmed"], [])

    def test_profile_columns_template_supports_real_csv_and_xlsx_exports(self):
        import openpyxl
        record = self.add()
        self.approve(record)
        self.session.use_categories_as_columns()
        mappings = {f["name"]: f["name"] for f in self.session.workspace.schema}
        self.session.set_mapping(mappings, True)
        revision = self.session.workspace.template["revision"]
        csv_rows = list(csv.DictReader(io.StringIO(self.session.export("csv", expected_revision=revision).decode("utf-8-sig"))))
        self.assertEqual(csv_rows[0], record["values"])
        book = openpyxl.load_workbook(io.BytesIO(self.session.export("xlsx", expected_revision=revision)))
        try:
            sheet = book.active
            self.assertEqual(sheet.cell(2, 2).value, "EX-001")
            self.assertEqual(sheet.cell(2, 9).value, "Example medicine 20 mg Daily")
            self.assertEqual(sheet.max_row, 2)
        finally:
            book.close()

    def test_generic_columns_template_also_supports_csv_and_xlsx(self):
        import openpyxl
        self.session.set_schema([{"name": "record_id", "label": "Record ID", "type": "text", "required": True}, {"name": "score", "label": "Score", "type": "integer", "required": True}])
        record = self.session.add_document(b"Record ID: EX-002\nScore: 7", "generic.txt")
        self.session.review_record(record["id"], record["values"], list(record["values"]), "Synthetic reviewer", True)
        self.session.use_categories_as_columns()
        self.session.set_mapping({"record_id": "record_id", "score": "score"}, True)
        revision = self.session.workspace.template["revision"]
        rows = list(csv.reader(io.StringIO(self.session.export("csv", expected_revision=revision).decode("utf-8-sig"))))
        self.assertEqual(rows, [["record_id", "score"], ["EX-002", "7"]])
        book = openpyxl.load_workbook(io.BytesIO(self.session.export("xlsx", expected_revision=revision)))
        try:
            self.assertEqual(list(book.active.values), [("record_id", "score"), ("EX-002", 7)])
        finally:
            book.close()


if __name__ == "__main__":
    unittest.main()
