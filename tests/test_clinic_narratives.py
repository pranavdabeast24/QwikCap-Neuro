"""Source assertions, absent findings, and procedure units in fictional clinic pages."""
from __future__ import annotations

import io
from pathlib import Path
import sys
import tempfile
import unittest

from reportlab.pdfgen import canvas

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def text_page(lines):
    return {"page": 1, "method": "pdf-text", "lines": [
        {"text": text, "words": [{"text": text, "x": .06, "y": .05 + i * .02,
                                    "width": .88, "height": .012}]}
        for i, text in enumerate(lines)]}


def radiology(exam, findings):
    return text_page([
        "Patient EXAMPLE, ADA Accession # SYN-0042",
        "DOB 02/03/1980 Exam date 04/05/2026",
        "MRN 00001234",
        "EXAM: " + exam,
        "CLINICAL HISTORY:", "Evaluate for a CSF-venous fistula. Pre-procedure evaluation.",
        "TECHNIQUE:", "Images obtained without intravenous contrast.",
        "COMPARISON:", "None available.", "FINDINGS:", *findings,
        "IMPRESSION:", "Source report impression.",
        "Electronically signed by: Fictional Reader, MD", "FINAL REPORT",
    ])


class ClinicNarrativeTests(unittest.TestCase):
    def setUp(self):
        from clinic_narratives import extract_procedure, extract_radiology
        self.extract_procedure, self.extract_radiology = extract_procedure, extract_radiology
        self.values, self.proofs = {}, {}

    def put(self, name, value, page, words=None, mapping=None):
        self.values[name] = str(value)
        self.proofs[name] = words

    def test_explicit_positive_negative_and_measurements_keep_unmentioned_fields_empty(self):
        page = radiology("MRI BRAIN WITHOUT IV CONTRAST", [
            "Diffuse smooth pachymeningeal (dural) enhancement.",
            "No subdural fluid collection.",
            "Mamillopontine distance measures 6.0 mm (decreased; normal >= 6.5 mm).",
            "Suprasellar cistern measures 6.1 mm.",
        ])
        issues = self.extract_radiology(page, self.put)
        self.assertEqual(self.values["scan_id"], "SYN-0042")
        self.assertEqual(self.values["scan_date"], "2026-04-05")
        self.assertEqual(self.values["scan_contrast"], "2")
        self.assertEqual(self.values["scan_findings___1"], "1")
        self.assertEqual(self.values["scan_findings___2"], "0")
        self.assertEqual(self.values["mpd"], "6.0")
        self.assertEqual(self.values["scd"], "6.1")
        self.assertNotIn("scan_findings___10", self.values)
        self.assertNotIn("brain_reader", self.values)
        self.assertNotIn("image_information_brain_scan_complete", self.values)
        self.assertTrue(all(self.proofs[name] for name in self.values))
        self.assertIsInstance(issues, list)

    def test_contradictory_assertions_are_not_selected_and_history_is_not_a_finding(self):
        page = radiology("CT MYELOGRAM, TOTAL SPINE", [
            "Adequate distribution of intrathecal contrast throughout the thecal sac.",
            "No perineural cyst.", "A perineural cyst is present at S2.",
        ])
        issues = self.extract_radiology(page, self.put)
        self.assertEqual(self.values["scan_findings_v2_v2___1"], "1")
        self.assertNotIn("scan_findings_v2_v2___2", self.values)
        self.assertNotIn("scan_findings_v2_v2___4", self.values)
        self.assertTrue(any("scan_findings_v2_v2___2" in issue for issue in issues))

    def test_spine_presence_absence_pairs_require_literal_assertions(self):
        page = radiology("MRI TOTAL SPINE WITHOUT IV CONTRAST", [
            "No extradural (extrathecal) fluid collection.",
            "Multiple nerve root sleeve diverticula are present.",
        ])
        self.extract_radiology(page, self.put)
        self.assertEqual(self.values["scan_findings_v2___1"], "0")
        self.assertEqual(self.values["scan_findings_v2___2"], "1")
        self.assertEqual(self.values["scan_findings_v2___3"], "1")
        self.assertEqual(self.values["scan_findings_v2___4"], "0")
        self.assertNotIn("scan_findings_v2___5", self.values)
        self.assertNotIn("scan_findings_v2___6", self.values)

    def test_uncertain_or_unhandled_negative_phrasing_never_becomes_positive(self):
        page = radiology("CT MYELOGRAM, TOTAL SPINE", [
            "Adequate distribution of intrathecal contrast throughout the thecal sac.",
            "A possible perineural cyst is present at S2.",
            "A CSF-venous fistula was not identified.",
        ])
        issues = self.extract_radiology(page, self.put)
        self.assertEqual(self.values["scan_findings_v2_v2___1"], "1")
        self.assertNotIn("scan_findings_v2_v2___2", self.values)
        self.assertNotIn("scan_findings_v2_v2___4", self.values)
        self.assertTrue(any("scan_findings_v2_v2___2" in issue for issue in issues))
        self.assertTrue(any("scan_findings_v2_v2___4" in issue for issue in issues))

    def test_dsm_specific_fistula_description_keeps_literal_source_detail(self):
        detail = "Right T7 CSF-venous fistula draining into a paraspinal venous plexus."
        page = radiology("DIGITAL SUBTRACTION MYELOGRAM", [detail])
        self.extract_radiology(page, self.put)
        self.assertEqual(self.values["scan_findings_dsm___4"], "1")
        self.assertEqual(self.values["scan_findings_other_v2_v2_dsm"], detail)
        self.assertTrue(self.proofs["scan_findings_other_v2_v2_dsm"])
        self.values.clear()
        page = radiology("DIGITAL SUBTRACTION MYELOGRAM", ["Possible " + detail])
        self.extract_radiology(page, self.put)
        self.assertNotIn("scan_findings_other_v2_v2_dsm", self.values)

    def test_native_procedure_signed_volume_and_not_performed(self):
        from pipeline import _make_pdf_pages
        output = io.BytesIO()
        pdf = canvas.Canvas(output, pagesize=(612, 792), invariant=1)
        pdf.setFont("Helvetica", 10)
        pdf.drawString(40, 740, "CSF Volume Provocation Procedure Record")
        pdf.drawString(40, 710, "Date of procedure 04/05/2026")
        headers = ((40, "Stage"), (135, "CSF volume change"), (235, "Opening pressure"),
                   (310, "Manometer"), (370, "Pain"), (420, "Pain location"),
                   (495, "Pain quality"), (555, "Other symptoms"))
        pdf.setFont("Helvetica", 7)
        for x, label in headers:
            pdf.drawString(x, 650, label)
        rows = [
            ("A. Baseline", "", "12.5", "Analog", "5/10", "temporal", "throbbing", "none"),
            ("B. Provocation #1", "-15 mL CSF", "8.0", "Digital", "4/10", "neck", "aching", "photophobia, visual aura"),
            ("C. Provocation #2", "Not performed", "", "", "", "", "", ""),
            ("D. Provocation #3", "Not performed", "", "", "", "", "", ""),
        ]
        for index, row in enumerate(rows):
            y = 610 - index * 40
            pdf.setFont("Helvetica-Bold", 7)
            if index:
                pdf.drawString(40, y, "ABCD"[index] + ". Provocation")
                pdf.drawString(40, y - 8, "#" + str(index))
            else:
                pdf.drawString(40, y, row[0])
            pdf.setFont("Courier-Bold", 7)
            for (x, _), value in zip(headers[1:], row[1:]):
                pdf.setFont("Courier-Bold", 3 if x == 555 else 7)
                pdf.drawString(x, y - (4 if index else 0), value)
        pdf.save()
        with tempfile.TemporaryDirectory() as folder:
            page = _make_pdf_pages(output.getvalue(), Path(folder), capture_geometry=True, capture_clinic=True)[0]
            self.extract_procedure(page, self.put)
        self.assertEqual(self.values["form_date"], "2026-04-05")
        self.assertEqual(self.values["baseline_opening_pressure"], "12.5")
        self.assertEqual(self.values["opening_headache_aod"], "1")
        self.assertEqual(self.values["baseline_headache_pain"], "5")
        self.assertEqual(self.values["csf_volume_delta"], "-15")
        self.assertEqual(self.values["css_change_unit"], "1")
        self.assertEqual(self.values["baseline_headache_pain_2"], "4")
        self.assertEqual(self.values["prov_2_yn"], "0")
        self.assertEqual(self.values["prov_associated_symptoms___2"], "1")
        self.assertEqual(self.values["prov_associated_symptoms___6"], "1")
        self.assertNotIn("baseline_opening_pressure_3", self.values)
        self.assertNotIn("csf_volume_provocation_form_complete", self.values)


if __name__ == "__main__":
    unittest.main()
