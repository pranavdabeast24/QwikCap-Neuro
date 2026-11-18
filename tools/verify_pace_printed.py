"""Verify the packaged PACE reader using one invented native-control PDF.

This checks the console companion directly. It does not drive the GUI, create
reviews or approve records. No dataset or answer-key files are opened.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from reportlab.pdfgen import canvas

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
from pace_profile import PROFILE, profile_schema
from runtime_paths import process_options
from server import terminate_tree


EXPECTED = {
    "record_id": "SYNTH-PACKAGED-01", "pt_email": "fictional@example.invalid",
    "mrn": "00001234", "patient_first": "Ada", "patient_last": "Fictional",
    "patient_dob": "1980-01-02", "patient_sex": "2",
    **{f"patient_race___{code}": "1" if code in (5, 6) else "0" for code in range(1, 9)},
    "patient_records_complete": "2",
}


class VerificationError(ValueError):
    pass


def require(value, message):
    if not value:
        raise VerificationError(message)


def synthetic_pdf():
    output = io.BytesIO()
    pdf = canvas.Canvas(output, pagesize=(612, 792), pageCompression=1)
    pdf.setFont("Helvetica", 9)
    pdf.drawString(40, 755, "Fictional packaged-reader acceptance form")
    pdf.drawRightString(570, 755, "Record ID: " + EXPECTED["record_id"])
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(40, 725, "Patient Records")
    pdf.setFont("Helvetica", 9)
    for y in (700, 665, 630, 595, 560, 525, 490, 455, 340, 300):
        pdf.line(40, y, 570, y)
    for label, value, y in (
        ("Record ID", EXPECTED["record_id"], 680),
        ("Email", EXPECTED["pt_email"], 645),
        ("Patient Medical Record Number", EXPECTED["mrn"], 610),
        ("Patient First Name", EXPECTED["patient_first"], 575),
        ("Patient Last Name", EXPECTED["patient_last"], 540),
        ("Patient Date of Birth", "01/02/1980", 505),
    ):
        pdf.drawString(45, y, label)
        pdf.drawString(300, y, value)
    pdf.drawString(45, 470, "Patient Sex")
    for index, (label, code) in enumerate((("Female", "1"), ("Male", "2"), ("Other", "3"))):
        x = 300 + index * 85
        pdf.circle(x, 474, 5, fill=0)
        pdf.drawString(x + 10, 470, label)
        if code == EXPECTED["patient_sex"]:
            pdf.drawCentredString(x, 471, "X")
    pdf.drawString(45, 433, "Patient Race")
    labels = (
        "American Indian or Alaska Native", "Asian", "Black or African American",
        "Native Hawaiian or Other Pacific Islander", "White", "Other", "Choose Not to Answer", "Unavailable",
    )
    for index, label in enumerate(labels):
        x, y = 300, 433 - index * 12
        pdf.rect(x - 5, y - 1, 10, 10, fill=0)
        pdf.drawString(x + 10, y, label)
        if EXPECTED[f"patient_race___{index + 1}"] == "1":
            pdf.drawCentredString(x, y, "X")
    pdf.drawString(45, 315, "Complete?")
    for index, (label, code) in enumerate((("Incomplete", "0"), ("Unverified", "1"), ("Complete", "2"))):
        x = 300 + index * 85
        pdf.circle(x, 319, 5, fill=0)
        pdf.drawString(x + 10, 315, label)
        if code == EXPECTED["patient_records_complete"]:
            pdf.drawCentredString(x, 316, "X")
    pdf.drawString(40, 275, "Fictional acceptance fixture - patient_records")
    pdf.save()
    return output.getvalue()


def verify(helper, output, report):
    require(helper.is_file() and (os.name == "nt" or os.access(helper, os.X_OK)),
            "Name an executable packaged companion")
    schema = profile_schema()
    require(len(schema) == 512 and schema[0].get("profile") == PROFILE,
            "The source canonical PACE schema is incomplete")
    with tempfile.TemporaryDirectory(prefix="fictional-pace-", dir=output) as temporary:
        payload = {"data": base64.b64encode(synthetic_pdf()).decode("ascii"),
                   "filename": "invented-patient-records.pdf", "schema": schema,
                   "assetDir": temporary, "recordId": "invented-packaged-pace"}
        process = subprocess.Popen([str(helper), "document"], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   cwd=output, **process_options())
        try:
            stdout, stderr = process.communicate(json.dumps(payload, ensure_ascii=True).encode("ascii"), timeout=90)
        except subprocess.TimeoutExpired:
            terminate_tree(process)
            process.communicate(timeout=15)
            raise VerificationError("Packaged PACE reader exceeded its deadline") from None
        report.update(exitCode=process.returncode, stdoutSHA256=hashlib.sha256(stdout).hexdigest(),
                      stderrSHA256=hashlib.sha256(stderr).hexdigest())
        require(process.returncode == 0 and len(stdout) <= 2 * 1024 * 1024,
                "Packaged PACE reader failed or returned oversized JSON")
        response = json.loads(stdout.decode("ascii"))
        require(isinstance(response, dict) and "error" not in response,
                "Packaged PACE reader returned an error")
        values, context = response.get("values", {}), response.get("sourceContext", {})
        require(set(values) == {field["name"] for field in schema}, "Packaged schema destinations changed")
        require(all(values.get(name) == value for name, value in EXPECTED.items()),
                "Packaged identity or visible-control extraction changed")
        require(set(response.get("applicableFields", [])) == set(EXPECTED),
                "Observed source-field applicability changed")
        require(all(value == "" for name, value in values.items() if name not in EXPECTED),
                "An absent source field was populated")
        require(context.get("profile") == PROFILE and context.get("recordIds") == [EXPECTED["record_id"]]
                and context.get("instruments") == ["patient_records"]
                and context.get("instrumentStarts") == [{"instrument": "patient_records", "page": 1}]
                and context.get("blockingIssues") == [], "Packaged source identity metadata is incomplete")
        require(context.get("identities") == [{"recordId": EXPECTED["record_id"], "firstName": "Ada",
                "lastName": "Fictional", "dob": EXPECTED["patient_dob"], "mrn": EXPECTED["mrn"], "page": 1}],
                "Packaged patient identity changed")
        require(response.get("issues") == [] and len(response.get("pages", [])) == 1,
                "Invented printed form requires unexpected manual review")
        require(all(response.get("evidence", {}).get(name, {}).get("method") == "pdf-text"
                    for name in EXPECTED), "Native text/control evidence was not retained")
    report.update(status="passed", documents=1, extractedMatches=len(EXPECTED), destinationColumns=512,
                  uncheckedZeros=6, inactiveBlanks=512 - len(EXPECTED), desktopUIUsed=False,
                  reviewsCreated=0, approvalsCreated=0,
                  checks=[{"check": name, "status": "passed"} for name in
                          ("packaged-catalog-resource", "canonical-destinations", "source-identity",
                           "visible-radio-and-checkbox-controls", "absent-fields-stay-blank", "native-evidence")])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--helper", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    report = {"format": "quickcap-packaged-pace-printed-v1", "status": "failed", "desktopUIUsed": False}
    try:
        verify(args.helper.resolve(), output, report)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        report["failure"] = str(exc) if isinstance(exc, VerificationError) else "Packaged PACE check could not complete"
    (output / "pace-printed-results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("status", "documents", "extractedMatches", "destinationColumns", "failure") if key in report}))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
