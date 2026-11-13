"""Native desktop backend acceptance, using only shipped fictional fixtures."""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

import openpyxl

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
from desktop_model import DesktopSession, InputError, ConflictError, atomic_write, bounded_read


FRIENDLY = {"Participant ID": "record_id", "Age (years)": "age", "Consent code": "consent", "Visit date": "visit_date", "Score": "symptom_score", "Research notes": "notes"}
EXPECTED = {"record_id": "DEMO-001", "visit_date": "2026-01-12", "age": "34", "consent": "1", "symptom_score": "3", "notes": "Practice entry alpha. No follow-up requested."}


class DesktopSessionTests(unittest.TestCase):
    def setUp(self):
        self.session = DesktopSession()
        self.session.set_schema(json.loads((APP / "samples/sample-schema.json").read_text()))
        self.addCleanup(self.session.close)
        self.files = tempfile.TemporaryDirectory(prefix="formbridge-desktop-test-")
        self.addCleanup(self.files.cleanup)
        self.folder = Path(self.files.name)

    def add_pdf(self):
        result = self.session.import_documents([APP / "samples/practice-01-text.pdf"])
        self.assertFalse(result["failed"])
        return self.session.workspace.records[-1]

    def approve(self, record):
        return self.session.review_record(record["id"], record["values"], list(record["values"]), "Fictional Reviewer", True)

    def test_real_pdf_review_mapping_csv_and_xlsx_exact_cells(self):
        record = self.add_pdf()
        self.assertEqual(record["values"], EXPECTED)
        self.assertTrue(self.session.page_path(record["id"], 1).is_file())
        with self.assertRaises(InputError):
            self.session.export("csv", mapped=False)
        with self.assertRaises(InputError):
            self.session.review_record(record["id"], record["values"], ["record_id"], "Fictional Reviewer", True)
        self.approve(record)
        self.session.load_sample_template("friendly")
        self.session.set_mapping(FRIENDLY, True)
        revision = self.session.workspace.template["revision"]
        csv_path = self.folder / "fictional output.csv"
        self.session.export("csv", csv_path, revision)
        rows = list(csv.reader(io.StringIO(csv_path.read_text(encoding="utf-8-sig"))))
        self.assertEqual(rows, [list(FRIENDLY), ["DEMO-001", "34", "1", "2026-01-12", "3", EXPECTED["notes"]]])
        workbook_bytes = self.session.export("xlsx", expected_revision=revision)
        book = openpyxl.load_workbook(io.BytesIO(workbook_bytes))
        try:
            sheet = book["Intake"]
            self.assertEqual([sheet.cell(4, col).value for col in range(1, 7)], ["DEMO-001", 34, "1", "2026-01-12", 3, EXPECTED["notes"]])
            self.assertEqual(sheet.freeze_panes, "A4")
        finally:
            book.close()

    def test_edit_clears_confirmation_approval_and_stales_export(self):
        record = self.add_pdf()
        self.approve(record)
        self.session.use_categories_as_columns()
        self.session.set_mapping({name: name for name in EXPECTED}, True)
        revision = self.session.workspace.template["revision"]
        changed = {**EXPECTED, "symptom_score": "0", "notes": ""}
        saved = self.session.review_record(record["id"], changed, list(EXPECTED), "Fictional Reviewer")
        self.assertEqual(saved["status"], "review")
        self.assertNotIn("symptom_score", saved["confirmed"])
        self.assertNotIn("notes", saved["confirmed"])
        with self.assertRaises(ConflictError):
            self.session.export("csv", expected_revision=revision)
        with self.assertRaises(InputError):
            self.session.export("csv", expected_revision=self.session.workspace.template["revision"])
        self.session.review_record(record["id"], changed, list(changed), "Fictional Reviewer", True)
        raw = self.session.export("csv", expected_revision=self.session.workspace.template["revision"])
        rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
        self.assertEqual(rows[0]["symptom_score"], "0")
        self.assertEqual(rows[0]["notes"], "")

    def test_missing_duplicate_and_unconfirmed_mapping_block_export(self):
        self.approve(self.add_pdf())
        self.session.load_sample_template("friendly")
        template = self.session.workspace.template
        for mapping in ({}, {**FRIENDLY, "Age (years)": "record_id"}, {**FRIENDLY, "Participant ID": None}):
            with self.subTest(mapping=mapping), self.assertRaises(InputError):
                self.session.set_mapping(mapping, True)
        self.session.set_mapping(FRIENDLY, False)
        with self.assertRaises(InputError):
            self.session.export("csv", expected_revision=template["revision"])
        with self.assertRaises(ConflictError):
            self.session.export("csv")

    def test_project_reopen_reprocesses_and_clears_all_gates(self):
        record = self.add_pdf()
        self.approve(record)
        self.session.load_sample_template("friendly")
        self.session.set_mapping(FRIENDLY, True)
        path = self.folder / "fictional project.json"
        self.session.save_project(path)
        self.assertFalse(self.session.dirty)
        old_assets, old_id = self.session.workspace.assets, record["id"]
        self.session.open_project(path)
        self.assertFalse(old_assets.exists())
        loaded = self.session.workspace.records[0]
        self.assertNotEqual(loaded["id"], old_id)
        self.assertEqual(loaded["values"], EXPECTED)
        self.assertEqual(loaded["confirmed"], [])
        self.assertEqual(loaded["status"], "review")
        self.assertEqual(loaded["reviewedBy"], "")
        self.assertEqual(self.session.workspace.template["mappings"], FRIENDLY)
        self.assertFalse(self.session.workspace.template["confirmed"])
        self.assertFalse(self.session.dirty)
        self.assertTrue(self.session.page_path(loaded["id"], 1).is_file())
        with self.assertRaises(InputError):
            self.session.export("csv", expected_revision=self.session.workspace.template["revision"])

    def test_project_hash_and_late_template_failure_roll_back_live_state(self):
        record = self.add_pdf()
        self.approve(record)
        before = self.session.snapshot()
        project = json.loads(self.session.project_bytes())
        project["records"][0]["sourceHash"] = "0" * 64
        path = self.folder / "broken.json"
        path.write_text(json.dumps(project))
        with self.assertRaisesRegex(InputError, "checksum"):
            self.session.open_project(path)
        self.assertEqual(self.session.snapshot(), before)
        project = json.loads(self.session.project_bytes())
        project["template"] = {"filename": "invalid.csv", "sourceData": "AA==", "mappings": {}}
        path.write_text(json.dumps(project))
        with self.assertRaises(InputError):
            self.session.open_project(path)
        self.assertEqual(self.session.snapshot(), before)
        self.assertTrue(self.session.page_path(record["id"], 1).is_file())

    def test_atomic_save_failure_preserves_existing_file_and_dirty_state(self):
        self.add_pdf()
        path = self.folder / "keep.json"
        path.write_bytes(b"previous")
        with patch("desktop_model.os.replace", side_effect=PermissionError("fictional denied")):
            with self.assertRaises(InputError):
                self.session.save_project(path)
        self.assertEqual(path.read_bytes(), b"previous")
        self.assertTrue(self.session.dirty)
        self.assertIsNone(self.session.project_path)
        self.assertEqual(list(self.folder.iterdir()), [path])

    def test_dictionary_categories_generate_columns_and_reprocess(self):
        self.add_pdf()
        dictionary = self.folder / "categories.json"
        dictionary.write_text(json.dumps([{"name": "study_id", "label": "Study ID", "aliases": ["Record ID"], "type": "text"}, {"name": "score", "label": "Symptom score", "type": "integer", "required": False}]))
        self.session.import_dictionary(dictionary)
        self.assertEqual([f["name"] for f in self.session.workspace.schema], ["study_id", "score"])
        self.assertEqual(self.session.workspace.records[0]["confirmed"], [])
        self.session.use_categories_as_columns()
        self.assertEqual([c["name"] for c in self.session.workspace.template["columns"]], ["study_id", "score"])
        self.assertEqual(self.session.workspace.template["mappings"], {"study_id": "study_id", "score": "score"})
        self.assertFalse(self.session.workspace.template["confirmed"])

    def test_batch_import_keeps_success_and_reports_only_failed_basename(self):
        progress = []
        result = self.session.import_documents([APP / "samples/practice-01-text.pdf", self.folder / "missing-fictional.pdf"], lambda current, total: progress.append((current, total)))
        self.assertEqual(len(result["added"]), 1)
        self.assertEqual(result["failed"][0]["filename"], "missing-fictional.pdf")
        self.assertEqual(progress, [(1, 2), (2, 2)])
        self.assertEqual(len(self.session.workspace.records), 1)

    def test_cancel_acknowledges_owner_before_cleanup(self):
        started, stopped = threading.Event(), threading.Event()
        errors = []
        def process(*args):
            started.set()
            if not stopped.wait(2):
                raise RuntimeError("Test cancellation was not delivered")
            raise InputError("Processing cancelled")
        def operation():
            try:
                self.session.add_document(b"fictional", "fictional.txt")
            except InputError as exc:
                errors.append(str(exc))
            finally:
                self.session.end_operation()
        self.session.begin_operation()
        with patch.object(self.session.workspace, "process", side_effect=process), patch.object(self.session.workspace, "stop_jobs", side_effect=stopped.set):
            owner = threading.Thread(target=operation)
            owner.start()
            self.assertTrue(started.wait(2))
            self.session.cancel()
            owner.join(2)
        self.assertFalse(owner.is_alive())
        self.assertEqual(errors, ["Processing cancelled"])
        self.assertFalse(self.session.workspace.records)
        self.session.begin_operation()
        self.session.end_operation()
        self.add_pdf()
        assets = self.session.workspace.assets
        self.session.close()
        self.assertFalse(assets.exists())

    def test_bounded_read_rejects_before_content_read_and_snapshots_detach(self):
        path = self.folder / "large.txt"
        path.write_bytes(b"f" * 1025)
        with self.assertRaises(InputError):
            bounded_read(path, 1024)
        state = self.session.snapshot()
        state["schema"][0]["label"] = "Changed copy"
        self.assertNotEqual(self.session.workspace.schema[0]["label"], "Changed copy")


if __name__ == "__main__":
    unittest.main()
