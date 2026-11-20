"""Verify automatic PACE patient review with generated fictional PDFs only.

The optional bundle runs document, PDF-bundle and spreadsheet jobs through its
packaged companion. Native window operation has a separate acceptance check.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import copy
import csv
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
from desktop_model import DesktopSession, InputError


CHECKS = (
    "auto-canonical-pace-catalog", "proposed-exact-mrn-group", "group-confirmation-and-temporary-id",
    "typed-choice-and-field-approval", "rules-only-loadout", "matching-layout-new-patient",
    "one-patient-csv-512", "one-patient-xlsx-512", "project-reopen-fresh-gates",
)


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def reject(action, message):
    try:
        action()
    except (InputError, ValueError):
        return
    raise AssertionError(message)


def fixture(kind, *, mrn, first, date, study="SYNTH-SOURCE-17"):
    output = io.BytesIO()
    pdf = canvas.Canvas(output, pagesize=(612, 792), invariant=1)
    pdf.setTitle("Fictional automatic PACE software acceptance")
    if kind == "registration":
        pdf.drawString(40, 730, "Patient Registration Form")
        pdf.drawString(40, 690, f"Last name Fictional First name {first} M.I.")
        pdf.drawString(40, 660, "Date of birth (mm/dd/yyyy) 02/03/1980 Sex: Female Male Other")
        pdf.drawString(40, 620, "Cell phone (555) 010-0100 Email invented@example.invalid")
        pdf.drawString(40, 90, f"OFFICE USE ONLY MRN: {mrn} Research Study ID: {study}")
        pdf.drawString(40, 50, "REG-100 Rev 02/2026 Page 1 of 1")
    else:
        pdf.drawString(390, 740, f"FICTIONAL, {first.upper()}")
        pdf.drawString(390, 725, "DOB 02/03/1980 Sex F")
        pdf.drawString(390, 710, f"MRN {mrn}")
        pdf.drawString(390, 695, f"Research Study ID: {study}")
        pdf.drawString(40, 660, "HIT-6 Headache Impact Test")
        pdf.drawString(40, 630, f"Date {date}")
        pdf.setFont("Helvetica", 8)
        for x, label in zip((350, 400, 455, 510, 568), ("Never", "Rarely", "Sometimes", "Very", "Always")):
            pdf.drawCentredString(x, 590, label)
        questions = ("Pain severe", "Limit your ability to do usual daily activities", "Wish you could lie down",
                     "Felt too tired", "Fed up or irritated", "Limit your ability to concentrate")
        for index, question in enumerate(questions, 1):
            y = 590 - index * 40
            pdf.drawString(40, y, str(index))
            pdf.drawString(60, y, question)
            pdf.drawCentredString(350 if index == 1 else 400, y, "X")
        pdf.drawString(40, 50, "HA-230 Rev 02/2026 Page 1 of 1")
    pdf.save()
    return output.getvalue()


def verify(output, report):
    sessions = []

    def fresh():
        session = DesktopSession()
        session.use_pace_auto_profile()
        sessions.append(session)
        return session

    def passed(name, **details):
        require(name == CHECKS[len(report["checks"])], "Acceptance check order changed")
        report["checks"].append({"check": name, "status": "passed", **details})

    def sources(prefix, **values):
        paths = []
        for kind in ("registration", "hit6"):
            path = output / f"fictional-{prefix}-{kind}.pdf"
            path.write_bytes(fixture(kind, **values))
            paths.append(path)
        return paths

    def confirm(session, paths):
        proposal = session.import_pace_documents(paths)
        require(not proposal["failed"] and len(proposal["groups"]) == 1, "Expected one complete proposed patient")
        group = proposal["groups"][0]
        require(not group["issues"] and group["sourceCount"] == 2, "Fictional sources unexpectedly require resolution")
        result = session.confirm_pace_groups([group["id"]], confirmed_identity=True)
        require(not result["failed"] and len(result["added"]) == 1, "Confirmed sources did not create one patient row")
        return session.snapshot()["records"][0]

    try:
        session = fresh()
        state = session.snapshot()
        columns = [field["name"] for field in state["schema"]]
        require(state["profile"] == "pace-auto-v1" and len(columns) == len(set(columns)) == 512,
                "Automatic PACE did not retain all canonical destinations")
        require([column["name"] for column in state["template"]["columns"]] == columns and not state["template"]["confirmed"],
                "Automatic PACE template or initial mapping gate changed")
        passed(CHECKS[0], destinationColumns=512)

        paths = sources("first", mrn="00001234", first="Ada", date="04/05/2026")
        result = session.import_pace_documents(paths)
        require(not result["failed"] and len(result["groups"]) == 1 and not session.snapshot()["records"],
                "Source import skipped proposed patient review")
        group = result["groups"][0]
        require(group["mrn"] == "00001234" and group["sourceCount"] == 2 and not group["issues"],
                "Exact source identity or patient grouping changed")
        require(set(group["instruments"]) == {"patient_records", "hit6"}, "Expected source instruments were not recognized")
        passed(CHECKS[1], originalForms=2, patientRows=1)

        before = copy.deepcopy(session.snapshot())
        reject(lambda: session.confirm_pace_groups([group["id"]]), "Grouping bypassed explicit source identity confirmation")
        require(session.snapshot() == before, "Rejected confirmation changed live patient state")
        session.confirm_pace_groups([group["id"]], confirmed_identity=True)
        record = session.snapshot()["records"][0]
        export_id = record["values"]["record_id"]
        require(export_id == "NEW000001" and export_id not in {"00001234", "SYNTH-SOURCE-17"},
                "Export identifier was substituted for source identity")
        require(record["sourceContext"]["profile"] == "pace-auto-v1" and record["sourceContext"]["recordIds"] == ["SYNTH-SOURCE-17"]
                and record["paceIdentityConfirmed"] and len(record["bundleSources"]) == 2,
                "Automatic profile identity metadata or source bundle is incomplete")
        passed(CHECKS[2], patientRows=1, originalForms=2)

        reject(lambda: session.review_record(record["id"], record["values"], [], "Fictional verifier", True),
               "Patient approval skipped field confirmation")
        values = {**record["values"], "hit6_severity": "13"}
        saved = session.review_record(record["id"], values, record["applicableFields"], "Fictional verifier")
        require("hit6_severity" not in saved["confirmed"], "Changed typed answer kept its old confirmation")
        reject(lambda: session.review_record(saved["id"], {**values, "hit6_severity": "99"}, [], "Fictional verifier", True),
               "A noncanonical choice code was approved")
        saved = session.review_record(saved["id"], {**values, "hit6_severity": "6"}, [], "Fictional verifier")
        require(saved["values"]["hit6_severity"] == "6" and not saved["validationErrors"],
                "A source-backed typed choice did not retain its canonical code")
        passed(CHECKS[3])

        proof = saved["evidence"]["hit6_date"]
        corrected = session.correct_pace_field(saved["id"], "hit6_date", {"page": proof["page"], **proof["region"]}, saved["revision"])
        require(corrected["values"]["hit6_date"] == "2026-04-05" and session.snapshot()["profile"] == "pace-auto-v1",
                "Answer-area correction lost source date or canonical profile")
        layout_path = output / "fictional-form-layout.json"
        session.save_pace_loadout(layout_path)
        layout = layout_path.read_text(encoding="utf-8")
        require(json.loads(layout)["rules"] and all(private not in layout for private in
                ("00001234", "SYNTH-SOURCE-17", "NEW000001", "Ada", "FICTIONAL", "2026-04-05", "sourceData")),
                "Saved layout contains patient answers or source identity")
        passed(CHECKS[4])

        other = fresh()
        other.load_pace_loadout(layout_path)
        next_record = confirm(other, sources("second", mrn="00009876", first="Bea", date="05/06/2026"))
        require(next_record["values"]["mrn"] == "00009876" and next_record["values"]["hit6_date"] == "2026-05-06"
                and next_record["evidence"]["hit6_date"]["mapping"] == "pace-layout-answer-area"
                and not next_record["confirmed"], "Loaded layout reused patient data or skipped fresh answer review")
        passed(CHECKS[5])

        record = session.snapshot()["records"][0]
        session.review_record(record["id"], record["values"], record["applicableFields"], "Fictional verifier", True)
        session.set_mapping(dict(session.snapshot()["template"]["mappings"]), True)
        csv_path = output / "fictional-one-patient.csv"
        session.export("csv", csv_path, expected_revision=session.snapshot()["template"]["revision"])
        rows = list(csv.reader(io.StringIO(csv_path.read_text(encoding="utf-8-sig"))))
        expected = [record["values"][name] for name in columns]
        require(len(rows) == 2 and rows[0] == columns and rows[1] == expected, "CSV did not preserve one exact 512-column patient row")
        passed(CHECKS[6], patientRows=1, headersMatched=512, cellsMatched=512)

        blank = output / "fictional-blank-512.xlsx"
        workbook = openpyxl.Workbook()
        workbook.active.append(columns)
        workbook.save(blank)
        workbook.close()
        session.import_template(blank)
        session.set_mapping({name: name for name in columns}, True)
        xlsx_path = output / "fictional-one-patient.xlsx"
        session.export("xlsx", xlsx_path, expected_revision=session.snapshot()["template"]["revision"])
        workbook = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=False)
        try:
            xlsx_rows = [["" if value is None else str(value) for value in row] for row in workbook.active.iter_rows(values_only=True)]
            require(len(xlsx_rows) == 2 and xlsx_rows[0] == columns and xlsx_rows[1] == expected,
                    "XLSX did not preserve one exact 512-column patient row")
        finally:
            workbook.close()
        passed(CHECKS[7], patientRows=1, headersMatched=512, cellsMatched=512)

        project = output / "fictional-patient-project.json"
        session.save_project(project)
        reopened = fresh()
        reopened.open_project(project)
        restored = reopened.snapshot()["records"][0]
        require(restored["values"]["record_id"] == export_id and restored["values"] == record["values"]
                and not restored["paceIdentityConfirmed"] and not restored["confirmed"] and restored["status"] == "review"
                and not reopened.snapshot()["template"]["confirmed"], "Project reopening changed IDs or retained approval gates")
        reject(lambda: reopened.review_record(restored["id"], restored["values"], restored["applicableFields"], "Fictional verifier", True),
               "Reopened project approved before source identity was checked again")
        reopened.confirm_pace_identity(restored["id"], confirmed=True)
        restored = reopened.snapshot()["records"][0]
        reopened.review_record(restored["id"], restored["values"], restored["applicableFields"], "Fictional verifier", True)
        passed(CHECKS[8])
        report.update(destinationColumns=512, patientRows=1, originalForms=2, exportedCellsMatched=1024)
    finally:
        for session in reversed(sessions):
            session.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    report = {"format": "qwikcap-pace-auto-acceptance-v1", "status": "failed", "worker": "source",
              "notice": "Generated fictional software acceptance data only. No user dataset read.",
              "nativeUI": "Not covered. Run the separate native startup and UI acceptance checks.", "checks": []}
    try:
        with ExitStack() as stack:
            if args.bundle:
                bundle = args.bundle.resolve()
                runtime = bundle / "Contents/Frameworks" if bundle.suffix == ".app" else bundle / "_internal"
                require(runtime.is_dir(), "Name a complete native application bundle")
                stack.enter_context(patch.object(sys, "frozen", True, create=True))
                stack.enter_context(patch.object(sys, "_MEIPASS", str(runtime), create=True))
                if sys.platform == "darwin":
                    stack.enter_context(patch.dict(os.environ, {"PATH": ""}))
                report["worker"] = "real packaged companion"
            verify(output, report)
        require(tuple(item["check"] for item in report["checks"]) == CHECKS, "Required automatic PACE checks are incomplete")
        report["status"] = "passed"
    except Exception as error:
        report["failure"] = str(error) if isinstance(error, (AssertionError, InputError)) else "Automatic PACE acceptance could not complete"
    target = output / "pace-auto-results.json"
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "worker": report["worker"], "checksPassed": len(report["checks"]),
                      **({"failure": report["failure"]} if "failure" in report else {})}))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
