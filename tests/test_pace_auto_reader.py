"""Source identity and rules-only layout reuse with fictional documents."""
from __future__ import annotations

import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

from reportlab.pdfgen import canvas

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pace_auto as auto
import pipeline


def source_pdf(*, mrn="00001234", first="Ada", last="Example", sticker=(390, 740),
               date="04/05/2026", second_sticker=None, question_shift=0, reorder=False, revision="02/2026", marked_column=400):
    output = io.BytesIO()
    document = canvas.Canvas(output, pagesize=(612, 792), invariant=1)
    for x, y, given, family in [(*sticker, first, last)] + ([second_sticker] if second_sticker else []):
        document.drawString(x, y, f"{family.upper()}, {given.upper()}")
        document.drawString(x, y - 15, "DOB 02/03/1980 Sex F")
        document.drawString(x, y - 30, f"MRN {mrn}")
    document.drawString(40, 660, "HIT-6 Headache Impact Test")
    document.drawString(40, 630, f"Date {date}")
    document.setFont("Helvetica", 8)
    for x, label in zip((350, 400, 455, 510, 568), ("Never", "Rarely", "Sometimes", "Very", "Always")):
        document.drawCentredString(x, 590, label)
    questions = ["Pain severe", "Limit your ability to do usual daily activities", "Wish you could lie down",
                 "Felt too tired", "Fed up or irritated", "Limit your ability to concentrate"]
    if reorder:
        questions[0], questions[1] = questions[1], questions[0]
    for index, question in enumerate(questions, 1):
        y = 590 - index * 40 + question_shift
        document.drawString(40, y, str(index))
        document.drawString(60, y, question)
        if marked_column is not None:
            document.drawCentredString(marked_column, y, "X")
    document.drawString(40, 50, f"HA-230 Rev {revision} Page 1 of 1")
    document.save()
    return output.getvalue()


def continuation_pdf(*, missing_first=False, second_mrn=None):
    output = io.BytesIO()
    document = canvas.Canvas(output, pagesize=(612, 792), invariant=1)
    for number in (1, 2):
        if number == 1 and not missing_first or number == 2 and second_mrn:
            document.drawString(390, 740, "EXAMPLE, ADA")
            document.drawString(390, 725, "DOB 02/03/1980 Sex F")
            document.drawString(390, 710, f"MRN {second_mrn if number == 2 else '00001234'}")
        document.drawString(40, 660, "Headache History - Clinician Intake")
        if number == 1:
            document.drawString(40, 610, "1. Is the patient currently experiencing headaches?")
            document.drawString(420, 610, "Yes No")
        document.drawString(40, 50, f"HA-210C Rev 02/2026 Page {number} of 2")
        document.showPage()
    document.save()
    return output.getvalue()


def printed_identity_pages():
    def word(text, x, y, width=.2):
        return {"text": text, "x": x, "y": y, "width": width, "height": .012}

    def line(*words):
        return {"text": " ".join(item["text"] for item in words), "words": list(words)}

    first = {"page": 1, "method": "pdf-text", "lines": [
        line(word("Intracranial Hypotension_PACE Record ID: SOURCE-17", .06, .03, .7)),
        line(word("Patient Records", .06, .07, .7)),
        *[line(word(label, .06, y, .35), word(value, .5, y)) for label, value, y in (
            ("Patient Medical Record Number", "00001234", .15),
            ("Patient First Name", "Ada", .25),
            ("Patient Last Name", "Example", .35),
            ("Patient Date of Birth", "02/03/1980", .45))],
    ], "rules": [{"x": .06, "y": y, "width": .88, "height": .001} for y in (.1, .2, .3, .4, .5, .6)],
        "controls": [{"kind": "circle", "x": .5 + index * .14, "y": .55, "width": .016, "height": .012} for index in range(3)]}
    choices = [line(word("Patient Sex", .06, .55, .3))]
    choices.extend(line(word(label, .523 + index * .14, .55, .07)) for index, label in enumerate(("Female", "Male", "Other")))
    choices.append(line(word("X", .504, .551, .006)))
    first["lines"].extend(choices)
    second = {**copy.deepcopy(first), "page": 2, "lines": copy.deepcopy(choices) + [line(word("Confidential patient_records", .06, .9, .7))]}
    return [first, second]


class PaceAutoReaderTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="qwikcap-auto-reader-")
        self.addCleanup(self.temporary.cleanup)
        self.index = 0

    def process(self, data):
        self.index += 1
        return pipeline.process_document(data, "fictional.pdf", auto.profile_schema(), Path(self.temporary.name), f"source{self.index}")

    def test_canonical_fields_and_export_id_are_independent_of_sticker(self):
        record = self.process(source_pdf())
        self.assertEqual(len(record["values"]), 512)
        self.assertEqual(record["values"]["mrn"], "00001234")
        self.assertEqual(record["values"]["record_id"], "")
        self.assertEqual(record["values"]["hit6_severity"], "8")
        self.assertEqual(record["sourceContext"]["recordIds"], [])
        self.assertEqual(record["sourceContext"]["blockingIssues"], [])
        self.assertTrue(any("confirm" in issue for issue in auto.source_issues(record)))
        record.update(bundleRecordId="NEW000001", bundleSources=[{"firstPage": 1, "lastPage": 1}], paceIdentityConfirmed=True)
        record["values"]["record_id"] = "NEW000001"
        self.assertEqual(auto.source_issues(record, record["values"]), [])

    def test_whole_sticker_moves_without_changing_identity(self):
        for sticker in ((390, 740), (45, 755), (45, 260)):
            with self.subTest(sticker=sticker):
                record = self.process(source_pdf(sticker=sticker))
                self.assertEqual(auto.identity_issues(record), [])
                self.assertEqual(record["values"]["mrn"], "00001234")
                self.assertEqual(record["values"]["patient_dob"], "1980-02-03")
                self.assertEqual(record["values"]["patient_first"], "ADA")

    def test_full_spaced_mrn_is_never_replaced_by_a_prefix(self):
        record = self.process(source_pdf(mrn="0012 345"))
        self.assertEqual(record["values"]["mrn"], "0012 345")
        self.assertEqual(record["sourceContext"]["identities"][0]["mrn"], "0012 345")
        bad = self.process(source_pdf(mrn="0012@345"))
        self.assertEqual(bad["values"]["mrn"], "")
        self.assertTrue(auto.identity_issues(bad))

    def test_two_stickers_with_same_mrn_but_different_names_block(self):
        record = self.process(source_pdf(second_sticker=(45, 755, "Bea", "Different")))
        self.assertEqual(record["values"]["patient_first"], "")
        self.assertTrue(any("name" in issue for issue in record["sourceContext"]["blockingIssues"]))

    def test_explicit_known_sequence_can_inherit_first_page_sticker(self):
        record = self.process(continuation_pdf())
        self.assertEqual(auto.identity_issues(record), [])
        identities = record["sourceContext"]["identities"]
        self.assertEqual(identities[1]["mrn"], "00001234")
        self.assertEqual(identities[1]["inheritedFromPage"], 1)
        self.assertEqual(len(record["sourceContext"]["instrumentStarts"]), 1)
        self.assertTrue(auto.identity_issues(self.process(continuation_pdf(missing_first=True))))
        self.assertTrue(auto.identity_issues(self.process(continuation_pdf(second_mrn="9999"))))

    def test_printed_structured_identity_and_same_instrument_continuation(self):
        record = auto.extract(printed_identity_pages())
        self.assertEqual(auto.identity_issues(record), [])
        self.assertEqual(record["values"]["mrn"], "00001234")
        self.assertEqual(record["values"]["patient_first"], "Ada")
        self.assertEqual(record["sourceContext"]["identities"][1]["inheritedFromPage"], 1)
        self.assertEqual(len(record["sourceContext"]["instrumentStarts"]), 1)
        self.assertEqual(auto.bundle_issues(record, "NEW000001", [{"firstPage": 1, "lastPage": 2}]), [])
        self.assertTrue(auto.bundle_issues(record, "NEW000001", [{"firstPage": 1, "lastPage": 1}, {"firstPage": 2, "lastPage": 2}]))

    def test_printed_identity_cannot_override_a_conflicting_sticker(self):
        pages = printed_identity_pages()
        pages[0]["lines"].append({"text": "Patient: Other, Wrong DOB: 02/03/1980 MRN: 00001234", "words": []})
        record = auto.extract(pages)
        self.assertTrue(any("conflicts with the source identity" in issue for issue in record["sourceContext"]["blockingIssues"]))

    def test_unknown_page_and_cover_phrase_on_a_source_page_do_not_disappear(self):
        page = {"page": 2, "method": "pdf-text", "lines": [{"text": "Source bundle for one study record", "words": []},
                {"text": "No patient identity was inferred.", "words": []}]}
        record = auto.extract([page])
        self.assertTrue(any("Page 2" in issue for issue in record["sourceContext"]["blockingIssues"]))
        self.assertEqual(len(record["sourceContext"]["identities"]), 1)

    def rule(self, record):
        proof = record["evidence"]["hit6_date"]
        return auto.make_rule(record, "hit6_date", {"page": proof["page"], **proof["region"]})

    def test_rules_reuse_geometry_and_extract_new_answers_without_patient_values(self):
        original = self.process(source_pdf())
        rule = self.rule(original)
        loadout = auto.parse_loadout({"format": auto.LOADOUT_FORMAT, "name": "HIT-6 layout", "rules": [rule]})
        serialized = json.dumps(loadout)
        for private in ("00001234", "ADA", "EXAMPLE", "04/05/2026", "1980-02-03", "values", "sourceData"):
            self.assertNotIn(private, serialized)
        other = self.process(source_pdf(mrn="00009999", first="Bea", last="Different", date="07/09/2026", sticker=(45, 260), marked_column=568))
        other["values"]["hit6_date"] = ""
        self.assertEqual(auto.apply_rules(other, loadout["rules"]), ["hit6_date"])
        self.assertEqual(other["values"]["hit6_date"], "2026-07-09")
        self.assertEqual(other["values"]["mrn"], "00009999")
        self.assertEqual(other["values"]["hit6_severity"], "13")

    def test_layout_with_same_title_but_changed_geometry_order_or_revision_abstains(self):
        rule = self.rule(self.process(source_pdf()))
        for options in ({"question_shift": 30}, {"reorder": True}, {"revision": "03/2026"}):
            with self.subTest(options=options):
                record = self.process(source_pdf(**options))
                record["values"]["hit6_date"] = ""
                self.assertEqual(auto.apply_rules(record, [rule]), [])
                self.assertEqual(record["values"]["hit6_date"], "")

    def test_loadout_rejects_arbitrary_patient_anchors_fields_and_extra_values(self):
        record = self.process(source_pdf())
        rule = self.rule(record)
        for mutation in ({"anchors": ["EXAMPLE", "00001234"]}, {"field": "not_a_pace_field"}, {"values": {"hit6_date": "2026-04-05"}}, {"instrument": "patient_records"}):
            invalid = {**copy.deepcopy(rule), **mutation}
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                auto.parse_loadout({"format": auto.LOADOUT_FORMAT, "name": "Layout", "rules": [invalid]})
        for field in ("record_id", "mrn", "patient_first", "headaches_yn"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                auto.make_rule(record, field, {"page": 1, "x": .1, "y": .1, "width": .2, "height": .05})

    def test_corrected_choice_crop_cannot_keep_a_source_blank_waiver_or_disable_identity_guards(self):
        from extraction_profiles import _source_context
        from server import validate_values

        record = self.process(source_pdf(marked_column=None))
        name = "hit6_severity"
        self.assertIn(name, record["sourceContext"]["unansweredFields"])
        proof = record["evidence"][name]
        rule = auto.make_rule(record, name, {"page": proof["page"], **proof["region"]})
        self.assertEqual(auto.apply_rules(record, [rule]), [name])
        self.assertNotIn(name, record["sourceContext"]["unansweredFields"])
        self.assertIsNotNone(_source_context(record, auto.PROFILE))
        record.update(bundleRecordId="NEW000001", bundleSources=[{"firstPage": 1, "lastPage": 1}],
                      paceIdentityConfirmed=True, confirmed=list(record["applicableFields"]))
        record["values"]["record_id"] = "NEW000001"
        edited = {**record["values"], "mrn": "OTHER", "patient_first": "Wrong", "patient_last": "Other", "patient_dob": "1999-01-01"}
        errors = validate_values(auto.profile_schema(), edited, record)
        self.assertTrue({name, "mrn", "patient_first", "patient_last", "patient_dob"} <= set(errors))

    def test_malformed_json_rule_types_raise_value_error_before_any_application(self):
        record = self.process(source_pdf())
        rule = self.rule(record)
        for key, value in (("field", []), ("instrument", {}), ("layout", []), ("anchors", [["HA-230"]]),
                           ("anchorRegions", []), ("revision", {}), ("pageOffset", True), ("region", None)):
            invalid = {**copy.deepcopy(rule), key: value}
            before = copy.deepcopy(record)
            with self.subTest(key=key), self.assertRaises(ValueError):
                auto.apply_rules(record, [rule, invalid])
            self.assertEqual(record, before)

    def test_distinct_layout_versions_can_share_the_same_canonical_field(self):
        original = self.rule(self.process(source_pdf()))
        shifted = self.rule(self.process(source_pdf(question_shift=30)))
        revised = self.rule(self.process(source_pdf(revision="03/2026")))
        parsed = auto.parse_loadout({"format": auto.LOADOUT_FORMAT, "name": "HIT-6 layouts", "rules": [original, shifted, revised]})
        self.assertEqual(len(parsed["rules"]), 3)

    def test_overlapping_layout_versions_abstain_instead_of_choosing_last_rule(self):
        record = self.process(source_pdf())
        original = self.rule(record)
        other = copy.deepcopy(original)
        first_anchor = other["anchors"][0]
        other["anchorRegions"][first_anchor]["x"] += .005
        other["region"]["y"] += .1
        record["values"]["hit6_date"] = ""
        self.assertEqual(auto.apply_rules(record, [original, other]), [])
        self.assertEqual(record["values"]["hit6_date"], "")
        self.assertTrue(any("More than one saved layout rule" in issue for issue in record["issues"]))
        reordered = {**copy.deepcopy(original), "anchors": list(reversed(original["anchors"]))}
        with self.assertRaises(ValueError):
            auto.parse_loadout({"format": auto.LOADOUT_FORMAT, "name": "Layout", "rules": [original, reordered]})

    def test_source_ids_conflict_and_missing_manifest_pages_block(self):
        record = self.process(source_pdf())
        identity = record["sourceContext"]["identities"][0]
        identity["recordId"] = "SOURCE-A"
        other = {**identity, "page": 2, "recordId": "SOURCE-B"}
        record["sourceContext"]["identities"].append(other)
        self.assertTrue(any("study IDs conflict" in issue for issue in auto.identity_issues(record)))
        record["sourceContext"]["identities"] = [identity]
        manifest = [{"firstPage": 1, "lastPage": 2}]
        self.assertTrue(any("Every original source page" in issue for issue in auto.bundle_issues(record, "NEW000001", manifest)))

    def test_invalid_source_context_blocks_without_throwing(self):
        record = self.process(source_pdf())
        for malformed in (None, [], {"profile": auto.PROFILE, "identities": None}, {"profile": auto.PROFILE, "identities": [{"recordId": []}]}):
            with self.subTest(context=malformed):
                self.assertTrue(auto.source_issues({**record, "sourceContext": malformed}))


if __name__ == "__main__":
    unittest.main()
