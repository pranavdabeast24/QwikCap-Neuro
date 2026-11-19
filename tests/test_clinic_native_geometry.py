"""Opt-in native clinic selections and text styles with invented PDF content."""
import io
import math
from pathlib import Path
import sys
import tempfile
import unittest

import pypdfium2 as pdfium
from reportlab.pdfgen import canvas

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline import _make_pdf_pages, _pdf_geometry, _pdf_lines


def shaped_pdf(steps=32, horizontal_radius=45):
    output = io.BytesIO()
    pdf = canvas.Canvas(output, pagesize=(612, 792), invariant=1)
    path = pdf.beginPath()
    for inset in (0, 1):
        rx, ry = horizontal_radius - inset, 7 - inset
        point = lambda t: (200 + rx * math.cos(t), 600 + ry * math.sin(t))
        derivative = lambda t: (-rx * math.sin(t), ry * math.cos(t))
        path.moveTo(*point(0))
        step = 2 * math.pi / steps
        for index in range(steps):
            start, end = index * step, (index + 1) * step
            p0, p3 = point(start), point(end)
            d0, d1 = derivative(start), derivative(end)
            path.curveTo(p0[0] + step * d0[0] / 3, p0[1] + step * d0[1] / 3,
                         p3[0] - step * d1[0] / 3, p3[1] - step * d1[1] / 3, *p3)
        path.close()
    pdf.drawPath(path, stroke=0, fill=1)
    pdf.circle(500, 600, 12, stroke=0, fill=1)
    pdf.rect(100, 500, 100, 15, stroke=1, fill=0)
    pdf.roundRect(300, 500, 100, 15, 4, stroke=1, fill=0)
    opened = pdf.beginPath()
    opened.moveTo(300, 400)
    opened.curveTo(350, 415, 400, 415, 450, 400)
    pdf.drawPath(opened, stroke=1, fill=0)
    blob = pdf.beginPath()
    blob.moveTo(300, 300)
    blob.curveTo(290, 330, 450, 280, 420, 310)
    blob.curveTo(390, 280, 310, 310, 300, 300)
    blob.close()
    pdf.drawPath(blob, stroke=1, fill=0)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(40, 200, "X")
    pdf.setFont("Helvetica", 10)
    pdf.drawString(46.67, 200, "White")
    pdf.save()
    return output.getvalue()


class ClinicNativeGeometryTests(unittest.TestCase):
    def setUp(self):
        self.document = pdfium.PdfDocument(shaped_pdf())
        self.addCleanup(self.document.close)
        self.page = self.document[0]
        self.addCleanup(self.page.close)

    def test_double_contour_answer_is_opt_in_and_other_shapes_are_rejected(self):
        old = _pdf_geometry(self.page, 1224, 1584)
        self.assertNotIn("selections", old)
        clinic = _pdf_geometry(self.page, 1224, 1584, capture_clinic=True)
        self.assertEqual(clinic["controls"], old["controls"])
        self.assertEqual(clinic["rules"], old["rules"])
        self.assertEqual(len(clinic["selections"]), 1)
        ellipse = clinic["selections"][0]
        self.assertEqual(ellipse["kind"], "ellipse")
        self.assertAlmostEqual(ellipse["x"], 155 / 612, places=3)
        self.assertAlmostEqual(ellipse["width"], 90 / 612, places=3)

    def test_style_capture_separates_mark_from_printed_label_without_changing_default(self):
        ordinary = _pdf_lines(self.page, 1224, 1584)
        self.assertTrue(all("font" not in word for line in ordinary for word in line["words"]))
        styled = _pdf_lines(self.page, 1224, 1584, capture_styles=True)
        words = [word for line in styled for word in line["words"]]
        self.assertEqual([word["text"] for word in words], ["X", "White"])
        self.assertEqual([word["font"] for word in words], ["Helvetica-Bold", "Helvetica"])
        self.assertEqual(_pdf_lines(self.page, 1224, 1584), ordinary)

    def test_clinic_page_capture_exposes_candidates_and_styles_together(self):
        with tempfile.TemporaryDirectory() as folder:
            page = _make_pdf_pages(shaped_pdf(), Path(folder), capture_clinic=True)[0]
            self.assertEqual(len(page["selections"]), 1)
            self.assertTrue(all("font" in word for line in page["lines"] for word in line["words"]))

    def test_long_choice_outline_keeps_more_than_512_native_segments(self):
        document = pdfium.PdfDocument(shaped_pdf(steps=128, horizontal_radius=103.5))
        self.addCleanup(document.close)
        page = document[0]
        self.addCleanup(page.close)
        ordinary = _pdf_geometry(page, 1224, 1584)
        clinic = _pdf_geometry(page, 1224, 1584, capture_clinic=True)
        self.assertEqual(len(clinic["selections"]), 1)
        self.assertEqual(clinic["controls"], ordinary["controls"])
        self.assertAlmostEqual(clinic["selections"][0]["width"], 207 / 612, places=3)


if __name__ == "__main__":
    unittest.main()
