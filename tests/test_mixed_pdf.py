"""Mixed-content PDF regressions built entirely from synthetic in-memory data."""
from __future__ import annotations

import io
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

import pipeline


SCHEMA = [
    {"name": "study_id", "label": "Study ID", "required": True},
    {"name": "sample_count", "label": "Sample count", "type": "integer", "required": True},
    {"name": "study_arm", "label": "Study arm", "required": True},
]
EXPECTED = {"study_id": "SYN-042", "sample_count": "24", "study_arm": "Control"}


def synthetic_pdf(*, native_labels: bool = False, native_lines: tuple[str, ...] = (), include_raster: bool = False) -> bytes:
    """A native heading plus raster answers, with optional native field labels."""
    output = io.BytesIO()
    document = canvas.Canvas(output, pagesize=(612, 792))
    document.setFont("Helvetica-Bold", 18)
    document.drawString(40, 744, "Synthetic study worksheet")
    for index, text in enumerate(native_lines):
        document.setFont("Helvetica", 14)
        document.drawString(40, 700 - index * 36, text)
    if not native_lines or include_raster:
        image = Image.new("RGB", (1064, 360), "white")
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default(size=38)
        for index, (label, value) in enumerate(zip(("Study ID", "Sample count", "Study arm"), EXPECTED.values())):
            draw.text((0 if native_labels else 20, 25 + index * 105), value if native_labels else f"{label}: {value}", fill="black", font=font)
            if native_labels:
                document.setFont("Helvetica", 19)
                document.drawString(40, 641 - index * 52.5, f"{label}:")
        document.drawImage(ImageReader(image), 230 if native_labels else 40, 490, width=532, height=180)
        image.close()
    document.showPage()
    document.save()
    return output.getvalue()


def ocr_lines(*texts: str) -> list[dict]:
    lines = []
    for index, text in enumerate(texts):
        words = []
        x = 0.065
        for token in text.split():
            width = len(token) * 0.012
            words.append({"text": token, "x": x, "y": 0.105 + index * 0.05, "width": width, "height": 0.02})
            x += width + 0.012
        lines.append(pipeline._line(words))
    return lines


class MixedPdfTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.assets = Path(self.temporary.name)

    def process(self, data: bytes, schema: list | None = None):
        return pipeline.process_document(data, "synthetic-mixed.pdf", SCHEMA if schema is None else schema, self.assets, "synthetic-mixed")

    def test_actual_mixed_pdf_recovers_raster_labels_and_answers(self):
        if not pipeline.capabilities()["ocrDetected"]:
            self.skipTest("No local OCR engine detected")
        result = self.process(synthetic_pdf())
        self.assertEqual(result["values"], EXPECTED)
        self.assertEqual(result["issues"], [])
        self.assertEqual(len(result["pages"]), 1)
        for evidence in result["evidence"].values():
            self.assertIn(evidence["method"], {"apple-vision", "tesseract"})
            self.assertEqual(evidence["page"], 1)
            self.assertTrue(0.10 < evidence["region"]["y"] < 0.40)
            self.assertGreater(evidence["region"]["width"], 0)
            self.assertGreater(evidence["region"]["height"], 0)

    def test_actual_mixed_pdf_recovers_raster_answers_beside_native_labels(self):
        if not pipeline.capabilities()["ocrDetected"]:
            self.skipTest("No local OCR engine detected")
        result = self.process(synthetic_pdf(native_labels=True))
        self.assertEqual(result["values"], EXPECTED)
        self.assertEqual(result["issues"], [])
        for evidence in result["evidence"].values():
            self.assertIn(evidence["method"], {"apple-vision", "tesseract"})
            self.assertEqual(evidence["page"], 1)
            self.assertTrue(0.10 < evidence["region"]["y"] < 0.40)

    def test_resolved_native_fields_including_zero_code_do_not_call_ocr(self):
        schema = [{"name": "study_arm", "label": "Study arm", "choices": {"0": "Control", "1": "Active"}}]
        with patch.object(pipeline, "_ocr") as ocr:
            result = self.process(synthetic_pdf(native_lines=("Study arm: Control",)), schema)
        ocr.assert_not_called()
        self.assertEqual(result["values"], {"study_arm": "0"})
        self.assertEqual(result["evidence"]["study_arm"]["method"], "pdf-text")
        self.assertEqual(result["issues"], [])

    def test_equal_native_and_ocr_regions_do_not_duplicate_answers(self):
        schema = [
            {"name": "study_id", "label": "Study ID", "region": {"page": 1, "x": 0, "y": 0.09, "width": 1, "height": 0.045}},
            {"name": "sample_count", "label": "Sample count", "required": True},
        ]
        with patch.object(pipeline, "_ocr", return_value=(ocr_lines("Study ID: SYN-042", "Sample count: 24"), "apple-vision", None)) as ocr:
            result = self.process(synthetic_pdf(native_lines=("Study ID: SYN-042",), include_raster=True), schema)
        self.assertEqual(ocr.call_count, 1)
        self.assertEqual(result["values"], {"study_id": "SYN-042", "sample_count": "24"})
        self.assertEqual(result["evidence"]["study_id"]["method"], "pdf-text")
        self.assertEqual(result["evidence"]["sample_count"]["method"], "apple-vision")
        self.assertEqual(result["sourceText"].count("Study ID: SYN-042"), 1)
        self.assertEqual(len(result["pages"]), 1)
        self.assertEqual(result["issues"], [])

    def test_different_native_and_ocr_values_stay_blank_with_source_methods(self):
        schema = SCHEMA[:2]
        with patch.object(pipeline, "_ocr", return_value=(ocr_lines("Study ID: SYN-999", "Sample count: 24"), "apple-vision", None)):
            result = self.process(synthetic_pdf(native_lines=("Study ID: SYN-042",), include_raster=True), schema)
        self.assertEqual(result["values"], {"study_id": "", "sample_count": "24"})
        self.assertNotIn("study_id", result["evidence"])
        self.assertTrue(any("study_id: Multiple different" in issue and "apple-vision, pdf-text" in issue for issue in result["issues"]))

    def test_ocr_lost_separator_does_not_hide_disagreement_with_native_value(self):
        with patch.object(pipeline, "_ocr", return_value=(ocr_lines("Study ID SYN-999", "Sample count: 24"), "apple-vision", None)):
            result = self.process(synthetic_pdf(native_lines=("Study ID: SYN-042",), include_raster=True), SCHEMA[:2])
        self.assertEqual(result["values"]["study_id"], "")
        self.assertTrue(any("Multiple different" in issue for issue in result["issues"]))

    def test_optional_native_blank_does_not_trigger_ocr(self):
        schema = [{"name": "study_arm", "label": "Study arm", "choices": {"0": "Control", "1": "Active"}}, {"name": "notes", "label": "Notes"}]
        with patch.object(pipeline, "_ocr") as ocr:
            result = self.process(synthetic_pdf(native_lines=("Study arm: Control", "Notes:")), schema)
        ocr.assert_not_called()
        self.assertEqual(result["values"], {"study_arm": "0", "notes": ""})
        self.assertEqual(result["issues"], [])

    def test_optional_mixed_blank_gets_one_fallback_and_stays_unconfirmed(self):
        schema = [
            {"name": "study_arm", "label": "Study arm", "choices": {"0": "Control", "1": "Active"}},
            {"name": "notes", "label": "Notes"},
        ]
        with patch.object(pipeline, "_tesseract_path", return_value=None), patch.object(pipeline, "_vision_available", return_value=False), patch.object(pipeline, "_ocr", wraps=pipeline._ocr) as ocr:
            result = self.process(synthetic_pdf(native_lines=("Study arm: Control", "Notes:"), include_raster=True), schema)
        self.assertEqual(ocr.call_count, 1)
        self.assertEqual(result["values"], {"study_arm": "0", "notes": ""})
        self.assertNotIn("notes", result["evidence"])
        self.assertEqual(result["evidence"]["study_arm"]["method"], "pdf-text")
        self.assertTrue(any("Local OCR is unavailable" in issue and "manual entry remains available" in issue for issue in result["issues"]))

    def test_unavailable_mixed_pdf_ocr_keeps_native_text_and_manual_entry(self):
        with patch.object(pipeline, "_tesseract_path", return_value=None), patch.object(pipeline, "_vision_available", return_value=False):
            result = self.process(synthetic_pdf())
        self.assertEqual(result["values"], dict.fromkeys(EXPECTED, ""))
        self.assertEqual(result["evidence"], {})
        self.assertIn("Synthetic study worksheet", result["sourceText"])
        self.assertTrue(any("mixed-content OCR fallback" in issue and "manual entry remains available" in issue for issue in result["issues"]))
        self.assertEqual(sum("Required field was not found" in issue for issue in result["issues"]), 3)

    def test_mixed_pdf_empty_region_retry_keeps_page_coordinates_and_method(self):
        schema = [{"name": "sample_count", "label": "Sample count", "type": "integer", "required": True, "region": {"page": 1, "x": 0.1, "y": 0.2, "width": 0.3, "height": 0.05}}]
        heading = pipeline._line([{"text": "Synthetic", "x": 0.05, "y": 0.04, "width": 0.2, "height": 0.02}])
        crop_value = pipeline._line([{"text": "24", "x": 0.4, "y": 0.4, "width": 0.2, "height": 0.2}])
        with patch.object(pipeline, "_ocr", side_effect=[([heading], "apple-vision", None), ([crop_value], "apple-vision", None)]) as ocr:
            result = self.process(synthetic_pdf(native_lines=("Unrelated synthetic note",), include_raster=True), schema)
        self.assertEqual(ocr.call_count, 2)
        self.assertEqual(result["values"], {"sample_count": "24"})
        evidence = result["evidence"]["sample_count"]
        self.assertEqual(evidence["method"], "apple-vision")
        self.assertEqual(evidence["page"], 1)
        self.assertEqual(evidence["mapping"], "region")
        self.assertTrue(0.1 <= evidence["region"]["x"] < 0.4)
        self.assertTrue(0.2 <= evidence["region"]["y"] < 0.25)
        self.assertTrue(any(stage["stage"] == "Retry field regions" for stage in result["pipeline"]))

    def test_full_page_fallback_is_bounded_by_document_page_limit(self):
        output = io.BytesIO()
        document = canvas.Canvas(output, pagesize=(612, 792))
        raster = Image.new("RGB", (100, 40), "white")
        ImageDraw.Draw(raster).text((5, 5), "Raster answer", fill="black")
        for page in range(pipeline.MAX_PAGES):
            document.drawString(40, 744, f"Synthetic page {page + 1}")
            document.drawImage(ImageReader(raster), 40, 650, width=100, height=40)
            document.showPage()
        document.save()
        raster.close()
        with patch.object(pipeline, "_ocr", return_value=([], "apple-vision", "Local OCR found no readable text on this page.")) as ocr:
            result = self.process(output.getvalue())
        self.assertEqual(ocr.call_count, pipeline.MAX_PAGES)
        self.assertEqual(len(result["pages"]), pipeline.MAX_PAGES)


if __name__ == "__main__":
    unittest.main()
