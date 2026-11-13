#!/usr/bin/env python3
"""Create deterministic, fictional FormBridge PDF and image practice inputs.

No patient records, network requests, camera, or source documents are used.
The first five completed PDFs have text layers. The next five contain only a
raster image, which deliberately requires the OCR path in FormBridge.

Run: python generate_samples.py
Dependencies: reportlab, Pillow, pypdfium2
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageEnhance, ImageFilter
from reportlab.lib.colors import HexColor, white
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parent
SAMPLES = ROOT / "samples"
PAGE_W, PAGE_H = 612, 792
WARNING = "FICTIONAL PRACTICE DATA - NOT A PATIENT RECORD"

# All content is synthetic, fixed, and reproducible. Dates identify fictional
# visits only. The optional notes field includes one intentional empty value.
RECORDS = [
    {"record_id": "DEMO-001", "visit_date": "2026-01-12", "age": 34, "consent": "1", "symptom_score": 3, "notes": "Practice entry alpha. No follow-up requested."},
    {"record_id": "DEMO-002", "visit_date": "2026-01-13", "age": 58, "consent": "1", "symptom_score": 6, "notes": "Practice entry beta. Review next visit."},
    {"record_id": "DEMO-003", "visit_date": "2026-01-14", "age": 27, "consent": "0", "symptom_score": 0, "notes": "Fictional participant declined consent."},
    {"record_id": "DEMO-004", "visit_date": "2026-01-15", "age": 71, "consent": "1", "symptom_score": 10, "notes": "Practice entry delta. Check score carefully."},
    {"record_id": "DEMO-005", "visit_date": "2026-01-16", "age": 42, "consent": "1", "symptom_score": 4, "notes": ""},
    {"record_id": "DEMO-006", "visit_date": "2026-01-19", "age": 39, "consent": "1", "symptom_score": 2, "notes": "Image-only practice entry zeta."},
    {"record_id": "DEMO-007", "visit_date": "2026-01-20", "age": 63, "consent": "0", "symptom_score": 7, "notes": "Image-only practice entry eta."},
    {"record_id": "DEMO-008", "visit_date": "2026-01-21", "age": 19, "consent": "1", "symptom_score": 1, "notes": "Image-only practice entry theta."},
    {"record_id": "DEMO-009", "visit_date": "2026-01-22", "age": 46, "consent": "1", "symptom_score": 5, "notes": "Image-only practice entry iota."},
    {"record_id": "DEMO-010", "visit_date": "2026-01-23", "age": 82, "consent": "1", "symptom_score": 9, "notes": "Image-only practice entry kappa."},
]

# The answer boxes begin immediately after the printed label and colon.
# PDF origins are bottom-left; the application uses normalized top-left regions.
ROW_TOPS = [592, 524, 456, 388, 320, 252]
ROW_H = 54
VALUE_X = 197
VALUE_W = 357
FIELDS = [
    {"name": "record_id", "label": "Record ID", "type": "text", "required": True, "aliases": ["Record ID", "Record identifier", "Study ID"]},
    {"name": "visit_date", "label": "Visit date", "type": "date", "required": True, "aliases": ["Visit date", "Date of visit"], "format": "YYYY-MM-DD"},
    {"name": "age", "label": "Age", "type": "integer", "required": True, "aliases": ["Age", "Age in years"], "min": 18, "max": 120},
    {"name": "consent", "label": "Consent", "type": "choice", "required": True, "aliases": ["Consent", "Consent obtained"], "choices": {"1": "Yes", "0": "No"}},
    {"name": "symptom_score", "label": "Symptom score", "type": "integer", "required": True, "aliases": ["Symptom score", "Symptom rating"], "min": 0, "max": 10},
    {"name": "notes", "label": "Notes", "type": "text", "required": False, "aliases": ["Notes", "Comments"], "max_length": 1000},
]
for field, row_top in zip(FIELDS, ROW_TOPS):
    field["region"] = {
        "page": 1,
        "x": round(VALUE_X / PAGE_W, 6),
        "y": round((PAGE_H - row_top + 1) / PAGE_H, 6),
        "width": round(VALUE_W / PAGE_W, 6),
        "height": round((ROW_H - 2) / PAGE_H, 6),
    }


def make_form(record: dict | None, target: Path | io.BytesIO) -> None:
    """Render one fixed-layout original using only core PDF fonts."""
    pdf = canvas.Canvas(target, pagesize=(PAGE_W, PAGE_H), invariant=1, pageCompression=1)
    pdf.setTitle("Fictional FormBridge Practice Form")
    pdf.setAuthor("FormBridge synthetic fixture generator")
    pdf.setSubject("Fictional practice data. Not a patient record.")
    pdf.setFillColor(HexColor("#f6f8fb"))
    pdf.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    pdf.setFillColor(HexColor("#173654"))
    pdf.rect(0, PAGE_H - 150, PAGE_W, 150, fill=1, stroke=0)
    pdf.setFillColor(HexColor("#a9d5e8"))
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(42, 750, "FORMBRIDGE / RESEARCH PRACTICE")
    pdf.setFillColor(white)
    pdf.setFont("Helvetica-Bold", 28)
    pdf.drawString(42, 711, "Research intake form")
    pdf.setFont("Helvetica", 11)
    pdf.drawString(42, 685, "Structured extraction and human review practice")
    pdf.setFillColor(HexColor("#fff3cd"))
    pdf.roundRect(42, 612, 528, 27, 5, fill=1, stroke=0)
    pdf.setFillColor(HexColor("#714f05"))
    pdf.setFont("Helvetica-Bold", 9.4)
    pdf.drawCentredString(PAGE_W / 2, 621, WARNING)

    for field, row_top in zip(FIELDS, ROW_TOPS):
        name, label = field["name"], field["label"]
        row_bottom = row_top - ROW_H
        pdf.setFillColor(white)
        pdf.setStrokeColor(HexColor("#c4d0dc"))
        pdf.setLineWidth(0.8)
        pdf.roundRect(42, row_bottom, 528, ROW_H, 5, fill=1, stroke=1)
        pdf.setFillColor(HexColor("#263f56"))
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(56, row_top - 31, label + ":")
        # A visible dashed answer-region border teaches manual crop mapping.
        pdf.setDash(3, 2)
        pdf.setStrokeColor(HexColor("#d4dfe7"))
        pdf.rect(VALUE_X, row_bottom + 5, VALUE_W, ROW_H - 10, fill=0, stroke=1)
        pdf.setDash()
        value = "" if record is None else str(record[name])
        if name == "consent" and value:
            value = {"1": "Yes", "0": "No"}[value]
        pdf.setFillColor(HexColor("#102a43"))
        pdf.setFont("Helvetica", 10.5 if name == "notes" else 12)
        pdf.drawString(VALUE_X + 9, row_top - 31, value)

    pdf.setFillColor(HexColor("#5f7387"))
    pdf.setFont("Helvetica", 9)
    pdf.drawString(42, 165, "Consent coding: 1 = Yes; 0 = No. Symptom score: whole number from 0 to 10.")
    pdf.drawString(42, 149, "Visit date uses YYYY-MM-DD. All data on this sheet is invented for software testing.")
    pdf.setStrokeColor(HexColor("#c4d0dc"))
    pdf.line(42, 111, 570, 111)
    pdf.setFillColor(HexColor("#5f7387"))
    pdf.setFont("Helvetica-Bold", 8.4)
    pdf.drawString(42, 91, "SYNTHETIC FIXTURE  /  REVIEW BEFORE EXPORT")
    pdf.setFont("Helvetica", 8.4)
    pdf.drawRightString(570, 91, "FormBridge practice - Page 1 of 1")
    pdf.save()


def render_pdf(source: Path | bytes, scale: float = 2.0) -> Image.Image:
    with pdfium.PdfDocument(source if isinstance(source, bytes) else str(source)) as document:
        bitmap = document[0].render(scale=scale)
        return bitmap.to_pil().convert("RGB").copy()


def image_pdf(image: Image.Image, target: Path) -> None:
    """Embed pixels only, so a text extractor cannot bypass OCR."""
    pdf = canvas.Canvas(str(target), pagesize=(PAGE_W, PAGE_H), invariant=1, pageCompression=1)
    pdf.setTitle("Fictional image-only FormBridge practice form")
    pdf.setAuthor("FormBridge synthetic fixture generator")
    pdf.drawImage(ImageReader(image), 0, 0, PAGE_W, PAGE_H)
    pdf.showPage()
    pdf.save()


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    SAMPLES.mkdir(parents=True, exist_ok=True)
    make_form(None, str(SAMPLES / "blank-form.pdf"))
    files = []
    for index, record in enumerate(RECORDS, 1):
        kind = "text" if index <= 5 else "scan"
        filename = f"practice-{index:02d}-{kind}.pdf"
        target = SAMPLES / filename
        if index <= 5:
            make_form(record, str(target))
        else:
            original = io.BytesIO()
            make_form(record, original)
            image = render_pdf(original.getvalue(), scale=2.5)
            # A mild deterministic scan effect retains a realistic OCR input
            # without introducing stochastic fixtures or inaccessible fonts.
            image = ImageEnhance.Contrast(image).enhance(0.94)
            image = image.filter(ImageFilter.GaussianBlur(radius=0.12))
            image_pdf(image, target)
            if index == 6:
                image.save(SAMPLES / "practice-06-scan.png", optimize=True)
        files.append({"file": filename, "mode": "text-layer" if index <= 5 else "image-only", "expected": record})

    schema = {
        "name": "Fictional Research Intake",
        "version": 1,
        "description": "Synthetic practice schema; replace it with your approved REDCap dictionary before research use.",
        "region_coordinates": "normalized-top-left",
        "page_size_points": {"width": PAGE_W, "height": PAGE_H},
        "fields": FIELDS,
    }
    write_json(SAMPLES / "sample-schema.json", schema)
    write_json(SAMPLES / "answer-key.json", {"warning": WARNING, "records": files})
    headers = [field["name"] for field in FIELDS]
    with (SAMPLES / "redcap-import-template.csv").open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerow(headers)
    with (SAMPLES / "expected-redcap.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(RECORDS)
    dictionary_headers = ["Variable / Field Name", "Form Name", "Field Type", "Field Label", "Choices, Calculations, OR Slider Labels", "Text Validation Type OR Show Slider Number", "Text Validation Min", "Text Validation Max", "Required Field?"]
    with (SAMPLES / "sample-data-dictionary.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=dictionary_headers)
        writer.writeheader()
        for field in FIELDS:
            kind = field["type"]
            validation = "date_ymd" if kind == "date" else kind if kind in {"integer", "number"} else ""
            writer.writerow({"Variable / Field Name": field["name"], "Form Name": "fictional_intake", "Field Type": "radio" if kind == "choice" else "notes" if field["name"] == "notes" else "text", "Field Label": field["label"], "Choices, Calculations, OR Slider Labels": " | ".join(f"{code}, {label}" for code, label in field.get("choices", {}).items()), "Text Validation Type OR Show Slider Number": validation, "Text Validation Min": field.get("min", ""), "Text Validation Max": field.get("max", ""), "Required Field?": "y" if field["required"] else ""})
    preview = render_pdf(SAMPLES / "practice-01-text.pdf", scale=1.5)
    preview.save(SAMPLES / "practice-preview.png", optimize=True)
    readme = """# Fictional practice inputs

