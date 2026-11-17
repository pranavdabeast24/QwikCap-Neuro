import csv
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PaceCatalogDataTests(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads((ROOT / "study_profiles/pace.json").read_text())
        self.fields = {field["name"]: field for field in self.catalog["fields"]}

    def test_csv_and_catalog_preserve_the_same_complete_order(self):
        with (ROOT / "spreadsheets/pace-import-template.csv").open(newline="") as handle:
            rows = list(csv.reader(handle))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0], self.catalog["columns"])
        self.assertEqual([field["name"] for field in self.catalog["fields"]], rows[0])
        self.assertEqual(len(rows[0]), 512)
        self.assertEqual(len(set(rows[0])), 512)
        self.assertTrue(all(re.fullmatch(r"[a-z][a-z0-9_]*", name) for name in rows[0]))
        self.assertEqual(rows[0][0], "record_id")
        self.assertEqual(rows[0][-1], "duke_neuroradiology_headache_questionnaire_patient_complete")
        self.assertTrue(any("trailing empty header" in warning for warning in self.catalog["warnings"]))

    def test_every_field_has_bounded_metadata_and_known_membership(self):
        instruments = {item["name"] for item in self.catalog["instruments"]}
        self.assertEqual(len(instruments), 9)
        for field in self.fields.values():
            self.assertIn(field["instrument"], instruments | {"record_context"})
            self.assertIn(field["type"], {"text", "integer", "number", "date", "choice"})
            self.assertIsInstance(field["required"], bool)
            self.assertTrue(0 <= field["sourcePage"] <= 30)
            self.assertTrue(0 < len(field["label"]) <= 200)
            self.assertLessEqual(len(field["notes"]), 2000)
            self.assertLessEqual(len(field["branching"]), 1000)
            self.assertNotIn("Unverified field.", field["notes"])
            self.assertNotIn("Unverified checkbox code.", field["notes"])
            if field["type"] == "choice":
                self.assertTrue(field["choices"])
                self.assertTrue(all(isinstance(code, str) and 0 < len(label) <= 200 for code, label in field["choices"].items()))
            if field["type"] == "date":
                self.assertEqual(field["sourceDateFormat"], "mdy")
                self.assertIn("date_mdy", field["validation"])

    def test_checkbox_expansion_keeps_binary_codes_and_base_identity(self):
        checkboxes = [field for field in self.fields.values() if "___" in field["name"]]
        self.assertEqual(len(checkboxes), 294)
        for field in checkboxes:
            self.assertEqual(field["sourceField"], field["name"].split("___")[0])
            self.assertEqual(field["choices"], {"0": "Unchecked", "1": "Checked"})
            self.assertIn("Blank means missing", field["notes"])
            self.assertNotIn("default", field)
        self.assertIn("headache_assocaited_other", self.fields)
        self.assertIn("baseline_associated_symptoms___nausea", self.fields)
        self.assertIn("css_change_unit", self.fields)

    def test_distinct_medication_codes_are_not_merged_by_label(self):
        for medication in ("caf", "topiramate", "triptan", "emgality", "diamox", "glp1a"):
            baseline = self.fields[f"med_{medication}"]["choices"]
            patient = self.fields[f"med_{medication}_v2"]["choices"]
            self.assertEqual(baseline, {"1": "Taken, symptoms improved", "2": "Taken, no change in symptoms", "3": "Taken, symptoms worsened", "4": "Have not taken", "5": "Not Recorded"})
            self.assertEqual(patient, {"1": "Taken, symptoms improved", "3": "Taken, no change in symptoms", "5": "Taken, symptoms worsened", "6": "Have not taken"})

    def test_completion_context_and_omitted_nonexport_fields(self):
        completion = [field for field in self.fields.values() if field["name"].endswith("_complete")]
        self.assertEqual(len(completion), 9)
        for field in completion:
            self.assertEqual(field["choices"], {"0": "Incomplete", "1": "Unverified", "2": "Complete"})
            self.assertIn("No completion value is defaulted", field["notes"])
            self.assertNotIn("default", field)
        dsm = self.fields["image_information_ct_dsm_or_fluroscopic_guided_complete"]
        self.assertEqual(dsm["label"], "Complete?")
        self.assertEqual(dsm["sourcePage"], 21)
        self.assertEqual(dsm["branching"], "")
        context = {field["name"] for field in self.fields.values() if field["sourcePage"] == 0}
        self.assertEqual(context, {"record_id", "redcap_repeat_instrument", "redcap_repeat_instance", "redcap_data_access_group"})
        for name in context:
            self.assertEqual(self.fields[name]["instrument"], "record_context")
        for name in ("total28", "total28_v2", "hit6_total", "connective_tissue_prompt", "connective_tissue_prompt_v2", "image_dis_v2"):
            self.assertNotIn(name, self.fields)

    def test_bounds_required_flags_and_uncertainty_remain_explicit(self):
        severe = self.fields["severe_past28"]
        self.assertEqual((severe["type"], severe["min"], severe["max"]), ("integer", 0, 28))
        delta = self.fields["csf_volume_delta"]
        self.assertEqual((delta["type"], delta["min"], delta["max"]), ("number", -100, 100))
        self.assertTrue(self.fields["hit6_severity"]["required"])
        self.assertFalse(self.fields["lying_down_v2"]["required"])
        self.assertTrue(self.fields["cough_v2"]["required"])
        self.assertEqual(self.fields["hit6_severity"]["choices"], {"6": "Never", "8": "Rarely", "10": "Sometimes", "11": "Very Often", "13": "Always"})
        uncertain = [field for field in self.fields.values() if "Uncertain option label:" in field["notes"]]
        self.assertEqual(len(uncertain), 69)
        self.assertIn("label unreadable", self.fields["baseline_associated_symptoms___1"]["label"])
        self.assertIn("source label clipped", self.fields["headache_location_v2___2"]["label"])
        self.assertIn("No field label is printed", self.fields["hit6_date"]["notes"])


if __name__ == "__main__":
    unittest.main()
