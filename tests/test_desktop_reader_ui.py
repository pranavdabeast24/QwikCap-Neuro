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
        self.assertIn("Read NEU clinic forms", app.field_detail.get())
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

    def test_neu_clinic_reader_is_explicitly_selectable_from_the_menu(self):
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
        choices = [call.kwargs["command"] for item in menus for call in item.add_command.call_args_list
                   if call.kwargs.get("label") == "Read NEU clinic forms"]
        self.assertEqual(len(choices), 1, "The NEU clinic reader must be reachable from the menu")
        choices[0]()
        self.assertEqual(session.snapshot()["profile"], "neurology-training-v1")
        self.assertEqual(len(session.snapshot()["schema"]), 45)


if __name__ == "__main__":
    unittest.main()
