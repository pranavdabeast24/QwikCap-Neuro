"""Headless regression for pending editor values crossing native menu boundaries."""
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from desktop import DesktopApp
from desktop_model import DesktopSession


class EditorValue:
    def __init__(self, value, changed):
        self.value, self.changed = value, changed

    def get(self):
        return self.value

    def set(self, value):
        self.value = value
        self.changed()


class Table:
    def __init__(self):
        self.rows, self.selected, self.options = {}, (), {}

    def get_children(self):
        return tuple(self.rows)

    def delete(self, *keys):
        for key in keys:
            self.rows.pop(key, None)
        self.selected = tuple(key for key in self.selected if key in self.rows)

    def insert(self, _parent, _position, iid, values):
        self.rows[iid] = tuple(values)

    def selection(self):
        return self.selected

    def selection_set(self, key):
        self.selected = (key,)

    def exists(self, key):
        return key in self.rows

    def configure(self, **options):
        self.options.update(options)

    def heading(self, *_args, **_kwargs):
        pass

    def column(self, *_args, **_kwargs):
        pass

    def item(self, key, _option):
        return self.rows[key]


class DraftEditorBoundaryTests(unittest.TestCase):
    def test_typing_stays_pending_and_identifier_and_navigation_flush_complete_edits(self):
        session = DesktopSession()
        self.addCleanup(session.close)
        session.replace_draft({"name": "Fictional custom type", "identifierField": None,
                               "pages": [{"page": 1, "aspectRatio": .75}],
                               "fields": [{"id": "fictionalkey", "name": "original_id", "label": "Original label", "type": "text", "required": False,
                                           "region": {"page": 1, "x": .1, "y": .1, "width": .5, "height": .1}}]})
        app = DesktopApp.__new__(DesktopApp)
        app.root, app.design_help = Mock(), Mock()
        app.busy = app.closing = app._rendering = app._draft_unsent = app._choices_error = False
        app._draft_after = app.design_start = None
        app.design_selected = "fictionalkey"
        app.design_draft = session.snapshot()["draft"]
        app._show_choice_settings = Mock()
        for attribute, value in (("type_name", "Fictional custom type"), ("design_name", "original_id"),
                                 ("design_label", "Original label"), ("design_kind", "text"),
                                 ("design_required", False), ("design_identifier", False), ("design_choices", "")):
            setattr(app, attribute, EditorValue(value, app._design_changed))
        # Execute the same queued model mutation and completion callback synchronously.
        def submit(_title, function, callback=None):
            result = function()
            if callback:
                callback(result)
        app._submit = submit
        app.session = session
        app.design_name.set("renamed_id")
        app.design_label.set("Edited identifier label")
        self.assertEqual(session.draft["fields"][0]["name"], "original_id")
        app.root.after.assert_not_called()
        app.use_selected_identifier()
        self.assertEqual(session.draft["fields"][0]["name"], "renamed_id")
        self.assertEqual(session.draft["fields"][0]["label"], "Edited identifier label")
        self.assertEqual(session.draft["identifierField"], "fictionalkey")
        self.assertFalse(app._draft_unsent)
        app.design_label.set("Final pending label")
        app.editor_dirty = False
        app._record = lambda: None
        app.snapshot = {"reviewer": ""}
        app.reviewer_var = EditorValue("", lambda: None)
        observed = []
        app._with_draft(lambda: observed.append(session.draft["fields"][0]["label"]))
        self.assertEqual(observed, ["Final pending label"])
        self.assertFalse(app._draft_unsent)

    def test_choice_json_keeps_semicolons_equals_and_exact_codes(self):
        app = DesktopApp.__new__(DesktopApp)
        app._rendering = False
        app.design_selected = "selected"
        app.design_draft = {"name": "Example", "identifierField": None, "fields": [{"id": "selected", "name": "answer", "type": "date", "sourceDateFormat": "mdy"}]}
        app._show_choice_settings = Mock()
        app.design_help = Mock()
        for attribute, value in (("type_name", "Example"), ("design_name", "answer"), ("design_label", "Answer"), ("design_kind", "choice"),
                                 ("design_required", False), ("design_identifier", False), ("design_choices", '{"0":"None; no symptoms","2":"A=B"}')):
            setattr(app, attribute, EditorValue(value, lambda: None))
        app._design_changed()
        self.assertEqual(app.design_draft["fields"][0]["choices"], {"0": "None; no symptoms", "2": "A=B"})
        self.assertNotIn("sourceDateFormat", app.design_draft["fields"][0])
        self.assertFalse(app._choices_error)
        app.design_choices.set('{"0":"First","0":"Second"}')
        app._design_changed()
        self.assertTrue(app._choices_error)


