"""Custom mask acceptance with generated fictional sources and real local workers."""
from __future__ import annotations

import copy
import csv
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

from reportlab.pdfgen import canvas

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
from desktop_model import DesktopSession, InputError
from form_types import compile_draft, new_draft, normalized_drag, parse_form_type, percentage_region, validate_region


def fictional_pdf(identifier, score, pagesize=(612, 792)):
    stream = io.BytesIO()
    page = canvas.Canvas(stream, pagesize=pagesize)
    page.drawString(72, pagesize[1] - 72, identifier)
    page.showPage()
    page.drawString(72, pagesize[1] - 72, str(score))
    page.save()
    return stream.getvalue()


def draft_for(session):
    draft = session.snapshot()["draft"]
    draft.update(name="Fictional custom visit", identifierField="identitykey", fields=[
        {"id": "identitykey", "name": "custom_id", "label": "Custom identifier", "type": "text", "required": True,
         "region": {"page": 1, "x": .1, "y": .065, "width": .6, "height": .05}},
        {"id": "scorekey", "name": "custom_score", "label": "Custom score", "type": "integer", "required": True,
         "region": {"page": 2, "x": .1, "y": .065, "width": .6, "height": .05}}])
    return draft


class CustomTypeTests(unittest.TestCase):
    def setUp(self):
        self.session = DesktopSession()
        self.addCleanup(self.session.close)
        folder = tempfile.TemporaryDirectory(prefix="formbridge-custom-test-")
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)

    def commit_first(self):
        self.session.add_document(fictional_pdf("CUSTOM-A", 7), "fictional-first.pdf")
        self.session.replace_draft(draft_for(self.session))
        self.session.apply_draft()

    def test_blank_first_import_and_draft_block_all_downstream_actions(self):
        self.assertEqual(self.session.snapshot()["schema"], [])
        self.assertEqual(self.session.phase, "empty")
        record = self.session.add_document(fictional_pdf("CUSTOM-A", 7), "fictional-first.pdf")
        self.assertEqual(self.session.phase, "design")
        self.assertEqual(len(self.session.draft["pages"]), 2)
        self.assertEqual(record["values"], {})
        for action in (lambda: self.session.review_record(record["id"], {}, [], "Fictional reviewer", True),
                       self.session.use_categories_as_columns, lambda: self.session.export("csv", mapped=False)):
            with self.assertRaisesRegex(InputError, "Apply"):
                action()
        invalid = draft_for(self.session)
        invalid["identifierField"] = None
        self.session.replace_draft(invalid)
        with self.assertRaisesRegex(InputError, "Explicitly choose"):
            self.session.apply_draft()
        self.assertEqual(self.session.workspace.schema, [])

    def test_real_two_page_masks_reuse_changed_answers_and_exact_export(self):
        self.commit_first()
        self.assertEqual(self.session.workspace.records[0]["values"], {"custom_id": "CUSTOM-A", "custom_score": "7"})
        path = self.folder / "custom-type.json"
        self.session.save_form_type(path)
        saved = path.read_text()
        for private in ("CUSTOM-A", "fictional-first.pdf", "sourceData", "sourceText", "evidence", "values"):
            self.assertNotIn(private, saved)
        fresh = DesktopSession()
        self.addCleanup(fresh.close)
        fresh.load_form_type(path)
        self.assertEqual(fresh.phase, "review")
        record = fresh.add_document(fictional_pdf("CUSTOM-B", 12), "fictional-second.pdf")
        self.assertEqual(record["values"], {"custom_id": "CUSTOM-B", "custom_score": "12"})
        fresh.review_record(record["id"], record["values"], list(record["values"]), "Fictional reviewer", True)
        fresh.use_categories_as_columns()
        fresh.set_mapping({"custom_id": "custom_id", "custom_score": "custom_score"}, True)
        exported = fresh.export("csv", expected_revision=fresh.workspace.template["revision"])
        self.assertEqual(list(csv.reader(io.StringIO(exported.decode("utf-8-sig")))), [["custom_id", "custom_score"], ["CUSTOM-B", "12"]])
        # Editing a loaded type keeps its explicit identifier attached to its new internal key.
        fresh.start_design()
        self.assertEqual(compile_draft(fresh.draft)["identifierField"], "custom_id")
        with self.assertRaises(InputError):
            fresh.export("csv", expected_revision=fresh.workspace.template["revision"])

    def test_project_restores_invalid_draft_without_committing_it(self):
        self.commit_first()
        active = copy.deepcopy(self.session.form_type)
        self.session.start_design()
        draft = self.session.snapshot()["draft"]
        draft["name"] = "Unfinished edits"
        draft["fields"][0]["name"] = ""
        self.session.replace_draft(draft)
        path = self.folder / "draft-project.json"
        self.session.save_project(path)
        self.session.reset()
        self.session.open_project(path)
        self.assertEqual(self.session.form_type, active)
        self.assertEqual(self.session.draft["fields"][0]["name"], "")
        self.assertEqual(self.session.phase, "design")
        self.assertTrue(self.session.page_path(self.session.workspace.records[0]["id"], 2).is_file())
        self.session.discard_draft()
        self.assertEqual(self.session.phase, "review")

    def test_layout_mismatch_retains_source_and_blocks_values_and_approval(self):
        self.commit_first()
        record = self.session.add_document(fictional_pdf("WRONG-SHAPE", 55, (792, 612)), "fictional-wide.pdf")
        self.assertTrue(record["formTypeIssues"])
        self.assertEqual(set(record["values"].values()), {""})
        self.assertTrue(self.session.page_path(record["id"], 1).is_file())
        with self.assertRaisesRegex(InputError, "page shape"):
            self.session.review_record(record["id"], {"custom_id": "MANUAL", "custom_score": "55"}, ["custom_id", "custom_score"], "Fictional reviewer", True)

    def test_rules_allowlist_geometry_and_blank_projects(self):
        blank = self.folder / "blank.json"
        self.session.save_project(blank)
        self.session.open_project(blank)
        self.assertEqual(self.session.phase, "empty")
        self.session.add_document(fictional_pdf("CUSTOM-A", 7), "fictional-first.pdf")
        definition = compile_draft(draft_for(self.session))
        for altered in ({**definition, "sourceData": "not allowed"},
                        {**definition, "fields": [{**definition["fields"][0], "values": "not allowed"}]}):
            with self.assertRaises(InputError):
                parse_form_type(altered)
        self.assertEqual(normalized_drag((212, 112), (2, 2), 200, 100, 2), {"page": 2, "x": 0, "y": 0, "width": 1, "height": 1})
        with self.assertRaises(InputError):
            normalized_drag((20, 20), (22, 22), 200, 100, 1)

    def test_project_cannot_remove_geometry_to_bypass_mask_guards(self):
        self.commit_first()
        project = json.loads(self.session.project_bytes())
        project["formType"] = None
        path = self.folder / "missing-geometry.json"
        path.write_text(json.dumps(project))
        self.session.open_project(path)
        record = self.session.workspace.records[0]
        self.assertTrue(record["formTypeIssues"])
        self.assertEqual(set(record["values"].values()), {""})
        with self.assertRaisesRegex(InputError, "page geometry"):
            self.session.review_record(record["id"], {"custom_id": "ATTEMPT", "custom_score": "7"}, ["custom_id", "custom_score"], "Fictional reviewer", True)
        # Legacy projects remain readable, but region use needs explicit geometry.
        project["format"] = "formbridge-project-v1"
        project.pop("formType")
        project.pop("draft")
        path.write_text(json.dumps(project))
        self.session.open_project(path)
        self.assertTrue(self.session.workspace.records[0]["formTypeIssues"])
        self.session.set_schema([{"name": "manual_id", "type": "text", "label": "Manual ID"}])
        self.assertEqual(self.session.workspace.records[0]["formTypeIssues"], [])

    def test_cancelled_apply_preserves_committed_type_and_edit_draft(self):
        self.commit_first()
        self.session.start_design()
        draft = self.session.snapshot()["draft"]
        draft["name"] = "Unapplied replacement"
        self.session.replace_draft(draft)
        before = self.session.snapshot()
        self.session._cancel.set()
        with self.assertRaisesRegex(InputError, "cancelled"):
            self.session.apply_draft()
        self.assertEqual(self.session.snapshot(), before)

    def test_keyboard_percentages_and_drag_share_the_same_geometry(self):
        typed = percentage_region("2", "10", "20", "30", "40", 2)
        dragged = normalized_drag((112, 212), (412, 612), 1000, 1000, 2)
        self.assertEqual(typed, dragged)
        self.assertEqual(validate_region(typed), typed)

    def test_keyboard_coordinates_reject_wrong_pages_and_invalid_rectangles(self):
        for coordinates in (("3", "10", "20", "30", "40"), ("1", "90", "20", "30", "40"),
                            ("1", "10", "20", "0", "40"), ("1", "NaN", "20", "30", "40"),
                            ("1", "10", "20", "30", "-4"), ("1", "10", "20", "infinity", "40")):
            with self.subTest(coordinates=coordinates), self.assertRaises(InputError):
                percentage_region(*coordinates, 2)


if __name__ == "__main__":
    unittest.main()
