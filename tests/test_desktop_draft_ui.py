"""Headless regression for pending editor values crossing native menu boundaries."""
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

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


if __name__ == "__main__":
    unittest.main()
