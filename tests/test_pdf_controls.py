"""Native vector controls provide evidence for visible unchecked answers."""
import io
from pathlib import Path
import tempfile
import unittest

from reportlab.pdfgen import canvas

from pipeline import _make_pdf_pages


class PDFControlGeometryTests(unittest.TestCase):
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
