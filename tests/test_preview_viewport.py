"""Page geometry keeps source points stable and normalized masks unchanged."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from desktop import DesktopApp
from form_types import normalized_drag
from preview_viewport import PreviewViewport


class PreviewViewportTests(unittest.TestCase):
    def test_zoom_anchors_both_axes_after_scroll_using_rounded_dimensions(self):
        view = PreviewViewport((1001, 1603), (500, 400), scale=.5, fit_width=False)
        origin = view.zoom(1.25, (173, 119), (137, 281))
        self.assertEqual(view.image_size, (626, 1002))
        self.assertAlmostEqual(origin[0], 212.096)
        self.assertAlmostEqual(origin[1], 377.7581047381546)
        self.assertFalse(view.fit_width)

    def test_fit_follows_width_and_manual_resize_keeps_scale_and_current_origin(self):
        view = PreviewViewport((1000, 2000))
        view.resize((500, 400), (0, 0))
        self.assertEqual(view.image_size, (476, 952))
        view.resize((700, 500), (0, 300))
        self.assertEqual(view.image_size, (676, 1352))
        view.zoom(1.25, (350, 250), (0, 300))
        origin = view.resize((900, 700), (140, 260))
        self.assertEqual(view.image_size, (845, 1690))
        self.assertEqual(origin, (140, 260))
        origin = view.fit(origin)
        self.assertEqual(view.image_size, (876, 1752))
        self.assertEqual(origin[0], 0)
        self.assertTrue(view.fit_width)

    def test_reverse_drag_matches_overlay_at_multiple_zoom_levels(self):
        region = {"page": 2, "x": .1, "y": .2, "width": .3, "height": .15}
        view = PreviewViewport((1000, 2000), (600, 500), scale=.75, fit_width=False)
        self.assertEqual(view.rectangle(region), (87, 312, 312, 537))
        for factor in (1, 1.25, .8, 1.7):
            view.zoom(factor, (200, 200), (120, 240))
            x1, y1, x2, y2 = view.rectangle(region)
            self.assertEqual(normalized_drag((x2, y2), (x1, y1), *view.image_size, 2), region)

    def test_mouse_zoom_yields_to_drawing_without_changing_review_or_gesture(self):
        app = DesktopApp.__new__(DesktopApp)
        app.viewport = PreviewViewport((1000, 2000), (600, 500), scale=.75, fit_width=False)
        app.display_size = app.viewport.image_size
        app.review_values, app.review_confirmed = {"answer": "2"}, {"answer"}
        app.editor_dirty = False
        for tool in ("new", "redraw", "pace-redraw"):
            app.design_tool, app.design_start = tool, (112, 212)
            app._preview_double_click(SimpleNamespace(state=0, x=160, y=240))
            app.change_zoom(.8, (160, 240), mouse=True)
            self.assertEqual((app.viewport.scale, app.design_start, app.design_tool), (.75, (112, 212), tool))
        self.assertEqual((app.review_values, app.review_confirmed, app.editor_dirty), ({"answer": "2"}, {"answer"}, False))

    def test_wheel_uses_platform_modifier_and_shift_axis_and_zero_is_idle(self):
        app = DesktopApp.__new__(DesktopApp)
        app.root = Mock()
        for platform, modifier in (("aqua", 8), ("win32", 4)):
            app.root.tk.call.return_value = platform
            positions = {"x": 0, "y": 0, "scale": 1.0, "anchor": None}
            canvas = Mock()
            canvas.xview_scroll.side_effect = lambda amount, _unit: positions.update(x=positions["x"] + amount)
            canvas.yview_scroll.side_effect = lambda amount, _unit: positions.update(y=positions["y"] + amount)
            def zoom(factor, anchor):
                positions.update(scale=positions["scale"] * factor, anchor=anchor)
            for state in (0, 1, modifier):
                app._source_wheel(SimpleNamespace(delta=120, state=state, x=130, y=210), canvas, zoom)
            app._source_wheel(SimpleNamespace(delta=0, state=0), canvas, zoom)
            self.assertEqual(positions, {"x": -1 if platform == "aqua" else -3, "y": -1 if platform == "aqua" else -3, "scale": 1.25, "anchor": (130, 210)})


if __name__ == "__main__":
    unittest.main()
