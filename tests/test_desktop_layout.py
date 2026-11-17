"""Native geometry regressions for the mask designer inspector."""
from pathlib import Path
import sys
from types import SimpleNamespace
import tkinter as tk
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from desktop import DesktopApp


class DesignerLayoutTests(unittest.TestCase):
    def test_choice_inspector_keeps_mask_list_and_scrolls_settings_at_supported_sizes(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Native Tk display is unavailable: {exc}")
        app = None
        try:
            app = DesktopApp(root)
            app.session.replace_draft({"name": "Fictional patient bundle", "identifierField": "identifier",
                                       "pages": [{"page": 1, "aspectRatio": 612 / 792}],
                                       "fields": [{"id": "identifier", "name": "record_id", "label": "Study record ID", "type": "text", "required": True},
                                                  {"id": "sex", "name": "patient_sex", "label": "Patient Sex", "type": "choice", "required": False,
                                                   "choices": {"1": "Female", "2": "Male", "3": "Other"}}]})
            app.design_selected = "sex"
            app._render(app.session.snapshot())
            app.design_help.set("Selected study fields need masks. Select a field, then use Redraw or Add mask by coordinates. Choose a text identifier explicitly.")
            for geometry in ("1320x850", "1024x700"):
                with self.subTest(geometry=geometry):
                    root.geometry(geometry)
                    root.update()
                    app.design_canvas.yview_moveto(0)
                    root.update_idletasks()
                    self.assertGreater(app.mask_tree.winfo_height(), 50)
                    self.assertGreaterEqual(app.mask_tree.winfo_rooty(), app.design_canvas.winfo_rooty())
                    self.assertLess(app.mask_tree.winfo_rooty() + 50, app.design_canvas.winfo_rooty() + app.design_canvas.winfo_height())
                    self.assertEqual(app.mask_tree.get_children(), ("identifier", "sex"))
                    self.assertTrue(app.design_choices_entry.winfo_ismapped())
                    self.assertLess(app.design_apply_button.winfo_rooty() + app.design_apply_button.winfo_height(), root.winfo_rooty() + root.winfo_height())
                    app._reveal_design_widget(SimpleNamespace(widget=app.design_choices_entry))
                    root.update_idletasks()
                    self.assertGreaterEqual(app.design_choices_entry.winfo_rooty(), app.design_canvas.winfo_rooty() - 1)
                    self.assertLessEqual(app.design_choices_entry.winfo_rooty() + app.design_choices_entry.winfo_height(), app.design_canvas.winfo_rooty() + app.design_canvas.winfo_height() + 1)
                    app.design_canvas.yview_moveto(1)
                    root.update_idletasks()
                    self.assertAlmostEqual(app.design_canvas.yview()[1], 1.0, places=2)
                    if geometry == "1024x700":
                        self.assertGreater(app.design_canvas.yview()[0], 0)
                        self.assertTrue(app.design_scrollbar.winfo_ismapped())
        finally:
            if app is not None:
                app.commands.put(None)
                app.thread.join(timeout=1)
                app.session.close()
            for pending in root.tk.call("after", "info"):
                root.after_cancel(pending)
            root.destroy()


if __name__ == "__main__":
    unittest.main()
