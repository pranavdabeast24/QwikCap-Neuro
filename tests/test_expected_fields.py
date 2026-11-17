"""Expected destinations remain independent from selected, masked rules."""
from __future__ import annotations

import copy
import csv
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

import openpyxl
from reportlab.pdfgen import canvas

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

from desktop_model import DesktopSession, InputError, ConflictError
from field_catalog import CatalogError, load_catalog, parse_catalog
from form_types import compile_draft, new_draft, validate_draft
from limits import MAX_COLUMNS, MAX_FIELDS, MAX_SCHEMA_BYTES
from pipeline import DocumentError, _validate_value, process_document
from server import parse_schema, validate_values
import templates


def xlsx_headers(count):
    book = openpyxl.Workbook()
    try:
        book.active.append([f"field_{n}" for n in range(count)])
        output = io.BytesIO()
        book.save(output)
        return output.getvalue()
    finally:
        book.close()


def fictional_pdf():
    output = io.BytesIO()
    page = canvas.Canvas(output, pagesize=(612, 792))
    page.drawString(72, 750, "FICTIONAL-PACE-01")
    page.drawString(72, 690, "02/29/2000")
    page.save()
    return output.getvalue()


class SharedBoundTests(unittest.TestCase):
    def test_exact_600_fields_and_columns_across_boundaries(self):
        self.assertEqual((MAX_FIELDS, MAX_COLUMNS, MAX_SCHEMA_BYTES), (600, 600, 1048576))
        rules = [{"name": f"field_{n}", "type": "text"} for n in range(600)]
        fields = parse_schema(rules)
        draft = new_draft(pages=[{"page": 1, "aspectRatio": 612 / 792}])
        draft.update(name="Fictional large type", identifierField="key0", fields=[
            {"id": f"key{n}", **field, "region": {"page": 1, "x": .1, "y": .1, "width": .1, "height": .1}}
            for n, field in enumerate(fields)])
        self.assertEqual(len(compile_draft(draft)["fields"]), 600)
        for kind, data in (("csv", (",".join(f"field_{n}" for n in range(600)) + ",\n").encode()), ("xlsx", xlsx_headers(600))):
            with self.subTest(kind=kind):
                spec = templates.inspect_template(data, f"fictional.{kind}")
                self.assertEqual(len(spec["columns"]), 600)
                self.assertTrue(templates.validate_mapping(spec, fields, {field["name"]: field["name"] for field in fields})["valid"])
        with self.assertRaisesRegex(InputError, "600"):
            parse_schema(rules + [{"name": "overflow", "type": "text"}])
        draft["fields"].append({"id": "overflowkey", "name": "overflow", "type": "text"})
        with self.assertRaisesRegex(InputError, "600"):
            validate_draft(draft)
        for kind, data in (("csv", (",".join(f"field_{n}" for n in range(601)) + "\n").encode()), ("xlsx", xlsx_headers(601))):
            with self.subTest(kind=kind), self.assertRaisesRegex(templates.TemplateError, "600"):
                templates.inspect_template(data, f"fictional.{kind}")
        with tempfile.TemporaryDirectory() as folder, self.assertRaisesRegex(DocumentError, "600"):
            process_document(b"Fictional", "fictional.txt", rules + [{"name": "overflow"}], Path(folder), "example")

    def test_schema_byte_limit_cannot_be_bypassed_by_few_fields(self):
        rule = [{"name": "record_id", "type": "text", "unused": "x" * MAX_SCHEMA_BYTES}]
        with self.assertRaisesRegex(InputError, "1 MiB"):
            parse_schema(rule)
        with self.assertRaisesRegex(templates.TemplateError, "1 MiB"):
            templates._schema_fields(rule)
        with tempfile.TemporaryDirectory() as folder, self.assertRaisesRegex(DocumentError, "1 MiB"):
            process_document(b"Fictional", "fictional.txt", rule, Path(folder), "example")

    def test_only_explicit_mdy_dates_normalize_and_evidence_stays_original(self):
        date_rule = {"name": "visit_date", "type": "date", "sourceDateFormat": "mdy"}
        self.assertEqual(_validate_value("02/29/2000", date_rule), ("2000-02-29", None))
        self.assertEqual(_validate_value("2000-02-29", date_rule), ("2000-02-29", None))
        for value in ("02/29/2001", "13/1/2000", "2/30/2000", "2/3/00"):
            self.assertEqual(_validate_value(value, date_rule)[0], "")
            self.assertIsNotNone(_validate_value(value, date_rule)[1])
        self.assertEqual(_validate_value("2/29/2000", {"type": "date"})[0], "")
        for kind, source_format in (("date", "dmy"), ("text", "mdy"), ("date", None)):
            with self.assertRaisesRegex(InputError, "sourceDateFormat"):
                parse_schema([{"name": "record_id", "type": "text"}, {"name": "date", "type": kind, "sourceDateFormat": source_format}])
        fields = parse_schema([{"name": "record_id", "type": "text"}, date_rule])
        with tempfile.TemporaryDirectory() as folder:
            result = process_document(b"record_id: FICTIONAL-01\nvisit_date: 02/29/2000", "fictional.txt", fields, Path(folder), "example")
        self.assertEqual(result["values"]["visit_date"], "2000-02-29")
        self.assertEqual(result["evidence"]["visit_date"]["text"], "02/29/2000")
        self.assertEqual(validate_values(fields, result["values"]), {})


