"""Invented cases only. No dataset keys or app-written workbooks are fixtures."""
import contextlib
import copy
from datetime import datetime
import io
import json
from pathlib import Path
import tempfile
import unittest

from openpyxl import Workbook

from tools.verify_actual_pace_readout import (
    InputProblem, build_expectations, canonical, main,
    verify_extraction, verify_project, verify_workbook,
)


def invented_catalog():
    specs = [
        ("record_id", "text", "record_id", None),
        ("redcap_repeat_instrument", "text", "redcap_repeat_instrument", None),
        ("redcap_repeat_instance", "text", "redcap_repeat_instance", None),
        ("redcap_data_access_group", "text", "redcap_data_access_group", None),
        ("mrn", "text", "mrn", None),
        ("scan_date", "date", "scan_date", None),
        ("score", "number", "score", None),
        ("count", "integer", "count", None),
        ("code", "choice", "code", {"01": "First", "1": "Second"}),
        ("note", "text", "note", None),
        ("flag___1", "choice", "flag", {"0": "Unchecked", "1": "Checked"}),
        ("flag___2", "choice", "flag", {"0": "Unchecked", "1": "Checked"}),
        ("flag___3", "choice", "flag", {"0": "Unchecked", "1": "Checked"}),
        ("unmarked___1", "choice", "unmarked", {"0": "Unchecked", "1": "Checked"}),
        ("unmarked___2", "choice", "unmarked", {"0": "Unchecked", "1": "Checked"}),
        ("demo_complete", "choice", "demo_complete", {"2": "Complete"}),
    ]
    specs.extend((f"unused_{index}", "text", f"unused_{index}", None) for index in range(512 - len(specs)))
    fields = [{"name": name, "type": kind, "sourceField": source,
               "instrument": "record_context" if index < 4 else "demo",
               **({"choices": choices} if choices is not None else {})}
              for index, (name, kind, source, choices) in enumerate(specs)]
    return {"columns": [field["name"] for field in fields], "fields": fields}


def invented_expected():
    contents = [
        ("doc_01.pdf", "0007", {"mrn": "000042", "scan_date": "03/04/2026", "score": "-7.5",
                                 "count": "2", "code": "01", "flag___1": "1", "demo_complete": "2"}),
        ("doc_02.pdf", "0007", {"note": "A  ﬁstula, Left.", "scan_date": "2026-03-04", "score": "-7.50"}),
        ("doc_03.pdf", "0011", {"record_id": "0011", "note": "Different patient."}),
    ]
    return {"documents": [
        {"formFile": name, "keyFile": name.replace(".pdf", "_key.pdf"), "pages": 1,
         "identifiers": {"recordID": record_id, "formType": "demo"},
         "fields": [{"name": field, "expectedRaw": value, "keyPage": 1, "notes": []}
                    for field, value in values.items()]}
        for name, record_id, values in contents
    ]}


def invented_census(expected):
    return {"documents": [
        {"file": "/fictional/train/forms/" + document["formFile"],
         "record_id": document["identifiers"]["recordID"],
         "visible_choice_families": [
             {"source_field": "unmarked", "kind": "checkbox_group"},
             {"source_field": "code", "kind": "single_choice"},
         ]}
        for document in expected["documents"]
    ]}


def invented_project(catalog, census=False):
    rows = []
    for identifier, populated in [
        ("0007", {"mrn": "000042", "scan_date": "2026-03-04", "score": "-7.50", "count": "2",
                  "code": "01", "note": "A fistula, Left.", "flag___1": "1", "flag___2": "0",
                  "flag___3": "0", "demo_complete": "2"}),
        ("0011", {"note": "Different patient."}),
    ]:
        values = dict.fromkeys(catalog["columns"], "")
        values.update(record_id=identifier, **populated)
        if census:
            values.update(unmarked___1="0", unmarked___2="0")
        rows.append({"values": values})
    return {"format": "formbridge-project-v2", "schema": [{"name": name} for name in catalog["columns"]], "records": rows}