class StudyFieldUiTests(unittest.TestCase):
    @staticmethod
    def value(value):
        return EditorValue(value, lambda: None)

    def test_catalog_filters_by_exact_instrument_and_reports_missing_masks(self):
        app = DesktopApp.__new__(DesktopApp)
        app.catalog_window = Mock()
        app.catalog_window.winfo_exists.return_value = True
        app.catalog_tree = Table()
        app.catalog_selected = None
        app.catalog_instrument_combo = Mock()
        app.catalog_query = self.value("score")
        app.catalog_instrument = self.value("Follow-up")
        app.catalog_count = self.value("")
        app._catalog_selected = Mock()
        app.snapshot = {"schema": [], "expectedFields": [{"name": "score", "label": "Score", "instrument": "baseline"},
                                                        {"name": "score_v2", "label": "Score", "instrument": "followup"}],
                        "expectedInstruments": [{"name": "baseline", "label": "Baseline"}, {"name": "followup", "label": "Follow-up"}]}
        app.design_draft = {"fields": [{"name": "score_v2", "id": "chosen"}]}
        app._refresh_catalog()
        self.assertEqual(app.catalog_tree.rows, {"score_v2": ("score_v2", "Score", "Needs mask")})
        self.assertIn("1 of 2 fields", app.catalog_count.get())

    def test_preview_pages_keep_zero_one_and_blank_values(self):
        app = DesktopApp.__new__(DesktopApp)
        names = [f"column_{index}" for index in range(25)]
        values = {name: "" for name in names}
        values.update(column_0="0", column_1="1", column_24="last")
        app.snapshot = {"template": {"columns": [{"name": name} for name in names]},
                        "templatePreview": {"rows": [{"id": "record", "status": "review", "values": values}]}}
        app.preview_tree = Table()
        app.preview_offset = 0
        app.preview_range = self.value("")
        app.selected_record = "record"
        app._render_template_preview()
        self.assertEqual(len(app.preview_tree.options["columns"]), 13)
        self.assertEqual(app.preview_tree.rows["record"][:4], ("Draft", "0", "1", ""))
        app.move_preview_columns(1)
        self.assertIn("13 through 24 of 25", app.preview_range.get())
        app.move_preview_columns(1)
        self.assertEqual(app.preview_tree.rows["record"], ("Draft", "last"))
        app.move_preview_columns(1)
        self.assertEqual(app.preview_offset, 24)
        self.assertEqual(len(app.snapshot["template"]["columns"]), 25)

    def test_destination_search_and_assignment_filter_keep_full_template(self):
        app = DesktopApp.__new__(DesktopApp)
        app.snapshot = {"schema": [{"name": "answer", "label": "Answer"}], "records": [],
                        "template": {"columns": [{"name": "record_id"}, {"name": "score_one"}, {"name": "score_two"}]},
                        "templatePreview": {"rows": []}}
        app.destination_tree, app.preview_tree = Table(), Table()
        app.destination_query = self.value("score")
        app.destination_filter = self.value("Unassigned")
        app.mappings = {"record_id": "answer", "score_one": None}
        app._destination_selected = Mock()
        app._refresh_destinations()
        self.assertEqual(app.destination_tree.rows, {"dest2": ("score_two", "Unassigned", "")})
        app.destination_filter.set("Leave blank")
        app._refresh_destinations()
        self.assertEqual(app.destination_tree.rows, {"dest1": ("score_one", "Leave blank", "")})
        self.assertEqual(len(app.snapshot["template"]["columns"]), 3)

    def test_bulk_blank_requires_explicit_confirmation_and_current_revision(self):
        app = DesktopApp.__new__(DesktopApp)
        app.root = Mock()
        app.busy = False
        app.snapshot = {"template": {"revision": 7, "columns": [{"name": "record_id"}, {"name": "score"}, {"name": "optional"}]}}
        app.mappings = {"record_id": "record_id"}
        app.session = Mock()
        app._with_draft = lambda action: action()
        app._submit = lambda _title, action: action()
        with patch("desktop.messagebox.askyesno", return_value=False):
            app.leave_remaining_columns_blank()
        app.session.leave_remaining_columns_blank.assert_not_called()
        with patch("desktop.messagebox.askyesno", return_value=True) as ask:
            app.leave_remaining_columns_blank()
        self.assertIn("remaining 2", ask.call_args.args[1])
        app.session.leave_remaining_columns_blank.assert_called_once_with(7)


