"""Verify the SIH clinic reader and exports with invented native PDF fixtures.

No supplied dataset, answer keys, manifest or patient documents are read.
--bundle runs the real packaged companion through DesktopSession.
"""
from __future__ import annotations

import argparse
import base64
from contextlib import ExitStack
import copy
import csv
from datetime import date, datetime
import hashlib
import io
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

import openpyxl
from reportlab.pdfgen import canvas

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
from desktop_model import DesktopSession
from server import InputError

SIZE = (612, 792)
STUDY_ID = "SYNTH-CLINIC-001"
MRN = "00001234"
HEADER_DIGEST = "0ea2180b9abc8978130930158e81addfe5d2309118daa2be3f7fbe12ad2c604a"
HIT_ROWS = (
    ("hit6_severity", "Pain severe", 0, "6"),
    ("hit6_limitactivities", "Limit your ability to do usual daily activities", 1, "8"),
    ("hit6_liedown", "Wish you could lie down", 2, "10"),
    ("hit6_tired", "Felt too tired", 3, "11"),
    ("hit6_irritated", "Fed up or irritated", 4, "13"),
    ("hit6_limitconcentration", "Limit your ability to concentrate", 1, "8"),
)
EXPECTED = {
    "record_id": STUDY_ID,
    "mrn": MRN,
    "patient_first": "Ada",
    "patient_last": "Example",
    "patient_dob": "1980-02-03",
    "patient_sex": "1",
    "pt_email": "ada@example.invalid",
    "hit6_date": "2026-04-05",
    **{name: value for name, _, _, value in HIT_ROWS},
}


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def reject(call, message):
    try:
        call()
    except (InputError, ValueError):
        return
    raise AssertionError(message)


def registration_fixture():
    stream = io.BytesIO()
    pdf = canvas.Canvas(stream, pagesize=SIZE, invariant=1)
    pdf.setTitle("Invented SIH clinic registration acceptance fixture")
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(40, 750, "Patient Registration Form")
    pdf.setFont("Helvetica", 10)
    pdf.drawString(40, 720, "FICTIONAL SOFTWARE ACCEPTANCE. No patient data.")
    pdf.drawString(40, 690, "Last name Example First name Ada M.I.")
    prefix = "Date of birth (mm/dd/yyyy) 02/03/1980 Sex: "
    pdf.drawString(40, 660, prefix + "Female Male Other")
    left = 40 + pdf.stringWidth(prefix, "Helvetica", 10)
    width = pdf.stringWidth("Female", "Helvetica", 10)
    pdf.setLineWidth(1.2)
    pdf.ellipse(left - 3, 657, left + width + 3, 670, stroke=1, fill=0)
    pdf.drawString(40, 620, "Email ada@example.invalid")
    pdf.drawString(40, 90, f"OFFICE USE ONLY MRN: {MRN} Research Study ID: {STUDY_ID}")
    pdf.drawString(40, 50, "REG-100 Rev 02/2026 Page 1 of 1")
    pdf.save()
    return stream.getvalue()


def hit6_fixture(mrn=MRN):
    stream = io.BytesIO()
    pdf = canvas.Canvas(stream, pagesize=SIZE, invariant=1)
    pdf.setTitle("Invented SIH clinic HIT-6 acceptance fixture")
    pdf.setFont("Helvetica", 10)
    pdf.drawString(40, 770, "FICTIONAL SOFTWARE ACCEPTANCE. No patient data.")
    pdf.drawString(400, 740, "EXAMPLE, ADA")
    pdf.drawString(400, 725, "DOB 02/03/1980 Sex F")
    pdf.drawString(400, 710, f"MRN {mrn}")
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(40, 660, "HIT-6 Headache Impact Test")
    pdf.setFont("Helvetica", 10)
    pdf.drawString(40, 630, "Date 04/05/2026")
    columns = (350, 400, 455, 510, 568)
    pdf.setFont("Helvetica", 8)
    for x, label in zip(columns, ("Never", "Rarely", "Sometimes", "Very", "Always")):
        pdf.drawCentredString(x, 590, label)
    for index, (_, label, column, _) in enumerate(HIT_ROWS, 1):
        y = 590 - index * 40
        pdf.setFont("Helvetica", 8)
        pdf.drawString(40, y, str(index))
        pdf.drawString(60, y, label)
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawCentredString(columns[column], y, "X")
    pdf.setFont("Helvetica", 10)
    pdf.drawString(40, 50, "HA-230 Rev 02/2026 Page 1 of 1")
    pdf.save()
    return stream.getvalue()


