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


def hit6(mrn="00001234", first="Ada", last="Example", letterhead=False, dob="02/03/1980", study=None,
         form_code="HA-230", frequency_headers=True, first_mark_x=350):
    output = io.BytesIO()
    pdf = canvas.Canvas(output, pagesize=(612, 792), invariant=1)
    if letterhead:
        pdf.drawString(40, 770, "4100 Fictional Street, Suite 300, Example Town")
    pdf.drawString(400, 740, f"{last.upper()}, {first.upper()}")
    pdf.drawString(400, 725, f"DOB {dob} Sex F")
    pdf.drawString(400, 710, f"MRN {mrn}")
    if study is not None:
        pdf.drawString(400, 695, f"Research Study ID: {study}")
    pdf.drawString(40, 660, "HIT-6 Headache Impact Test")
    pdf.drawString(40, 630, "Date 04/05/2026")
    pdf.setFont("Helvetica", 8)
    if frequency_headers:
        for x, label in zip((350, 400, 455, 510, 568), ("Never", "Rarely", "Sometimes", "Very", "Always")):
            pdf.drawCentredString(x, 590, label)
    questions = ("Pain severe", "Limit your ability to do usual daily activities", "Wish you could lie down",
                 "Felt too tired", "Fed up or irritated", "Limit your ability to concentrate")
    for index, question in enumerate(questions, 1):
        y = 590 - index * 40
        pdf.drawString(40, y, str(index))
        pdf.drawString(60, y, question)
        pdf.drawCentredString(first_mark_x if index == 1 else 400, y, "X")
    pdf.drawString(40, 50, f"{form_code} Rev 02/2026 Page 1 of 1")
    pdf.save()
    return output.getvalue()


def clinician_questionnaire(*, visible_options=True, declared_pages=1):
    output = io.BytesIO()
    pdf = canvas.Canvas(output, pagesize=(612, 792), invariant=1)
    pdf.drawString(400, 740, "EXAMPLE, ADA")
    pdf.drawString(400, 725, "DOB 02/03/1980 Sex F")
    pdf.drawString(400, 710, "MRN 00001234")
    pdf.drawString(40, 660, "Headache History - Clinician Intake")
    pdf.drawString(40, 610, "1. Is the patient currently experiencing headaches?")
    if visible_options:
        pdf.drawString(420, 610, "Yes No")
    pdf.drawString(40, 50, f"HA-210C Rev 02/2026 Page 1 of {declared_pages}")
    pdf.save()
    return output.getvalue()