class PatientBundleUiTests(unittest.TestCase):
    @staticmethod
    def value(value):
        return EditorValue(value, lambda: None)

    def test_source_order_rows_show_filenames_and_preserve_full_paths(self):
        app = DesktopApp.__new__(DesktopApp)
        paths = ["/fictional/long/common/source/folder/baseline.pdf",
                 "/fictional/long/common/source/folder/assessment.pdf"]
        app.bundle_paths = list(paths)
        app.bundle_tree = Table()
        app._refresh_bundle_sources(1)
        self.assertEqual(app.bundle_tree.rows, {"source0": (1, "baseline.pdf"), "source1": (2, "assessment.pdf")})
        self.assertEqual(app.bundle_paths, paths)
        self.assertEqual(app.bundle_tree.selection(), ("source1",))

    def test_reordering_sources_clears_same_patient_and_order_confirmation(self):
        app = DesktopApp.__new__(DesktopApp)
        app.bundle_paths = ["baseline.pdf", "assessment.pdf", "followup.pdf"]
        app.bundle_tree = Table()
        app.bundle_confirmation = self.value(True)
        app._refresh_bundle_sources(1)
        app._move_bundle_source(-1)
        self.assertEqual(app.bundle_paths, ["assessment.pdf", "baseline.pdf", "followup.pdf"])
        self.assertFalse(app.bundle_confirmation.get())
        self.assertEqual(app.bundle_tree.selection(), ("source0",))
        app._move_bundle_source(-1)
        self.assertEqual(app.bundle_paths, ["assessment.pdf", "baseline.pdf", "followup.pdf"])

    def test_bundle_submit_requires_identifier_and_explicit_confirmation(self):
        app = DesktopApp.__new__(DesktopApp)
        app.busy = False
        app.bundle_dialog = Mock()
        app.bundle_record_id = self.value("")
        app.bundle_confirmation = self.value(False)
        app.bundle_error = self.value("")
        app.bundle_paths = ["baseline.pdf", "followup.pdf"]
        app.session = Mock()
        app._with_draft = lambda action: action()
        app._submit = lambda _title, action, _complete: action()
        app._submit_patient_bundle()
        self.assertIn("study record_id", app.bundle_error.get())
        app.session.add_patient_bundle.assert_not_called()
        app.bundle_record_id.set("Fictional-001")
        app._submit_patient_bundle()
        self.assertIn("confirmation box", app.bundle_error.get())
        app.session.add_patient_bundle.assert_not_called()
        app.bundle_confirmation.set(True)
        app._submit_patient_bundle()
        app.session.add_patient_bundle.assert_called_once_with(("baseline.pdf", "followup.pdf"), "Fictional-001", confirmed_same_patient=True)
        self.assertIsNone(app.bundle_dialog)

    def test_existing_ordinary_records_are_kept_and_bundle_projects_can_add_patients(self):
        app = DesktopApp.__new__(DesktopApp)
        app.busy = False
        app.bundle_dialog = None
        app.root = Mock()
        app.snapshot = {"schema": [], "records": [{"id": "ordinary"}], "draft": {"fields": []}}
        app._open_patient_bundle_dialog = Mock()
        with patch("desktop.messagebox.showinfo") as info, patch("desktop.filedialog.askopenfilenames") as picker:
            app.combine_patient_pdfs()
        info.assert_called_once()
        picker.assert_not_called()
        self.assertEqual(app.snapshot["records"], [{"id": "ordinary"}])
        app.snapshot = {"schema": [{"name": "record_id"}], "formType": {"name": "Bundle type"}, "records": [{"bundleSources": [{"filename": "prior.pdf"}]}]}
        with patch("desktop.filedialog.askopenfilenames", return_value=("next.pdf",)):
            app.combine_patient_pdfs()
        app._open_patient_bundle_dialog.assert_called_once_with(("next.pdf",))


if __name__ == "__main__":
    unittest.main()
