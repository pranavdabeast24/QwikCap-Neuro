"""Verify patient bundles and the 512-column PACE export with fictional PDFs.

Run from a clone with requirements installed. No supplied study documents or
reserved evaluation dataset are read. --bundle uses the real packaged worker.
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
from pypdf import PdfReader
from reportlab.pdfgen import canvas

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
from desktop_model import DesktopSession
from server import InputError

HEADER_DIGEST = "0ea2180b9abc8978130930158e81addfe5d2309118daa2be3f7fbe12ad2c604a"
SIZE = (612, 792)
DRAWINGS = [
    ("patient_sex", 2, 680, "Female", "1"),
    ("patient_dob", 2, 644, "02/29/2000", "2000-02-29"),
    ("headaches_yn", 2, 608, "Yes", "1"),
    ("med_caf", 2, 572, "Taken, no change in symptoms", "2"),
    ("baseline_opening_pressure", 2, 536, "12.5", "12.5"),
    ("patient_race___1", 2, 500, "Checked", "1"),
    ("patient_race___2", 2, 464, "Unchecked", "0"),
    ("patient_race___3", 2, 428, "", ""),
    ("med_caf_v2", 3, 680, "Taken, no change in symptoms", "3"),
    ("csf_volume_delta", 3, 644, "-20.5", "-20.5"),
    ("hit6_severity", 3, 608, "Rarely", "8"),
]
STUDY_ID = "SYN-PACE-001"
EXPECTED = {"record_id": STUDY_ID, **{name: value for name, _, _, _, value in DRAWINGS}}


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def reject(call, message):
    try:
        call()
    except (InputError, ValueError):
        return
    raise AssertionError(message)


def fixture(part):
    stream = io.BytesIO()
    pdf = canvas.Canvas(stream, pagesize=SIZE, invariant=1)
    pdf.setTitle("Fictional PACE software acceptance form")
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(48, 748, "FICTIONAL SOFTWARE ACCEPTANCE")
    pdf.setFont("Helvetica", 10)
    pdf.drawString(48, 726, "Generated example only. No patient records or user dataset.")
    for name, page, y, raw, _ in DRAWINGS:
        if page != part + 1:
            continue
        pdf.setFont("Helvetica", 9)
        pdf.drawString(48, y, name)
        pdf.rect(250, y - 8, 312, 28)
        pdf.setFont("Helvetica", 11)
        pdf.drawString(262, y, raw)
    pdf.setFont("Helvetica", 10)
    pdf.drawString(48, 160, "Outside-mask distractor: Taken, symptoms worsened")
    pdf.drawString(48, 140, "Outside-mask distractor date: 01/01/1980")
    pdf.drawString(48, 120, "Checkbox text tests coded entry; image mark recognition is not tested.")
    pdf.showPage()
    pdf.save()
    return stream.getvalue()


def expected_columns():
    path = APP / "spreadsheets/pace-import-template.csv"
    rows = list(csv.reader(io.StringIO(path.read_text(encoding="utf-8-sig"))))
    require(len(rows) == 1, "The shipped study template contains record rows")
    names = rows[0]
    require(len(names) == len(set(names)) == 512, "Expected exactly 512 named destination columns")
    actual = hashlib.sha256(json.dumps(names, separators=(",", ":")).encode()).hexdigest()
    require(actual == HEADER_DIGEST, "Header names/order differ from the independently recorded supplied reference")
    return names


def normalized_cell(value):
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def check_rows(rows, columns):
    require(len(rows) == 2, "Two source forms did not produce exactly one patient data row")
    require(rows[0] == columns, "Export header names/order changed")
    wanted = [EXPECTED.get(name, "") for name in columns]
    require(rows[1] == wanted, "Exported cells differ from the independent fictional answer key")
    require(rows[1][columns.index("patient_race___2")] == "0", "A reviewed zero was lost")
    require(rows[1][columns.index("patient_race___3")] == "", "An absent observation became an unchecked zero")
    require(all(rows[1][columns.index(name)] == "" for name in
                ("redcap_repeat_instrument", "redcap_repeat_instance", "redcap_data_access_group", "hit6_complete")),
            "Repeat, access-group or completion metadata was invented")


def verify(output, report):
    columns = expected_columns()
    files = [output / "fictional-intake.pdf", output / "fictional-followup.pdf"]
    for index, path in enumerate(files, 1):
        path.write_bytes(fixture(index))
    sessions = []

    def fresh():
        session = DesktopSession()
        sessions.append(session)
        return session

    def passed(name, **details):
        report["checks"].append({"check": name, "status": "passed", **details})

    try:
        session = fresh()
        require(session.snapshot()["schema"] == [], "Startup has preset executable fields")
        session.use_pace_template()
        state = session.snapshot()
        require(state["schema"] == [] and len(state["expectedFields"]) == 512, "Catalog import created active fields")
        require([c["name"] for c in state["template"]["columns"]] == columns, "Study destination order changed")
        catalog_project = output / "empty-study-project.json"
        session.save_project(catalog_project)
        restored_blank = fresh()
        restored_blank.open_project(catalog_project)
        require(restored_blank.snapshot()["schema"] == [] and len(restored_blank.snapshot()["expectedFields"]) == 512,
                "Empty-project reopening lost the expected field catalog")
        passed("blank startup, explicit 512-field catalog and empty-project roundtrip", destinationColumns=512)

        before = copy.deepcopy(session.snapshot())
        reject(lambda: session.add_patient_bundle(files, STUDY_ID), "Bundle import bypassed explicit same-patient confirmation")
        require(session.snapshot() == before, "Rejected grouping changed live state")
        session.add_patient_bundle(files, STUDY_ID, confirmed_same_patient=True)
        state = session.snapshot()
        require(len(state["records"]) == 1 and len(state["records"][0]["pages"]) == 3,
                "The two forms and operator cover were not one three-page patient record")
        record = state["records"][0]
        require("bundleSources" not in record or all("data" not in item and "sourceData" not in item for item in record["bundleSources"]),
                "Snapshot exposed original source bytes")
        passed("ordered patient source bundle with explicit record identifier and grouping consent", originalForms=2, patientRecords=1)

        for name, _, _, _, _ in DRAWINGS:
            session.add_expected_field(name)
        reject(session.apply_draft, "Selected expected fields applied without masks")
        draft = session.snapshot()["draft"]
        draft["name"] = "Fictional PACE patient bundle"
        for field in draft["fields"]:
            if field["name"] == "record_id":
                draft["identifierField"] = field["id"]
                continue
            _, page, y, _, _ = next(d for d in DRAWINGS if d[0] == field["name"])
            field["region"] = {"page": page, "x": 250 / SIZE[0], "y": (SIZE[1] - y - 20) / SIZE[1],
                               "width": 312 / SIZE[0], "height": 28 / SIZE[1]}
        session.replace_draft(draft)
        session.apply_draft()
        record = session.snapshot()["records"][0]
        require(record["values"] == EXPECTED, "Exact source extraction/code/date mapping differs from the independent answer key")
        require(not record["validationErrors"], "Valid synthetic values failed validation")
        require(record["evidence"]["patient_dob"]["text"] == "02/29/2000", "Normalized date lost its original source evidence")
        for name, page, _, raw, _ in DRAWINGS:
            if raw:
                require(record["evidence"][name]["page"] == page and record["evidence"][name]["mapping"] == "region",
                        "A selected value did not come from its independently drawn source mask")
        passed("selected masks, original date evidence and instrument-specific choice codes", fieldsMatched=len(EXPECTED))

        reject(lambda: session.export("csv", expected_revision=session.snapshot()["template"]["revision"]),
               "Unapproved/unmapped record exported")
        partial = list(record["values"])[1:]
        reject(lambda: session.review_record(record["id"], record["values"], partial, "Fictional verifier", True, record["revision"]),
               "Approval accepted an unconfirmed field")
        record = session.snapshot()["records"][0]
        session.review_record(record["id"], record["values"], list(record["values"]), "Fictional verifier", True, record["revision"])
        session.set_mapping({name: name for name in EXPECTED}, False, session.snapshot()["template"]["revision"])
        revision = session.snapshot()["template"]["revision"]
        session.leave_remaining_columns_blank(revision)
        state = session.snapshot()
        mappings = state["template"]["mappings"]
        require(len(mappings) == 512 and not state["template"]["confirmed"], "Explicit blank action bypassed mapping confirmation")
        require(all(mappings[n] == (n if n in EXPECTED else None) for n in columns), "Explicit blank action overwrote a mapped field")
        reject(lambda: session.leave_remaining_columns_blank(revision), "Stale blank action was accepted")
        reject(lambda: session.export("csv", expected_revision=state["template"]["revision"]), "Unconfirmed mapping exported")
        session.set_mapping(mappings, True, state["template"]["revision"])
        passed("field approval, explicit blank decisions and stale mapping gates", explicitlyBlankColumns=512-len(EXPECTED))

        csv_path = output / "pace-one-patient.csv"
        session.export("csv", csv_path, expected_revision=session.snapshot()["template"]["revision"])
        with csv_path.open(encoding="utf-8-sig", newline="") as stream:
            check_rows(list(csv.reader(stream)), columns)
        passed("independently reopened exact-width CSV has one patient row from two source forms", headersMatched=512, cellsMatched=512)

        workbook = openpyxl.Workbook()
        workbook.active.append(columns)
        xlsx_input = output / "fictional-wide-blank-template.xlsx"
        workbook.save(xlsx_input)
        workbook.close()
        session.import_template(xlsx_input)
        require(not session.snapshot()["template"]["confirmed"], "New destination retained mapping consent")
        session.set_mapping(mappings, True, session.snapshot()["template"]["revision"])
        xlsx_path = output / "pace-one-patient.xlsx"
        session.export("xlsx", xlsx_path, expected_revision=session.snapshot()["template"]["revision"])
        workbook = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=False)
        try:
            check_rows([[normalized_cell(v) for v in row] for row in workbook.active.iter_rows(values_only=True)], columns)
        finally:
            workbook.close()
        passed("independently reopened 512-column XLSX preserves blank, zero and date values", headersMatched=512, cellsMatched=512)

        type_path = output / "fictional-patient-bundle-type.json"
        session.save_form_type(type_path)
        definition = json.loads(type_path.read_text())
        require(set(definition) == {"format", "name", "identifierField", "pages", "fields"}, "Reusable type contains non-rule data")
        require(len(definition["fields"]) == len(EXPECTED), "Reusable type contains the full expected catalog")
        require(STUDY_ID not in type_path.read_text() and all(path.name not in type_path.read_text() for path in files),
                "Reusable type leaked a study ID or source filename")
        passed("saved reusable type contains only selected rules and masks", fields=len(EXPECTED))

        project_path = output / "fictional-patient-bundle-project.json"
        session.save_project(project_path)
        body = json.loads(project_path.read_text())
        originals = body["records"][0].get("bundleSources", [])
        require(len(originals) == 2, "Project did not preserve both original input forms")
        for original, path in zip(originals, files):
            raw = base64.b64decode(original["sourceData"], validate=True)
            require(raw == path.read_bytes(), "Project changed original source bytes or source order")
            require(hashlib.sha256(raw).hexdigest() == original["sha256"], "Original source hash is incorrect")
        reopened = fresh()
        reopened.open_project(project_path)
        state = reopened.snapshot()
        require(len(state["expectedFields"]) == 512 and len(state["records"]) == 1, "Project reopening lost expected fields or patient bundle")
        require(state["records"][0]["values"] == EXPECTED, "Project changed reviewed patient values")
        require(state["records"][0]["status"] != "approved" and not state["records"][0]["confirmed"]
                and not state["template"]["confirmed"], "Project reopening bypassed fresh review gates")
        passed("patient project preserves exact original PDFs and clears review gates on reopening", originalsPreserved=2)

        before = copy.deepcopy(reopened.snapshot())
        bad = output / "populated-reference.csv"
        with bad.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(columns)
            writer.writerow(["SYNTHETIC RECORD ROW"] + [""] * 511)
        reject(lambda: reopened.load_expected_fields(bad), "A populated destination was treated as a blank field catalog")
        require(reopened.snapshot() == before, "Rejected catalog import changed current patient state")
        passed("invalid populated template rejects transactionally")
        report.update(destinationColumns=512, patientRows=1, originalForms=2, mappedFields=len(EXPECTED), exportedCellsMatched=1024)
    finally:
        for session in reversed(sessions):
            session.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--output", type=Path, default=APP / "verification/pace")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    report = {"notice": "Generated fictional software acceptance data only; no user dataset read.",
              "method": "Independent physical PDF geometry and literal answer key; CSV/XLSX reopened independently.",
              "nativeUI": "Not covered; requires separate native app verification.", "worker": "source", "checks": []}
    status = 0
    try:
        with ExitStack() as stack:
            if args.bundle:
                bundle = args.bundle.resolve()
                runtime = bundle / "Contents/Frameworks" if bundle.suffix == ".app" else bundle / "_internal"
                stack.enter_context(patch.object(sys, "frozen", True, create=True))
                stack.enter_context(patch.object(sys, "_MEIPASS", str(runtime), create=True))
                if sys.platform == "darwin":
                    stack.enter_context(patch.dict(os.environ, {"PATH": ""}))
                report.update(worker="real packaged companion", bundle=bundle.name)
            verify(args.output, report)
        report["status"] = "passed"
    except Exception as error:
        status = 1
        report.update(status="failed", error=f"{type(error).__name__}: {error}")
    target = args.output / "pace-results.json"
    target.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "checksPassed": len(report["checks"]), "report": str(target),
                      **({"error": report["error"]} if status else {})}))
    raise SystemExit(status)


if __name__ == "__main__":
    main()