class ExpectedFieldSessionTests(unittest.TestCase):
    def setUp(self):
        self.session = DesktopSession()
        self.addCleanup(self.session.close)
        temporary = tempfile.TemporaryDirectory(prefix="quickcap-expected-test-")
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)

    def test_blank_start_generic_headers_and_bad_import_rollback(self):
        initial = self.session.snapshot()
        self.assertEqual((initial["phase"], initial["schema"], initial["expectedFields"]), ("empty", [], []))
        path = self.folder / "fictional.csv"
        path.write_text("fictional_id,fictional_score,\n")
        loaded = self.session.load_expected_fields(path)
        self.assertEqual([field["name"] for field in loaded["expectedFields"]], ["fictional_id", "fictional_score"])
        self.assertTrue(all(not field["metadataVerified"] for field in loaded["expectedFields"]))
        self.assertEqual((loaded["phase"], loaded["schema"], loaded["draft"]), ("empty", [], None))
        self.assertFalse(loaded["templatePreview"]["ready"])
        before = self.session.snapshot()
        for text in ("duplicate,duplicate\n", "field_a,,field_b\n", "field_a\nFictional answer\n"):
            path.write_text(text)
            with self.assertRaises(InputError):
                self.session.load_expected_fields(path)
            self.assertEqual(self.session.snapshot(), before)
        with self.assertRaisesRegex(InputError, "Choose"):
            self.session.add_expected_field("unknown_name")

    def test_catalog_subset_mask_and_identifier_gates_and_exact_rules(self):
        state = self.session.use_pace_template()
        self.assertEqual(len(state["expectedFields"]), 512)
        self.assertEqual(state["schema"], [])
        first = self.session.add_expected_field("record_id")
        dob = self.session.add_expected_field("patient_dob")
        baseline = self.session.add_expected_field("med_caf")
        patient = self.session.add_expected_field("med_caf_v2")
        self.assertEqual((baseline["choices"]["2"], patient["choices"]["3"]), ("Taken, no change in symptoms",) * 2)
        self.assertEqual(dob["sourceDateFormat"], "mdy")
        self.assertIsNone(self.session.draft["identifierField"])
        self.assertNotIn("region", dob)
        with self.assertRaisesRegex(InputError, "already selected"):
            self.session.add_expected_field("patient_dob")
        draft = self.session.snapshot()["draft"]
        draft["name"] = "Fictional selected subset"
        self.session.replace_draft(draft)
        with self.assertRaisesRegex(InputError, "Explicitly choose"):
            self.session.apply_draft()
        draft["identifierField"] = first["id"]
        self.session.replace_draft(draft)
        with self.assertRaisesRegex(InputError, "mask"):
            self.session.apply_draft()
        self.assertEqual(self.session.workspace.schema, [])
        draft["fields"][1]["region"] = {"page": 1, "x": .1, "y": .1, "width": .5, "height": .05}
        self.session.replace_draft(draft)
        changed = self.session.add_expected_field("patient_sex", dob["id"])
        self.assertEqual(changed["id"], dob["id"])
        self.assertEqual(changed["region"], draft["fields"][1]["region"])
        self.assertNotIn("sourceDateFormat", changed)
        self.assertEqual(len(self.session.snapshot()["expectedFields"]), 512)

    def test_blank_and_incomplete_draft_projects_keep_expected_headers(self):
        self.session.use_pace_template()
        path = self.folder / "fictional-blank.json"
        self.session.save_project(path)
        self.session.reset()
        self.session.open_project(path)
        self.assertEqual(self.session.phase, "empty")
        self.assertEqual(len(self.session.snapshot()["expectedFields"]), 512)
        field = self.session.add_expected_field("patient_dob")
        self.session.save_project(path)
        self.session.reset()
        self.session.open_project(path)
        self.assertEqual(self.session.draft["fields"][0], field)
        self.assertEqual(self.session.phase, "design")
        self.assertFalse(self.session.workspace.template["confirmed"])

    def test_real_selected_masks_export_all_destinations_and_reopen_gates(self):
        self.session.use_pace_template()
        self.session.add_document(fictional_pdf(), "fictional-pace.pdf")
        identifier = self.session.add_expected_field("record_id")
        dob = self.session.add_expected_field("patient_dob")
        draft = self.session.snapshot()["draft"]
        draft.update(name="Fictional PACE date test", identifierField=identifier["id"])
        for field, y in zip(draft["fields"], (.025, .10)):
            field["region"] = {"page": 1, "x": .1, "y": y, "width": .7, "height": .06}
        self.session.replace_draft(draft)
        self.session.apply_draft()
        record = self.session.workspace.records[0]
        self.assertEqual(record["values"], {"record_id": "FICTIONAL-PACE-01", "patient_dob": "2000-02-29"})
        self.assertEqual(record["evidence"]["patient_dob"]["text"], "02/29/2000")
        self.session.review_record(record["id"], record["values"], list(record["values"]), "Fictional reviewer", True)
        self.session.set_mapping({"record_id": "record_id", "patient_dob": "patient_dob"}, False)
        revision = self.session.workspace.template["revision"]
        self.session.leave_remaining_columns_blank(revision)
        with self.assertRaises(ConflictError):
            self.session.leave_remaining_columns_blank(revision)
        self.assertFalse(self.session.workspace.template["confirmed"])
        self.assertEqual(self.session.workspace.template["mappings"]["patient_dob"], "patient_dob")
        with self.assertRaises(InputError):
            self.session.export("csv", expected_revision=self.session.workspace.template["revision"])
        self.session.set_mapping(dict(self.session.workspace.template["mappings"]), True)
        output = self.session.export("csv", expected_revision=self.session.workspace.template["revision"])
        rows = list(csv.reader(io.StringIO(output.decode("utf-8-sig"))))
        self.assertEqual([len(row) for row in rows], [512, 512])
        self.assertEqual(rows[1][rows[0].index("patient_dob")], "2000-02-29")
        self.assertEqual(rows[1][rows[0].index("patient_sex")], "")
        type_path = self.folder / "fictional-type.json"
        self.session.save_form_type(type_path)
        saved = type_path.read_text()
        for private in ("FICTIONAL-PACE-01", "02/29/2000", "sourceData", "metadataVerified", "codebookSHA256"):
            self.assertNotIn(private, saved)
        self.assertEqual(len(json.loads(saved)["fields"]), 2)
        project = self.folder / "fictional-project.json"
        self.session.save_project(project)
        self.session.open_project(project)
        reopened = self.session.snapshot()
        self.assertEqual(len(reopened["expectedFields"]), 512)
        self.assertFalse(reopened["template"]["confirmed"])
        self.assertEqual(reopened["records"][0]["confirmed"], [])
        self.assertEqual(reopened["records"][0]["status"], "review")

    def test_catalog_validation_and_exact_order_gate(self):
        profile = load_catalog(APP / "study_profiles" / "pace.json")
        for mutate in (lambda raw: raw["fields"][0].update(type=[]),
                       lambda raw: raw["fields"][0].update(sourceData="forbidden"),
                       lambda raw: raw["fields"].reverse()):
            raw = copy.deepcopy(profile)
            mutate(raw)
            with self.assertRaises(CatalogError):
                parse_catalog(raw)
        names = list(profile["columns"])
        names[0], names[1] = names[1], names[0]
        path = self.folder / "reordered.csv"
        path.write_text(",".join(names) + "\n")
        self.session.load_expected_fields(path)
        self.assertFalse(any(field["metadataVerified"] for field in self.session.snapshot()["expectedFields"]))

    def test_checkbox_blank_zero_and_one_are_distinct(self):
        self.session.use_pace_template()
        name = next(field["name"] for field in self.session.snapshot()["expectedFields"] if "___" in field["name"])
        field = self.session.add_expected_field(name)
        self.assertEqual(field["choices"], {"0": "Unchecked", "1": "Checked"})
        for value in ("", "0", "1"):
            self.assertEqual(_validate_value(value, field), (value, None))

    def test_selected_repeatable_instruments_have_manual_import_warning(self):
        self.session.use_pace_template()
        self.assertEqual(self.session.snapshot()["patientRowExportWarning"], "")
        self.session.add_expected_field("csf_volume_delta")
        state = self.session.snapshot()
        self.assertIn("separate instrument/instance rows", state["patientRowExportWarning"])
        self.assertIn(state["patientRowExportWarning"], state["expectedWarnings"])
        self.assertIn(state["patientRowExportWarning"], state["template"]["warnings"])
        self.assertNotIn(state["patientRowExportWarning"], self.session.workspace.template["warnings"])


if __name__ == "__main__":
    unittest.main()
