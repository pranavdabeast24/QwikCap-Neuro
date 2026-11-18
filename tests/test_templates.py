"""Synthetic, exact-value and hostile-input coverage for template exports."""
from __future__ import annotations

import csv
import io
import itertools
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import warnings
import zipfile

import openpyxl
from openpyxl.styles import PatternFill, Font
from openpyxl.worksheet.datavalidation import DataValidation

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
import templates


SCHEMA = [
    {"name": "record_id", "label": "Record ID", "type": "text", "aliases": ["Study identifier"]},
    {"name": "visit_date", "label": "Visit date", "type": "date"},
    {"name": "age", "label": "Age", "type": "integer"},
    {"name": "consent", "label": "Consent", "type": "choice", "choices": {"0": "No", "1": "Yes"}},
    {"name": "notes", "label": "Notes", "type": "text", "aliases": ["Comments"]},
    {"name": "amount", "label": "Amount", "type": "number"},
]
ROWS = [
    {"record_id": "0001", "visit_date": "2026-10-25", "age": "0", "consent": "0", "notes": "", "amount": "0.25"},
    {"record_id": "0002", "visit_date": "2026-10-26", "age": "25", "consent": "1", "notes": "Fictional practice only", "amount": "3.5"},
]


def workbook_bytes(headers=None, header_row=1, other_sheet=False, configure=None):
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Import"
    headers = headers or [field["name"] for field in SCHEMA]
    if header_row > 1:
        sheet["A1"] = "Synthetic template instructions"
    for column, header in enumerate(headers, start=1):
        sheet.cell(header_row, column, header)
        sheet.cell(header_row, column).font = Font(bold=True, color="FFFFFF")
        sheet.cell(header_row, column).fill = PatternFill("solid", fgColor="123456")
        sheet.cell(header_row + 1, column).fill = PatternFill("solid", fgColor="F0F8FF")
    sheet.column_dimensions["A"].width = 28
    sheet.row_dimensions[header_row + 1].height = 24
    sheet.freeze_panes = f"A{header_row + 1}"
    workbook.properties.creator = "Synthetic private author marker"
    workbook.properties.title = "Synthetic private document title"
    if other_sheet:
        hidden = workbook.create_sheet("Unrelated hidden data")
        hidden.sheet_state = "hidden"
        hidden["A1"] = "Synthetic unrelated data marker"
    if configure:
        configure(workbook, sheet)
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


def rewrite_zip(data, replacements=None, extras=None):
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as source, zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as destination:
        for entry in source.infolist():
            payload = source.read(entry)
            if replacements and entry.filename in replacements:
                replacement = replacements[entry.filename]
                payload = replacement(payload) if callable(replacement) else replacement
            destination.writestr(entry, payload)
        for name, payload in (extras or []):
            entry = zipfile.ZipInfo(name)
            # Preserve hostile names that ZipInfo normalizes on Windows.
            entry.filename = name
            destination.writestr(entry, payload, compress_type=zipfile.ZIP_DEFLATED)
    return output.getvalue()


