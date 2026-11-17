"""Headless presentation regressions using invented source metadata only."""
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from desktop import DesktopApp


class ReadabilityTests(unittest.TestCase):
    def render_queue(self, staging):
        record = {
            "id": "invented-record", "filename": "invented-medications-source.pdf",
            "status": "review", "confirmed": ["patient_mrn"],
            "values": {"patient_mrn": "FAKE-0001", "patient_name": "Fictional Person",
                       "instrument_family": "Medications", "form_date": "2026-11-12"},
        }
        state = {"profile": "neurology-training-v1" if staging else None,
                 "records": [record], "schema": [{"name": "patient_mrn"}],
                 "patientGroups": [{"conflict": False}], "dirty": False}
        app = DesktopApp.__new__(DesktopApp)
        app.selected_record = record["id"]
        app._practice_schema = state["schema"]
        for name in ("queue_tree", "mode_label", "queue_label", "reviewer_var", "project_label",
                     "_render_fields", "_render_page", "_render_spreadsheet", "_render_designer", "_refresh_catalog"):
            setattr(app, name, Mock())
        app.queue_tree.get_children.return_value = ()
        app._record = lambda: record
        DesktopApp._render(app, state)
        return app

    def test_staging_queue_has_two_readable_columns_and_preserves_group_counts(self):
        app = self.render_queue(True)
        app.queue_tree.configure.assert_any_call(columns=("document", "state"))
        app.queue_tree.configure.assert_any_call(style="StagingQueue.Treeview")
        self.assertEqual([call.args for call in app.queue_tree.heading.call_args_list],
                         [("document",), ("state",)])
        self.assertEqual([call.kwargs["text"] for call in app.queue_tree.heading.call_args_list],
                         ["Assessment", "Review"])
        assessment, review = app.queue_tree.insert.call_args.kwargs["values"]
        self.assertIn("invented", assessment.splitlines()[0])
        self.assertEqual(assessment.splitlines()[1], "Medications · 2026-11-12")
        self.assertEqual(review, "1/1")
        self.assertIn("1 MRN groups", app.queue_label.set.call_args.args[0])

    def test_generic_queue_keeps_its_existing_filename_and_review_text(self):
        app = self.render_queue(False)
        self.assertEqual(app.queue_tree.insert.call_args.kwargs["values"],
                         ("invented-medications-source.pdf", "1/1 checked"))
        app.queue_tree.configure.assert_any_call(style="Treeview")

    def test_source_scroll_actions_route_to_pdf_canvas_or_text_preview(self):
        app = DesktopApp.__new__(DesktopApp)
        app.canvas, app.source_text = Mock(), Mock()
        app._record = lambda: {"pages": ["invented-page"]}
        DesktopApp.scroll_source(app, 1)
        app.canvas.yview_scroll.assert_called_once_with(1, "pages")
        app.source_text.yview_scroll.assert_not_called()
        app._record = lambda: {"pages": []}
        DesktopApp.scroll_source(app, -1)
        app.source_text.yview_scroll.assert_called_once_with(-1, "pages")


if __name__ == "__main__":
    unittest.main()
