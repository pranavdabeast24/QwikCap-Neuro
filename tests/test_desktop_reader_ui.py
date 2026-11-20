"""Reader selection and unsupported-layout guidance without a native window."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from desktop import DesktopApp
from desktop_model import DesktopSession
from pace_profile import extract, profile_schema
from server import InputError


class Value:
    def __init__(self, value=""):
        self.value = value

    def set(self, value):
        self.value = value

    def get(self):
        return self.value


class ReaderPresentationTests(unittest.TestCase):
    def app_for(self, record):
        app = DesktopApp.__new__(DesktopApp)
        app.snapshot = {"profile": "pace-printed-v1", "schema": profile_schema()}
        app.selected_field = "record_id"
        app.review_values = dict(record["values"])
        app.review_confirmed = set()
        app._record = lambda: record
        app._refresh_presentation = Mock()
        app._reset_gesture = Mock()
        app._resize_after = None
        for name in ("field_title", "value_var", "confirm_var", "field_detail", "record_title",
                     "record_context", "page_label", "source_issues"):
            setattr(app, name, Value())
        for name in ("entry", "choice", "confirm_check", "canvas", "bundle_sources_button",
                     "source_text", "page_yscroll", "page_xscroll", "record_context_label"):
            setattr(app, name, Mock())
        return app

    def test_unsupported_layout_explains_reader_recovery_and_keeps_approval_blocked(self):
        session = DesktopSession()
        self.addCleanup(session.close)
        session.use_pace_profile()
        record = session.add_document(b"Fictional unsupported layout", "unsupported.txt")
        before = deepcopy(record)
        app = self.app_for(record)
        app._show_field()
        self.assertIn("Unsupported PACE layout", app.field_detail.get())
        self.assertIn("new PACE automatic project", app.field_detail.get())
        self.assertNotIn("first name is missing", app.field_detail.get())
        app._render_page()
        self.assertEqual(app.source_issues.get(), app.field_detail.get())
        self.assertEqual(record, before)
        with self.assertRaises(InputError):
            session.review_record(record["id"], record["values"], record["applicableFields"],
                                  "Synthetic reviewer", True)

    def test_recognized_source_identity_errors_are_not_replaced_with_layout_guidance(self):
        output = extract([{"page": 1, "method": "pdf-text", "lines": [{"text": "Fictional unsupported layout"}]}])
        record = {**output, "filename": "fictional.txt", "sourceText": "Fictional source", "pages": []}
        record["sourceContext"]["instruments"] = ["patient_records"]
        record["sourceContext"]["instrumentStarts"] = [{"instrument": "patient_records", "page": 1}]
        app = self.app_for(record)
        app._show_field()
        self.assertIn("record ID", app.field_detail.get())
        self.assertNotIn("Unsupported PACE layout", app.field_detail.get())
        app._render_page()
        self.assertIn("Printed sources", app.source_issues.get())

    def test_only_automatic_pace_reader_is_selectable_from_the_menu(self):
        session = DesktopSession()
        self.addCleanup(session.close)
        app = DesktopApp.__new__(DesktopApp)
        app.root, app.advanced_var = Mock(), Mock()
        app.session = session
        app.busy = app.closing = False
        app._confirm_schema_change = lambda: True
        app._with_draft = lambda action: action()
        app._submit = lambda _title, action: action()
        menus = []
        def menu(*_args, **_kwargs):
            result = Mock()
            menus.append(result)
            return result
        with patch("desktop.tk.Menu", side_effect=menu):
            app._build_menu()
        self.assertIsNone(session.snapshot()["profile"])
        labels = [call.kwargs.get("label") for item in menus for call in item.add_command.call_args_list]
        self.assertNotIn("Read NEU clinic forms", labels)
        self.assertNotIn("Read SIH clinic forms", labels)
        self.assertNotIn("Read PACE printed forms", labels)
        choices = [call.kwargs["command"] for item in menus for call in item.add_command.call_args_list
                   if call.kwargs.get("label") == "PACE automatic review"]
        self.assertEqual(len(choices), 1)
        choices[0]()
        self.assertEqual(session.snapshot()["profile"], "pace-auto-v1")
        self.assertEqual(len(session.snapshot()["schema"]), 512)
        session.use_neurology_profile()
        self.assertEqual(session.snapshot()["profile"], "neurology-training-v1")
        self.assertEqual(len(session.snapshot()["schema"]), 45)


class PatientBundleReaderTests(unittest.TestCase):
    def app_for(self, session):
        app = DesktopApp.__new__(DesktopApp)
        app.root = Mock()
        app.busy = False
        app.bundle_dialog = None
        app.snapshot = session.snapshot()
        app._open_patient_bundle_dialog = Mock()
        return app

    def test_patient_readers_open_the_pdf_picker_and_pass_selected_sources_to_the_dialog(self):
        for reader in ("use_sih_clinic_profile", "use_pace_profile"):
            with self.subTest(reader=reader):
                session = DesktopSession()
                self.addCleanup(session.close)
                getattr(session, reader)()
                app = self.app_for(session)
                before = deepcopy(app.snapshot)
                paths = ("registration.pdf", "questionnaire.pdf")
                with patch("desktop.messagebox.showinfo") as info, patch(
                    "desktop.filedialog.askopenfilenames", return_value=paths
                ) as picker:
                    app.combine_patient_pdfs()
                picker.assert_called_once_with(
                    parent=app.root, title="Choose this patient's PDFs in source order",
                    filetypes=[("PDF documents", "*.pdf")],
                )
                app._open_patient_bundle_dialog.assert_called_once_with(paths)
                info.assert_not_called()
                self.assertEqual(app.snapshot, before)

    def test_incompatible_categories_and_ordinary_records_require_a_new_project(self):
        for kind in ("neu", "custom", "clinic-ordinary", "pace-ordinary"):
            with self.subTest(kind=kind):
                session = DesktopSession()
                self.addCleanup(session.close)
                if kind == "custom":
                    session.set_schema([{"name": "record_id", "type": "text"}])
                elif kind == "neu":
                    session.use_neurology_profile()
                else:
                    getattr(session, "use_sih_clinic_profile" if kind == "clinic-ordinary" else "use_pace_profile")()
                    session.add_document(b"Fictional unsupported layout", "ordinary.txt")
                app = self.app_for(session)
                before = deepcopy(app.snapshot)
                with patch("desktop.messagebox.showinfo") as info, patch(
                    "desktop.filedialog.askopenfilenames"
                ) as picker:
                    app.combine_patient_pdfs()
                self.assertEqual(info.call_args.args[0], "Start a patient bundle project")
                self.assertIn("File > New project", info.call_args.args[1])
                picker.assert_not_called()
                app._open_patient_bundle_dialog.assert_not_called()
                self.assertEqual(app.snapshot, before)


if __name__ == "__main__":
    unittest.main()
