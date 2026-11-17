"""Explicit patient source bundles produce one reviewed patient row."""
from __future__ import annotations

import base64
import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from reportlab.pdfgen import canvas

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
from desktop_model import DesktopSession, InputError
from limits import MAX_PAGES
from server import source_bytes
import pipeline


def source_pdf(value, count=1):
    output = io.BytesIO()
    document = canvas.Canvas(output, pagesize=(612, 792), invariant=1)
    for _ in range(count):
        document.drawString(72, 720, value)
        document.showPage()
    document.save()
    return output.getvalue()


class PatientBundleSessionTests(unittest.TestCase):
    def setUp(self):
        self.session = DesktopSession()
        self.addCleanup(self.session.close)
        temporary = tempfile.TemporaryDirectory(prefix="quickcap-patient-test-")
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.paths = [self.folder / "fictional-date.pdf", self.folder / "fictional-sex.pdf"]
        self.originals = [source_pdf("02/29/2000"), source_pdf("Female")]
        for path, data in zip(self.paths, self.originals):
            path.write_bytes(data)

    def apply_bundle_type(self):
        self.session.use_pace_template()
        self.session.add_patient_bundle(self.paths, "00042", confirmed_same_patient=True)
        for name, page in (("patient_dob", 2), ("patient_sex", 3)):
            field = self.session.add_expected_field(name)
            draft = self.session.snapshot()["draft"]
            next(item for item in draft["fields"] if item["id"] == field["id"])["region"] = {"page": page, "x": .1, "y": .065, "width": .7, "height": .06}
            draft["name"] = "Fictional patient bundle type"
            self.session.replace_draft(draft)
        self.session.apply_draft()
        return self.session.workspace.records[0]

    def test_operator_consent_is_required_before_any_source_read(self):
        before = self.session.snapshot()
        with patch("desktop_model.bounded_read", side_effect=AssertionError("must not read")):
            for consent in (False, 1, "yes"):
                with self.assertRaisesRegex(InputError, "Explicitly confirm"):
                    self.session.add_patient_bundle(self.paths, "00042", consent)
            with self.assertRaisesRegex(InputError, "study record ID"):
                self.session.add_patient_bundle(self.paths, "Invalid ID", True)
        self.assertEqual(self.session.snapshot(), before)

    def test_first_bundle_has_explicit_cover_identifier_and_public_manifest(self):
        self.session.use_pace_template()
        selected = self.session.add_expected_field("patient_dob")
        state_before = copy.deepcopy(self.session.draft)
        record = self.session.add_patient_bundle(self.paths, "00042", True)
        self.assertEqual(record["bundleRecordId"], "00042")
        self.assertEqual([entry["filename"] for entry in record["bundleSources"]], [path.name for path in self.paths])
        self.assertEqual([(entry["firstPage"], entry["lastPage"]) for entry in record["bundleSources"]], [(2, 2), (3, 3)])
        self.assertEqual(len(record["pages"]), 3)
        self.assertEqual(record["values"], {})
        self.assertFalse(any("sourceData" in source for source in record["bundleSources"]))
        self.assertNotIn("sourceData", record)
        draft = self.session.snapshot()["draft"]
        cover = next(field for field in draft["fields"] if field["name"] == "record_id")
        self.assertEqual(draft["identifierField"], cover["id"])
        self.assertEqual(cover["region"]["page"], 1)
        self.assertEqual(next(field for field in draft["fields"] if field["id"] == selected["id"]), state_before["fields"][0])
        self.assertEqual(len(self.session.snapshot()["expectedFields"]), 512)
        with self.assertRaisesRegex(InputError, "Name"):
            self.session.apply_draft()

    def test_several_forms_export_one_row_and_reopen_originals_with_fresh_gates(self):
        record = self.apply_bundle_type()
        expected = {"record_id": "00042", "patient_dob": "2000-02-29", "patient_sex": "1"}
        self.assertEqual(record["values"], expected)
        self.assertEqual(record["evidence"]["patient_dob"]["page"], 2)
        self.assertEqual(record["evidence"]["patient_sex"]["page"], 3)
        public = self.session.review_record(record["id"], expected, list(expected), "Fictional reviewer", True)
        self.assertFalse(any("sourceData" in source for source in public["bundleSources"]))
        self.session.set_mapping({name: name for name in expected}, False)
        self.session.leave_remaining_columns_blank(self.session.workspace.template["revision"])
        self.session.set_mapping(dict(self.session.workspace.template["mappings"]), True)
        output = self.session.export("csv", expected_revision=self.session.workspace.template["revision"])
        rows = list(csv.reader(io.StringIO(output.decode("utf-8-sig"))))
        self.assertEqual(len(rows), 2)
        self.assertEqual([len(row) for row in rows], [512, 512])
        self.assertEqual([rows[1][rows[0].index(name)] for name in expected], list(expected.values()))
        project = json.loads(self.session.project_bytes())
        saved = project["records"][0]
        self.assertEqual([base64.b64decode(source["sourceData"]) for source in saved["bundleSources"]], self.originals)
        self.assertEqual(source_bytes(self.session.workspace.records), len(base64.b64decode(saved["sourceData"])) + sum(map(len, self.originals)))
        type_path = self.folder / "fictional-type.json"
        self.session.save_form_type(type_path)
        type_text = type_path.read_text()
        for private in ("00042", "fictional-date.pdf", "bundleSources", "sourceData", "02/29/2000"):
            self.assertNotIn(private, type_text)
        path = self.folder / "fictional-project.json"
        self.session.save_project(path)
        self.session.open_project(path)
        reopened = self.session.snapshot()
        self.assertEqual(reopened["records"][0]["values"], expected)
        self.assertEqual(reopened["records"][0]["bundleRecordId"], "00042")
        self.assertEqual(reopened["records"][0]["confirmed"], [])
        self.assertEqual(reopened["records"][0]["status"], "review")
        self.assertFalse(reopened["template"]["confirmed"])
        self.assertFalse(any("sourceData" in source for source in reopened["records"][0]["bundleSources"]))

    def test_saved_original_hash_page_manifest_and_combined_pdf_are_verified_atomically(self):
        self.apply_bundle_type()
        original = json.loads(self.session.project_bytes())
        before = self.session.snapshot()
        path = self.folder / "altered-project.json"
        def changed_original(project):
            project["records"][0]["bundleSources"][0]["sourceData"] = base64.b64encode(source_pdf("Different")).decode()
        def changed_manifest(project):
            project["records"][0]["bundleSources"][0]["firstPage"] = 3
        def changed_combined(project):
            data = source_pdf("Unrelated combined source", 3)
            project["records"][0].update(sourceData=base64.b64encode(data).decode(), sourceHash=hashlib.sha256(data).hexdigest())
        for mutate in (changed_original, changed_manifest, changed_combined):
            project = copy.deepcopy(original)
            mutate(project)
            path.write_text(json.dumps(project))
            with self.assertRaises(InputError):
                self.session.open_project(path)
            self.assertEqual(self.session.snapshot(), before)

    def test_applied_bundle_type_accepts_next_patient_but_layout_failure_rolls_back(self):
        first = self.apply_bundle_type()
        self.session.review_record(first["id"], first["values"], list(first["values"]), "Fictional reviewer", True)
        second = self.session.add_patient_bundle(self.paths, "00043", True)
        self.assertEqual(second["values"]["record_id"], "00043")
        self.assertEqual(len(self.session.workspace.records), 2)
        before = self.session.snapshot()
        with self.assertRaisesRegex(InputError, "already"):
            self.session.add_patient_bundle(self.paths, "00043", True)
        extra = self.folder / "extra-pages.pdf"
        extra.write_bytes(source_pdf("Different layout", 2))
        with self.assertRaisesRegex(InputError, "page count"):
            self.session.add_patient_bundle([extra, self.paths[1]], "00044", True)
        self.assertEqual(self.session.snapshot(), before)

    def test_bundle_failure_and_ordinary_project_rejection_preserve_state(self):
        self.session.use_pace_template()
        before = self.session.snapshot()
        broken = self.folder / "broken.pdf"
        broken.write_bytes(b"%PDF-not-a-pdf")
        with self.assertRaises(InputError):
            self.session.add_patient_bundle([broken], "00042", True)
        self.assertEqual(self.session.snapshot(), before)
        self.session.add_document(self.originals[0], "ordinary.pdf")
        before = self.session.snapshot()
        with self.assertRaisesRegex(InputError, "new project"):
            self.session.add_patient_bundle(self.paths, "00042", True)
        self.assertEqual(self.session.snapshot(), before)

    def test_original_and_combined_bytes_share_the_session_budget(self):
        with patch("desktop_model.MAX_SESSION_BYTES", 1):
            with self.assertRaisesRegex(InputError, "20 MiB"):
                self.session.add_patient_bundle(self.paths, "00042", True)
        self.assertEqual(self.session.workspace.records, [])


class DocumentResourceTests(unittest.TestCase):
    def test_page_32_is_usable_but_page_33_is_rejected(self):
        self.assertEqual(MAX_PAGES, 32)
        with tempfile.TemporaryDirectory() as folder:
            result = pipeline.process_document(source_pdf("Fictional", 32), "fictional.pdf", [], Path(folder), "pages32")
            self.assertEqual(len(result["pages"]), 32)
            with self.assertRaisesRegex(pipeline.DocumentError, "32"):
                pipeline.process_document(source_pdf("Fictional", 33), "fictional.pdf", [], Path(folder), "pages33")

    def test_aggregate_render_and_asset_bounds_stop_processing(self):
        for limit, value, error in (("MAX_RENDER_PIXELS", 1, "120-megapixel"), ("MAX_ASSET_BYTES", 1, "128 MiB")):
            with tempfile.TemporaryDirectory() as folder, patch.object(pipeline, limit, value):
                with self.assertRaisesRegex(pipeline.DocumentError, error):
                    pipeline.process_document(source_pdf("Fictional", 2), "fictional.pdf", [], Path(folder), "bounded")


if __name__ == "__main__":
    unittest.main()
