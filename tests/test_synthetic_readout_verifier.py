"""Verifier negatives stay in memory; no app-written workbook is edited."""
import unittest
from openpyxl import Workbook
from tools.verify_synthetic_pace_readout import verify_workbook


class SyntheticReadoutVerifierTests(unittest.TestCase):
    def make_workbook(self):
        book = Workbook()
        sheet = book.active
        columns = ["record_id", "checkbox", "optional", "score"]
        fields = {"record_id": {"type": "text"}, "checkbox": {"type": "choice", "choices": {"0": "Unchecked"}},
                  "optional": {"type": "text"}, "score": {"type": "number"}}
        cases = [{"expectedExport": {"record_id": "SYNTH-001", "checkbox": "0", "optional": "", "score": "-7.5"}}]
        sheet.append(columns)
        sheet.append(["SYNTH-001", "0", None, -7.5])
        return book, columns, fields, cases

    def test_literal_zero_and_blank_are_distinct(self):
        book, *args = self.make_workbook()
        self.assertEqual(verify_workbook(book, *args), [])
        book.active["C2"] = "0"
        self.assertEqual(verify_workbook(book, *args)[0]["reason"], "Expected blank was populated")

    def test_numeric_choice_cannot_replace_literal_code(self):
        book, *args = self.make_workbook()
        book.active["B2"] = 0
        self.assertIn("choice mismatch", verify_workbook(book, *args)[0]["reason"])

    def test_minus_sign_and_formulas_are_checked(self):
        book, *args = self.make_workbook()
        book.active["D2"] = 7.5
        self.assertEqual(verify_workbook(book, *args)[0]["reason"], "Numeric value mismatch")
        book.active["D2"] = "=-7.5"
        self.assertEqual(verify_workbook(book, *args)[0]["reason"], "Formula or spreadsheet error")

    def test_header_order_and_identifier_are_checked(self):
        book, *args = self.make_workbook()
        book.active["A1"] = "different_id"
        book.active["A2"] = "SYNTH-002"
        self.assertEqual(len(verify_workbook(book, *args)), 2)