def clinician_text_questionnaire(answer="", font="Helvetica", *,
                                prompt="4. Briefly describe your current headache"):
    output = io.BytesIO()
    pdf = canvas.Canvas(output, pagesize=(612, 792), invariant=1)
    pdf.drawString(400, 740, "EXAMPLE, ADA")
    pdf.drawString(400, 725, "DOB 02/03/1980 Sex F")
    pdf.drawString(400, 710, "MRN 00001234")
    pdf.drawString(40, 660, "Headache History - Clinician Intake")
    pdf.drawString(40, 610, prompt)
    pdf.setFont(font, 12)
    pdf.drawString(40, 585, answer)
    pdf.setFont("Helvetica", 12)
    pdf.drawString(40, 50, "HA-210C Rev 02/2026 Page 1 of 1")
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

    def test_letterhead_comma_is_not_patient_identity(self):
        self.choose_reader()
        record = self.session.add_patient_bundle([
            self.write("registration.pdf", registration()),
            self.write("clinic.pdf", hit6(letterhead=True)),
        ], "SYNTH-001", confirmed_same_patient=True)
        header = next(identity for identity in record["sourceContext"]["identities"] if identity["page"] == 3)
        self.assertEqual(header["firstName"], "ADA")
        self.assertEqual(header["lastName"], "EXAMPLE")

    def test_accented_names_link_registration_to_clinic_source(self):
        self.choose_reader()
        record = self.session.add_patient_bundle([
            self.write("registration.pdf", registration(first="José", last="García")),
            self.write("clinic.pdf", hit6(first="José", last="García")),
        ], "SYNTH-001", confirmed_same_patient=True)
        header = next(identity for identity in record["sourceContext"]["identities"] if identity["page"] == 3)
        self.assertEqual(header["firstName"], "JOSÉ")
        self.assertEqual(header["lastName"], "GARCÍA")
        self.assertEqual(record["values"]["record_id"], "SYNTH-001")
        self.assertEqual(record["values"]["mrn"], "00001234")

    def test_mrn_internal_spaces_are_preserved_and_cannot_hide_a_conflict(self):
        self.choose_reader()
        with self.assertRaises(InputError):
            self.session.add_patient_bundle([
                self.write("registration.pdf", registration(mrn="0000 1234")),
                self.write("different-mrn.pdf", hit6(mrn="0000 9999")),
            ], "SYNTH-001", confirmed_same_patient=True)
        record = self.session.add_patient_bundle([
            self.write("same-registration.pdf", registration(mrn="0000 1234")),
            self.write("same-mrn.pdf", hit6(mrn="0000 1234")),
        ], "SYNTH-001", confirmed_same_patient=True)
        self.assertEqual(record["values"]["mrn"], "0000 1234")

    def test_printed_study_id_cannot_be_silently_shortened(self):
        self.choose_reader()
        for index, (printed, entered) in enumerate((("SYNTH-001 EXTRA", "SYNTH-001"), ("A" * 81, "A" * 80))):
            with self.subTest(printed=printed):
                with self.assertRaises(InputError):
                    self.session.add_patient_bundle([
                        self.write(f"registration-{index}.pdf", registration(study=printed)),
                        self.write(f"hit6-{index}.pdf", hit6()),
                    ], entered, confirmed_same_patient=True)

    def test_complete_header_birth_date_and_other_printed_study_ids_are_checked(self):
        self.choose_reader()
        for index, kwargs in enumerate(({"dob": "02/03/19800"}, {"study": "SYNTH-OTHER"},
                                        {"study": "SYNTH-001 EXTRA"})):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(InputError):
                    self.session.add_patient_bundle([
                        self.write(f"anchor-{index}.pdf", registration()),
                        self.write(f"other-{index}.pdf", hit6(**kwargs)),
                    ], "SYNTH-001", confirmed_same_patient=True)

    def test_unknown_or_repeated_source_instrument_rolls_back(self):
        self.choose_reader()
        anchor = self.write("registration.pdf", registration())
        questionnaire = self.write("hit6.pdf", hit6())
        before = self.session.snapshot()
        for extra in (self.write("unrecognized.pdf", hit6(form_code="UNKNOWN")),
                      self.write("repeat-hit6.pdf", hit6())):
            with self.subTest(extra=extra.name):
                with self.assertRaises(InputError):
                    self.session.add_patient_bundle([anchor, questionnaire, extra], "SYNTH-001", True)
                self.assertEqual(self.session.snapshot(), before)

    def test_reopen_reconstructs_registration_anchor_and_resets_review(self):
        self.choose_reader()
        record = self.session.add_patient_bundle([
            self.write("registration.pdf", registration()), self.write("hit6.pdf", hit6()),
        ], "SYNTH-001", True)
        record = self.session.review_record(record["id"], record["values"], record["applicableFields"],
                                            "Fictional Reviewer", True)
        self.assertEqual(record["status"], "approved")
        project = json.loads(self.session.project_bytes())
        project["records"][0]["sourceContext"] = {"profile": "forged", "registrationAnchors": []}
        project["records"][0]["applicableFields"] = ["record_id"]
        path = self.write("project.json", json.dumps(project).encode())
        self.session.open_project(path)
        reopened = self.session.snapshot()["records"][0]
        self.assertEqual(reopened["sourceContext"]["profile"], "sih-clinic-v1")
        self.assertEqual(len(reopened["sourceContext"]["registrationAnchors"]), 1)
        self.assertIn("mrn", reopened["applicableFields"])
        self.assertEqual(reopened["confirmed"], [])
        self.assertEqual(reopened["status"], "review")
        self.assertEqual(reopened["reviewedBy"], "")
        # Even an edited review value cannot rewrite the recomputed source anchor.
        project["records"][0]["values"]["mrn"] = "99999999"
        path.write_text(json.dumps(project))
        self.session.open_project(path)
        reopened = self.session.snapshot()["records"][0]
        self.assertIn("mrn", reopened["validationErrors"])
        with self.assertRaises(InputError):
            self.session.review_record(reopened["id"], reopened["values"], reopened["applicableFields"],
                                       "Fictional Reviewer", True)

    def test_missing_radio_options_do_not_gain_a_source_blank_waiver(self):
        self.choose_reader()
        with self.assertRaises(InputError):
            self.session.add_patient_bundle([
                self.write("registration.pdf", registration()),
                self.write("missing-options.pdf", clinician_questionnaire(visible_options=False)),
            ], "SYNTH-001", True)
        record = self.session.add_patient_bundle([
            self.write("registration-visible.pdf", registration()),
            self.write("visible-unmarked.pdf", clinician_questionnaire()),
        ], "SYNTH-001", True)
        self.assertIn("headaches_yn", record["sourceContext"]["unansweredFields"])

    def test_located_blank_or_unreadable_text_remains_available_for_review(self):
        for answer in ("", "Fictional response"):
            with self.subTest(answer=answer):
                session = DesktopSession()
                self.addCleanup(session.close)
                session.use_sih_clinic_profile()
                record = session.add_patient_bundle([
                    self.write("registration.pdf", registration()),
                    self.write("questionnaire.pdf", clinician_text_questionnaire(answer)),
                ], "SYNTH-001", True)
                self.assertIn("headaches_description", record["applicableFields"])
                self.assertEqual(record["values"]["headaches_description"], "")
                self.assertTrue(any("headaches_description" in issue and "manual" in issue.casefold()
                                    for issue in record["issues"]))
                self.assertNotIn("headaches_description", record["sourceContext"]["unansweredFields"])
                evidence = record["evidence"]["headaches_description"]
                self.assertEqual(evidence["page"], 3)
                self.assertEqual(evidence["text"], "")
                self.assertLess(evidence["region"]["height"], .2)
                self.assertEqual(len(record["values"]), 512)

    def test_permitted_text_answer_is_still_extracted(self):
        self.choose_reader()
        record = self.session.add_patient_bundle([
            self.write("registration.pdf", registration()),
            self.write("questionnaire.pdf", clinician_text_questionnaire("Fictional response", "Courier")),
        ], "SYNTH-001", True)
        self.assertIn("headaches_description", record["applicableFields"])
        self.assertEqual(record["values"]["headaches_description"], "Fictional response")
        self.assertEqual(record["evidence"]["headaches_description"]["text"], "Fictional response")
        self.assertFalse(any("headaches_description" in issue for issue in record["issues"]))

    def test_malformed_date_and_number_remain_active_without_invented_values(self):
        examples = (
            ("headache_start", "3. When did your current headaches first start?", "Unsure"),
            ("standing_up_time", "17. If better lying down: how many minutes?", "Several minutes"),
        )
        for name, prompt, answer in examples:
            with self.subTest(name=name):
                session = DesktopSession()
                self.addCleanup(session.close)
                session.use_sih_clinic_profile()
                record = session.add_patient_bundle([
                    self.write("registration.pdf", registration()),
                    self.write("questionnaire.pdf", clinician_text_questionnaire(answer, "Courier", prompt=prompt)),
                ], "SYNTH-001", True)
                self.assertIn(name, record["applicableFields"])
                self.assertEqual(record["values"][name], "")
                self.assertTrue(any(name in issue and "manual" in issue.casefold() for issue in record["issues"]))
                self.assertNotIn(name, record["sourceContext"]["unansweredFields"])

    def test_unlocated_text_prompt_is_not_added_to_review(self):
        self.choose_reader()
        record = self.session.add_patient_bundle([
            self.write("registration.pdf", registration()),
            self.write("questionnaire.pdf", clinician_questionnaire()),
        ], "SYNTH-001", True)
        self.assertIn("headaches_yn", record["applicableFields"])
        self.assertNotIn("headaches_description", record["applicableFields"])

    def test_unreadable_text_can_be_recovered_and_confirmed_manually(self):
        self.choose_reader()
        record = self.session.add_patient_bundle([
            self.write("registration.pdf", registration()),
            self.write("questionnaire.pdf", clinician_text_questionnaire("Fictional response")),
        ], "SYNTH-001", True)
        self.assertIn("headaches_description", record["applicableFields"])
        values = {**record["values"], "headaches_description": "Fictional response"}
        saved = self.session.review_record(record["id"], values, record["applicableFields"], "Fictional reviewer")
        self.assertEqual(saved["values"]["headaches_description"], "Fictional response")
        self.assertNotIn("headaches_description", saved["confirmed"])
        approved = self.session.review_record(saved["id"], saved["values"], saved["applicableFields"],
                                              "Fictional reviewer", True)
        self.assertEqual(approved["status"], "approved")
        self.assertIn("headaches_description", approved["confirmed"])

    def test_malformed_hit6_table_cannot_omit_required_answers_or_guess_columns(self):
        self.choose_reader()
        for index, kwargs in enumerate(({"frequency_headers": False}, {"first_mark_x": 15}, {"first_mark_x": 602})):
            with self.subTest(kwargs=kwargs):
                session = DesktopSession()
                self.addCleanup(session.close)
                session.use_sih_clinic_profile()
                with self.assertRaises(InputError):
                    session.add_patient_bundle([
                        self.write(f"registration-{index}.pdf", registration()),
                        self.write(f"malformed-table-{index}.pdf", hit6(**kwargs)),
                    ], "SYNTH-001", True)

    def test_declared_instrument_page_count_must_be_complete(self):
        self.choose_reader()
        with self.assertRaises(InputError):
            self.session.add_patient_bundle([
                self.write("registration.pdf", registration()),
                self.write("partial-questionnaire.pdf", clinician_questionnaire(declared_pages=4)),
            ], "SYNTH-001", True)


if __name__ == "__main__":
    unittest.main()