Every value is synthetic. These fixtures do not contain patient records.

- `practice-01-text.pdf` through `practice-05-text.pdf`: selectable PDF text.
- `practice-06-scan.pdf` through `practice-10-scan.pdf`: image-only PDFs, for actual OCR.
- `practice-06-scan.png`: equivalent image upload fixture.
- `blank-form.pdf`: same layout without answers.
- `sample-schema.json`: six fields and normalized answer regions (top-left origin).
- `answer-key.json` and `expected-redcap.csv`: exact expected normalized values.
- `redcap-import-template.csv`: header-only REDCap-shaped CSV template.
- `sample-data-dictionary.csv`: importable fictional REDCap field definitions.

The REDCap headers are `record_id,visit_date,age,consent,symptom_score,notes`.
Consent values export as 1 (Yes) or 0 (No). The optional notes value is blank
for DEMO-005; the review interface should preserve that deliberate blank.

Regenerate with `python generate_samples.py` from the application folder.
All records and layout values are fixed in that script. PDF timestamps and
document IDs are deterministic. No external service is contacted.
"""
    (SAMPLES / "README.md").write_text(readme, encoding="utf-8")
    print(f"Generated 11 PDFs, 2 PNGs, schema, answer key, and 3 CSVs in {SAMPLES}")


if __name__ == "__main__":
    main()