class TemplateTests(unittest.TestCase):
    def setUp(self):
        self.xlsx = workbook_bytes()
        self.spec = templates.inspect_template(self.xlsx, "practice.xlsx")
        self.mapping = {field["name"]: field["name"] for field in SCHEMA}

    def test_csv_bom_exact_headers_and_excel_letters(self):
        headers = [f"field_{number}" for number in range(28)]
        data = (",".join(headers) + "\r\n").encode("utf-8-sig")
        spec = templates.inspect_template(data, "practice.CSV")
        self.assertEqual(spec["format"], "csv")
        self.assertEqual(spec["sheet"], None)
        self.assertEqual(spec["columns"][26], {"name": "field_26", "index": 26, "letter": "AA"})
        self.assertEqual([column["name"] for column in spec["columns"]], headers)

    def test_first_useful_visible_sheet_and_header_auto_detection(self):
        def configure(workbook, sheet):
            empty = workbook.create_sheet("Empty", 0)
            empty.sheet_state = "visible"
        data = workbook_bytes(header_row=4, other_sheet=True, configure=configure)
        spec = templates.inspect_template(data, "practice.xlsx")
        self.assertEqual(spec["sheet"], "Import")
        self.assertEqual(spec["headerRow"], 4)
        self.assertEqual(spec["sheets"], ["Empty", "Import"])
        self.assertTrue(any("all other worksheets" in warning for warning in spec["warnings"]))

    def test_explicit_sheet_and_header_are_respected(self):
        data = workbook_bytes(header_row=3)
        self.assertEqual(templates.inspect_template(data, "practice.xlsx", "Import", 3)["headerRow"], 3)
        for sheet in ["missing", "Unrelated hidden data"]:
            with self.subTest(sheet=sheet), self.assertRaises(templates.TemplateError):
                templates.inspect_template(workbook_bytes(other_sheet=True), "practice.xlsx", sheet)

    def test_duplicate_empty_internal_formula_and_control_headers_rejected(self):
        for row in ["id,id", "ID, id ", "id,,age", "id,=SUM(A1)", "id, +danger", "id,bad\tname", "id,\ufeffhidden"]:
            with self.subTest(row=row), self.assertRaises(templates.TemplateError):
                templates.inspect_template(row.encode(), "practice.csv")
        for headers in [["id", "id"], ["id", None, "age"], ["id", 42]]:
            with self.subTest(headers=headers), self.assertRaises(templates.TemplateError):
                templates.inspect_template(workbook_bytes(headers), "practice.xlsx")

    def test_trailing_styled_blank_headers_do_not_add_columns(self):
        data = workbook_bytes(["record_id", "age"], configure=lambda workbook, sheet: setattr(sheet["D1"], "fill", PatternFill("solid", fgColor="123456")))
        spec = templates.inspect_template(data, "practice.xlsx")
        self.assertEqual([column["name"] for column in spec["columns"]], ["record_id", "age"])

    def test_prepopulated_destination_rows_rejected_even_outside_headers(self):
        for data, filename in [(b"record_id,age\n001,30\n", "practice.csv"), (workbook_bytes(configure=lambda workbook, sheet: setattr(sheet["G2"], "value", "existing data")), "practice.xlsx")]:
            with self.subTest(filename=filename), self.assertRaisesRegex(templates.TemplateError, "already contains"):
                templates.inspect_template(data, filename)

    def test_merged_headers_and_destination_cells_rejected(self):
        for merged in ["A1:B1", "A2:B2", "A1:A2"]:
            data = workbook_bytes(configure=lambda workbook, sheet: sheet.merge_cells(merged))
            with self.subTest(merged=merged), self.assertRaisesRegex(templates.TemplateError, "Merged"):
                templates.inspect_template(data, "practice.xlsx")

    def test_unresolved_explicit_blank_duplicate_and_identifier_mapping(self):
        unresolved = dict(self.mapping)
        unresolved.pop("notes")
        result = templates.validate_mapping(self.spec, SCHEMA, unresolved)
        self.assertFalse(result["valid"])
        self.assertEqual(result["unmapped"], ["notes"])
        unresolved["notes"] = None
        self.assertTrue(templates.validate_mapping(self.spec, SCHEMA, unresolved)["valid"])
        unresolved["age"] = "record_id"
        self.assertFalse(templates.validate_mapping(self.spec, SCHEMA, unresolved)["valid"])
        unresolved = {**self.mapping, "record_id": None}
        self.assertFalse(templates.validate_mapping(self.spec, SCHEMA, unresolved)["valid"])
        for changes in [{"notes": "unknown"}, {"unknown": None}, {"notes": ""}]:
            self.assertFalse(templates.validate_mapping(self.spec, SCHEMA, {**self.mapping, **changes})["valid"])

    def test_suggestions_are_exact_normalized_unambiguous_only(self):
        data = b"Study identifier,Visit Date,Age,consent,Comments,unrecognized\n"
        spec = templates.inspect_template(data, "practice.csv")
        result = templates.suggested_mapping(spec, SCHEMA)
        self.assertEqual(result, {"Study identifier": "record_id", "Visit Date": "visit_date", "Age": "age", "consent": "consent", "Comments": "notes"})
        self.assertFalse(templates.validate_mapping(spec, SCHEMA, result)["valid"])
        ambiguous = SCHEMA + [{"name": "other", "label": "Other", "aliases": ["Comments"]}]
        self.assertNotIn("Comments", templates.suggested_mapping(spec, ambiguous))
        repeated = templates.inspect_template(b"record_id,Study identifier\n", "practice.csv")
        self.assertEqual(templates.suggested_mapping(repeated, SCHEMA), {})

    def test_all_header_permutations_fill_exact_columns_without_positional_guessing(self):
        fields = [SCHEMA[0], SCHEMA[2], SCHEMA[3]]
        for permutation in itertools.permutations([field["name"] for field in fields]):
            with self.subTest(columns=permutation):
                data = (",".join(permutation) + "\n").encode()
                spec = templates.inspect_template(data, "practice.csv")
                rows = [{name: ROWS[0][name] for name in permutation}]
                output = templates.fill_template(data, "practice.csv", spec, {name: name for name in permutation}, fields, rows)
                actual = list(csv.reader(io.StringIO(output.decode("utf-8-sig"))))
                self.assertEqual(actual, [list(permutation), [ROWS[0][name] for name in permutation]])

    def test_xlsx_exact_values_blanks_zeros_codes_and_styles_and_metadata_removal(self):
        headers = ["Consent code", "Study identifier", "Comments", "Age", "Visit Date", "Amount", "Review later"]
        data = workbook_bytes(headers, header_row=3, other_sheet=True)
        spec = templates.inspect_template(data, "practice.xlsx")
        mapping = {"Consent code": "consent", "Study identifier": "record_id", "Comments": "notes", "Age": "age", "Visit Date": "visit_date", "Amount": "amount", "Review later": None}
        output = templates.fill_template(data, "practice.xlsx", spec, mapping, SCHEMA, ROWS)
        book = openpyxl.load_workbook(io.BytesIO(output), data_only=False)
        self.assertEqual(book.sheetnames, ["Import"])
        sheet = book.active
        actual = [["" if cell.value is None else cell.value for cell in row] for row in sheet.iter_rows(min_row=4, max_row=5, max_col=7)]
        self.assertEqual(actual, [["0", "0001", "", 0, "2026-10-25", 0.25, ""], ["1", "0002", "Fictional practice only", 25, "2026-10-26", 3.5, ""]])
        self.assertEqual(sheet["B4"].data_type, "s")
        self.assertEqual(sheet["A4"].data_type, "s")
        self.assertEqual(sheet["D4"].data_type, "n")
        self.assertEqual(sheet["A3"].fill.fgColor.rgb, "00123456")
        self.assertEqual(sheet["A4"].fill.fgColor.rgb, sheet["A5"].fill.fgColor.rgb)
        self.assertEqual(sheet.column_dimensions["A"].width, 28)
        self.assertGreaterEqual(sheet.row_dimensions[5].height, 24)
        self.assertEqual(sheet.freeze_panes, "A4")
        # openpyxl supplies its own default creator on read when this property
        # is absent; verify the serialized package, not that reader default.
        self.assertNotEqual(book.properties.creator, "Synthetic private author marker")
        self.assertIsNone(book.properties.title)
        with zipfile.ZipFile(io.BytesIO(output)) as archive:
            core = archive.read("docProps/core.xml")
            self.assertNotIn(b"created", core)
            self.assertNotIn(b"modified", core)
            self.assertNotIn(b"creator", core)
            self.assertFalse(any(b"Synthetic private" in archive.read(entry) for entry in archive.namelist()))
            self.assertFalse(any(b"unrelated data marker" in archive.read(entry) for entry in archive.namelist()))
        book.close()

    def test_xlsx_multiline_medications_and_wrapped_values_have_visible_rows(self):
        medications = "\n".join(f"Fictional medication {number}: 10 mg each morning" for number in range(1, 8))
        schema = [{"name": "record_id", "type": "text"}, {"name": "medications", "type": "text"}]
        mapping = {field["name"]: field["name"] for field in schema}
        def configure(workbook, sheet):
            sheet.column_dimensions["A"].width = 45
            sheet.column_dimensions["B"].width = 45
            sheet["B4"].font = Font(name="Calibri", size=11)
        data = workbook_bytes(list(mapping), header_row=3, configure=configure)
        spec = templates.inspect_template(data, "medications.xlsx")
        rows = [{"record_id": "0001", "medications": medications}, {"record_id": "0002", "medications": "Short answer"}]
        output = templates.fill_template(data, "medications.xlsx", spec, mapping, schema, rows)
        book = openpyxl.load_workbook(io.BytesIO(output), data_only=False)
        sheet = book.active
        self.assertEqual(sheet["B4"].value, medications)
        self.assertGreaterEqual(sheet.row_dimensions[4].height, 7 * 11 * 1.35)
        self.assertLessEqual(sheet.row_dimensions[4].height, templates.MAX_EXCEL_ROW_HEIGHT)
        self.assertEqual(sheet.row_dimensions[5].height, 24)
        self.assertTrue(sheet["B4"].alignment.wrap_text)
        self.assertEqual(sheet.column_dimensions["B"].width, 45)
        self.assertTrue(all(cell.data_type != "f" for cell in sheet._cells.values()))
        self.assertEqual([[sheet.cell(row, col).value for col in (1, 2)] for row in (4, 5)], [[row["record_id"], row["medications"]] for row in rows])
        book.close()

    def test_xlsx_row_sizing_uses_width_font_and_preserves_larger_template_heights(self):
        def export(width, size, height=24):
            def configure(workbook, sheet):
                sheet.column_dimensions["E"].width = width
                sheet["E2"].font = Font(name="Calibri", size=size)
                sheet.row_dimensions[2].height = height
            data = workbook_bytes(configure=configure)
            spec = templates.inspect_template(data, "practice.xlsx")
            output = templates.fill_template(data, "practice.xlsx", spec, self.mapping, SCHEMA, [{**ROWS[0], "notes": "Fictional review text " * 8}])
            book = openpyxl.load_workbook(io.BytesIO(output))
            actual = book.active.row_dimensions[2].height
            self.assertEqual(book.active["E2"].font.sz, size)
            self.assertEqual(book.active["E2"].value, "Fictional review text " * 8)
            book.close()
            return actual
        self.assertGreater(export(18, 11), export(45, 11))
        self.assertGreater(export(45, 20), export(45, 11))
        self.assertEqual(export(100, 11, 180), 180)

    def test_xlsx_oversized_display_is_bounded_and_explicit_without_changing_values(self):
        value = "=Literal review text\n" + "Fictional medication\n" * 180
        self.assertLessEqual(len(value), templates.MAX_VALUE_LENGTH)
        rows = [{**ROWS[0], "notes": value}, {**ROWS[1], "notes": "x" * 4000}]
        output = templates.fill_template(self.xlsx, "practice.xlsx", self.spec, self.mapping, SCHEMA, rows)
        book = openpyxl.load_workbook(io.BytesIO(output), data_only=False)
        sheet = book.active
        self.assertEqual(sheet.row_dimensions[2].height, templates.MAX_EXCEL_ROW_HEIGHT)
        self.assertEqual(sheet["E2"].value, value)
        self.assertEqual(sheet["E2"].data_type, "s")
        self.assertIn("409.5", sheet["E2"].comment.text)
        self.assertIn("full cell value is preserved", sheet["E2"].comment.text)
        self.assertEqual(sheet.row_dimensions[3].height, templates.MAX_EXCEL_ROW_HEIGHT)
        self.assertEqual(sheet["E3"].value, rows[1]["notes"])
        self.assertIsNotNone(sheet["E3"].comment)
        book.close()

    def test_xlsx_formula_like_text_is_literal_and_csv_rejects_without_silent_changes(self):
        for dangerous in ["=1+1", "+cmd", "-not-a-number", "@SUM(A1)", " \t=2+2"]:
            with self.subTest(value=dangerous):
                rows = [{**ROWS[0], "notes": dangerous}]
                output = templates.fill_template(self.xlsx, "practice.xlsx", self.spec, self.mapping, SCHEMA, rows)
                book = openpyxl.load_workbook(io.BytesIO(output), data_only=False)
                self.assertEqual(book.active["E2"].value, dangerous)
                self.assertEqual(book.active["E2"].data_type, "s")
                book.close()
                with self.assertRaisesRegex(templates.TemplateError, "formula-like"):
                    templates.fill_template(self.xlsx, "practice.xlsx", self.spec, self.mapping, SCHEMA, rows, export_format="csv")

    def test_xlsx_numeric_precision_identifier_dates_choice_codes_remain_exact(self):
        rows = [{**ROWS[0], "record_id": "0000000000000000001", "age": "9007199254740993", "amount": "123456789012345.5"}]
        output = templates.fill_template(self.xlsx, "practice.xlsx", self.spec, self.mapping, SCHEMA, rows)
        book = openpyxl.load_workbook(io.BytesIO(output))
        sheet = book.active
        self.assertEqual(sheet["A2"].value, rows[0]["record_id"])
        self.assertEqual(sheet["C2"].value, "9007199254740993")
        self.assertEqual(sheet["F2"].value, "123456789012345.5")
        self.assertEqual(sheet["B2"].data_type, "s")
        self.assertEqual(sheet["D2"].value, "0")
        book.close()

    def test_xlsx_to_csv_exact_records_and_numeric_negatives(self):
        rows = [{**ROWS[0], "age": "-5", "amount": "-0.25"}, ROWS[1]]
        output = templates.fill_template(self.xlsx, "practice.xlsx", self.spec, self.mapping, SCHEMA, rows, export_format="csv")
        self.assertTrue(output.startswith(b"\xef\xbb\xbf"))
        actual = list(csv.DictReader(io.StringIO(output.decode("utf-8-sig"))))
        self.assertEqual(actual, rows)
        self.assertEqual(len(actual), 2)

    def test_changed_template_spec_rejected(self):
        for changes in [{"sheet": "missing"}, {"headerRow": 2}, {"columns": list(reversed(self.spec["columns"]))}]:
            with self.subTest(changes=changes), self.assertRaises(templates.TemplateError):
                templates.fill_template(self.xlsx, "practice.xlsx", {**self.spec, **changes}, self.mapping, SCHEMA, ROWS)

    def test_empty_duplicate_or_oversized_records_rejected(self):
        invalid = [[], ROWS * 31, [{**ROWS[0], "record_id": ""}], [ROWS[0], ROWS[0]], [{**ROWS[0], "notes": "x" * 4001}], [{**ROWS[0], "age": 0}], [{**ROWS[0], "notes": "bad\x00data"}], [{**ROWS[0], "unknown": "value"}]]
        for rows in invalid:
            with self.subTest(rows=str(rows)[:80]), self.assertRaises(templates.TemplateError):
                templates.fill_template(self.xlsx, "practice.xlsx", self.spec, self.mapping, SCHEMA, rows)

    def test_wrong_signatures_unsupported_formats_and_oversized_uploads_rejected(self):
        for data, filename in [(self.xlsx, "practice.csv"), (b"id\n", "practice.xlsx"), (self.xlsx, "practice.xlsm"), (self.xlsx, "practice.xls"), (b"%PDF-1.7", "practice.csv"), (b"id\n\xff", "practice.csv"), (b"x" * (templates.MAX_TEMPLATE_BYTES + 1), "practice.csv")]:
            with self.subTest(filename=filename), self.assertRaises(templates.TemplateError):
                templates.inspect_template(data, filename)

    def test_formulas_on_any_sheet_and_in_table_expressions_rejected(self):
        data = workbook_bytes(other_sheet=True, configure=lambda workbook, sheet: setattr(workbook.worksheets[1]["A2"], "value", "=1+1"))
        with self.assertRaisesRegex(templates.TemplateError, "Formula"):
            templates.inspect_template(data, "practice.xlsx")

    def test_literal_validation_constants_allowed_but_dynamic_validation_rejected(self):
        def configure(workbook, sheet):
            bounds = DataValidation(type="whole", operator="between", formula1="18", formula2="120")
            sheet.add_data_validation(bounds)
            bounds.add("C2:C21")
            choices = DataValidation(type="list", formula1='"1,0"')
            sheet.add_data_validation(choices)
            choices.add("D2:D21")
        data = workbook_bytes(configure=configure)
        self.assertEqual(templates.inspect_template(data, "practice.xlsx")["headerRow"], 1)
        templates.fill_template(data, "practice.xlsx", templates.inspect_template(data, "practice.xlsx"), self.mapping, SCHEMA, ROWS)
        for kind, expression in [("whole", "A1"), ("whole", "=18"), ("whole", "SUM(A1:A2)"), ("list", "NamedRange"), ("list", '"safe,=CMD()"'), ("custom", "18")]:
            def malicious(workbook, sheet):
                rule = DataValidation(type=kind, formula1=expression)
                sheet.add_data_validation(rule)
                rule.add("C2:C21")
            with self.subTest(kind=kind, expression=expression), self.assertRaisesRegex(templates.TemplateError, "Formula"):
                templates.inspect_template(workbook_bytes(configure=malicious), "practice.xlsx")

    def test_actual_authored_templates_fill_every_answer_key_value_in_both_formats(self):
        schema = json.loads((APP / "samples/sample-schema.json").read_text())["fields"]
        records = json.loads((APP / "samples/answer-key.json").read_text())["records"]
        rows = [{key: str(value) for key, value in item["expected"].items()} for item in records]
        mappings = {
            "redcap-template.xlsx": {field["name"]: field["name"] for field in schema},
            "friendly-template.xlsx": {"Participant ID": "record_id", "Age (years)": "age", "Consent code": "consent", "Visit date": "visit_date", "Score": "symptom_score", "Research notes": "notes"},
        }
        for filename, mapping in mappings.items():
            with self.subTest(template=filename):
                data = (APP / "spreadsheets" / filename).read_bytes()
                spec = templates.inspect_template(data, filename)
                expected = [[row[mapping[column["name"]]] for column in spec["columns"]] for row in rows]
                output = templates.fill_template(data, filename, spec, mapping, schema, rows)
                workbook = openpyxl.load_workbook(io.BytesIO(output), data_only=False)
                actual = [["" if cell.value is None else str(cell.value) for cell in row] for row in workbook.active.iter_rows(min_row=spec["headerRow"] + 1, max_row=spec["headerRow"] + len(rows), max_col=len(spec["columns"]))]
                self.assertEqual(actual, expected)
                self.assertEqual(len(workbook.active.data_validations.dataValidation), 3)
                self.assertTrue(all(cell.data_type != "f" for cell in workbook.active._cells.values()))
                workbook.close()
                output_csv = templates.fill_template(data, filename, spec, mapping, schema, rows, export_format="csv")
                actual_csv = list(csv.reader(io.StringIO(output_csv.decode("utf-8-sig"))))
                self.assertEqual(actual_csv[0], [column["name"] for column in spec["columns"]])
                self.assertEqual(actual_csv[1:], expected)

    def test_sparse_worksheets_do_not_materialize_entire_blank_rectangles(self):
        def configure(workbook, sheet):
            sheet["CV2000"].fill = PatternFill("solid", fgColor="123456")
        data = workbook_bytes(configure=configure)
        workbook = templates._load_xlsx(data)
        self.assertLess(len(workbook.active._cells), 20)
        workbook.close()
        data = rewrite_zip(self.xlsx, extras=[("xl/tables/table99.xml", b'<table><calculatedColumnFormula>1+1</calculatedColumnFormula></table>')])
        with self.assertRaisesRegex(templates.TemplateError, "Formula"):
            templates.inspect_template(data, "practice.xlsx")

    def test_external_hyperlink_and_relationship_rejected(self):
        data = workbook_bytes(configure=lambda workbook, sheet: setattr(sheet["A1"], "hyperlink", "https://example.org/synthetic"))
        with self.assertRaisesRegex(templates.TemplateError, "External"):
            templates.inspect_template(data, "practice.xlsx")
        relation = b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="x" Type="synthetic" Target="../../../escape.xml"/></Relationships>'
        data = rewrite_zip(self.xlsx, extras=[("xl/_rels/untrusted.xml.rels", relation)])
        with self.assertRaisesRegex(templates.TemplateError, "traversal"):
            templates.inspect_template(data, "practice.xlsx")

    def test_macros_objects_controls_connections_and_scripts_rejected(self):
        for name in ["xl/vbaProject.bin", "xl/embeddings/oleObject1.bin", "xl/activeX/activeX1.xml", "xl/connections.xml", "xl/externalLinks/externalLink1.xml", "xl/media/script.svg"]:
            with self.subTest(name=name), self.assertRaises(templates.TemplateError):
                templates.inspect_template(rewrite_zip(self.xlsx, extras=[(name, b"synthetic")]), "practice.xlsx")

    def test_malformed_xml_entities_duplicate_entries_and_traversal_rejected(self):
        for payload in [b"<invalid", b'<!DOCTYPE a [<!ENTITY x "expanded">]><a>&x;</a>']:
            data = rewrite_zip(self.xlsx, extras=[("xl/untrusted.xml", payload)])
            with self.subTest(payload=payload), self.assertRaisesRegex(templates.TemplateError, "XML"):
                templates.inspect_template(data, "practice.xlsx")
        for name in ["../escape.xml", "/absolute.xml", "xl/../escape.xml", "xl\\escape.xml", "xl/null.xml\x00ignored"]:
            for separator in ("/", "\\"):
                with self.subTest(name=name, separator=separator), patch.object(zipfile.os, "sep", separator):
                    data = rewrite_zip(self.xlsx, extras=[(name, b"<a/>")])
                    with zipfile.ZipFile(io.BytesIO(data)) as archive:
                        self.assertEqual(archive.infolist()[-1].orig_filename, name)
                    with self.assertRaisesRegex(templates.TemplateError, "traversal"):
                        templates.inspect_template(data, "practice.xlsx")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            duplicate = rewrite_zip(self.xlsx, extras=[("xl/workbook.xml", b"<a/>")])
        with self.assertRaisesRegex(templates.TemplateError, "duplicate"):
            templates.inspect_template(duplicate, "practice.xlsx")

    def test_zip_entry_expanded_size_symlink_and_encryption_bounds(self):
        data = rewrite_zip(self.xlsx, extras=[(f"extra/{number}.xml", b"<a/>") for number in range(301)])
        with self.assertRaisesRegex(templates.TemplateError, "entries"):
            templates.inspect_template(data, "practice.xlsx")
        bomb = rewrite_zip(self.xlsx, extras=[("xl/bomb.xml", b"<a>" + b"x" * (templates.MAX_EXPANDED_BYTES + 1) + b"</a>")])
        with self.assertRaisesRegex(templates.TemplateError, "30 MB"):
            templates.inspect_template(bomb, "practice.xlsx")
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            link = zipfile.ZipInfo("link")
            link.create_system = 3
            link.external_attr = 0o120777 << 16
            archive.writestr(link, "target")
        with self.assertRaisesRegex(templates.TemplateError, "Symbolic"):
            templates.inspect_template(output.getvalue(), "practice.xlsx")
        encrypted = bytearray(self.xlsx)
        encrypted[6] |= 1
        central = encrypted.index(b"PK\x01\x02")
        encrypted[central + 8] |= 1
        with self.assertRaisesRegex(templates.TemplateError, "Encrypted"):
            templates.inspect_template(bytes(encrypted), "practice.xlsx")

    def test_row_and_column_bounds_apply_before_openpyxl_loads(self):
        for configure in [lambda workbook, sheet: setattr(sheet["WC1"], "value", "too wide"), lambda workbook, sheet: setattr(sheet["A2001"], "value", "too tall")]:
            data = workbook_bytes(configure=configure)
            with patch.object(openpyxl, "load_workbook", side_effect=AssertionError("must not load")):
                with self.assertRaisesRegex(templates.TemplateError, "600 columns|2,000"):
                    templates.inspect_template(data, "practice.xlsx")
        with self.assertRaises(templates.TemplateError):
            templates.inspect_template((",".join(f"column_{n}" for n in range(601)) + "\n").encode(), "practice.csv")


if __name__ == "__main__":
    unittest.main()