class ActualPaceVerifierTests(unittest.TestCase):
    def setUp(self):
        self.catalog = invented_catalog()
        self.expected = invented_expected()
        self.reference = build_expectations(self.expected, self.catalog)
        self.project = invented_project(self.catalog)

    def workbook(self):
        book = Workbook()
        sheet = book.active
        sheet.append(self.catalog["columns"])
        for record in self.project["records"]:
            row = []
            for field in self.catalog["fields"]:
                value = record["values"][field["name"]]
                if value and field["type"] in {"number", "integer"}:
                    value = float(value) if field["type"] == "number" else int(value)
                row.append(None if value == "" else value)
            sheet.append(row)
        return book

    def reasons(self, report):
        return [issue["reason"] for issue in report["issues"]]

    def test_explicit_family_zeros_and_hidden_blanks_are_separate(self):
        self.assertEqual(self.reference.explicit_rows, 12)
        self.assertEqual(self.reference.inferred_zero_rows, 2)
        self.assertEqual(self.reference.inferred_patient_zero_cells, 2)
        self.assertEqual(self.reference.patients["0007"]["flag___2"], "0")
        self.assertEqual(self.reference.patients["0007"]["unmarked___1"], "")
        self.assertEqual(self.reference.patients["0011"]["flag___1"], "")
        self.assertTrue(all(self.reference.patients["0007"][name] == "" for name in self.catalog["columns"][1:4]))

    def test_census_only_expands_observed_checkbox_groups(self):
        census = invented_census(self.expected)
        reference = build_expectations(self.expected, self.catalog, census)
        self.assertEqual(reference.inferred_zero_rows, 8)
        self.assertEqual(reference.inferred_patient_zero_cells, 6)
        self.assertEqual(reference.patients["0011"]["code"], "")
        self.assertEqual(verify_project(invented_project(self.catalog, census=True), reference)["issues"], [])
        census["documents"][0]["record_id"] = "different"
        with self.assertRaisesRegex(InputProblem, "identity conflicts"):
            build_expectations(self.expected, self.catalog, census)

    def test_conflicting_repeats_stop_instead_of_choosing(self):
        expected = copy.deepcopy(self.expected)
        expected["documents"][1]["fields"][2]["expectedRaw"] = "7.5"
        with self.assertRaisesRegex(InputProblem, "Conflicting expected repeats"):
            build_expectations(expected, self.catalog)

    def test_conflicting_checkbox_repeats_and_header_ids_stop(self):
        expected = copy.deepcopy(self.expected)
        expected["documents"][1]["fields"].append({"name": "flag___2", "expectedRaw": "1"})
        with self.assertRaisesRegex(InputProblem, "Conflicting expected repeats"):
            build_expectations(expected, self.catalog)
        expected = copy.deepcopy(self.expected)
        expected["documents"][0]["fields"].append({"name": "record_id", "expectedRaw": "7"})
        with self.assertRaisesRegex(InputProblem, "key header"):
            build_expectations(expected, self.catalog)

    def test_duplicate_expected_fields_stop_and_key_only_rows_remain_visible(self):
        expected = copy.deepcopy(self.expected)
        expected["documents"][0]["fields"].append(expected["documents"][0]["fields"][0])
        with self.assertRaisesRegex(InputProblem, "Duplicate explicit"):
            build_expectations(expected, self.catalog)
        expected["documents"][0]["fields"][-1] = {"name": "not_in_catalog", "expectedRaw": "003.0"}
        reference = build_expectations(expected, self.catalog)
        self.assertEqual(reference.key_only_rows, 1)
        self.assertEqual(reference.document_values["doc_01.pdf"]["not_in_catalog"], "003.0")
        self.assertNotIn("not_in_catalog", reference.patients["0007"])
        self.assertEqual(len(reference.patients["0007"]), 512)

    def test_key_only_raw_fields_need_no_invented_destination_or_applicability(self):
        expected = copy.deepcopy(self.expected)
        expected["documents"][0]["fields"].append({"name": "key_only_total", "expectedRaw": "003.0"})
        reference = build_expectations(expected, self.catalog)
        documents = {}
        for document in expected["documents"]:
            values = {name: str(value) for name, value in reference.document_values[document["formFile"]].items()}
            documents[document["formFile"]] = {"values": values, "applicableFields": [name for name in values if name in reference.fields]}
        report = verify_extraction({"documents": documents}, reference)
        self.assertEqual(report["issues"], [])
        self.assertEqual((report["key_only_rows"], report["key_only_rows_checked"], report["key_only_rows_matched"]), (1, 1, 1))
        documents["doc_01.pdf"]["values"]["key_only_total"] = "3.0"
        self.assertIn("Normalized value mismatch", self.reasons(verify_extraction({"documents": documents}, reference)))
        del documents["doc_01.pdf"]["values"]["key_only_total"]
        report = verify_extraction({"documents": documents}, reference)
        self.assertEqual(len(report["issues"]), 1)
        self.assertIn("Key-only expectation was not supplied by extraction diagnostics", self.reasons(report))

    def test_normalization_is_driven_by_catalog_type(self):
        fields = self.reference.fields
        self.assertEqual(canonical("03/04/2026", fields["scan_date"]), "2026-03-04")
        self.assertEqual(canonical("03/04/2026", fields["note"]), "03/04/2026")
        self.assertEqual(canonical("000042", fields["mrn"]), "000042")
        self.assertEqual(canonical(" A\u00a0 ﬁstula, Left. ", fields["note"]), "A fistula, Left.")
        self.assertNotEqual(canonical("01", fields["code"]), canonical("1", fields["code"]))
        for value in ["NaN", "Infinity", "-Infinity"]:
            with self.assertRaises(InputProblem):
                canonical(value, fields["score"])
        with self.assertRaises(InputProblem):
            canonical("2.1", fields["count"])
        with self.assertRaises(InputProblem):
            canonical("02/30/2026", fields["scan_date"])

    def test_project_full_cells_and_patient_order(self):
        self.project["records"].reverse()
        report = verify_project(self.project, self.reference)
        self.assertEqual(report["issues"], [])
        self.assertEqual(report["full_checked_cells"], 1024)
        self.assertEqual(report["patient_rows_matched"], 2)

    def test_project_detects_codes_case_sign_hidden_values_and_missing_fields(self):
        changes = [("code", "1"), ("note", "A fistula, left."), ("score", "7.5"),
                   ("unmarked___1", "0"), ("mrn", 42)]
        for name, value in changes:
            with self.subTest(field=name):
                project = copy.deepcopy(self.project)
                project["records"][0]["values"][name] = value
                issues = verify_project(project, self.reference)["issues"]
                self.assertEqual(len(issues), 1)
                self.assertEqual(issues[0]["field"], name)
                self.assertNotIn("expected", issues[0])
                self.assertNotIn("actual", issues[0])
        del self.project["records"][0]["values"]["count"]
        self.assertIn("Missing destination field", self.reasons(verify_project(self.project, self.reference)))

    def test_project_header_identity_and_duplicate_rows(self):
        self.project["schema"].reverse()
        self.project["records"].append(copy.deepcopy(self.project["records"][0]))
        report = verify_project(self.project, self.reference)
        self.assertIn("Project field order differs from catalog", self.reasons(report))
        self.assertIn("Duplicate patient row", self.reasons(report))
        self.project["records"][0]["values"]["record_id"] = "7"
        self.assertIn("Patient ID is absent, non-text, or unexpected", self.reasons(verify_project(self.project, self.reference)))

    def test_workbook_accepts_literal_text_and_native_numbers(self):
        book = self.workbook()
        self.assertEqual(verify_workbook(book, self.reference)["issues"], [])
        self.assertEqual(verify_workbook(book, self.reference)["full_checked_cells"], 1024)
        book.close()

    def test_workbook_excel_type_constraints(self):
        for field, value in [("mrn", 42), ("code", 1), ("score", "-7.5"),
                             ("score", True), ("scan_date", datetime(2026, 3, 4))]:
            with self.subTest(field=field, kind=type(value).__name__):
                book = self.workbook()
                book.active.cell(2, self.catalog["columns"].index(field) + 1, value)
                issues = verify_workbook(book, self.reference)["issues"]
                self.assertTrue(any(issue.get("field") == field for issue in issues))
                book.close()

    def test_workbook_formula_error_hidden_header_and_extra_content(self):
        book = self.workbook()
        sheet = book.active
        sheet.row_dimensions[2].hidden = True
        sheet.column_dimensions["B"].hidden = True
        sheet.cell(1, 1, "wrong")
        sheet.cell(10, 513, "=1+1")
        sheet.cell(2, 7, "#VALUE!")
        hidden = book.create_sheet("Extra")
        hidden.sheet_state = "veryHidden"
        reasons = self.reasons(verify_workbook(book, self.reference))
        for reason in ["Workbook contains hidden content", "Formula or spreadsheet error",
                       "Expected exactly one worksheet", "Header order differs from catalog",
                       "Workbook dimensions differ from the complete patient readout"]:
            self.assertIn(reason, reasons)
        book.close()

    def test_document_raw_coverage_is_separate_from_checkbox_expansion(self):
        documents = []
        for document in self.expected["documents"]:
            values = dict(self.reference.document_values[document["formFile"]])
            values = {name: str(value) for name, value in values.items()}
            documents.append({"filename": document["formFile"], "result": {"values": values, "applicableFields": list(values)}})
        report = verify_extraction({"documents": documents}, self.reference)
        self.assertEqual(report["issues"], [])
        self.assertEqual((report["raw_key_rows_expected"], report["raw_key_rows_checked"], report["raw_key_rows_matched"]), (12, 12, 12))
        self.assertEqual(report["inferred_zero_rows_checked"], 2)
        documents[0]["result"]["values"]["code"] = "1"
        documents[0]["result"]["applicableFields"].remove("mrn")
        report = verify_extraction({"documents": documents}, self.reference)
        self.assertEqual(report["raw_key_rows_matched"], 10)
        self.assertEqual({issue["field"] for issue in report["issues"]}, {"code", "mrn"})

    def test_document_mapping_shape_and_missing_document(self):
        result = {document["formFile"]: {"values": {name: str(value) for name, value in self.reference.document_values[document["formFile"]].items()},
                                            "applicableFields": list(self.reference.document_values[document["formFile"]])}
                  for document in self.expected["documents"]}
        self.assertEqual(verify_extraction({"documents": result}, self.reference)["issues"], [])
        del result["doc_02.pdf"]
        report = verify_extraction({"documents": result}, self.reference)
        self.assertEqual(report["raw_key_rows_checked"], 9)
        self.assertIn("Missing or malformed extraction result", self.reasons(report))

    def test_cli_is_read_only_and_does_not_print_cell_values(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = {}
            for name, value in [("expected", self.expected), ("catalog", self.catalog), ("project", self.project)]:
                path = Path(folder) / (name + ".json")
                path.write_text(json.dumps(value))
                paths[name] = path
            original = {name: path.read_bytes() for name, path in paths.items()}
            arguments = ["--expected-json", str(paths["expected"]), "--catalog-json", str(paths["catalog"]),
                         "--project-json", str(paths["project"])]
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                status = main(arguments)
            report = json.loads(output.getvalue())
            self.assertEqual(status, 0)
            self.assertTrue(report["input_unchanged"])
            self.assertEqual(report["full_checked_cells"], 1024)
            self.assertEqual({name: path.read_bytes() for name, path in paths.items()}, original)
            self.project["records"][0]["values"]["mrn"] = "FICTIONAL-VALUE-MUST-NOT-PRINT"
            paths["project"].write_text(json.dumps(self.project))
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                status = main(arguments)
            self.assertEqual(status, 1)
            self.assertNotIn("FICTIONAL-VALUE-MUST-NOT-PRINT", output.getvalue())
            self.assertNotIn("000042", output.getvalue())


if __name__ == "__main__":
    unittest.main()
