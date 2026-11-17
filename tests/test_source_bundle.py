"""Source bundles use generated fictional PDFs only."""
import base64
import copy
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, DictionaryObject, NameObject, NumberObject, TextStringObject
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import source_bundle
from source_bundle import BundleError, make_bundle


def fictional_pdf(*texts):
    output = io.BytesIO()
    pdf = canvas.Canvas(output, invariant=1)
    for text in texts:
        pdf.drawString(72, 700, text)
        pdf.showPage()
    pdf.save()
    return output.getvalue()


def document(filename, data):
    return {"filename": filename, "data": base64.b64encode(data).decode("ascii")}


def rewrite(data, change):
    writer = PdfWriter()
    writer.append(PdfReader(io.BytesIO(data)))
    change(writer)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


class SourceBundleTests(unittest.TestCase):
    def setUp(self):
        self.first = fictional_pdf("Fictional form alpha page one", "Fictional form alpha page two")
        self.second = fictional_pdf("Fictional form beta page one")
        self.payload = {"recordId": "00042-A_1.2", "documents": [document("alpha.pdf", self.first), document("beta.PDF", self.second)]}

    def test_preserves_source_order_text_bytes_and_manifest(self):
        original = copy.deepcopy(self.payload)
        result = make_bundle(self.payload)
        reader = PdfReader(io.BytesIO(base64.b64decode(result["data"])))
        self.assertEqual(len(reader.pages), 4)
        self.assertEqual([page.extract_text().strip() for page in reader.pages[1:]], ["Fictional form alpha page one", "Fictional form alpha page two", "Fictional form beta page one"])
        self.assertEqual(result["manifest"], [
            {"filename": "alpha.pdf", "sha256": hashlib.sha256(self.first).hexdigest(), "pages": 2, "firstPage": 2, "lastPage": 3},
            {"filename": "beta.PDF", "sha256": hashlib.sha256(self.second).hexdigest(), "pages": 1, "firstPage": 4, "lastPage": 4},
        ])
        self.assertEqual(self.payload, original)
        self.assertEqual(set(result), {"data", "manifest", "identifierField"})
        self.assertEqual(set(result["manifest"][0]), {"filename", "sha256", "pages", "firstPage", "lastPage"})
        text = reader.pages[0].extract_text()
        self.assertIn("No patient identity was inferred.", text)
        self.assertIn("1. Pages 2-3 | alpha.pdf", text)
        self.assertIn("2. Pages 4 | beta.PDF", text)

    def test_leading_zero_id_is_exact_and_isolated_in_declared_region(self):
        import pypdfium2 as pdfium
        result = make_bundle(self.payload)
        field = result["identifierField"]
        self.assertEqual({key: field[key] for key in ("name", "label", "type", "required")}, {"name": "record_id", "label": "Study record ID (operator-entered)", "type": "text", "required": True})
        pdf = pdfium.PdfDocument(base64.b64decode(result["data"]))
        page = pdf[0]
        text = page.get_textpage()
        try:
            region = field["region"]
            width, height = page.get_size()
            answer = text.get_text_bounded(region["x"] * width, (1 - region["y"] - region["height"]) * height, (region["x"] + region["width"]) * width, (1 - region["y"]) * height)
            self.assertEqual(answer.strip(), "00042-A_1.2")
            self.assertEqual(text.get_text_range().count("00042-A_1.2"), 1)
        finally:
            text.close()
            page.close()
            pdf.close()

    def test_deterministic_bundle_and_full_length_id(self):
        self.payload["recordId"] = "0" + "A" * 79
        first = make_bundle(self.payload)
        self.assertEqual(first, make_bundle(self.payload))
        self.assertIn(self.payload["recordId"], PdfReader(io.BytesIO(base64.b64decode(first["data"]))).pages[0].extract_text())

    def test_sixteen_long_names_show_bounded_previews_and_preserve_full_manifest(self):
        import pypdfium2 as pdfium
        names = [f"form_{index:02}_" + "W" * 184 + ".pdf" for index in range(16)]
        self.payload["documents"] = [document(name, self.second) for name in names]
        result = make_bundle(self.payload)
        data = base64.b64decode(result["data"])
        reader = PdfReader(io.BytesIO(data))
        self.assertEqual(len(reader.pages), 17)
        compact = "".join(reader.pages[0].extract_text().split())
        for index, name in enumerate(names):
            self.assertIn(f"form_{index:02}_", compact)
            self.assertNotIn(name, compact)
        self.assertIn("...[sha256" + hashlib.sha256(self.second).hexdigest()[:12] + "]", compact)
        self.assertIn("Filenamepreviewsmaybeshortened.", compact)
        self.assertIn("FulloriginalfilenamesandchecksumsareinPatientbundlesourcesandtheprojectmanifest.", compact)
        self.assertEqual([item["filename"] for item in result["manifest"]], names)
        pdf = pdfium.PdfDocument(data)
        page = pdf[0]
        text = page.get_textpage()
        try:
            width, height = page.get_size()
            self.assertEqual((width, height), (612, 792))
            for index in range(text.count_chars()):
                left, bottom, right, top = text.get_charbox(index)
                self.assertTrue(0 <= left <= right <= width and 0 <= bottom <= top <= height, f"Cover glyph {index} clips outside its page")
        finally:
            text.close()
            page.close()
            pdf.close()

    def test_unicode_names_preserve_manifest_and_cover_geometry_for_reused_mask(self):
        import pypdfium2 as pdfium
        short = make_bundle(self.payload)
        name = "fictional_" + "\u6e2c" * 180 + ".pdf"
        self.payload["recordId"] = "00043-B"
        self.payload["documents"] = [document(name, self.second)] * 16
        result = make_bundle(self.payload)
        self.assertEqual(result["identifierField"]["region"], short["identifierField"]["region"])
        cover = PdfReader(io.BytesIO(base64.b64decode(result["data"]))).pages[0]
        self.assertEqual(list(cover.mediabox), [0, 0, 612, 792])
        compact = "".join(cover.extract_text().split())
        self.assertIn("fictional_\\u6e2c", compact)
        self.assertIn("...[sha256" + hashlib.sha256(self.second).hexdigest()[:12] + "]", compact)
        self.assertEqual(result["manifest"][0]["filename"], name)
        pdf = pdfium.PdfDocument(base64.b64decode(result["data"]))
        page = pdf[0]
        text = page.get_textpage()
        try:
            region = short["identifierField"]["region"]
            width, height = page.get_size()
            answer = text.get_text_bounded(region["x"] * width, (1 - region["y"] - region["height"]) * height, (region["x"] + region["width"]) * width, (1 - region["y"]) * height)
            self.assertEqual(answer.strip(), "00043-B")
        finally:
            text.close()
            page.close()
            pdf.close()

    def test_accepts_31_source_pages_and_rejects_32_source_pages(self):
        self.payload["documents"] = [document("fictional.pdf", fictional_pdf(*[f"Fictional page {index}" for index in range(31)]))]
        result = make_bundle(self.payload)
        self.assertEqual(len(PdfReader(io.BytesIO(base64.b64decode(result["data"]))).pages), 32)
        self.payload["documents"] = [document("fictional.pdf", fictional_pdf(*[f"Fictional page {index}" for index in range(32)]))]
        with self.assertRaisesRegex(BundleError, "32 pages"):
            make_bundle(self.payload)

    def test_total_page_limit_applies_across_sources(self):
        sixteen_pages = fictional_pdf(*[f"Fictional page {index}" for index in range(16)])
        self.payload["documents"] = [document("first.pdf", sixteen_pages), document("second.pdf", sixteen_pages)]
        with self.assertRaisesRegex(BundleError, "32 pages"):
            make_bundle(self.payload)

    def test_shape_and_record_id_rejections(self):
        for value in (None, {}, [], {**self.payload, "extra": True}, {**self.payload, "documents": []}, {**self.payload, "documents": self.payload["documents"] * 9}):
            with self.subTest(value_type=type(value).__name__), self.assertRaises(BundleError):
                make_bundle(value)
        for record_id in ("", " 00042", "00042 ", "-42", "a/b", "a\n", "\u00e942", "a" * 81, 42, True, None):
            with self.subTest(record_id=repr(record_id)), self.assertRaises(BundleError):
                make_bundle({**self.payload, "recordId": record_id})

    def test_unsafe_filenames_and_document_shapes_rejected(self):
        for name in ("/private/form.pdf", "../form.pdf", "folder/form.pdf", "C:\\form.pdf", "a\x00.pdf", "a\n.pdf", "a\u202e.pdf", "a.txt", "a" * 197 + ".pdf", None):
            with self.subTest(name=repr(name)), self.assertRaises(BundleError):
                make_bundle({**self.payload, "documents": [document(name, self.second)]})
        for source in ({}, {"filename": "a.pdf"}, {**self.payload["documents"][0], "privatePath": "/private/fictional"}, None):
            with self.subTest(source_type=type(source).__name__), self.assertRaises(BundleError):
                make_bundle({**self.payload, "documents": [source]})

    def test_invalid_base64_pdf_signature_and_malformed_pdf_rejected(self):
        for value in ("", "%%%%", "Zg==\n", "Zh==", "\u00e9", 42, base64.b64encode(b"Fictional non-PDF data").decode(), base64.b64encode(b"%PDF-1.7\nFictional malformed PDF\n%%EOF").decode()):
            with self.subTest(data_type=type(value).__name__), self.assertRaises(BundleError):
                make_bundle({**self.payload, "documents": [{"filename": "fictional.pdf", "data": value}]})

    def test_encrypted_and_malformed_page_pdf_rejected(self):
        encrypted = rewrite(self.second, lambda writer: writer.encrypt("fictional-password"))
        with self.assertRaisesRegex(BundleError, "Encrypted"):
            make_bundle({**self.payload, "documents": [document("encrypted.pdf", encrypted)]})
        malformed = rewrite(self.second, lambda writer: writer.pages[0].__setitem__(NameObject("/MediaBox"), ArrayObject([NumberObject(0), NumberObject(0), NumberObject(0), NumberObject(792)])))
        with self.assertRaisesRegex(BundleError, "invalid page size"):
            make_bundle({**self.payload, "documents": [document("malformed.pdf", malformed)]})

    def test_interactive_forms_and_visual_annotations_require_flattening(self):
        output = io.BytesIO()
        pdf = canvas.Canvas(output, invariant=1)
        pdf.drawString(72, 700, "Fictional interactive form")
        pdf.acroForm.textfield(name="fictional_field", value="Fictional typed value", x=72, y=620, width=200, height=24)
        pdf.showPage()
        pdf.save()
        with self.assertRaisesRegex(BundleError, "flattened or scanned"):
            make_bundle({**self.payload, "documents": [document("interactive.pdf", output.getvalue())]})
        annotated = rewrite(self.second, lambda writer: writer.pages[0].__setitem__(NameObject("/Annots"), ArrayObject([DictionaryObject({NameObject("/Type"): NameObject("/Annot"), NameObject("/Subtype"): NameObject("/Ink")})])))
        with self.assertRaisesRegex(BundleError, "flattened or scanned"):
            make_bundle({**self.payload, "documents": [document("annotated.pdf", annotated)]})

    def test_links_actions_and_attachments_do_not_enter_bundle(self):
        def active(writer):
            writer.add_js("app.alert('fictional-javascript-probe')")
            writer.add_attachment("fictional-attachment.txt", b"fictional-attachment-probe")
            action = DictionaryObject({NameObject("/S"): NameObject("/JavaScript"), NameObject("/JS"): TextStringObject("fictional-page-action-probe")})
            writer.pages[0][NameObject("/AA")] = DictionaryObject({NameObject("/O"): action})
            writer.pages[0][NameObject("/Annots")] = ArrayObject([DictionaryObject({NameObject("/Type"): NameObject("/Annot"), NameObject("/Subtype"): NameObject("/Link"), NameObject("/A"): action, NameObject("/Rect"): ArrayObject([NumberObject(10), NumberObject(10), NumberObject(20), NumberObject(20)])})])
        data = rewrite(self.second, active)
        result = make_bundle({**self.payload, "documents": [document("active.pdf", data)]})
        combined = base64.b64decode(result["data"])
        reader = PdfReader(io.BytesIO(combined))
        self.assertEqual(reader.pages[1].extract_text().strip(), "Fictional form beta page one")
        self.assertNotIn("/Annots", reader.pages[1])
        self.assertNotIn("/AA", reader.pages[1])
        self.assertNotIn("/Names", reader.trailer["/Root"])
        for marker in (b"fictional-javascript-probe", b"fictional-page-action-probe", b"fictional-attachment-probe"):
            self.assertNotIn(marker, combined)

    def test_input_and_final_output_sizes_are_bounded(self):
        padded = self.second + b" " * (12 * 1024 * 1024 - len(self.second))
        with self.assertRaisesRegex(BundleError, "combined 12 MiB"):
            make_bundle({**self.payload, "documents": [document("large.pdf", padded), document("second.pdf", self.second)]})
        with self.assertRaisesRegex(BundleError, "12 MiB"):
            make_bundle({**self.payload, "documents": [document("large.pdf", padded + b" ")]})
        with patch.object(source_bundle, "MAX_OUTPUT_BYTES", 1000):
            with self.assertRaisesRegex(BundleError, "combined PDF exceeds"):
                make_bundle(self.payload)

    def test_worker_success_disposes_inputs_without_disk_files(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, "-B", str(ROOT / "bundle_worker.py")], input=json.dumps(self.payload).encode(), capture_output=True, cwd=directory, timeout=30, check=True)
            response = json.loads(result.stdout)
            self.assertEqual(response["result"]["manifest"][0]["sha256"], hashlib.sha256(self.first).hexdigest())
            self.assertEqual(result.stderr, b"")
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_worker_rejects_invalid_utf8_duplicate_keys_and_nonfinite_json(self):
        for raw in (b"\xff", b'{"recordId":"first","recordId":"second","documents":[]}', b'{"recordId":NaN,"documents":[]}', b'{"recordId":"fictional",'):
            with self.subTest(raw_type=raw[:1]):
                result = subprocess.run([sys.executable, "-B", str(ROOT / "bundle_worker.py")], input=raw, capture_output=True, timeout=30, check=True)
                response = json.loads(result.stdout)
                self.assertEqual(set(response), {"error"})
                self.assertIn("valid UTF-8 JSON", response["error"])
                self.assertLessEqual(len(response["error"]), 300)
                self.assertEqual(result.stderr, b"")

    def test_worker_error_does_not_echo_filename_record_or_pdf_content(self):
        payload = {"recordId": "FictionalSensitiveID", "documents": [document("fictional-private-name.pdf", b"%PDF-1.7\nFictionalSensitiveContent\n%%EOF")]}
        result = subprocess.run([sys.executable, "-B", str(ROOT / "bundle_worker.py")], input=json.dumps(payload).encode(), capture_output=True, timeout=30, check=True)
        response = json.loads(result.stdout)
        self.assertEqual(set(response), {"error"})
        self.assertLessEqual(len(response["error"]), 300)
        for value in (b"FictionalSensitiveID", b"fictional-private-name.pdf", b"FictionalSensitiveContent"):
            self.assertNotIn(value, result.stdout + result.stderr)
        self.assertEqual(result.stderr, b"")


if __name__ == "__main__":
    unittest.main()
