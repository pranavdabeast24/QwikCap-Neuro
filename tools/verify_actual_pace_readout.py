"""Independently compare named fictional train artifacts without changing them.

Only catalog metadata is used. Application extraction and session code are never
imported. Diagnostics contain field names and reasons, never expected or actual
cell values. No records, approvals, projects, or workbooks are created.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import unicodedata
import zipfile

from openpyxl import load_workbook


ROOT = Path(__file__).resolve().parents[1]
CONTEXT = {"redcap_repeat_instrument", "redcap_repeat_instance", "redcap_data_access_group"}
FIELD_NAME = re.compile(r"[a-z][a-z0-9_]{0,99}")
TYPES = {"text", "date", "integer", "number", "choice"}


class InputProblem(ValueError):
    def __init__(self, reason, field=None):
        super().__init__(reason)
        self.field = field


@dataclass
class Expectations:
    columns: list
    fields: dict
    raw_fields: dict
    documents: list
    document_values: dict
    patients: dict
    explicit_rows: int
    inferred_zero_rows: int
    inferred_patient_zero_cells: int
    key_only_rows: int


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InputProblem("Duplicate JSON object keys")
        result[key] = value
    return result


def read_json(path, maximum=64 * 1024 * 1024):
    path = Path(path)
    if not path.is_file() or path.stat().st_size > maximum:
        raise InputProblem("A named JSON input is absent or exceeds its size limit")
    try:
        return json.loads(path.read_bytes(), object_pairs_hook=_unique_object,
                          parse_constant=lambda _: (_ for _ in ()).throw(InputProblem("Nonfinite JSON constant")))
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise InputProblem("A named input is not supported JSON") from exc


def canonical(value, field):
    if not isinstance(value, str):
        raise InputProblem("Expected a text representation", field["name"])
    if value == "":
        return ""
    kind = field["type"]
    if kind == "literal":
        return value
    if kind == "choice":
        if value not in field.get("choices", {}):
            raise InputProblem("Invalid literal choice code", field["name"])
        return value
    if kind in {"integer", "number"}:
        try:
            number = Decimal(value)
        except InvalidOperation as exc:
            raise InputProblem("Invalid numeric representation", field["name"]) from exc
        if not number.is_finite() or (kind == "integer" and number != number.to_integral_value()):
            raise InputProblem("Invalid finite numeric value", field["name"])
        return number
    if kind == "date":
        try:
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                return date.fromisoformat(value).isoformat()
            if re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", value):
                return datetime.strptime(value, "%m/%d/%Y").date().isoformat()
        except ValueError:
            pass
        raise InputProblem("Invalid calendar date", field["name"])
    return " ".join(unicodedata.normalize("NFKC", value).split())


def build_expectations(expected, catalog, census=None):
    if not isinstance(catalog, dict) or not isinstance(catalog.get("columns"), list) or not isinstance(catalog.get("fields"), list):
        raise InputProblem("Catalog needs ordered columns and field metadata")
    columns = catalog["columns"]
    if (len(columns) != 512 or len(set(columns)) != 512
            or any(not isinstance(name, str) or not FIELD_NAME.fullmatch(name) for name in columns)
            or [field.get("name") for field in catalog["fields"]] != columns):
        raise InputProblem("Catalog must contain exactly 512 ordered unique fields")
    fields = {field["name"]: field for field in catalog["fields"]}
    if "record_id" not in fields or not CONTEXT.issubset(fields):
        raise InputProblem("Catalog is missing record context fields")
    for field in fields.values():
        if field.get("type") not in TYPES or not isinstance(field.get("sourceField"), str):
            raise InputProblem("Unsupported catalog field metadata", field["name"])
        if field["type"] == "choice" and not isinstance(field.get("choices"), dict):
            raise InputProblem("Choice metadata is missing", field["name"])
    families = {}
    for field in fields.values():
        if (field["type"] == "choice" and "___" in field["name"]
                and set(field.get("choices", {})) == {"0", "1"}):
            families.setdefault(field["sourceField"], []).append(field["name"])
    if not isinstance(expected, dict) or not isinstance(expected.get("documents"), list) or not expected["documents"]:
        raise InputProblem("Expected JSON needs a nonempty documents list")
    documents = expected["documents"]
    names = [document.get("formFile") for document in documents]
    if (any(not isinstance(name, str) or Path(name).name != name for name in names)
            or len(set(names)) != len(names)):
        raise InputProblem("Expected document filenames must be unique plain filenames")
    census_documents = {}
    if census is not None:
        if not isinstance(census, dict) or not isinstance(census.get("documents"), list):
            raise InputProblem("Census JSON needs a documents list")
        for entry in census["documents"]:
            if not isinstance(entry, dict) or not isinstance(entry.get("file"), str):
                raise InputProblem("Census document lacks its explicit filename")
            name = Path(entry["file"]).name
            if name in census_documents:
                raise InputProblem("Duplicate census document")
            census_documents[name] = entry
        if set(census_documents) != set(names):
            raise InputProblem("Census and expected document coverage differ")
    patients = {}
    assigned = {}
    document_values = {}
    explicit_rows = inferred_rows = 0
    key_only_rows = 0
    raw_fields = dict(fields)
    inferred_pairs, explicit_pairs = set(), set()
    for document in documents:
        name = document["formFile"]
        identifiers = document.get("identifiers")
        record_id = identifiers.get("recordID") if isinstance(identifiers, dict) else None
        if not isinstance(record_id, str) or not record_id:
            raise InputProblem("Expected document needs a literal header record ID", "record_id")
        rows = document.get("fields")
        if not isinstance(rows, list) or not rows:
            raise InputProblem("Expected document needs explicit field rows")
        values, seen = {}, set()
        visible_families = set()
        for row in rows:
            field_name = row.get("name") if isinstance(row, dict) else None
            if not isinstance(field_name, str) or not FIELD_NAME.fullmatch(field_name):
                raise InputProblem("Invalid literal expected field identifier")
            if field_name not in fields:
                raw_fields.setdefault(field_name, {"name": field_name, "type": "literal"})
                key_only_rows += 1
            if field_name in seen:
                raise InputProblem("Duplicate explicit expected field within document", field_name)
            seen.add(field_name)
            raw = row.get("expectedRaw")
            values[field_name] = canonical(raw, raw_fields[field_name])
            if field_name in CONTEXT and values[field_name] != "":
                raise InputProblem("Repeat and access-group context must be blank", field_name)
            explicit_pairs.add((record_id, field_name))
            if field_name in fields:
                family = fields[field_name]["sourceField"]
                if field_name in families.get(family, []):
                    visible_families.add(family)
            explicit_rows += 1
        if "record_id" in values and values["record_id"] != record_id:
            raise InputProblem("Literal record field conflicts with key header", "record_id")
        values["record_id"] = record_id
        if census is not None:
            entry = census_documents[name]
            if entry.get("record_id") != record_id:
                raise InputProblem("Census identity conflicts with key header", "record_id")
            observed = entry.get("visible_choice_families")
            if not isinstance(observed, list):
                raise InputProblem("Census document needs visible choice families")
            for family in observed:
                if not isinstance(family, dict):
                    raise InputProblem("Malformed visible choice family")
                if family.get("kind") != "checkbox_group":
                    continue
                source = family.get("source_field")
                if source not in families:
                    raise InputProblem("Visible checkbox family is absent from catalog")
                if any(fields[member].get("instrument") != identifiers.get("formType") for member in families[source]):
                    raise InputProblem("Census checkbox family belongs to another instrument")
                visible_families.add(source)
        for family in visible_families:
            for member in families[family]:
                if member not in values:
                    values[member] = "0"
                    inferred_pairs.add((record_id, member))
                    inferred_rows += 1
        document_values[name] = values
        patients.setdefault(record_id, {column: "" for column in columns})
        assigned.setdefault(record_id, {})
        for field_name, value in values.items():
            if field_name in assigned[record_id] and assigned[record_id][field_name] != value:
                raise InputProblem("Conflicting expected repeats; evaluation stopped", field_name)
            assigned[record_id][field_name] = value
            if field_name in fields:
                patients[record_id][field_name] = value
    return Expectations(columns, fields, raw_fields, documents, document_values, patients, explicit_rows,
                        inferred_rows, len(inferred_pairs - explicit_pairs), key_only_rows)


def cell_problem(value, expected, field, excel=False, data_type=None, present=True):
    if not present:
        return "Missing destination field"
    if data_type in {"f", "e"}:
        return "Formula or spreadsheet error"
    if not excel and not isinstance(value, str):
        return "Saved project values must be text"
    if expected == "":
        return None if value in (None, "") else "Expected blank was populated"
    kind = field["type"]
    if excel:
        if kind in {"integer", "number"}:
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                return "Expected a finite Excel number"
            value = str(value)
        elif not isinstance(value, str):
            return "Expected literal Excel text for identifier, date, text, or code"
    try:
        actual = canonical(value, field)
    except InputProblem:
        return "Invalid destination representation"
    if actual == expected:
        return None
    return "Literal choice code mismatch" if kind == "choice" else "Normalized value mismatch"


def compare_patient_rows(rows, expectations, excel=False):
    issues, matched, checked = [], set(), 0
    patient_indices = {record_id: index for index, record_id in enumerate(expectations.patients, 1)}
    for row_index, row in enumerate(rows, 2):
        values = row.get("values") if isinstance(row, dict) else None
        if not isinstance(values, dict):
            issues.append({"row": row_index, "field": "record_id", "reason": "Malformed patient row"})
            continue
        identifier = values.get("record_id")
        if excel and hasattr(identifier, "value"):
            identifier = identifier.value
        if not isinstance(identifier, str) or identifier not in expectations.patients:
            issues.append({"row": row_index, "field": "record_id", "reason": "Patient ID is absent, non-text, or unexpected"})
            continue
        patient_index = patient_indices[identifier]
        if identifier in matched:
            issues.append({"row": row_index, "patient_index": patient_index, "field": "record_id", "reason": "Duplicate patient row"})
            continue
        matched.add(identifier)
        if set(values) - set(expectations.columns):
            issues.append({"row": row_index, "patient_index": patient_index, "reason": "Unexpected destination fields"})
        for field_name in expectations.columns:
            value = values.get(field_name)
            data_type = None
            if excel and value is not None:
                data_type, value = value.data_type, value.value
            problem = cell_problem(value, expectations.patients[identifier][field_name],
                                   expectations.fields[field_name], excel, data_type, field_name in values)
            checked += 1
            if problem:
                issues.append({"row": row_index, "patient_index": patient_index, "field": field_name, "reason": problem})
    for identifier, patient_index in patient_indices.items():
        if identifier not in matched:
            issues.append({"patient_index": patient_index, "field": "record_id", "reason": "Missing patient row"})
    return {"patient_rows_expected": len(expectations.patients), "patient_rows_matched": len(matched),
            "full_expected_cells": len(expectations.patients) * len(expectations.columns),
            "full_checked_cells": checked, "issues": issues}


def verify_project(project, expectations):
    if not isinstance(project, dict) or project.get("format") not in {"formbridge-project-v1", "formbridge-project-v2"}:
        raise InputProblem("Name an app-saved project JSON")
    if not isinstance(project.get("records"), list):
        raise InputProblem("Saved project needs patient records")
    result = compare_patient_rows(project["records"], expectations)
    schema = project.get("schema")
    if not isinstance(schema, list) or [field.get("name") if isinstance(field, dict) else None for field in schema] != expectations.columns:
        result["issues"].insert(0, {"reason": "Project field order differs from catalog"})
    return result


def verify_workbook(workbook, expectations):
    issues = []
    if len(workbook.worksheets) != 1:
        issues.append({"reason": "Expected exactly one worksheet"})
    for sheet in workbook.worksheets:
        if (sheet.sheet_state != "visible" or any(dimension.hidden for dimension in sheet.row_dimensions.values())
                or any(dimension.hidden for dimension in sheet.column_dimensions.values())):
            issues.append({"reason": "Workbook contains hidden content"})
        for cell in sheet._cells.values():
            if cell.data_type in {"f", "e"}:
                field = expectations.columns[cell.column - 1] if cell.column <= len(expectations.columns) else None
                issue = {"row": cell.row, "reason": "Formula or spreadsheet error"}
                if field is not None:
                    issue["field"] = field
                issues.append(issue)
        if sheet.merged_cells.ranges:
            issues.append({"reason": "Workbook contains merged cells"})
    if not workbook.worksheets:
        return {"patient_rows_expected": len(expectations.patients), "patient_rows_matched": 0,
                "full_expected_cells": len(expectations.patients) * len(expectations.columns),
                "full_checked_cells": 0, "issues": issues + [{"reason": "Workbook has no worksheet"}]}
    sheet = workbook.worksheets[0]
    if sheet.max_column != len(expectations.columns) or sheet.max_row != len(expectations.patients) + 1:
        issues.append({"reason": "Workbook dimensions differ from the complete patient readout"})
    if [sheet.cell(1, index).value for index in range(1, len(expectations.columns) + 1)] != expectations.columns:
        issues.append({"reason": "Header order differs from catalog"})
    rows = [{"values": {name: sheet.cell(row, column) for column, name in enumerate(expectations.columns, 1)}}
            for row in range(2, min(sheet.max_row, len(expectations.patients) + 2) + 1)]
    result = compare_patient_rows(rows, expectations, excel=True)
    result["issues"] = issues + result["issues"]
    return result


def verify_extraction(extraction, expectations):
    payload = extraction.get("documents") if isinstance(extraction, dict) else None
    if isinstance(payload, dict):
        if "filename" in payload and "result" in payload:
            payload = [payload]
        else:
            payload = [{"filename": filename, "result": result.get("result", result) if isinstance(result, dict) else result}
                       for filename, result in payload.items()]
    if not isinstance(payload, list):
        raise InputProblem("Extraction JSON needs named documents")
    documents = {}
    for item in payload:
        if not isinstance(item, dict) or not isinstance(item.get("filename"), str):
            raise InputProblem("Extraction document needs its explicit filename")
        filename = Path(item["filename"]).name
        if filename in documents:
            raise InputProblem("Duplicate extraction document")
        documents[filename] = item.get("result")
    issues, checked, matched, zeros_checked, key_only_checked, key_only_matched = [], 0, 0, 0, 0, 0
    for document in expectations.documents:
        filename = document["formFile"]
        result = documents.get(filename)
        if not isinstance(result, dict) or not isinstance(result.get("values"), dict) or not isinstance(result.get("applicableFields"), list):
            issues.append({"document": filename, "reason": "Missing or malformed extraction result"})
            continue
        values, active = result["values"], result["applicableFields"]
        if any(not isinstance(name, str) for name in active) or len(set(active)) != len(active):
            raise InputProblem("Malformed applicable field list")
        if set(active) - set(expectations.raw_fields) or set(values) - set(expectations.raw_fields):
            issues.append({"document": filename, "reason": "Unexpected extraction destinations"})
        for field in document["fields"]:
            name = field["name"]
            if name in values:
                checked += 1
                if name not in expectations.fields:
                    key_only_checked += 1
            problem = cell_problem(values.get(name), canonical(field["expectedRaw"], expectations.raw_fields[name]),
                                   expectations.raw_fields[name], present=name in values)
            if name not in expectations.fields and name not in values:
                problem = "Key-only expectation was not supplied by extraction diagnostics"
            if name in expectations.fields and name not in active:
                issues.append({"document": filename, "field": name, "reason": "Explicit key field is not applicable"})
            elif problem is None:
                matched += 1
                if name not in expectations.fields:
                    key_only_matched += 1
            if problem:
                issues.append({"document": filename, "field": name, "reason": problem})
        explicit = {field["name"] for field in document["fields"]}
        for name, expected in expectations.document_values[filename].items():
            if name in explicit or name == "record_id":
                continue
            if name in values:
                zeros_checked += 1
            problem = cell_problem(values.get(name), expected, expectations.fields[name], present=name in values)
            if name not in active:
                issues.append({"document": filename, "field": name, "reason": "Visible checkbox destination is not applicable"})
            if problem:
                issues.append({"document": filename, "field": name, "reason": problem})
    if set(documents) - {document["formFile"] for document in expectations.documents}:
        issues.append({"reason": "Unexpected extraction documents"})
    return {"documents_expected": len(expectations.documents), "documents_present": len(documents),
            "raw_key_rows_expected": expectations.explicit_rows, "raw_key_rows_checked": checked,
            "raw_key_rows_matched": matched, "key_only_rows": expectations.key_only_rows,
            "key_only_rows_checked": key_only_checked, "key_only_rows_matched": key_only_matched,
            "mapped_key_rows": expectations.explicit_rows - expectations.key_only_rows,
            "inferred_zero_rows_checked": zeros_checked, "issues": issues}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-json", required=True, type=Path)
    parser.add_argument("--catalog-json", type=Path, default=ROOT / "study_profiles/pace.json")
    parser.add_argument("--census-json", type=Path)
    parser.add_argument("--extraction-json", type=Path)
    readout = parser.add_mutually_exclusive_group(required=True)
    readout.add_argument("--project-json", type=Path)
    readout.add_argument("--xlsx", type=Path)
    args = parser.parse_args(argv)
    paths = {name: path for name, path in vars(args).items() if path is not None}
    try:
        for path in paths.values():
            if not path.is_file() or path.stat().st_size > 64 * 1024 * 1024:
                raise InputProblem("A named input is absent or exceeds its size limit")
        before = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in paths.items()}
        expectations = build_expectations(read_json(args.expected_json), read_json(args.catalog_json),
                                          read_json(args.census_json) if args.census_json else None)
        package_issues = []
        if args.project_json:
            report = verify_project(read_json(args.project_json), expectations)
        else:
            with zipfile.ZipFile(args.xlsx) as archive:
                members = archive.infolist()
                if len(members) > 1000 or sum(member.file_size for member in members) > 50 * 1024 * 1024:
                    raise InputProblem("Workbook package exceeds supported bounds")
                names = [member.filename.lower() for member in members]
                if len(set(names)) != len(names):
                    raise InputProblem("Workbook package has duplicate parts")
                if any("externallinks/" in name or "vbaproject" in name for name in names):
                    package_issues.append({"reason": "Workbook contains external or active content"})
            workbook = load_workbook(args.xlsx, data_only=False, read_only=False, keep_links=False)
            try:
                report = verify_workbook(workbook, expectations)
            finally:
                workbook.close()
        report["issues"] = package_issues + report["issues"]
        report.update(columns=len(expectations.columns), documents=len(expectations.documents),
                      raw_key_rows=expectations.explicit_rows,
                      raw_key_rows_expected=expectations.explicit_rows,
                      mapped_key_rows=expectations.explicit_rows - expectations.key_only_rows,
                      key_only_rows=expectations.key_only_rows,
                      key_only_fields=sorted(set(expectations.raw_fields) - set(expectations.fields)),
                      inferred_checkbox_zero_rows=expectations.inferred_zero_rows,
                      inferred_patient_checkbox_zero_cells=expectations.inferred_patient_zero_cells)
        if args.extraction_json:
            report["document_diagnostics"] = verify_extraction(read_json(args.extraction_json), expectations)
        after = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in paths.items()}
        if before != after:
            raise InputProblem("An input changed during verification")
        report["input_unchanged"] = True
        report["input_sha256"] = before
        report["readout_passed"] = not report["issues"]
        report["raw_diagnostics_requested"] = args.extraction_json is not None
        report["raw_diagnostics_passed"] = not report["document_diagnostics"]["issues"] if args.extraction_json else None
        report["passed"] = report["readout_passed"] and report["raw_diagnostics_passed"] is not False
        report["issue_count"] = len(report["issues"]) + len(report.get("document_diagnostics", {}).get("issues", []))
        print(json.dumps(report, ensure_ascii=False))
        return 0 if report["passed"] else 1
    except InputProblem as exc:
        issue = {"reason": str(exc)}
        if exc.field is not None:
            issue["field"] = exc.field
        print(json.dumps({"passed": False, "input_error": True, "issues": [issue]}))
        return 2
    except (OSError, KeyError, TypeError, ValueError, AttributeError, zipfile.BadZipFile):
        print(json.dumps({"passed": False, "input_error": True,
                          "issues": [{"reason": "Could not verify the named fictional inputs"}]}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
