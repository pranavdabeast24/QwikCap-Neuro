"""Regressions for reviewed template display, parser and stale-preview defects."""
import io
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

import openpyxl
from openpyxl.styles import Font

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server
import templates

SCHEMA = [{"name": "record_id", "label": "Record ID", "type": "text", "required": True}, {"name": "age", "label": "Age", "type": "integer", "required": True}]
MAPPING = {"record_id": "record_id", "age": "age"}


def blank_xlsx(configure=None):
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = "Import"
    sheet.append(["record_id", "age"])
    if configure:
        configure(sheet)
    out = io.BytesIO()
    book.save(out)
    book.close()
    return out.getvalue()


class HardeningTests(unittest.TestCase):
    def test_renamed_xml_package_part_is_rejected_before_workbook_load(self):
        source = blank_xlsx()
        output = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(source)) as original, zipfile.ZipFile(output, "w") as changed:
            for name in original.namelist():
                data = original.read(name)
                if name in {"[Content_Types].xml", "xl/_rels/workbook.xml.rels"}:
                    data = data.replace(b"sheet1.xml", b"sheet1.other")
                target = "xl/worksheets/sheet1.other" if name == "xl/worksheets/sheet1.xml" else name
                changed.writestr(target, data)
        with self.assertRaisesRegex(templates.TemplateError, "unsupported package parts"):
            templates.inspect_template(output.getvalue(), "fictional.xlsx")

    def test_populated_export_cells_are_visible_and_not_hidden_by_number_format(self):
        def configure(sheet):
            sheet.row_dimensions[1].hidden = True
            sheet.row_dimensions[2].hidden = True
            sheet.column_dimensions["B"].hidden = True
            sheet.column_dimensions["B"].width = 0
            sheet["B2"].number_format = ";;;"
            sheet["B2"].font = Font(color="FFFFFF")
            sheet.auto_filter.ref = "A1:B2"
        data = blank_xlsx(configure)
        spec = templates.inspect_template(data, "fictional.xlsx")
        result = templates.fill_template(data, "fictional.xlsx", spec, MAPPING, SCHEMA, [{"record_id": "SYN-001", "age": "42"}])
        book = openpyxl.load_workbook(io.BytesIO(result))
        sheet = book.active
        self.assertEqual(sheet["B2"].value, 42)
        self.assertFalse(sheet.row_dimensions[1].hidden)
        self.assertFalse(sheet.row_dimensions[2].hidden)
        self.assertFalse(sheet.column_dimensions["B"].hidden)
        self.assertGreaterEqual(sheet.column_dimensions["B"].width, 8)
        self.assertEqual(sheet["B2"].number_format, "General")
        self.assertEqual(sheet["B2"].font.color.rgb, "00243A43")
        self.assertIsNone(sheet.auto_filter.ref)
        book.close()

    def test_record_edits_invalidate_export_preview_revision_without_losing_mapping(self):
        with tempfile.TemporaryDirectory() as folder:
            workspace = server.Workspace(folder)
            workspace.schema = server.parse_schema(SCHEMA)
            record = workspace.add(b"Record ID: SYN-001\nAge: 42", "fictional.txt")
            workspace.import_template(b"record_id,age\n", "fictional.csv")
            workspace.set_template_mapping(MAPPING, True, workspace.template["revision"])
            workspace.review({"id": record["id"], "values": {"record_id": "SYN-001", "age": "42"}, "confirmed": ["record_id", "age"], "reviewer": "Fictional Reviewer", "approve": True, "expectedRevision": record["revision"]})
            old_revision = workspace.template["revision"]
            workspace.review({"id": record["id"], "values": {"record_id": "SYN-001", "age": "99"}, "confirmed": ["record_id", "age"], "reviewer": "Fictional Reviewer", "approve": True, "expectedRevision": record["revision"]})
            with self.assertRaises(server.ConflictError):
                workspace.check_template_revision(old_revision)
            self.assertTrue(workspace.template["confirmed"])
            self.assertEqual(workspace.template_preview()["rows"][0]["values"]["age"], "99")


if __name__ == "__main__":
    unittest.main()
