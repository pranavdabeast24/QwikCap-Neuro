"""Synthetic-only integration and failure behavior checks for local extraction."""
from __future__ import annotations

import io
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

import pipeline
from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas


def fictional_pdf(lines: list[str], page_count: int = 1) -> bytes:
    output = io.BytesIO()
    document = canvas.Canvas(output, pagesize=(612, 792))
    for page in range(page_count):
        document.setFont("Helvetica", 12)
        for index, text in enumerate(lines):
            document.drawString(40, 720 - index * 40, text)
        document.showPage()
    document.save()
    return output.getvalue()


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.assets = Path(self.temporary.name)

    def process(self, data: bytes, schema: list, filename: str = "fictional.pdf"):
        return pipeline.process_document(data, filename, schema, self.assets, "synthetic-test")

    def test_all_five_text_pdfs_match_all_thirty_answer_key_fields(self):
        schema = json.loads((APP / "samples/sample-schema.json").read_text())["fields"]
        records = json.loads((APP / "samples/answer-key.json").read_text())["records"]
        for index, record in enumerate(records[:5]):
            with self.subTest(file=record["file"]):
                result = pipeline.process_document((APP / "samples" / record["file"]).read_bytes(), record["file"], schema, self.assets, f"fictional-{index}")
                self.assertEqual(result["values"], {key: str(value) for key, value in record["expected"].items()})
                self.assertEqual(result["issues"], [])
                self.assertEqual({entry["method"] for entry in result["evidence"].values()}, {"pdf-text"})
                self.assertTrue((self.assets / f"fictional-{index}" / "page-1.png").is_file())

    def test_exact_labels_work_without_configured_regions(self):
        schema = json.loads((APP / "samples/sample-schema.json").read_text())["fields"]
        for field in schema:
            field.pop("region", None)
        expected = json.loads((APP / "samples/answer-key.json").read_text())["records"][0]
        result = self.process((APP / "samples" / expected["file"]).read_bytes(), schema)
        self.assertEqual(result["values"], {key: str(value) for key, value in expected["expected"].items()})

    def test_actual_scanned_pdf_uses_detected_local_ocr(self):
        if not pipeline.capabilities()["ocrDetected"]:
            self.skipTest("No local OCR executable or Apple Vision adapter detected")
        schema = json.loads((APP / "samples/sample-schema.json").read_text())["fields"]
        record = json.loads((APP / "samples/answer-key.json").read_text())["records"][5]
        result = self.process((APP / "samples" / record["file"]).read_bytes(), schema)
        if any("could not" in issue or "exceeded" in issue or "unavailable" in issue for issue in result["issues"]):
            self.skipTest("Local OCR framework is unavailable in this execution environment")
        self.assertEqual(result["values"], {key: str(value) for key, value in record["expected"].items()})
        self.assertTrue(all(item["method"] in {"apple-vision", "tesseract"} for item in result["evidence"].values()))

    def test_tesseract_reads_binary_stdin_from_unicode_image_path(self):
        folder = self.assets / "Folder with spaces 測試 Café 😀"
        folder.mkdir()
        path = folder / "fictional scan 測試.png"
        with Image.new("RGB", (200, 100), "white") as image:
            image.save(path, "PNG")
        image_bytes = path.read_bytes()
        output = (b"level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
                  b"5\t1\t1\t1\t1\t1\t20\t10\t40\t10\t99\tAge:\n"
                  b"5\t1\t1\t1\t1\t2\t70\t10\t20\t10\t99\t21\n")

        def local_tesseract(command, *, stdin, **options):
            if command[1] != "stdin":
                return subprocess.CompletedProcess(command, 1, stdout=b"", stderr=b"Cannot open Unicode filename")
            self.assertEqual(command, ["fictional-tesseract", "stdin", "stdout", "--psm", "6", "tsv"])
            self.assertEqual(stdin.read(), image_bytes)
            return subprocess.CompletedProcess(command, 0, stdout=output, stderr=b"")

        with patch.object(pipeline.subprocess, "run", side_effect=local_tesseract):
            lines = pipeline._tesseract_lines(path, 200, 100, "fictional-tesseract")
        self.assertEqual(lines, [{"text": "Age: 21", "words": [
            {"text": "Age:", "x": 0.1, "y": 0.1, "width": 0.2, "height": 0.1},
            {"text": "21", "x": 0.35, "y": 0.1, "width": 0.1, "height": 0.1}],
            "x": 0.1, "y": 0.1, "width": 0.35, "height": 0.1}])

    def test_conflicting_exact_labels_leave_value_blank(self):
        result = self.process(fictional_pdf(["Age: 21", "Age: 70"]), [{"name": "age", "label": "Age", "type": "integer"}])
        self.assertEqual(result["values"]["age"], "")
        self.assertTrue(any("Multiple different" in issue for issue in result["issues"]))

    def test_case_distinct_identifiers_are_conflicting(self):
        result = self.process(fictional_pdf(["Record ID: ABC", "Record ID: abc"]), [{"name": "record_id", "label": "Record ID", "type": "text"}])
        self.assertEqual(result["values"]["record_id"], "")
        self.assertTrue(any("Multiple different" in issue for issue in result["issues"]))

    def test_long_extracted_text_is_not_silently_truncated(self):
        result = self.process(b"Notes: " + b"x" * 4001, [{"name": "notes", "label": "Notes", "type": "text"}], filename="fictional.txt")
        self.assertEqual(result["values"]["notes"], "")
        self.assertTrue(any("4,000" in issue for issue in result["issues"]))
        self.assertEqual(len(result["evidence"]["notes"]["text"]), 4001)

    def test_large_numeric_bound_is_checked_without_float_rounding(self):
        result = self.process(b"Count: 9007199254740993", [{"name": "count", "label": "Count", "type": "integer", "max": 9007199254740992}], filename="fictional.txt")
        self.assertEqual(result["values"]["count"], "")
        self.assertTrue(any("max" in issue for issue in result["issues"]))

    def test_page_two_region_has_page_two_evidence(self):
        output = io.BytesIO()
        document = canvas.Canvas(output, pagesize=(612, 792))
        document.drawString(40, 720, "Record ID: PAGE-ONE")
        document.showPage()
        document.drawString(40, 720, "Record ID: PAGE-TWO")
        document.showPage()
        document.save()
        field = {"name": "record_id", "label": "Record ID", "type": "text", "region": {"page": 2, "x": 0, "y": 0.05, "width": 0.8, "height": 0.1}}
        result = self.process(output.getvalue(), [field])
        self.assertEqual(result["values"]["record_id"], "PAGE-TWO")
        self.assertEqual(result["evidence"]["record_id"]["page"], 2)
        self.assertEqual(len(result["pages"]), 2)

    def test_unknown_choice_does_not_guess_a_code(self):
        field = {"name": "consent", "label": "Consent", "choices": [{"value": "1", "label": "Yes"}, {"value": "0", "label": "No"}]}
        result = self.process(fictional_pdf(["Consent: Maybe"]), [field])
        self.assertEqual(result["values"]["consent"], "")
        self.assertEqual(result["evidence"]["consent"]["text"], "Maybe")
        self.assertTrue(any("does not uniquely match" in issue for issue in result["issues"]))

    def test_region_selects_second_value_instead_of_conflicting_first_value(self):
        field = {"name": "age", "label": "Age", "type": "integer", "region": {"page": 1, "x": 0, "y": 0.12, "width": 0.5, "height": 0.04}}
        result = self.process(fictional_pdf(["Age: 21", "Age: 70"]), [field])
        self.assertEqual(result["values"]["age"], "70")
        self.assertEqual(result["evidence"]["age"]["page"], 1)
        self.assertEqual(result["evidence"]["age"]["mapping"], "region")
        box = result["evidence"]["age"]["region"]
        self.assertTrue(0.12 <= box["y"] <= 0.16)

    def test_invalid_region_never_falls_back_to_global_label(self):
        field = {"name": "age", "label": "Age", "region": {"page": 1, "x": 0.9, "y": 0.1, "width": 0.5, "height": 0.1}}
        result = self.process(fictional_pdf(["Age: 21"]), [field])
        self.assertEqual(result["values"]["age"], "")
        self.assertTrue(any("region is invalid" in issue for issue in result["issues"]))

    def test_user_regular_expression_is_not_executed(self):
        field = {"name": "notes", "label": "Notes", "pattern": "(a+)+$"}
        result = self.process(fictional_pdf(["Notes: synthetic only"]), [field])
        self.assertEqual(result["values"]["notes"], "synthetic only")
        self.assertTrue(any("not executed" in issue for issue in result["issues"]))

    def test_numeric_limits_and_invalid_calendar_dates_require_review(self):
        fields = [{"name": "age", "label": "Age", "type": "integer", "min": 18, "max": 120}, {"name": "visit_date", "label": "Visit date", "type": "date"}]
        result = self.process(fictional_pdf(["Age: 140", "Visit date: 2026-02-30"]), fields)
        self.assertEqual(result["values"], {"age": "", "visit_date": ""})
        self.assertEqual(len(result["issues"]), 2)

    def test_mismatched_extension_and_signature_are_rejected(self):
        with self.assertRaisesRegex(pipeline.DocumentError, "signature"):
            self.process(fictional_pdf(["Synthetic"]), [], filename="fictional.png")

    def test_invalid_image_signature_content_is_rejected(self):
        with self.assertRaises(pipeline.DocumentError):
            self.process(b"\x89PNG\r\n\x1a\ninvalid", [], filename="fictional.png")

    def test_excess_pages_are_rejected(self):
        with self.assertRaisesRegex(pipeline.DocumentError, "32"):
            self.process(fictional_pdf(["Synthetic"], page_count=33), [])

    def test_encrypted_pdf_is_rejected(self):
        reader = PdfReader(io.BytesIO(fictional_pdf(["Synthetic"])))
        writer = PdfWriter()
        writer.append_pages_from_reader(reader)
        writer.encrypt("fictional-password")
        output = io.BytesIO()
        writer.write(output)
        with self.assertRaisesRegex(pipeline.DocumentError, "Encrypted"):
            self.process(output.getvalue(), [])

    def test_record_id_cannot_escape_asset_root(self):
        with self.assertRaisesRegex(pipeline.DocumentError, "identifier"):
            pipeline.process_document(b"Age: 21", "fictional.txt", [], self.assets, "../escape")

    def test_absent_ocr_returns_blanks_and_an_explicit_manual_review_issue(self):
        schema = [{"name": "record_id", "label": "Record ID", "required": True}]
        with patch.object(pipeline, "_tesseract_path", return_value=None), patch.object(pipeline, "_vision_available", return_value=False):
            result = self.process((APP / "samples/practice-06-scan.pdf").read_bytes(), schema)
        self.assertEqual(result["values"]["record_id"], "")
        self.assertTrue(any("Local OCR is unavailable" in issue for issue in result["issues"]))
        self.assertEqual(result["evidence"], {})


if __name__ == "__main__":
    unittest.main()
