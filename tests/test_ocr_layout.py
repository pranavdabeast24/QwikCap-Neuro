"""Configured page masks use sparse OCR without changing generic crop layout."""
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pipeline


HEADER = b"level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"


class OCRLayoutTests(unittest.TestCase):
    def process(self, schema, outputs, *, framed=False):
        image = io.BytesIO()
        with Image.new("RGB", (200, 100), "white") as source:
            if framed:
                ImageDraw.Draw(source).rectangle((20, 30, 119, 79), outline="black")
            source.save(image, "PNG")
        modes = []

        def tesseract(command, *, stdin, **options):
            self.assertEqual(command[:4], ["fictional-tesseract", "stdin", "stdout", "--psm"])
            self.assertEqual(command[5:], ["tsv"])
            self.assertEqual(options["timeout"], 45)
            self.assertTrue(stdin.read().startswith(b"\x89PNG"))
            modes.append(command[4])
            return subprocess.CompletedProcess(command, 0, stdout=HEADER + outputs[len(modes) - 1], stderr=b"")

        with tempfile.TemporaryDirectory() as folder, patch.object(pipeline, "_tesseract_path", return_value="fictional-tesseract"), patch.object(pipeline.subprocess, "run", side_effect=tesseract):
            result = pipeline.process_document(image.getvalue(), "synthetic.png", schema, Path(folder), "layout")
        return result, modes

    def test_masked_page_uses_sparse_layout_and_preserves_zero(self):
        result, modes = self.process(
            [{"name": "answer", "type": "integer", "region": {"page": 1, "x": 0.05, "y": 0.05, "width": 0.5, "height": 0.5}}],
            [b"5\t1\t1\t1\t1\t1\t20\t10\t20\t10\t99\t0\n"],
        )
        self.assertEqual(result["values"], {"answer": "0"})
        self.assertEqual(result["evidence"]["answer"]["method"], "tesseract")
        self.assertEqual(modes, ["11"])

    def test_label_only_page_keeps_block_layout(self):
        result, modes = self.process(
            [{"name": "age", "label": "Age", "type": "integer"}],
            [b"5\t1\t1\t1\t1\t1\t20\t10\t40\t10\t99\tAge:\n"
             b"5\t1\t1\t1\t1\t2\t70\t10\t20\t10\t99\t21\n"],
        )
        self.assertEqual(result["values"], {"age": "21"})
        self.assertEqual(modes, ["6"])

    def test_generic_text_region_retry_keeps_multiline_block_layout(self):
        result, modes = self.process(
            [{"name": "notes", "type": "text", "region": {"page": 1, "x": 0.1, "y": 0.3, "width": 0.5, "height": 0.5}}],
            [b"5\t1\t1\t1\t1\t1\t150\t5\t40\t10\t99\tHeading\n",
             b"5\t1\t1\t1\t1\t1\t40\t40\t30\t10\t99\tFirst\n"
             b"5\t1\t1\t1\t2\t1\t40\t70\t30\t10\t99\tSecond\n"],
        )
        self.assertEqual(result["values"], {"notes": "First\nSecond"})
        self.assertEqual(modes, ["11", "6"])

    def test_invalid_choice_is_retried_without_erasing_original_ocr(self):
        result, modes = self.process(
            [{"name": "answer", "type": "choice", "choices": {"0": "No", "1": "Yes"},
              "region": {"page": 1, "x": 0.1, "y": 0.3, "width": 0.5, "height": 0.5}}],
            [b"5\t1\t1\t1\t1\t1\t30\t40\t20\t10\t99\tO\n",
             b"5\t1\t1\t1\t1\t1\t40\t40\t30\t10\t99\t0\n"],
            framed=True,
        )
        self.assertEqual(result["values"], {"answer": "0"})
        self.assertEqual(result["sourceText"], "O\n0")
        self.assertEqual(modes, ["11", "7"])
        box = result["evidence"]["answer"]["region"]
        self.assertTrue(0.1 < box["x"] < box["x"] + box["width"] < 0.6)
        self.assertTrue(0.3 < box["y"] < box["y"] + box["height"] < 0.8)

    def test_rejecting_invalid_candidate_preserves_valid_conflict(self):
        schema = [{"name": "answer", "type": "choice", "choices": {"0": "No", "1": "Yes"},
                   "region": {"page": 1, "x": 0.1, "y": 0.3, "width": 0.5, "height": 0.5}}]
        pages = [{"page": 1, "method": "tesseract", "lines": [pipeline._line([
            {"text": text, "x": 0.2, "y": 0.4, "width": 0.1, "height": 0.1}])]} for text in ("O", "0", "1")]
        values, _, issues = pipeline._map_fields(schema, pages)
        self.assertEqual(values, {"answer": ""})
        self.assertEqual(issues, ["answer: Multiple different source values were found (tesseract); no value was selected."])

    def test_generic_text_keeps_ambiguity_between_long_and_short_readings(self):
        for region in (None, {"page": 1, "x": 0.1, "y": 0.3, "width": 0.5, "height": 0.5}):
            with self.subTest(region=region):
                field = {"name": "notes", "label": "Notes", "type": "text"}
                if region:
                    field["region"] = region
                pages = [{"page": 1, "method": "tesseract", "lines": [pipeline._line([
                    {"text": "Notes: " + text, "x": 0.2, "y": 0.4, "width": 0.1, "height": 0.1}])]} for text in ("x" * 4001, "Short note")]
                values, _, issues = pipeline._map_fields([field], pages)
                self.assertEqual(values, {"notes": ""})
                self.assertEqual(issues, ["notes: Multiple different source values were found (tesseract); no value was selected."])

    def test_frame_inset_requires_all_four_edges(self):
        with Image.new("RGB", (100, 50), "white") as image:
            draw = ImageDraw.Draw(image)
            draw.line((0, 0, 99, 0), fill="black")
            self.assertEqual(pipeline._frame_inset(image), 0)
            draw.rectangle((0, 0, 99, 49), outline="black")
            self.assertEqual(pipeline._frame_inset(image), 3)
        with Image.new("RGB", (6, 6), "black") as image:
            self.assertEqual(pipeline._frame_inset(image), 0)


if __name__ == "__main__":
    unittest.main()
