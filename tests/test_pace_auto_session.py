"""Automatic PACE patient review uses fictional, locally generated PDFs."""
from __future__ import annotations

import copy
import csv
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from desktop_model import DesktopSession, InputError
import pace_auto


def hit6_pdf(mrn="00001234", first="Ada", last="Example", date="04/05/2026", sticker_x=390, sticker_y=740, study=None, first_mark=True):
    output = io.BytesIO()
    pdf = canvas.Canvas(output, pagesize=(612, 792), invariant=1)
    pdf.drawString(sticker_x, sticker_y, f"{last.upper()}, {first.upper()}")
    pdf.drawString(sticker_x, sticker_y - 15, "DOB 02/03/1980 Sex F")
    pdf.drawString(sticker_x, sticker_y - 30, f"MRN {mrn}")
    if study:
        pdf.drawString(sticker_x, sticker_y - 45, f"Research Study ID: {study}")
    pdf.drawString(40, 660, "HIT-6 Headache Impact Test")
    pdf.drawString(40, 630, f"Date {date}")
    pdf.setFont("Helvetica", 8)
    for x, label in zip((350, 400, 455, 510, 568), ("Never", "Rarely", "Sometimes", "Very", "Always")):
        pdf.drawCentredString(x, 590, label)
    questions = ("Pain severe", "Limit your ability to do usual daily activities", "Wish you could lie down",
                 "Felt too tired", "Fed up or irritated", "Limit your ability to concentrate")
    for index, question in enumerate(questions, 1):
        y = 590 - index * 40
        pdf.drawString(40, y, str(index))
        pdf.drawString(60, y, question)
        if index != 1 or first_mark:
            pdf.drawCentredString(400, y, "X")
    pdf.drawString(40, 50, "HA-230 Rev 02/2026 Page 1 of 1")
    pdf.save()
    return output.getvalue()


class PaceAutoSessionTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix="qwikcap-auto-test-")
        self.addCleanup(self.folder.cleanup)
        self.directory = Path(self.folder.name)
        self.session = DesktopSession()
        self.addCleanup(self.session.close)
        self.session.use_pace_auto_profile()

    def source(self, name="fictional.pdf", **kwargs):
        path = self.directory / name
        path.write_bytes(hit6_pdf(**kwargs))
        return path

    def confirmed(self, path):
        result = self.session.import_pace_documents([path])
        self.assertEqual(result["failed"], [])
        self.assertEqual(len(result["groups"]), 1)
        self.assertEqual(result["groups"][0]["issues"], [])
        added = self.session.confirm_pace_groups([result["groups"][0]["id"]], confirmed_identity=True)
        return self.session._record(added["added"][0])

    def test_default_auto_profile_keeps_the_canonical_512_and_template(self):
        state = self.session.snapshot()
        self.assertEqual(state["profile"], "pace-auto-v1")
        self.assertEqual(len(state["schema"]), 512)
        self.assertEqual(len(state["template"]["columns"]), 512)
        self.assertFalse(state["template"]["confirmed"])
        self.assertEqual(state["draft"], None)

    def test_staging_requires_explicit_group_confirmation_and_preserves_zero_mrn(self):
        result = self.session.import_pace_documents([self.source(sticker_x=42, sticker_y=280)])
        self.assertEqual(self.session.workspace.records, [])
        group = result["groups"][0]
        self.assertEqual(group["mrn"], "00001234")
        self.assertEqual(group["issues"], [])
        self.assertTrue(Path(group["sources"][0]["pages"][0]["previewPath"]).is_file())
        with self.assertRaisesRegex(InputError, "explicitly confirm"):
            self.session.confirm_pace_groups([group["id"]])
        result = self.session.confirm_pace_groups([group["id"]], True)
        record = self.session._record(result["added"][0])
        self.assertEqual(record["values"]["mrn"], "00001234")
        self.assertEqual(record["values"]["record_id"], "NEW000001")
        self.assertEqual(record["sourceContext"]["recordIds"], [])
        self.assertTrue(record["paceIdentityConfirmed"])
        self.assertEqual(len(record["bundleSources"]), 1)
        self.assertEqual(self.session.snapshot()["pendingPatientGroups"], [])

    def test_unconfirmed_proposals_cannot_be_silently_saved_without_their_sources(self):
        self.assertFalse(self.session.snapshot()["dirty"])
        self.session.import_pace_documents([self.source()])
        self.assertTrue(self.session.snapshot()["dirty"])
        with self.assertRaisesRegex(InputError, "Check or discard"):
            self.session.project_bytes()
        self.session.cancel_pace_import()
        self.assertFalse(self.session.snapshot()["dirty"])

    def test_repeated_assessments_or_conflicting_names_block_grouping(self):
        for kwargs in ({}, {"first": "Different"}):
            with self.subTest(kwargs=kwargs):
                result = self.session.import_pace_documents([self.source("one.pdf"), self.source("two.pdf", date="04/06/2026", **kwargs)])
                self.assertEqual(len(result["groups"]), 1)
                group = result["groups"][0]
                self.assertTrue(any("Repeated" in issue for issue in group["issues"]))
                if kwargs:
                    self.assertTrue(any("conflict" in issue for issue in group["issues"]))
                with self.assertRaisesRegex(InputError, "Resolve"):
                    self.session.confirm_pace_groups([group["id"]], True)
                self.assertEqual(self.session.workspace.records, [])
                self.session.cancel_pace_import()

    def test_editing_a_review_value_cannot_move_the_source_mrn_to_another_group(self):
        record = self.confirmed(self.source())
        changed = self.session.review_record(record["id"], {**record["values"], "mrn": "9999"}, [], "Fictional reviewer")
        self.assertIn("mrn", changed["validationErrors"])
        result = self.session.import_pace_documents([self.source("more.pdf", date="04/06/2026")])
        self.assertEqual(result["groups"][0]["mrn"], "00001234")
        self.assertTrue(any("already has a patient row" in issue for issue in result["groups"][0]["issues"]))
        with self.assertRaises(InputError):
            self.session.confirm_pace_groups([result["groups"][0]["id"]], True)
        self.assertEqual(len(self.session.workspace.records), 1)

    def test_one_pdf_can_propose_distinct_patient_rows_without_zero_collapsing(self):
        writer = PdfWriter()
        for mrn, first in (("00001234", "Ada"), ("1234", "Grace")):
            writer.add_page(PdfReader(io.BytesIO(hit6_pdf(mrn=mrn, first=first))).pages[0])
        combined = self.directory / "fictional-batch.pdf"
        with combined.open("wb") as stream:
            writer.write(stream)
        result = self.session.import_pace_documents([combined])
        self.assertEqual({group["mrn"] for group in result["groups"]}, {"00001234", "1234"})
        self.assertTrue(all(not group["issues"] for group in result["groups"]))
        self.session.confirm_pace_groups([group["id"] for group in result["groups"]], True)
        self.assertEqual(len(self.session.workspace.records), 2)
        self.assertEqual({record["values"]["record_id"] for record in self.session.workspace.records}, {"NEW000001", "NEW000002"})

    def test_source_study_id_stays_distinct_and_unknown_layout_stays_blocked(self):
        record = self.confirmed(self.source(study="PRINTED-17"))
        self.assertEqual(record["values"]["record_id"], "NEW000001")
        self.assertEqual(record["sourceContext"]["recordIds"], ["PRINTED-17"])
        unknown = self.directory / "fictional-unknown.pdf"
        output = io.BytesIO()
        pdf = canvas.Canvas(output)
        pdf.drawString(40, 740, "EXAMPLE, ADA DOB 02/03/1980 MRN 00009999")
        pdf.drawString(40, 600, "Unrecognized questionnaire")
        pdf.save()
        unknown.write_bytes(output.getvalue())
        result = self.session.import_pace_documents([unknown])
        self.assertTrue(result["groups"][0]["issues"])

    def test_correction_loadout_reuses_rules_without_patient_values(self):
        first = self.confirmed(self.source())
        corrected = self.session.correct_pace_field(first["id"], "hit6_date", {"page": 2, "x": .11, "y": .18, "width": .3, "height": .05}, first["revision"])
        self.assertEqual(corrected["values"]["hit6_date"], "2026-04-05")
        self.assertEqual(self.session.snapshot()["profile"], "pace-auto-v1")
        self.assertEqual(len(self.session.workspace.schema), 512)
        saved = self.directory / "fictional-layout.json"
        self.session.save_pace_loadout(saved)
        text = saved.read_text()
        for private in ("00001234", "ADA", "EXAMPLE", "2026-04-05", "NEW000001", "fictional.pdf", "sourceData"):
            self.assertNotIn(private, text)
        project = self.directory / "corrected-project.json"
        self.session.save_project(project)
        self.session.open_project(project)
        reopened = self.session.workspace.records[0]
        self.assertEqual(reopened["values"]["hit6_date"], "2026-04-05")
        self.assertEqual(reopened["evidence"]["hit6_date"]["mapping"], "pace-layout-answer-area")
        self.session = DesktopSession()
        self.addCleanup(self.session.close)
        self.session.use_pace_auto_profile()
        self.session.load_pace_loadout(saved)
        second = self.confirmed(self.source("second.pdf", mrn="00009876", first="Grace", date="05/06/2026"))
        self.assertEqual(second["values"]["hit6_date"], "2026-05-06")
        self.assertEqual(second["evidence"]["hit6_date"]["mapping"], "pace-layout-answer-area")
        self.assertEqual(second["confirmed"], [])

    def test_approval_export_and_project_reopen_keep_one_patient_row_and_fresh_gates(self):
        record = self.confirmed(self.source())
        with self.assertRaisesRegex(InputError, "Confirm every field"):
            self.session.review_record(record["id"], record["values"], [], "Fictional reviewer", True)
        self.session.review_record(record["id"], record["values"], record["applicableFields"], "Fictional reviewer", True)
        self.session.set_mapping(dict(self.session.workspace.template["mappings"]), True)
        data = self.session.export("csv", expected_revision=self.session.workspace.template["revision"])
        rows = list(csv.reader(io.StringIO(data.decode("utf-8-sig"))))
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[1]), 512)
        self.assertEqual(rows[1][rows[0].index("mrn")], "00001234")
        project = self.directory / "fictional-project.json"
        self.session.save_project(project)
        self.session.open_project(project)
        reopened = self.session.workspace.records[0]
        self.assertEqual(reopened["values"]["record_id"], "NEW000001")
        self.assertFalse(reopened["paceIdentityConfirmed"])
        self.assertEqual(reopened["confirmed"], [])
        with self.assertRaises(InputError):
            self.session.review_record(reopened["id"], reopened["values"], reopened["applicableFields"], "Fictional reviewer", True)
        self.session.confirm_pace_identity(reopened["id"])
        self.session.review_record(reopened["id"], reopened["values"], reopened["applicableFields"], "Fictional reviewer", True)
        self.assertEqual(reopened["status"], "approved")

    def test_loadout_rejects_hidden_values_and_invalid_rule_without_mutation(self):
        before = self.session.snapshot()
        path = self.directory / "not-a-layout.json"
        path.write_text(json.dumps({"format": "qwikcap-pace-loadout-v1", "name": "Bad", "rules": [], "values": {"mrn": "private"}}))
        with self.assertRaises(InputError):
            self.session.load_pace_loadout(path)
        self.assertEqual(self.session.snapshot(), before)

    def test_loading_layout_invalidates_only_matching_answers(self):
        record = self.confirmed(self.source())
        proof = record["evidence"]["hit6_date"]
        rule = pace_auto.make_rule(record, "hit6_date", {"page": proof["page"], **proof["region"]})
        self.session.review_record(record["id"], record["values"], record["applicableFields"], "Fictional reviewer", True)
        before = copy.deepcopy(self.session._record(record["id"]))
        path = self.directory / "other-revision.json"
        path.write_text(json.dumps({"format": pace_auto.LOADOUT_FORMAT, "name": "Other revision", "rules": [{**rule, "revision": "03/2026"}]}))
        self.session.load_pace_loadout(path)
        self.assertEqual(self.session._record(record["id"]), before)
        path.write_text(json.dumps({"format": pace_auto.LOADOUT_FORMAT, "name": "Matching revision", "rules": [rule]}))
        self.session.load_pace_loadout(path)
        after = self.session._record(record["id"])
        self.assertEqual(after["status"], "review")
        self.assertEqual(set(after["confirmed"]), set(before["confirmed"]) - {"hit6_date"})
        self.assertEqual(after["revision"], before["revision"] + 1)

    def test_redrawing_source_blank_choice_keeps_identity_guards_and_removes_blank_waiver(self):
        record = self.confirmed(self.source(first_mark=False))
        self.assertIn("hit6_severity", record["sourceContext"]["unansweredFields"])
        proof = record["evidence"]["hit6_severity"]
        record = self.session.correct_pace_field(record["id"], "hit6_severity", {"page": proof["page"], **proof["region"]}, record["revision"])
        self.assertNotIn("hit6_severity", record["sourceContext"]["unansweredFields"])
        path = self.directory / "corrected-source-blank.json"
        self.session.save_project(path)
        self.session.open_project(path)
        record = self.session.confirm_pace_identity(self.session.workspace.records[0]["id"])
        self.assertNotIn("hit6_severity", record["sourceContext"]["unansweredFields"])
        for field, changed in (("mrn", "9999"), ("patient_first", "Wrong"), ("patient_last", "Wrong"), ("patient_dob", "1980-02-04")):
            with self.subTest(field=field):
                saved = self.session.review_record(record["id"], {**record["values"], field: changed}, [], "Fictional reviewer")
                self.assertIn(field, saved["validationErrors"])
                with self.assertRaises(InputError):
                    self.session.review_record(saved["id"], saved["values"], saved["applicableFields"], "Fictional reviewer", True)
        with self.assertRaises(InputError):
            self.session.review_record(record["id"], record["values"], record["applicableFields"], "Fictional reviewer", True)

    def test_invalid_source_blank_metadata_blocks_even_when_identity_guard_cannot_read_it(self):
        record = self.confirmed(self.source(first_mark=False))
        record["evidence"]["hit6_severity"]["mapping"] = "untrusted-proof"
        saved = self.session.review_record(record["id"], {**record["values"], "mrn": "9999"}, [], "Fictional reviewer")
        self.assertIn("record_id", saved["validationErrors"])
        with self.assertRaises(InputError):
            self.session.review_record(saved["id"], saved["values"], saved["applicableFields"], "Fictional reviewer", True)


if __name__ == "__main__":
    unittest.main()
