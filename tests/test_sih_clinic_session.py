"""Clinic registration anchors and native review boundaries with fictional PDFs."""
from __future__ import annotations

import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

from reportlab.pdfgen import canvas

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from desktop_model import DesktopSession, InputError


def registration(study="SYNTH-001", mrn="00001234", first="Ada", last="Example"):
    output = io.BytesIO()
    pdf = canvas.Canvas(output, pagesize=(612, 792), invariant=1)
    pdf.drawString(40, 730, "Patient Registration Form")
    pdf.drawString(40, 690, f"Last name {last} First name {first} M.I.")
    pdf.drawString(40, 660, "Date of birth (mm/dd/yyyy) 02/03/1980 Sex: Female Male Other")
    pdf.drawString(40, 620, "Cell phone (555) 010-0100 Email ada@example.invalid")
    pdf.drawString(40, 90, f"OFFICE USE ONLY MRN: {mrn} Research Study ID: {study}")
    pdf.drawString(40, 50, "REG-100 Rev 02/2026 Page 1 of 1")
    pdf.save()
    return output.getvalue()


def hit6(mrn="00001234", first="Ada", last="Example"):
    output = io.BytesIO()
    pdf = canvas.Canvas(output, pagesize=(612, 792), invariant=1)
    pdf.drawString(400, 740, f"{last.upper()}, {first.upper()}")
    pdf.drawString(400, 725, "DOB 02/03/1980 Sex F")
    pdf.drawString(400, 710, f"MRN {mrn}")
    pdf.drawString(40, 660, "HIT-6 Headache Impact Test")
    pdf.drawString(40, 630, "Date 04/05/2026")
    pdf.drawString(40, 50, "HA-230 Rev 02/2026 Page 1 of 1")
    pdf.save()
    return output.getvalue()


class SihClinicSessionTests(unittest.TestCase):
    def setUp(self):
        self.session = DesktopSession()
        self.addCleanup(self.session.close)
        self.folder = tempfile.TemporaryDirectory(prefix="qwikcap-clinic-contract-")
        self.addCleanup(self.folder.cleanup)

    def write(self, name, data):
        path = Path(self.folder.name) / name
        path.write_bytes(data)
        return path

    def choose_reader(self):
        self.session.use_sih_clinic_profile()

    def test_explicit_clinic_reader_keeps_canonical_512_destination(self):
        self.assertIsNone(self.session.snapshot()["profile"])
        self.choose_reader()
        snapshot = self.session.snapshot()
        self.assertEqual(snapshot["profile"], "sih-clinic-v1")
        self.assertEqual(len(snapshot["schema"]), 512)
        self.assertEqual(snapshot["schema"][0]["name"], "record_id")

    def test_registration_links_study_id_to_other_source_mrn(self):
        self.choose_reader()
        sources = [self.write("registration.pdf", registration()), self.write("hit6.pdf", hit6())]
        record = self.session.add_patient_bundle(sources, "SYNTH-001", confirmed_same_patient=True)
        self.assertEqual(record["values"]["record_id"], "SYNTH-001")
        self.assertEqual(record["values"]["mrn"], "00001234")
        self.assertEqual(record["sourceContext"]["profile"], "sih-clinic-v1")
        self.assertEqual(record["sourceContext"]["recordIds"], ["SYNTH-001"])
        nonregistration = [item for item in record["sourceContext"]["identities"] if item["page"] == 3]
        self.assertEqual(len(nonregistration), 1)
        self.assertEqual(nonregistration[0]["recordId"], "")

    def test_missing_registration_and_wrong_source_identity_cannot_be_combined(self):
        self.choose_reader()
        with self.assertRaises(InputError):
            self.session.add_patient_bundle([self.write("unanchored.pdf", hit6())], "SYNTH-001", confirmed_same_patient=True)
        with self.assertRaises(InputError):
            self.session.add_patient_bundle([
                self.write("registration.pdf", registration()),
                self.write("wrong-patient.pdf", hit6(mrn="99999999")),
            ], "SYNTH-001", confirmed_same_patient=True)


if __name__ == "__main__":
    unittest.main()
