"""Printed control semantics with fictional text and translated geometry."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pace_profile import PROFILE, extract, is_profile, profile_schema


def word(text, x, y, width=.1):
    return {"text": text, "x": x, "y": y, "width": width, "height": .012}


def line(*words):
    return {"text": " ".join(w["text"] for w in words), "words": list(words)}


def control(kind, x, y):
    return {"kind": kind, "x": x, "y": y, "width": .016, "height": .012}


def page(instrument="Patient Records", record="EXAMPLE-001"):
    return {"page": 1, "method": "pdf-text", "lines": [
        line(word(f"Intracranial Hypotension_PACE Record ID: {record}", .06, .03, .7)),
        line(word(instrument, .06, .07, .7)),
    ], "rules": [{"x": .06, "y": y, "width": .88, "height": .001} for y in (.1, .2, .3, .6, .7)], "controls": []}


def radio_page(selected=(0,)):
    result = page()
    result["lines"].append(line(word("Patient Sex", .06, .23, .25)))
    for index, label in enumerate(("Female", "Male", "Other")):
        x = .5 + index * .14
        result["controls"].append(control("circle", x, .23))
        result["lines"].append(line(word(label, x + .023, .23, .06)))
        if index in selected:
            result["lines"].append(line(word("●", x + .004, .233, .006)))
    return result


def checkbox_page(omit_last=False):
    result = page()
    labels = ("American Indian or Alaska Native", "Asian", "Black or African American",
              "Native Hawaiian or Other Pacific Islander", "White", "Other", "Choose Not to Answer", "Unavailable")
    result["lines"].append(line(word("Patient Race", .06, .34, .25)))
    for index, label in enumerate(labels):
        if omit_last and index == 7:
            continue
        x, y = .5 + index // 4 * .25, .34 + index % 4 * .05
        result["controls"].append(control("square", x, y))
        result["lines"].append(line(word(label, x + .023, y, .15)))
        if index == 4:
            result["lines"].append(line(word("X", x + .004, y + .001, .007)))
    return result


class PaceProfileTests(unittest.TestCase):
    def test_canonical_destination_order_and_opt_in_marker(self):
        schema = profile_schema()
        self.assertEqual(len(schema), 512)
        self.assertEqual([field["name"] for field in schema[:4]], ["record_id", "redcap_repeat_instrument", "redcap_repeat_instance", "redcap_data_access_group"])
        self.assertEqual(schema[0]["profile"], PROFILE)
        self.assertTrue(is_profile(schema))
        self.assertFalse(is_profile([{ "name": "record_id"}]))
        self.assertTrue(schema[0]["required"])
        self.assertTrue(next(field for field in schema if field["name"] == "patient_first")["required"])
        self.assertTrue(next(field for field in schema if field["name"] == "cough_v2")["required"])
        self.assertFalse(next(field for field in schema if field["name"] == "periods_v2")["required"])
        self.assertFalse(next(field for field in schema if field["name"] == "pt_email")["required"])

    def test_one_selected_radio_and_serializable_evidence(self):
        output = extract([radio_page((1,))])
        self.assertEqual(output["values"]["patient_sex"], "2")
        self.assertIn("patient_sex", output["applicableFields"])
        self.assertEqual(output["sourceContext"]["recordIds"], ["EXAMPLE-001"])
        self.assertEqual(json.loads(json.dumps(output))["values"]["patient_sex"], "2")

    def test_unmarked_and_multiply_marked_radios_stay_blank(self):
        for selections in ((), (0, 1)):
            with self.subTest(selections=selections):
                output = extract([radio_page(selections)])
                self.assertEqual(output["values"]["patient_sex"], "")
                self.assertIn("patient_sex", output["applicableFields"])
        self.assertTrue(any("More than one" in issue for issue in extract([radio_page((0, 1))])["issues"]))

    def test_only_resolved_unmarked_radios_prove_source_missingness(self):
        unmarked = extract([radio_page(())])
        self.assertEqual(unmarked["sourceContext"]["unansweredFields"], ["patient_sex"])
        self.assertEqual(unmarked["evidence"]["patient_sex"]["mapping"], "pace-unmarked-radio")
        self.assertEqual(unmarked["evidence"]["patient_sex"]["page"], 1)
        json.dumps(unmarked)
        for selections in ((0,), (0, 1)):
            self.assertEqual(extract([radio_page(selections)])["sourceContext"]["unansweredFields"], [])
        incomplete = radio_page(())
        incomplete["controls"].pop()
        self.assertEqual(extract([incomplete])["sourceContext"]["unansweredFields"], [])
        stray = radio_page(())
        stray["lines"].append(line(word("●", .92, .23, .006)))
        self.assertEqual(extract([stray])["sourceContext"]["unansweredFields"], [])
        repeated = radio_page((0,))
        repeated["page"] = 2
        self.assertEqual(extract([radio_page(()), repeated])["sourceContext"]["unansweredFields"], [])

    def test_visible_empty_checkbox_zero_and_x_means_selected(self):
        output = extract([checkbox_page()])
        self.assertEqual(output["values"]["patient_race___5"], "1")
        self.assertEqual(output["values"]["patient_race___1"], "0")
        self.assertEqual(output["values"]["patient_race___8"], "0")
        absent = extract([radio_page()])
        self.assertEqual(absent["values"]["patient_race___1"], "")
        self.assertNotIn("patient_race___1", absent["applicableFields"])

    def test_incomplete_checkbox_family_does_not_invent_zero(self):
        output = extract([checkbox_page(omit_last=True)])
        self.assertEqual(output["values"]["patient_race___5"], "1")
        self.assertEqual(output["values"]["patient_race___1"], "")
        self.assertEqual(output["values"]["patient_race___8"], "")
        self.assertTrue(any("incomplete" in issue for issue in output["issues"]))

    def test_translating_source_geometry_preserves_choice(self):
        original = radio_page((2,))
        shifted = copy.deepcopy(original)
        for item in shifted["rules"] + shifted["controls"] + [w for row in shifted["lines"] for w in row["words"]]:
            item["x"] += .025
            item["y"] += .04
        self.assertEqual(extract([original])["values"]["patient_sex"], "3")
        self.assertEqual(extract([shifted])["values"]["patient_sex"], "3")

    def test_conflicting_record_ids_block_source(self):
        first, second = radio_page(), radio_page()
        second["page"] = 2
        second["lines"][0] = line(word("Intracranial Hypotension_PACE Record ID: DIFFERENT", .06, .03, .7))
        result = extract([first, second])
        self.assertEqual(result["values"]["record_id"], "")
        self.assertTrue(result["sourceContext"]["blockingIssues"])

    def test_new_source_header_cannot_inherit_prior_instrument(self):
        first, second = radio_page(), radio_page()
        second["page"] = 2
        second["lines"][1] = line(word("UNSUPPORTED ASSESSMENT", .06, .07, .7))
        output = extract([first, second])
        self.assertTrue(any("Page 2" in issue for issue in output["sourceContext"]["blockingIssues"]))

    def test_repeated_instrument_starts_retain_source_boundaries(self):
        first, second = radio_page(), radio_page()
        second["page"] = 2
        output = extract([first, second])
        self.assertEqual(output["sourceContext"]["instrumentStarts"], [
            {"instrument": "patient_records", "page": 1},
            {"instrument": "patient_records", "page": 2},
        ])

    def test_conflicting_clinical_source_values_are_blocking(self):
        first, second = radio_page((0,)), radio_page((1,))
        second["page"] = 2
        output = extract([first, second])
        self.assertEqual(output["values"]["patient_sex"], "")
        self.assertTrue(any("patient_sex" in issue for issue in output["sourceContext"]["blockingIssues"]))

    def test_patient_medication_matrix_uses_its_nonsequential_codes(self):
        result = page("Duke Neuro-radiology Headache Questionnaire Patient Facing")
        result["rules"] = [{"x": .06, "y": y, "width": .88, "height": .001} for y in (.1, .2, .3, .4)]
        labels = ("Taken, symptoms improved", "Taken, no change in symptoms", "Taken, symptoms worsened", "Have not taken")
        for index, label in enumerate(labels):
            x = .5 + index * .11
            result["lines"].append(line(word(label, x - .025, .24, .066)))
            result["controls"].append(control("circle", x, .34))
        result["lines"].append(line(word("Caffeinated products or medications (Excedrin, BC, Fioricet)?", .06, .34, .36)))
        result["lines"].append(line(word("●", .724, .343, .006)))
        output = extract([result])
        self.assertEqual(output["values"]["med_caf_v2"], "5")
        result["lines"].pop()
        self.assertEqual(extract([result])["values"]["med_caf_v2"], "")
        self.assertIn("med_caf_v2", extract([result])["applicableFields"])

    def test_required_matrix_blank_has_source_evidence_without_downgrading_rule(self):
        result = page("Duke Neuro-radiology Headache Questionnaire Patient Facing")
        for index, label in enumerate(("Better", "Worse", "Uneffected")):
            x = .5 + index * .14
            result["lines"].append(line(word(label, x - .02, .24, .06)))
            result["controls"].append(control("circle", x, .34))
        result["lines"].append(line(word("When coughing or sneezing?", .06, .34, .35)))
        output = extract([result])
        self.assertEqual(output["sourceContext"]["unansweredFields"], ["cough_v2"])
        self.assertEqual(output["evidence"]["cough_v2"]["mapping"], "pace-unmarked-radio")
        self.assertEqual(output["values"]["cough_v2"], "")
        self.assertTrue(next(field for field in profile_schema() if field["name"] == "cough_v2")["required"])

    def test_matrix_question_can_extend_beyond_scalar_answer_column(self):
        result = page("Duke Neuro-radiology Headache Questionnaire Patient Facing")
        labels = ("Taken, symptoms improved", "Taken, no change in symptoms", "Taken, symptoms worsened", "Have not taken")
        for index, label in enumerate(labels):
            x = .6 + index * .09
            result["lines"].append(line(word(label, x - .022, .24, .06)))
            result["controls"].append(control("circle", x, .34))
        result["lines"].append(line(
            word("Topiramate (brand names include Trokendi XR, Qudexy XR, and", .06, .34, .44),
            word("Topamax)", .51, .34, .08)))
        result["lines"].append(line(word("●", .604, .343, .006)))
        result["lines"].append(line(word("Complete?", .06, .64, .2)))
        for index, label in enumerate(("Incomplete", "Unverified", "Complete")):
            x = .5 + index * .14
            result["controls"].append(control("circle", x, .64))
            result["lines"].append(line(word(label, x + .023, .64, .06)))
        output = extract([result])
        self.assertEqual(output["values"]["med_topiramate_v2"], "1")
        self.assertFalse(output["sourceContext"]["blockingIssues"])

    def test_wrapped_branch_reference_resolves_repeated_disorder_label(self):
        for prefix, question in (
                ("personal", "Have you ever been diagnosed with a connective tissue disorder?"),
                ("family", "Has anyone in the family been diagnosed with a connective tissue disorder?")):
            with self.subTest(prefix=prefix):
                result = page("Duke Neuro-radiology Headache Questionnaire Patient Facing")
                result["lines"].append(line(word(question, .06, .23, .38)))
                for index, label in enumerate(("Yes", "No")):
                    x = .5 + index * .14
                    result["controls"].append(control("circle", x, .23))
                    result["lines"].append(line(word(label, x + .023, .23, .06)))
                result["lines"].append(line(word("●", .504, .233, .006)))
                result["lines"].append(line(word("If specified, what is the disorder?", .06, .34, .35), word("Fictional source note", .5, .34, .3)))
                output = extract([result])
                self.assertEqual(output["values"][prefix + "_ctdisorder_v2"], "Fictional source note")
                self.assertFalse(output["values"][("family" if prefix == "personal" else "personal") + "_ctdisorder_v2"])

    def test_unknown_control_row_blocks_silent_question_omission(self):
        result = radio_page()
        result["lines"][2] = line(word("Unrecognized research question", .06, .23, .35))
        output = extract([result])
        self.assertTrue(any("visible control row" in issue for issue in output["sourceContext"]["blockingIssues"]))

    def test_clipped_option_aliases_follow_labels_after_control_reordering(self):
        result = page("CSF Volume Provocation Form")
        result["lines"].append(line(word("B. Provocation Headache #1", .06, .13, .6)))
        result["lines"].append(line(word("Associated Symptoms", .06, .34, .3)))
        options = (("Photophobia", "2"), ("Clouding of consciousness", "5"), ("Lacrimation", "3"),
                   ("Nausea / vomiting", "nausea"), ("Visual aura / halos", "6"),
                   ("Numbness / tingling in limbs", "1"), ("Nasal discharge", "4"))
        for index, (label, code) in enumerate(options):
            x, y = .5 + index // 4 * .25, .34 + index % 4 * .05
            result["controls"].append(control("square", x, y))
            result["lines"].append(line(word(label, x + .023, y, .15)))
            if code == "nausea":
                result["lines"].append(line(word("✓", x + .004, y + .001, .007)))
        output = extract([result])
        for _, code in options:
            self.assertEqual(output["values"]["prov_associated_symptoms___" + code], "1" if code == "nausea" else "0")


if __name__ == "__main__":
    unittest.main()
