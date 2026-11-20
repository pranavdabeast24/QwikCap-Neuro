"""PACE desktop commands keep grouping and source corrections explicit."""
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from desktop import DesktopApp


class Value:
    def __init__(self, value="", **_kwargs):
        self.value = value

    def set(self, value):
        self.value = value

    def get(self):
        return self.value


class PaceAutoUiTests(unittest.TestCase):
    def test_new_window_initializes_pace_before_reading_its_first_snapshot(self):
        session = Mock()
        session.snapshot.return_value = {"profile": "pace-auto-v1"}
        with patch("desktop.DesktopSession", return_value=session), patch("desktop.tk.StringVar", Value), patch(
            "desktop.tk.BooleanVar", Value
        ), patch("desktop.threading.Thread"), patch.object(DesktopApp, "_setup_style"), patch.object(
            DesktopApp, "_build"
        ), patch.object(DesktopApp, "_build_menu"), patch.object(DesktopApp, "_render"):
            app = DesktopApp(Mock())
        self.assertEqual([call[0] for call in session.method_calls[:2]], ["use_pace_auto_profile", "snapshot"])
        self.assertEqual(app.snapshot["profile"], "pace-auto-v1")

    def test_adding_pdfs_proposes_groups_before_adding_patient_rows(self):
        app = DesktopApp.__new__(DesktopApp)
        app.snapshot = {"profile": "pace-auto-v1", "pendingPatientGroups": [{"id": "g1"}]}
        app.session = Mock()
        app.session.import_pace_documents.return_value = {"added": [], "failed": [], "groups": [{"id": "g1"}]}
        app.show_pace_groups = Mock()
        app.status = Value()
        app._submit = lambda _title, action, callback: callback(action())
        paths = ("fictional-a.pdf", "fictional-b.pdf")
        app._import_paths(paths)
        app.session.import_pace_documents.assert_called_once_with(paths)
        app.session.import_documents.assert_not_called()
        app.session.confirm_pace_groups.assert_not_called()
        app.show_pace_groups.assert_called_once()

    def test_automatic_pace_menu_keeps_generic_schema_controls_hidden(self):
        app = DesktopApp.__new__(DesktopApp)
        app.snapshot = {"profile": "pace-auto-v1"}
        app.root, app.advanced_var = Mock(), Mock()
        app.busy = app.closing = False
        menus = []
        def menu(*_args, **_kwargs):
            result = Mock()
            menus.append(result)
            return result
        with patch("desktop.tk.Menu", side_effect=menu):
            app._build_menu()
        labels = [call.kwargs.get("label") for item in menus for call in item.add_command.call_args_list]
        for label in ("Design masks", "Draw new field", "Load extraction type…", "Use selected field as record identifier",
                      "Read NEU clinic forms", "Read SIH clinic forms", "Use categories as columns"):
            self.assertNotIn(label, labels)
        for label in ("PACE automatic review", "Study fields…", "Redraw answer area", "Save form layout…", "Load form layout…"):
            self.assertIn(label, labels)

    def test_source_redraw_keeps_the_canonical_field_and_revision(self):
        app = DesktopApp.__new__(DesktopApp)
        app.pace_redraw_target = ("patient1", "headaches_yn", 7)
        app.selected_record, app.selected_field = "patient1", "headaches_yn"
        app.design_tool = "pace-redraw"
        app.canvas, app.session = Mock(), Mock()
        app.status = Value()
        app._submit = lambda _title, action, callback: callback(action())
        region = {"page": 2, "x": .1, "y": .2, "width": .6, "height": .1}
        app._apply_pace_region(region)
        app.session.correct_pace_field.assert_called_once_with("patient1", "headaches_yn", region, expected_revision=7)
        app.session.replace_draft.assert_not_called()
        app.session.set_schema.assert_not_called()
        self.assertIsNone(app.pace_redraw_target)
        self.assertIsNone(app.design_tool)

    def test_patient_proposal_cannot_be_added_before_explicit_source_check(self):
        app = DesktopApp.__new__(DesktopApp)
        app.snapshot = {"profile": "pace-auto-v1", "pendingPatientGroups": [{"id": "group1", "mrn": "000042",
            "firstName": "Fictional", "lastName": "Example", "dob": "1980-01-01", "filenames": ["fictional.pdf"],
            "instruments": ["hit6"], "sourceCount": 1, "issues": [], "sources": []}]}
        app.busy = False
        app.patient_groups_dialog = None
        app.root, app.session, app._submit = Mock(), Mock(), Mock()
        tree = Mock()
        tree.selection.return_value = ("group1",)
        app._tree = lambda *_args, **_kwargs: (Mock(), tree)
        actions, checkboxes = {}, []
        def button(*_args, **kwargs):
            actions[kwargs.get("text")] = kwargs.get("command")
            return Mock()
        def checkbox(*_args, **kwargs):
            checkboxes.append(kwargs["variable"])
            return Mock()
        with patch("desktop.tk.Toplevel"), patch("desktop.tk.StringVar", Value), patch("desktop.tk.BooleanVar", Value), patch(
            "desktop.tk.Text"
        ), patch("desktop.tk.Canvas"), patch("desktop.ttk.Frame"), patch("desktop.ttk.Label"), patch(
            "desktop.ttk.Panedwindow"
        ), patch("desktop.ttk.Scrollbar"), patch("desktop.ttk.Button", side_effect=button), patch(
            "desktop.ttk.Checkbutton", side_effect=checkbox
        ):
            app.show_pace_groups()
            actions["Add checked patients"]()
            actions["Check patient group"]()
            app._submit.assert_not_called()
            app.session.confirm_pace_groups.assert_not_called()
            checkboxes[0].set(True)
            actions["Check patient group"]()
            actions["Add checked patients"]()
        self.assertEqual(app._submit.call_count, 1)
        app._submit.call_args.args[1]()
        app.session.confirm_pace_groups.assert_called_once_with(["group1"], confirmed_identity=True)

    def test_redraw_abstains_when_the_selected_field_changed(self):
        app = DesktopApp.__new__(DesktopApp)
        app.pace_redraw_target = ("patient1", "headaches_yn", 7)
        app.selected_record, app.selected_field = "patient1", "patient_dob"
        app.design_tool = "pace-redraw"
        app.canvas, app.session, app._submit = Mock(), Mock(), Mock()
        app.status = Value()
        app._apply_pace_region({"page": 2, "x": .1, "y": .2, "width": .6, "height": .1})
        app._submit.assert_not_called()
        self.assertIn("intended field", app.status.get())

    def test_pace_choices_offer_only_the_canonical_codes(self):
        app = DesktopApp.__new__(DesktopApp)
        app.snapshot = {"profile": "pace-auto-v1", "schema": [{"name": "headaches_yn", "label": "Headaches?",
            "type": "choice", "required": False, "choices": {"1": "Yes", "0": "No"}}]}
        app.selected_field = "headaches_yn"
        app.review_values, app.review_confirmed = {"headaches_yn": "1"}, set()
        app.entry, app.choice, app.confirm_check = Mock(), Mock(), Mock()
        app.field_title, app.value_var, app.confirm_var, app.field_detail = Value(), Value(), Value(), Value()
        app._record = lambda: {"sourceContext": {}}
        app._refresh_presentation = Mock()
        with patch("desktop.validate_values", return_value={}):
            app._show_field()
        app.choice.configure.assert_called_once_with(values=["", "Yes (1)", "No (0)"], state="readonly")
        self.assertEqual(app.value_var.get(), "Yes (1)")

    def test_new_project_restores_automatic_pace_defaults(self):
        app = DesktopApp.__new__(DesktopApp)
        app.session = Mock()
        app._guard_unsaved = lambda action: action()
        app._submit = lambda _title, action: action()
        app.new_project()
        self.assertEqual([call[0] for call in app.session.method_calls], ["reset", "use_pace_auto_profile"])


if __name__ == "__main__":
    unittest.main()
