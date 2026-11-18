"""Read-only check of the fictional 512-column practice-kit Excel export.

No application session is created. No spreadsheet, record, or approval is changed.
Only counts and field locations are printed, never cell values.
"""
from __future__ import annotations

import argparse
import csv
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import sys
import zipfile

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]


def load_expectations(kit: Path):
    with zipfile.ZipFile(kit) as archive:
        documents = []
        for name in ("answer-key.json", "synthetic-pace-extraction-type.json"):
            entry = archive.getinfo(name)
            if entry.file_size > 5_000_000:
                raise ValueError("Practice-kit metadata exceeds the supported size")
            documents.append(json.loads(archive.read(entry)))
    key, rules = documents
    with (ROOT / "spreadsheets/pace-import-template.csv").open(encoding="utf-8-sig", newline="") as stream:
        columns = next(csv.reader(stream))
    if len(columns) != 512 or len(set(columns)) != 512 or key["columns"] != columns:
        raise ValueError("Practice key must match the shipped 512-column template")
    fields = {field["name"]: field for field in rules["fields"]}
    if list(fields) != columns or len(key["cases"]) != 2:
        raise ValueError("Practice kit must contain 512 ordered fields and two cases")
    for case in key["cases"]:
        if set(case["expectedExport"]) != set(columns) or case["expectedExport"]["record_id"] != case["studyId"]:
            raise ValueError("Practice case does not match its literal expected row")
    return columns, fields, key["cases"]


def verify_workbook(workbook, columns, fields, cases):
    issues = []
    if len(workbook.worksheets) != 1:
        return [{"reason": "Expected exactly one worksheet"}]
    sheet = workbook.worksheets[0]
    if sheet.max_column != len(columns) or sheet.max_row != len(cases) + 1:
        return [{"reason": "Expected exactly 512 columns and two data rows"}]
    if [sheet.cell(1, i + 1).value for i in range(len(columns))] != columns:
        issues.append({"reason": "Header order differs from the REDCap reference"})
    if (sheet.sheet_state != "visible" or any(d.hidden for d in sheet.row_dimensions.values())
            or any(d.hidden for d in sheet.column_dimensions.values())):
        issues.append({"reason": "Export contains hidden content"})
    for row_index, case in enumerate(cases, 2):
        for column_index, name in enumerate(columns, 1):
            cell = sheet.cell(row_index, column_index)
            value, expected, field = cell.value, case["expectedExport"][name], fields[name]
            problem = None
            if cell.data_type in {"f", "e"}:
                problem = "Formula or spreadsheet error"
            elif expected == "":
                if value not in (None, ""):
                    problem = "Expected blank was populated"
            elif field["type"] in {"integer", "number"} and not field.get("choices") and name != "record_id":
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                    problem = "Expected a finite Excel number"
                elif Decimal(str(value)) != Decimal(expected):
                    problem = "Numeric value mismatch"
            elif not isinstance(value, str) or value != expected:
                problem = "Literal text, date, identifier, or choice mismatch"
            if problem:
                issues.append({"row": row_index, "column": column_index, "field": name, "reason": problem})
    return issues


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xlsx", type=Path)
    parser.add_argument("--kit", type=Path, default=ROOT / "examples/pace-synthetic-practice.zip")
    args = parser.parse_args()
    try:
        if not args.xlsx.is_file() or args.xlsx.stat().st_size > 20 * 1024 * 1024:
            raise ValueError("Name an existing practice export smaller than 20 MiB")
        columns, fields, cases = load_expectations(args.kit)
        before = hashlib.sha256(args.xlsx.read_bytes()).hexdigest()
        workbook = load_workbook(args.xlsx, data_only=False, read_only=False)
        try:
            issues = verify_workbook(workbook, columns, fields, cases)
        finally:
            workbook.close()
        if hashlib.sha256(args.xlsx.read_bytes()).hexdigest() != before:
            raise ValueError("The input changed during verification")
        print(json.dumps({"passed": not issues, "rows": 2, "columns": 512, "checked_cells": 1024,
                          "issue_count": len(issues), "issues": issues, "xlsx_sha256": before,
                          "input_unchanged": True}))
        return 1 if issues else 0
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile):
        print("Could not verify the named fictional workbook and practice kit.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
