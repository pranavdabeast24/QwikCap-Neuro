"""Independent custom-mask acceptance using generated fictional PDFs only.

Run from a clone with the dependencies in requirements.txt installed. --bundle
routes extraction and spreadsheet export through the real packaged companion,
without a listener. All fixtures and evidence are generated under --output; no
user dataset, existing form, or reserved evaluation material is read.
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
import traceback
from unittest.mock import patch

import openpyxl
from reportlab.pdfgen import canvas

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
from desktop_model import DesktopSession  # noqa: E402
from server import InputError  # noqa: E402


# Independent physical page geometry and answer key. Regions are computed from
# these drawing rectangles, never inferred from OCR, evidence, or source code.
PAGE_SIZE = (612, 792)
DRAWINGS = [
    {"id": "maskreference", "name": "record_id", "label": "Case reference", "type": "text", "page": 1, "baseline": 650},
    {"id": "maskcount", "name": "sample_count", "label": "Parcel count", "type": "integer", "page": 1, "baseline": 570},
    {"id": "masknote", "name": "notes", "label": "Dispatch note", "type": "text", "page": 2, "baseline": 650},
    {"id": "maskdate", "name": "event_date", "label": "Shipment date", "type": "date", "page": 2, "baseline": 570},
]
ANSWERS = [
    {"record_id": "SYN-ALPHA-104", "sample_count": "17", "notes": "Blue paper folder", "event_date": "2026-01-14"},
    {"record_id": "SYN-BETA-205", "sample_count": "42", "notes": "Amber archive box", "event_date": "2026-02-25"},
]


def pdf_bytes(values, *, pages=2, page_size=PAGE_SIZE):
    stream = io.BytesIO()
    pdf = canvas.Canvas(stream, pagesize=page_size, invariant=1)
    pdf.setTitle("Fictional custom-mask acceptance form")
    for page in range(1, pages + 1):
        pdf.setFont("Helvetica-Bold", 18)
        pdf.drawString(52, page_size[1] - 52, "FICTIONAL SHIPPING LOG")
        pdf.setFont("Helvetica", 11)
        pdf.drawString(52, page_size[1] - 76, f"Synthetic acceptance fixture — page {page}")
        for drawing in DRAWINGS:
            if drawing["page"] != page:
                continue
            y = drawing["baseline"]
            pdf.setFont("Helvetica", 12)
            pdf.drawString(52, y, drawing["label"])
            pdf.rect(230, y - 8, 310, 32, stroke=1, fill=0)
            pdf.setFont("Helvetica", 14)
            pdf.drawString(245, y, values[drawing["name"]])
        # Same-label distractors prove the selected values came from the masks.
        pdf.setFont("Helvetica", 11)
        pdf.drawString(52, 430, "Case reference: SYN-DECOY-999")
        pdf.drawString(52, 410, "Parcel count: 999")
        pdf.drawString(52, 390, "Dispatch note: Outside all selected rectangles")
        pdf.drawString(52, 370, "Shipment date: 2025-12-31")
        pdf.drawString(52, 52, "Generated fictional shipping data. No patient or user data.")
        pdf.showPage()
    pdf.save()
    return stream.getvalue()


def expected_fields():
    width, height = PAGE_SIZE
    fields = []
    for drawing in DRAWINGS:
        field = {key: drawing[key] for key in ("id", "name", "label", "type")}
        field.update(required=True, aliases=[], region={
            "page": drawing["page"], "x": 230 / width,
            "y": (height - drawing["baseline"] - 24) / height,
            "width": 310 / width, "height": 32 / height,
        })
        if field["type"] == "integer":
            field.update(min=0, max=1000)
        fields.append(field)
    return fields


def expected_pages():
    return [{"page": page, "aspectRatio": PAGE_SIZE[0] / PAGE_SIZE[1]} for page in (1, 2)]


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def rejected(callable_, message):
    try:
        callable_()
    except InputError as error:
        return str(error)
    raise AssertionError(message)


def checked_type_document(body, fixture_names):
    """An exact structural allowlist rejects hidden payloads at every level."""
    require(isinstance(body, dict), "Type root must be an object")
    root_keys = {"format", "name", "identifierField", "fields", "pages"}
    require(set(body) == root_keys, f"Unexpected type root keys: {set(body) ^ root_keys}")
    require(body["format"] == "formbridge-form-type-v1", "Wrong saved type format")
    require(body["name"] == "Fictional shipping log", "Type name was not retained")
    require(body["identifierField"] == "record_id", "Explicit identifier was not retained")
    require(body["pages"] == expected_pages(), "Type page geometry differs from physical fixture geometry")
    require(isinstance(body["fields"], list) and len(body["fields"]) == len(DRAWINGS), "Type has the wrong fields")
    expected = {field["name"]: field for field in expected_fields()}
    for field in body["fields"]:
        original = expected[field["name"]]
        wanted_keys = set(original) - {"id"}
        require(set(field) == wanted_keys, f"Unexpected type field keys: {set(field) ^ wanted_keys}")
        for key in ("name", "label", "type", "required", "aliases", "region"):
            require(field[key] == original[key], f"Saved definition changed {field['name']}.{key}")
        require(set(field["region"]) == {"page", "x", "y", "width", "height"}, "Region includes an unlisted key")
        if original["type"] == "integer":
            require(field.get("min") == 0 and field.get("max") == 1000, "Numeric limits were not retained")
    for page in body["pages"]:
        require(set(page) == {"page", "aspectRatio"}, "Page includes an unlisted key")
    encoded = json.dumps(body)
    for forbidden in fixture_names + [value for answer in ANSWERS for value in answer.values()]:
        require(forbidden not in encoded, f"Reusable type leaked a filename or extracted answer: {forbidden}")


def snapshot_state(session):
    return copy.deepcopy(session.snapshot())


def check_extracted(record, expected):
    require(record["values"] == expected, f"Exact extraction mismatch: {record['values']!r}")
    require(not record["validationErrors"], f"Unexpected value validation errors: {record['validationErrors']}")
    for drawing in DRAWINGS:
        name = drawing["name"]
        proof = record["evidence"][name]
        require(proof["mapping"] == "region", f"{name} was not extracted by its region")
        require(proof["page"] == drawing["page"], f"{name} evidence is on the wrong page")
        require(proof["text"] == expected[name], f"{name} evidence text differs from independent answer")
        region = next(f["region"] for f in expected_fields() if f["name"] == name)
        require(region["x"] <= proof["region"]["x"] < region["x"] + region["width"], f"{name} evidence x is outside its mask")
        require(region["y"] <= proof["region"]["y"] < region["y"] + region["height"], f"{name} evidence y is outside its mask")


def export_checks(session, output, expected):
    session.use_categories_as_columns()
    state = session.snapshot()
    require(not state["template"]["confirmed"], "New columns bypassed mapping confirmation")
    rejected(lambda: session.export("csv", expected_revision=state["template"]["revision"]), "Export accepted unconfirmed mapping")
    mapping = {drawing["name"]: drawing["name"] for drawing in DRAWINGS}
    session.set_mapping(mapping, True)
    revision = session.snapshot()["template"]["revision"]
    names = list(expected)
    wanted = [names, [expected[name] for name in names]]
    results = []
    for format_ in ("csv", "xlsx"):
        target = output / f"custom-mask-export.{format_}"
        session.export(format_, target, expected_revision=revision)
        if format_ == "csv":
            with target.open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.reader(stream))
        else:
            workbook = openpyxl.load_workbook(target, read_only=True, data_only=False)
            try:
                rows = [["" if value is None else str(value) for value in row] for row in workbook.active.iter_rows(values_only=True)]
            finally:
                workbook.close()
        require(rows == wanted, f"Independently reopened {format_} cells differ: {rows!r}")
        results.append({"file": target.name, "records": 1, "cellsMatched": len(names), "headersMatched": len(names)})
    return results


def approve(session, record):
    return session.review_record(record["id"], record["values"], list(record["values"]),
                                 "Fictional acceptance verifier", True, record["revision"])


def verify(output, report):
    fixtures = [output / "fictional-shipping-alpha.pdf", output / "fictional-shipping-beta.pdf"]
    for fixture, answer in zip(fixtures, ANSWERS):
        fixture.write_bytes(pdf_bytes(answer))
    (output / "independent-answer-key.json").write_text(json.dumps({"notice": "Generated fictional shipping data only.", "answers": ANSWERS, "fields": expected_fields(), "pages": expected_pages()}, indent=2) + "\n")
    sessions = []

    def fresh():
        session = DesktopSession()
        sessions.append(session)
        return session

    def passed(name, **evidence):
        report["checks"].append({"check": name, "status": "passed", **evidence})

    try:
        designer = fresh()
        state = designer.snapshot()
        require(state.get("phase") == "empty" and state["schema"] == [] and state["records"] == [], "Fresh session must start with no fields or documents")
        require(not state.get("formType"), "Fresh session must not have a preset form type")
        blank_project = output / "blank-project.formbridge.json"
        designer.save_project(blank_project)
        blank_restored = fresh()
        blank_restored.open_project(blank_project)
        require(blank_restored.snapshot()["schema"] == [] and blank_restored.snapshot()["records"] == [], "Blank project does not roundtrip")
        passed("blank start and blank project roundtrip")

        initial = designer.add_document(fixtures[0].read_bytes(), fixtures[0].name)
        state = designer.snapshot()
        require(state.get("phase") == "design" and state["schema"] == [], "First document must open unconfigured design mode")
        require(len(state["records"]) == 1 and len(state["records"][0]["pages"]) == 2, "First PDF was not rendered as two pages")
        require(all(Path(path).is_file() for path in state["records"][0]["pagePaths"].values()), "Rendered page paths are unavailable")
        draft = copy.deepcopy(state["draft"])
        draft.update(name="Fictional shipping log", identifierField="maskreference", fields=expected_fields(), pages=expected_pages())
        designer.replace_draft(draft)
        designer.apply_draft()
        state = designer.snapshot()
        require(state.get("phase") == "review", "Apply must enter review")
        check_extracted(state["records"][0], ANSWERS[0])
        passed("first PDF renders blank and custom page masks extract exact values", fieldsMatched=4)

        type_path = output / "fictional-shipping.formtype.json"
        designer.save_form_type(type_path)
        type_document = json.loads(type_path.read_text())
        checked_type_document(type_document, [path.name for path in fixtures])
        passed("saved reusable type strict structural allowlist and no source or answer leakage", rootKeys=sorted(type_document))

        processor = fresh()
        processor.load_form_type(type_path)
        require(not processor.snapshot()["records"], "Loading type unexpectedly loads source documents")
        second = processor.add_document(fixtures[1].read_bytes(), fixtures[1].name)
        check_extracted(second, ANSWERS[1])
        require(not second["confirmed"] and second["status"] == "review", "New extraction bypassed review")
        rejected(lambda: processor.export("csv", mapped=False), "Unapproved record exported")
        second = approve(processor, second)
        require(second["status"] == "approved", "Explicit field confirmations did not approve record")
        report["exports"] = export_checks(processor, output, ANSWERS[1])
        passed("fresh session type reuse, exact second-form extraction, review and independent exports", fieldsMatched=4, exportedCellsMatched=8)

        project_path = output / "custom-masks-project.formbridge.json"
        processor.save_project(project_path)
        restored = fresh()
        restored.open_project(project_path)
        reopened = restored.snapshot()
        require(reopened.get("formType") == processor.snapshot().get("formType"), "Project lost custom form type")
        require(len(reopened["records"]) == 1, "Project lost source")
        record = reopened["records"][0]
        check_extracted(record, ANSWERS[1])
        require(record["status"] == "review" and record["confirmed"] == [] and not record["reviewedBy"], "Project reopen retained approvals or confirmations")
        require(not reopened["template"]["confirmed"], "Project reopen retained mapping confirmation")
        rejected(lambda: restored.export("csv", expected_revision=reopened["template"]["revision"]), "Restored project bypassed export gates")
        passed("project restores definitions and source while clearing all review gates")

        processor.start_design()
        edited = copy.deepcopy(processor.snapshot()["draft"])
        edited["name"] = "Fictional shipping log revised"
        edited["fields"][0]["label"] = "Case reference revised"
        processor.replace_draft(edited)
        rejected(lambda: processor.export("csv", expected_revision=processor.snapshot()["template"]["revision"]), "Unfinished setup exported")
        processor.apply_draft()
        edited_state = processor.snapshot()
        check_extracted(edited_state["records"][0], ANSWERS[1])
        require(edited_state["records"][0]["status"] == "review" and not edited_state["records"][0]["confirmed"], "Type editing retained approvals")
        require(not edited_state["template"]["confirmed"], "Type editing retained mapping confirmation")
        passed("unfinished setup blocks export and applying edited type reprocesses and clears gates")

        malformed_cases = []
        for label, change in (
            ("unknown top-level data", lambda b: b.update(sourceData="MUST-NOT-LOAD")),
            ("unknown field data", lambda b: b["fields"][0].update(evidence={"text": "MUST-NOT-LOAD"})),
            ("duplicate name", lambda b: b["fields"][1].update(name=b["fields"][0]["name"])),
            ("invalid field name", lambda b: b["fields"][1].update(name="Bad field!")),
            ("missing identifier", lambda b: b.update(identifierField="")),
            ("invalid rectangle", lambda b: b["fields"][0]["region"].update(x=0.95, width=0.3)),
            ("missing page definition", lambda b: b.update(pages=b["pages"][:1])),
        ):
            body = copy.deepcopy(type_document)
            change(body)
            invalid_path = output / ("invalid-" + label.replace(" ", "-") + ".json")
            invalid_path.write_text(json.dumps(body))
            before = snapshot_state(restored)
            message = rejected(lambda: restored.load_form_type(invalid_path), f"Invalid type accepted: {label}")
            require(restored.snapshot() == before, f"Failed type load changed live state: {label}")
            malformed_cases.append({"case": label, "message": message})
        malformed_path = output / "invalid-json.json"
        malformed_path.write_text('{"format": "formbridge-form-type-v1",')
        before = snapshot_state(restored)
        rejected(lambda: restored.load_form_type(malformed_path), "Malformed JSON type accepted")
        require(restored.snapshot() == before, "Malformed JSON changed live state")
        passed("invalid type files reject transactionally", cases=malformed_cases + [{"case": "malformed JSON"}])

        for label, data in (("missing page", pdf_bytes(ANSWERS[1], pages=1)),
                            ("incompatible aspect ratio", pdf_bytes(ANSWERS[1], page_size=(792, 612)))):
            incompatible = fresh()
            incompatible.load_form_type(type_path)
            before = snapshot_state(incompatible)
            try:
                bad_record = incompatible.add_document(data, label.replace(" ", "-") + ".pdf")
            except InputError as error:
                require(incompatible.snapshot() == before, f"Rejected {label} upload changed state")
                passed(label + " blocks processing", message=str(error))
                continue
            problems = " ".join(str(value) for value in (bad_record.get("issues"), bad_record.get("validationErrors"), bad_record.get("formTypeIssues")))
            require(any(word in problems.lower() for word in ("page", "geometry", "aspect", "layout")), f"{label} has no explicit incompatibility evidence")
            rejected(lambda: approve(incompatible, bad_record), f"{label} record could be approved")
            rejected(lambda: incompatible.export("csv", mapped=False), f"{label} record could be exported")
            passed(label + " blocks approval and export", issues=problems)

        discard = fresh()
        discard.add_document(fixtures[0].read_bytes(), fixtures[0].name)
        initial_draft = copy.deepcopy(discard.snapshot()["draft"])
        invalid_draft = copy.deepcopy(initial_draft)
        invalid_draft.update(name="Invalid draft", identifierField="", fields=expected_fields(), pages=expected_pages())
        discard.replace_draft(invalid_draft)
        before = snapshot_state(discard)
        rejected(lambda: discard.apply_draft(), "Missing-identifier draft applied")
        require(discard.snapshot() == before, "Invalid draft apply changed state")
        processor.start_design()
        before_discard = copy.deepcopy(processor.snapshot()["formType"])
        processor.discard_draft()
        require(processor.snapshot()["phase"] == "review" and processor.snapshot()["formType"] == before_discard, "Discard changed the applied type")
        passed("invalid draft apply rejects transactionally and discarding edit preserves applied type")
    finally:
        for session in reversed(sessions):
            session.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, help="Real macOS .app or Windows application directory to exercise")
    parser.add_argument("--output", type=Path, default=APP / "verification/custom-masks",
                        help="Generated fictional fixtures, exports and JSON report (default: verification/custom-masks)")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    report = {"notice": "Generated fictional shipping data only; no user dataset read.",
              "method": "Independent DesktopSession acceptance; normalized masks derived from reportlab drawing geometry; exported files reopened independently",
              "nativeUI": "Not covered by this script; requires separate native-control evidence.",
              "worker": "source", "checks": [], "exports": []}
    status = 0
    try:
        with ExitStack() as stack:
            if args.bundle:
                bundle = args.bundle.resolve()
                runtime = bundle / "Contents/Frameworks" if bundle.suffix == ".app" else bundle / "_internal"
                helper = runtime / "helpers" / ("FormbridgeWorker.exe" if os.name == "nt" else "FormbridgeWorker")
                require(helper.is_file(), "Packaged companion worker is missing")
                stack.enter_context(patch.object(sys, "frozen", True, create=True))
                stack.enter_context(patch.object(sys, "_MEIPASS", str(runtime), create=True))
                if sys.platform == "darwin":
                    stack.enter_context(patch.dict(os.environ, {"PATH": ""}))
                report["worker"] = "real packaged companion"
                report["bundle"] = str(bundle)
            verify(args.output, report)
        report["status"] = "passed"
    except Exception as error:
        status = 1
        report.update(status="failed", error=f"{type(error).__name__}: {error}", traceback=traceback.format_exc())
    target = args.output / "custom-mask-results.json"
    target.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "checksPassed": len(report["checks"]), "report": str(target), **({"error": report["error"]} if status else {})}))
    raise SystemExit(status)


if __name__ == "__main__":
    main()
