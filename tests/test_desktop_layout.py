"""Native geometry regressions for the mask designer inspector."""
from pathlib import Path
from copy import deepcopy
import os
import sys
import tempfile
from types import SimpleNamespace
import tkinter as tk
from tkinter import ttk
import unittest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from desktop import DesktopApp


class DesignerLayoutTests(unittest.TestCase):
    def test_choice_inspector_keeps_mask_list_and_scrolls_settings_at_supported_sizes(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            if os.name == "nt":
                self.fail(f"Windows acceptance requires a native Tk display: {exc}")
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


class SourcePreviewLayoutTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            if os.name == "nt":
                self.fail(f"Windows acceptance requires a native Tk display: {exc}")
            self.skipTest(f"Native Tk display is unavailable: {exc}")
        self.app = DesktopApp(self.root)
        self.folder = tempfile.TemporaryDirectory()
        path = Path(self.folder.name) / "fictional-page.png"
        Image.new("RGB", (1224, 1584), "white").save(path)
        state = self.app.session.snapshot()
        state["schema"] = [{"name": "answer", "label": "Fictional answer", "type": "text", "required": False},
                           {"name": "other", "label": "Other answer", "type": "text", "required": False}]
        region = {"page": 1, "x": .1, "y": .2, "width": .3, "height": .15}
        record = {"id": "fictional", "filename": "Fictional preview.pdf", "status": "draft", "revision": 1,
                  "values": {"answer": "Example", "other": "Second"}, "confirmed": ["answer"],
                  "pages": [{"page": 1}, {"page": 2}], "pagePaths": {"1": str(path), "2": str(path)},
                  "evidence": {"answer": {"page": 1, "region": region}}, "paceIdentityConfirmed": False}
        state.update(phase="review", records=[record])
        self.app._render(state)
        self.root.update()
        self.app._render_page()

    def tearDown(self):
        if not hasattr(self, "app"):
            return
        self.app.commands.put(None)
        self.app.thread.join(timeout=1)
        self.app.session.close()
        for pending in self.root.tk.call("after", "info"):
            self.root.after_cancel(pending)
        self.root.destroy()
        self.folder.cleanup()

    def point(self, canvas, size, anchor):
        return ((canvas.canvasx(anchor[0]) - 12) / size[0], (canvas.canvasy(anchor[1]) - 12) / size[1])

    def test_source_and_review_actions_fit_supported_windows_in_procedure_order(self):
        app = self.app
        for geometry, minimum_width, minimum_rows in (("1320x850", 680, 150), ("1024x700", 390, 65)):
            with self.subTest(geometry=geometry):
                self.root.geometry(geometry)
                self.root.update()
                app._render_page()
                self.root.update_idletasks()
                self.assertGreaterEqual(app.canvas.winfo_width(), minimum_width)
                self.assertGreaterEqual(app.field_tree.winfo_height(), minimum_rows)
                self.assertGreaterEqual(app.review_field_frame.winfo_height(), minimum_rows + 15)
                self.assertLessEqual(app.review_field_frame.winfo_rooty() + app.review_field_frame.winfo_height(), app.review_editor.winfo_rooty())
                self.assertTrue(app.zoom_in_button.winfo_ismapped())
                self.assertTrue(app.zoom_out_button.winfo_ismapped())
                self.assertTrue(app.larger_view_button.winfo_ismapped())
                self.assertLess(app.check_patient_button.winfo_rooty(), app.field_tree.winfo_rooty())
                self.assertLess(app.redraw_answer_button.winfo_rooty(), app.confirm_next_button.winfo_rooty())
                self.assertLess(app.confirm_next_button.winfo_rooty(), app.reviewer_entry.winfo_rooty())
                self.assertLess(app.reviewer_entry.winfo_rooty(), app.approve_button.winfo_rooty())
                self.assertLessEqual(app.approve_button.winfo_rooty() + app.approve_button.winfo_height(), self.root.winfo_rooty() + self.root.winfo_height())
                self.assertLessEqual(app.larger_view_button.winfo_rootx() + app.larger_view_button.winfo_width(), app.canvas.winfo_rootx() + app.canvas.winfo_width())

    def test_scrolled_pointer_zoom_mask_and_same_page_render_preserve_review(self):
        app = self.app
        before = deepcopy(app.snapshot)
        app.change_zoom(2)
        app.canvas.xview_moveto(.12)
        app.canvas.yview_moveto(.22)
        anchor = (200, 170)
        point = self.point(app.canvas, app.display_size, anchor)
        app._preview_double_click(SimpleNamespace(state=0, x=anchor[0], y=anchor[1]))
        after = self.point(app.canvas, app.display_size, anchor)
        for actual, expected in zip(after, point):
            self.assertAlmostEqual(actual, expected, delta=.002)
        origin, scale = app._view_origin(app.canvas), app.viewport.scale
        app.field_tree.selection_set("other")
        app._field_selected()
        self.assertEqual(app._view_origin(app.canvas), origin)
        self.assertEqual(app.viewport.scale, scale)
        region = {"page": 1, "x": .1, "y": .2, "width": .3, "height": .15}
        x1, y1, x2, y2 = app.viewport.rectangle(region)
        captured = []
        app.design_tool = "pace-redraw"
        app.pace_redraw_target = ("fictional", "other", 1)
        app._apply_pace_region = captured.append
        app._mask_start(SimpleNamespace(x=x2 - origin[0], y=y2 - origin[1]))
        start = app.design_start
        app._preview_double_click(SimpleNamespace(state=0, x=200, y=170))
        self.assertEqual(app.design_start, start)
        app._mask_end(SimpleNamespace(x=x1 - origin[0], y=y1 - origin[1]))
        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0]["page"], 1)
        for key in ("x", "y", "width", "height"):
            self.assertAlmostEqual(captured[0][key], region[key], delta=1 / min(app.display_size))
        app.design_tool = None
        app.fit_page()
        app.change_page(1)
        self.assertEqual(app.snapshot, before)
        self.assertEqual((app.review_values, app.review_confirmed, app.editor_dirty), ({"answer": "Example", "other": "Second"}, {"answer"}, False))

    def test_manual_resize_and_page_change_keep_scale_new_record_restores_fit(self):
        app = self.app
        app.change_zoom(2)
        app.canvas.xview_moveto(.15)
        app.canvas.yview_moveto(.25)
        scale = app.viewport.scale
        origin = app._view_origin(app.canvas)
        self.root.geometry("1120x750")
        self.root.update()
        app._render_page()
        self.assertEqual(app._view_origin(app.canvas), origin)
        self.assertEqual(app.viewport.scale, scale)
        app.change_page(1)
        self.assertEqual(app.viewport.scale, scale)
        self.assertEqual(app._view_origin(app.canvas), (0, 0))
        second = deepcopy(app.snapshot["records"][0])
        second["id"] = "fictional-second"
        app.snapshot["records"].append(second)
        app._select_record("fictional-second")
        self.assertTrue(app.viewport.fit_width)
        self.assertEqual(app.display_size[0], app.canvas.winfo_width() - 24)

    def test_manual_resize_at_bottom_right_keeps_tk_clamp_without_a_second_shift(self):
        app = self.app
        self.root.geometry("1024x700")
        self.root.update()
        app._render_page()
        app.change_zoom(3)
        app.canvas.xview_moveto(1)
        app.canvas.yview_moveto(1)
        scale = app.viewport.scale
        self.root.geometry("1320x850")
        self.root.update()
        clamped = app._view_origin(app.canvas)
        app._render_page()
        self.assertEqual(app._view_origin(app.canvas), clamped)
        self.assertEqual(app.viewport.scale, scale)
        for actual, content, size in zip(clamped, app.viewport.content_size, app.viewport.viewport_size):
            self.assertAlmostEqual(actual, max(0, content - size), delta=1)

    def test_enlarged_view_fits_zooms_and_restores_only_existing_modal_grab(self):
        app = self.app
        before = deepcopy(app.snapshot)
        path = app._record()["pagePaths"]["1"]
        for nested in (False, True):
            parent = tk.Toplevel(self.root) if nested else self.root
            if nested:
                parent.grab_set()
            dialog = app._show_pace_source_page(path, "Fictional source", parent)
            self.root.update()
            frame = dialog.winfo_children()[0]
            canvas = next(widget for widget in frame.winfo_children() if isinstance(widget, tk.Canvas))
            toolbar = frame.winfo_children()[0]
            buttons = {widget.cget("text"): widget for widget in toolbar.winfo_children() if isinstance(widget, ttk.Button)}
            def image_size():
                return tuple(int(float(value)) - 24 for value in canvas.cget("scrollregion").split()[2:])
            image_width = lambda: image_size()[0]
            self.assertEqual(image_width(), canvas.winfo_width() - 24)
            buttons["＋"].invoke()
            canvas.xview_moveto(.05)
            canvas.yview_moveto(.2)
            point = self.point(canvas, image_size(), (200, 170))
            modifier = 8 if self.root.tk.call("tk", "windowingsystem") == "aqua" else 4
            canvas.event_generate("<MouseWheel>", delta=120, state=modifier, x=200, y=170)
            after = self.point(canvas, image_size(), (200, 170))
            for actual, expected in zip(after, point):
                self.assertAlmostEqual(actual, expected, delta=.003)
            buttons["Fit width"].invoke()
            self.assertEqual(image_width(), canvas.winfo_width() - 24)
            dialog.geometry("700x550")
            self.root.update()
            buttons["Fit width"].invoke()
            buttons["＋"].invoke()
            buttons["＋"].invoke()
            canvas.xview_moveto(1)
            canvas.yview_moveto(1)
            manual_size = image_size()
            dialog.geometry("1020x800")
            self.root.update()
            clamped = app._view_origin(canvas)
            ready = tk.BooleanVar()
            self.root.after(160, lambda: ready.set(True))
            self.root.wait_variable(ready)
            self.assertEqual(app._view_origin(canvas), clamped)
            self.assertEqual(image_size(), manual_size)
            buttons["Close preview"].invoke()
            self.assertEqual(self.root.grab_current(), parent if nested else None)
            if nested:
                parent.destroy()
        self.assertEqual(app.snapshot, before)


if __name__ == "__main__":
    unittest.main()