def expected_columns():
    rows = list(csv.reader(io.StringIO((APP / "spreadsheets/pace-import-template.csv").read_text(encoding="utf-8-sig"))))
    require(len(rows) == 1, "The shipped destination reference must have headers only")
    columns = rows[0]
    require(len(columns) == len(set(columns)) == 512, "Expected exactly 512 unique destination columns")
    digest = hashlib.sha256(json.dumps(columns, separators=(",", ":")).encode()).hexdigest()
    require(digest == HEADER_DIGEST, "Destination names or order differ from the independently recorded reference")
    return columns


def normalized_cell(value):
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def check_rows(rows, columns):
    require(len(rows) == 2, "Two clinic sources must export exactly one patient row")
    require(rows[0] == columns, "Exported header names or order changed")
    require(rows[1] == [EXPECTED.get(name, "") for name in columns],
            "Exported cells differ from the literal invented fixture values or expected blanks")
    require(all(rows[1][columns.index(name)] == "" for name in (
        "redcap_repeat_instrument", "redcap_repeat_instance", "redcap_data_access_group", "hit6_complete")),
        "Export invented repeat, access-group or completion metadata")


def verify(output, report):
    columns = expected_columns()
    expected = {name: EXPECTED.get(name, "") for name in columns}
    files = [output / "fictional-registration.pdf", output / "fictional-hit6.pdf"]
    files[0].write_bytes(registration_fixture())
    files[1].write_bytes(hit6_fixture())
    negative = output / "rejected-fixtures"
    negative.mkdir(exist_ok=True)
    other_mrn = negative / "fictional-other-mrn.pdf"
    other_mrn.write_bytes(hit6_fixture("99999999"))
    sessions = []

    def fresh():
        session = DesktopSession()
        sessions.append(session)
        return session

    def passed(name, **details):
        report["checks"].append({"check": name, "status": "passed", **details})

    try:
        session = fresh()
        require(session.snapshot()["schema"] == [], "Startup unexpectedly selected extraction fields")
        session.use_sih_clinic_profile()
        state = session.snapshot()
        require(state["profile"] == "sih-clinic-v1", "The explicit SIH clinic reader was not selected")
        require([field["name"] for field in state["schema"]] == columns,
                "Clinic reader did not retain the canonical 512-column destination")
        passed("explicit clinic reader retains canonical destination", destinationColumns=512)

        before = copy.deepcopy(state)
        reject(lambda: session.add_patient_bundle(files, STUDY_ID), "Grouping confirmation was bypassed")
        require(session.snapshot() == before, "Rejected grouping changed live state")
        reject(lambda: session.add_patient_bundle(files, "SYNTH-CLINIC-WRONG", confirmed_same_patient=True),
               "An operator ID conflicting with printed registration was accepted")
        require(session.snapshot() == before, "Rejected operator ID changed live state")
        reject(lambda: session.add_patient_bundle([files[0], other_mrn], STUDY_ID, confirmed_same_patient=True),
               "A conflicting source MRN was accepted")
        require(session.snapshot() == before, "Rejected source identity changed live state")
        passed("grouping, wrong study ID and conflicting MRN reject transactionally", rejectionCases=3)

        session.add_patient_bundle(files, STUDY_ID, confirmed_same_patient=True)
        state = session.snapshot()
        require(len(state["records"]) == 1, "Two source forms did not produce one patient record")
        record = state["records"][0]
        require(len(record["pages"]) == 3, "Expected two original pages and the operator bundle cover")
        require(record["values"] == expected, "Clinic extraction differs from literal invented values or blank coverage")
        require(set(record["applicableFields"]) == set(EXPECTED), "Fixture applicability differs from observable fields")
        require(not record["validationErrors"] and not record["profileBlockingIssues"], "Valid fixture has source validation blockers")
        context = record["sourceContext"]
        require(context["profile"] == "sih-clinic-v1" and context["recordIds"] == [STUDY_ID],
                "Clinic context lost its printed registration study ID")
        anchors = context["registrationAnchors"]
        require(len(anchors) == 1 and anchors[0]["recordId"] == STUDY_ID and anchors[0]["mrn"] == MRN
                and anchors[0]["page"] == 2, "Registration anchor does not identify its original source page")
        other_identity = [identity for identity in context["identities"] if identity["page"] == 3]
        require(len(other_identity) == 1 and other_identity[0]["recordId"] == ""
                and other_identity[0]["mrn"] == MRN, "Non-registration source gained a fabricated study ID")
        require(record["evidence"]["record_id"]["page"] == 2
                and record["evidence"]["record_id"]["mapping"] == "clinic-registration",
                "Export ID came from a fabricated cover instead of printed registration")
        require(record["evidence"]["patient_sex"]["mapping"] == "clinic-circled-choice", "Circled registration choice was not read")
        require(all(record["evidence"][name]["mapping"] == "clinic-table-column" for name, _, _, _ in HIT_ROWS),
                "HIT-6 marks did not come from their printed table columns")
        passed("source anchor, native circle and six native table marks match literal values", fieldsMatched=len(EXPECTED))

        session.use_categories_as_columns()
        template = session.snapshot()["template"]
        require([column["name"] for column in template["columns"]] == columns
                and not template["confirmed"], "Use fields as columns bypassed mapping review or changed headers")
        reject(lambda: session.export("csv", expected_revision=template["revision"]), "An unapproved patient row exported")
        reject(lambda: session.review_record(record["id"], record["values"], record["applicableFields"][1:],
                                             "Invented fixture verifier", True, record["revision"]),
               "Approval accepted an unconfirmed observed field")
        record = session.snapshot()["records"][0]
        session.review_record(record["id"], record["values"], record["applicableFields"],
                              "Invented fixture verifier", True, record["revision"])
        template = session.snapshot()["template"]
        reject(lambda: session.export("csv", expected_revision=template["revision"]), "Unconfirmed column mapping exported")
        session.set_mapping({name: name for name in columns}, True, template["revision"])
        passed("observed field approval and column mapping require separate confirmation", mappedFields=512)

        for kind in ("csv", "xlsx"):
            path = output / f"sih-clinic-one-patient.{kind}"
            session.export(kind, path, expected_revision=session.snapshot()["template"]["revision"])
            if kind == "csv":
                with path.open(encoding="utf-8-sig", newline="") as stream:
                    rows = list(csv.reader(stream))
            else:
                workbook = openpyxl.load_workbook(path, read_only=True, data_only=False)
                try:
                    rows = [[normalized_cell(value) for value in row]
                            for row in workbook.active.iter_rows(values_only=True)]
                finally:
                    workbook.close()
            check_rows(rows, columns)
            report["exports"].append({"format": kind, "records": 1, "headersMatched": 512, "cellsMatched": 512})
            passed(f"independently reopened {kind.upper()} matches every destination cell", headersMatched=512, cellsMatched=512)

        project_path = output / "fictional-sih-clinic-project.json"
        session.save_project(project_path)
        project = json.loads(project_path.read_text(encoding="utf-8"))
        originals = project["records"][0]["bundleSources"]
        require(len(originals) == 2, "Saved project did not preserve both original sources")
        for source, path in zip(originals, files):
            raw = base64.b64decode(source["sourceData"], validate=True)
            require(raw == path.read_bytes() and hashlib.sha256(raw).hexdigest() == source["sha256"],
                    "Saved original source bytes or checksums changed")
        reopened = fresh()
        reopened.open_project(project_path)
        state = reopened.snapshot()
        require(state["profile"] == "sih-clinic-v1" and len(state["records"]) == 1, "Project lost its reader or patient bundle")
        record = state["records"][0]
        require(record["values"] == expected and record["sourceContext"] == context, "Reopening changed extracted values or source identity")
        require(record["status"] != "approved" and not record["confirmed"] and not state["template"]["confirmed"],
                "Reopening retained approval, field confirmations or mapping confirmation")
        passed("saved project preserves original PDFs and reopens with fresh review gates", originalsPreserved=2)
        report.update(documents=2, originalForms=2, destinationColumns=512, patientRows=1,
                      extractedMatches=len(EXPECTED), mappedFields=512, exportedCellsMatched=1024)
    finally:
        for session in reversed(sessions):
            session.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bundle", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    report = {"format": "qwikcap-sih-clinic-acceptance-v1", "status": "failed", "worker": "source",
              "desktopUIUsed": False, "inventedFixturesOnly": True, "suppliedDatasetRead": False,
              "answerKeysRead": False, "manifestRead": False,
              "notice": "Invented software fixtures only. This does not evaluate any supplied train or test packet.",
              "checks": [], "exports": []}
    status = 0
    try:
        with ExitStack() as stack:
            if args.bundle:
                bundle = args.bundle.resolve()
                runtime = bundle / "Contents/Frameworks" if bundle.suffix == ".app" else bundle / "_internal"
                require(runtime.is_dir(), "Packaged runtime directory is missing")
                stack.enter_context(patch.object(sys, "frozen", True, create=True))
                stack.enter_context(patch.object(sys, "_MEIPASS", str(runtime), create=True))
                if sys.platform == "darwin":
                    stack.enter_context(patch.dict(os.environ, {"PATH": ""}))
                report.update(worker="real packaged companion", bundle=bundle.name)
            verify(output, report)
        report["status"] = "passed"
    except Exception as error:
        status = 1
        report.update(status="failed", error=f"{type(error).__name__}: {error}")
    target = output / "sih-clinic-results.json"
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "checksPassed": len(report["checks"]), "report": str(target),
                      **({"error": report["error"]} if status else {})}))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
