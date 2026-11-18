"""Native vector controls provide evidence for visible unchecked answers."""
import io
from pathlib import Path
import tempfile
import unittest

from reportlab.pdfgen import canvas

from pipeline import _make_pdf_pages


class PDFControlGeometryTests(unittest.TestCase):
    def test_nested_form_controls_follow_all_container_transforms(self):
        with tempfile.TemporaryDirectory() as folder:
            data = io.BytesIO()
            pdf = canvas.Canvas(data, pagesize=(612, 792))
            pdf.beginForm("inner")
            pdf.rect(0, 0, 10, 10, fill=0)
            pdf.circle(45, 5, 5, fill=0)
            pdf.endForm()
            pdf.beginForm("outer")
            pdf.translate(20, 30)
            pdf.doForm("inner")
            pdf.endForm()
            pdf.translate(280, 500)
            pdf.scale(1.5, 1.5)
            pdf.doForm("outer")
            pdf.save()
            page = _make_pdf_pages(data.getvalue(), Path(folder), capture_geometry=True)[0]
            self.assertEqual(len(page["controls"]), 2)
            for control, expected_x in zip(page["controls"], (317.5, 377.5)):
                self.assertAlmostEqual(control["x"] + control["width"] / 2, expected_x / 612, delta=.002)
                self.assertAlmostEqual(control["y"] + control["height"] / 2, (792 - 552.5) / 792, delta=.002)

    def test_vector_controls_survive_row_shift_and_page_rotation(self):
        for rotation in (0, 90):
            with self.subTest(rotation=rotation), tempfile.TemporaryDirectory() as folder:
                data = io.BytesIO()
                pdf = canvas.Canvas(data, pagesize=(612, 792))
                pdf.setPageRotation(rotation)
                pdf.line(40, 600, 570, 600)
                for x in (280, 330):
                    pdf.rect(x, 540, 10, 10, fill=0)
                    pdf.circle(x + 5, 510, 5, fill=0)
                # Decorations and large table cells are not answer controls.
                pdf.rect(40, 450, 530, 40, fill=0)
                for points in (((400, 540), (410, 540), (405, 550)),
                               ((425, 540), (430, 545), (425, 550), (420, 545))):
                    path = pdf.beginPath()
                    path.moveTo(*points[0])
                    for point in points[1:]:
                        path.lineTo(*point)
                    path.close()
                    pdf.drawPath(path)
                blob = pdf.beginPath()
                blob.moveTo(450, 540)
                blob.curveTo(460, 540, 460, 550, 450, 550)
                blob.curveTo(450, 548, 450, 542, 450, 540)
                blob.close()
                pdf.drawPath(blob)
                pdf.save()
                pages = _make_pdf_pages(data.getvalue(), Path(folder), capture_geometry=True)
                self.assertEqual(len(pages), 1)
                controls = pages[0]["controls"]
                self.assertEqual([c["kind"] for c in controls].count("square"), 2)
                self.assertEqual([c["kind"] for c in controls].count("circle"), 2)
                self.assertTrue(pages[0]["rules"])
                for box in controls + pages[0]["rules"]:
                    self.assertGreater(box["width"] + box["height"], 0)
                    for name in ("x", "y", "width", "height"):
                        self.assertGreaterEqual(box[name], 0)
                        self.assertLessEqual(box[name], 1)


if __name__ == "__main__":
    unittest.main()
