"""Source-backed extraction for the SIH clinic layouts and registration anchors."""
from __future__ import annotations

import copy
from datetime import datetime
from functools import lru_cache
from pathlib import Path
import re
import unicodedata

from field_catalog import load_catalog
from pace_profile import profile_schema as pace_schema
from clinic_narratives import extract_procedure, extract_radiology


PROFILE = "sih-clinic-v1"
FORM_INSTRUMENTS = {
    "REG-100": "patient_records",
    "HA-210C": "duke_neuroradiology_headache_questionnaire",
    "HA-220P": "duke_neuroradiology_headache_questionnaire_patient",
    "HA-230": "hit6",
    "PROC-310": "csf_volume_provocation_form",
}
_MARKS = {"X", "x", "✓", "✔", "✗", "✘", "☑", "☒", "×"}
_ANSWER_FONT = re.compile(r"menlo|noteworthy|bradley|hand|courier|chalkboard", re.I)


def normalized(value):
    return " ".join(unicodedata.normalize("NFKC", str(value)).split())


def _key(value):
    return re.sub(r"[^a-z0-9]", "", normalized(value).casefold())


@lru_cache(maxsize=1)
def _catalog():
    return load_catalog(Path(__file__).resolve().parent / "study_profiles" / "pace.json")


@lru_cache(maxsize=1)
def _fields():
    return {field["name"]: field for field in _catalog()["fields"]}


def profile_schema():
    schema = pace_schema()
    schema[0]["profile"] = PROFILE
    return schema


def _iso(value):
    value = normalized(value)
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    return ""


def _words(page):
    return [word for line in page.get("lines", []) for word in line.get("words", [])]


def _text(page):
    return "\n".join(normalized(line["text"]) for line in page.get("lines", []))


def _box(words):
    if not words:
        return {"x": .04, "y": .04, "width": .92, "height": .9}
    x, y = min(w["x"] for w in words), min(w["y"] for w in words)
    return {"x": x, "y": y,
            "width": max(w["x"] + w["width"] for w in words) - x,
            "height": max(w["y"] + w["height"] for w in words) - y}


def _inside(word, region, margin=0):
    x, y = word["x"] + word["width"] / 2, word["y"] + word["height"] / 2
    return (region["x"] - margin <= x <= region["x"] + region["width"] + margin
            and region["y"] - margin <= y <= region["y"] + region["height"] + margin)


def _region_words(page, region, *, answers=False):
    return [word for word in _words(page) if _inside(word, region)
            and (not answers or _ANSWER_FONT.search(word.get("font", "")))]


def _read_words(words):
    if not words:
        return ""
    rows = []
    for word in sorted(words, key=lambda w: (w["y"] + w["height"] / 2, w["x"])):
        cy = word["y"] + word["height"] / 2
        row = next((row for row in rows if abs(row[0] - cy) <= .006), None)
        if row is None:
            rows.append([cy, [word]])
        else:
            row[1].append(word)
    return normalized(" ".join(" ".join(w["text"] for w in sorted(row[1], key=lambda w: w["x"]))
                               for row in sorted(rows)))


def _find(page, pattern, region=None):
    for line in page.get("lines", []):
        if re.search(pattern, normalized(line["text"]), re.I):
            if region is None or any(_inside(word, region) for word in line.get("words", [])):
                return line
    return None


def _proof_words(page, value, fallback=None):
    alternatives = [str(value)]
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(value)):
        try:
            alternatives.append(datetime.strptime(str(value), "%Y-%m-%d").strftime("%m/%d/%Y"))
        except ValueError:
            pass
    for literal in alternatives:
        target = _key(literal)
        if not target:
            continue
        exact = [word for word in _words(page) if _key(word["text"]) == target]
        if exact:
            answer = next((word for word in exact if _ANSWER_FONT.search(word.get("font", ""))), exact[0])
            return [answer]
        for line in page.get("lines", []):
            if target in _key(line["text"]):
                return line.get("words", [])
    return fallback or []


def _visible_options(page, region, options):
    """Require a separate printed phrase for every unmarked radio option."""
    text = normalized(_read_words(_region_words(page, region))).casefold()
    matches = []
    for code, aliases in options.items():
        aliases = aliases if isinstance(aliases, list) else [aliases]
        for alias in aliases:
            tokens = re.findall(r"[a-z0-9]+", normalized(alias).casefold())
            if not tokens:
                continue
            pattern = r"\b" + r"[\W_]*".join(re.escape(token) for token in tokens) + r"\b"
            matches.extend((match.start(), match.end(), str(code)) for match in re.finditer(pattern, text))
    found, occupied = set(), []
    # Do not use the word "completely" inside "near completely" to prove two
    # different printed options. Each code needs its own non-overlapping span.
    for left, right, code in sorted(matches, key=lambda match: (match[1] - match[0]), reverse=True):
        if code not in found and not any(left < end and right > start for start, end in occupied):
            found.add(code)
            occupied.append((left, right))
    return bool(options) and found == {str(code) for code in options}


def _recognize(page):
    text = _text(page)
    codes = {code for code in FORM_INSTRUMENTS if re.search(r"\b" + re.escape(code) + r"\b", text)}
    local = re.search(r"\bPage\s+(\d+)\s+of\s+(\d+)\b", text, re.I)
    if len(codes) == 1 and local:
        return FORM_INSTRUMENTS[next(iter(codes))], int(local[1]) == 1
    exam = re.search(r"\bEXAM:\s*([^\n]+)", text, re.I)
    if exam and re.search(r"\bFINDINGS:", text) and re.search(r"\bIMPRESSION:", text):
        label = exam[1].upper()
        if "DIGITAL SUBTRACTION MYELOGRAM" in label:
            return "image_information_ct_dsm_or_fluroscopic_guided", True
        if "CT MYELOGRAM" in label:
            return "image_information_ct_myelogram", True
        if "MRI TOTAL SPINE" in label:
            return "image_information_spine_mri", True
        if "MRI BRAIN" in label or "CT HEAD" in label:
            return "image_information_brain_scan", True
    return None, False


def _identity(page, registration=False):
    text = _text(page)
    issues = []
    result = {"recordId": "", "firstName": "", "lastName": "", "dob": "", "mrn": "", "page": page["page"]}
    if registration:
        name = re.search(r"Last\s+name\s+(.+?)\s+First\s+name\s+(.+?)(?=\s+M\.?I\.?|\s+Date of birth)", text, re.I | re.S)
        dob = re.search(r"Date\s+of\s+birth\s*\(mm/dd/yyyy\)[ \t]*(\S+)", text, re.I)
        if name:
            result.update(firstName=normalized(name[2]), lastName=normalized(name[1]))
    else:
        dob = re.search(r"\bDOB[ \t]+(\S+)", text, re.I)
        dob_line = _find(page, r"\bDOB\s+\d{1,2}/\d{1,2}/\d{4}")
        candidates = []
        if dob_line:
            anchor = _box(dob_line["words"])
            for line in page.get("lines", []):
                literal = re.split(r"\s+Accession\s*#", normalized(line["text"]), flags=re.I)[0]
                name = re.fullmatch(r"(?:Patient\s+)?([A-Za-z][A-Za-z .’'\-]*),\s*([A-Za-z][A-Za-z .’'\-]*)", literal)
                box = _box(line.get("words", []))
                if (name and 0 < anchor["y"] - box["y"] < .055
                        and abs(anchor["x"] - box["x"]) < .035):
                    candidates.append(name)
        if len(candidates) == 1:
            result.update(firstName=normalized(candidates[0][2]), lastName=normalized(candidates[0][1]))
    mrns, studies = [], []
    for line in page.get("lines", []):
        literal = normalized(line["text"])
        if re.search(r"\bResearch\s+Study\s+ID:", literal, re.I):
            study = re.search(r"Research\s+Study\s+ID:\s*(.+?)(?=\s+(?:Verified by|Photo ID|Ins\.? card)\b|$)", literal, re.I)
            if study and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", study[1].strip()):
                studies.append(study[1].strip())
            else:
                issues.append("A printed clinic study record ID is invalid or ambiguous.")
        if not ("OFFICE USE ONLY" in literal if registration else re.match(r"^MRN\b", literal)):
            continue
        match = re.search(r"\bMRN\s*:?\s*(.+?)(?=\s+(?:Research Study ID|Ordering|Verified by|Photo ID)\b|$)", literal)
        if match and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_. -]{0,79}", match[1].strip()):
            mrns.append(match[1].strip())
    if len(set(mrns)) == 1:
        result["mrn"] = mrns[0]
    if len(set(studies)) == 1:
        result["recordId"] = studies[0]
    elif len(set(studies)) > 1:
        issues.append("Printed clinic study record IDs conflict within a page.")
    if dob:
        result["dob"] = _iso(dob[1])
    return result, issues


class _Reader:
    def __init__(self):
        self.values = {name: "" for name in _fields()}
        self.evidence, self.candidates = {}, {}
        self.active = {"record_id"}
        self.issues = []
        self.declared_pages = {}
        self.context = {"profile": PROFILE, "recordIds": [], "identities": [], "instruments": [],
                        "instrumentStarts": [], "registrationAnchors": [], "unansweredFields": [], "blockingIssues": []}

    def put(self, name, value, page, words=None, mapping="clinic-native", *, source_blank=False):
        if name not in self.values:
            return
        value = normalized(value)
        if _fields()[name]["type"] in {"integer", "number"} and value.startswith("+"):
            value = value[1:]
        words = _proof_words(page, value) if words is None else words
        if not words:
            self.active.add(name)
            self.issues.append(f"{name}: Source text could not be localized; review the original page manually.")
            return
        proof = {"text": _read_words(words), "page": page["page"], "region": _box(words),
                 "method": page.get("method", "pdf-text"), "mapping": mapping}
        self.active.add(name)
        if source_blank and not value:
            proof["mapping"] = "clinic-unmarked-radio"
            self.evidence[name] = proof
            if name not in self.context["unansweredFields"]:
                self.context["unansweredFields"].append(name)
        elif value:
            self.candidates.setdefault(name, []).append((value, proof))
        else:
            self.evidence[name] = proof

    def blank(self, name, page, words, *, checkbox=False):
        self.put(name, "", page, words, "clinic-unmarked-checkbox" if checkbox else "clinic-unmarked-radio",
                 source_blank=not checkbox)

    def selected(self, page, region, options):
        matches = []
        for selection in page.get("selections", []):
            if not _inside(selection, region):
                continue
            words = _region_words(page, selection)
            printed = _key(_read_words(words))
            candidates = set()
            for code, aliases in options.items():
                aliases = [aliases] if isinstance(aliases, str) else aliases
                for alias in aliases:
                    target = _key(alias)
                    if target and (printed == target or min(len(printed), len(target)) >= 12
                                   and (printed.startswith(target) or target.startswith(printed))):
                        candidates.add(str(code))
            if len(candidates) == 1:
                matches.append((candidates.pop(), words))
        return matches

    def radio(self, name, page, region, options=None, *, words=None):
        if name not in _fields():
            return
        options = options or _fields()[name].get("choices", {})
        matches = self.selected(page, region, options)
        if len({value for value, _ in matches}) == 1:
            self.put(name, matches[0][0], page, matches[0][1], "clinic-circled-choice")
        elif not matches:
            if _visible_options(page, region, options):
                self.blank(name, page, _region_words(page, region))
            else:
                self.active.add(name)
                self.context["blockingIssues"].append(
                    f"{name}: Printed radio options are missing or ambiguous; no source-blank waiver was issued.")
        else:
            self.active.add(name)
            self.issues.append(f"{name}: Multiple circled choices need source review.")

    def registration(self, page, identity):
        names = {"record_id": "recordId", "mrn": "mrn", "patient_first": "firstName",
                 "patient_last": "lastName", "patient_dob": "dob"}
        for name, key in names.items():
            if identity[key]:
                self.put(name, identity[key], page, _proof_words(page, identity[key]), "clinic-registration")
        text = _text(page)
        email = re.search(r"\bEmail\s+([A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})", text)
        if email:
            self.put("pt_email", email[1], page)
        line = _find(page, r"\bSex:")
        if line:
            box = _box(line["words"])
            region = {"x": box["x"], "y": box["y"] - .01, "width": .95 - box["x"], "height": box["height"] + .025}
            self.radio("patient_sex", page, region)
        self.checkbox_group(page, "patient_race", r"Race \(check all", r"Ethnicity:", allow_unchecked=True)

    def checkbox_group(self, page, prefix, anchor, end, *, allow_unchecked=False):
        start = _find(page, anchor)
        if not start:
            return
        top = _box(start["words"])["y"]
        stop = next((line for line in page.get("lines", []) if re.search(end, normalized(line["text"]), re.I)
                     and _box(line.get("words", []))["y"] > top + .004), None)
        if not stop:
            return
        bottom = _box(stop["words"])["y"]
        region = {"x": .04, "y": top, "width": .92, "height": max(0, bottom - top)}
        fields = {name: field for name, field in _fields().items() if name.startswith(prefix + "___")}
        controls = [box for box in page.get("controls", []) if box.get("kind") == "square" and _inside(box, region)]
        matches = []
        for box in controls:
            right = min([other["x"] for other in controls if other["x"] > box["x"] + .03
                         and abs(other["y"] - box["y"]) < .014] or [.96])
            below = min([other["y"] for other in controls if abs(other["x"] - box["x"]) < .02
                         and other["y"] > box["y"] + .008] or [bottom])
            label_region = {"x": box["x"] + box["width"], "y": box["y"] - .004,
                            "width": max(0, right - box["x"] - box["width"]),
                            "height": min(.05, below - box["y"])}
            words = [w for w in _region_words(page, label_region) if w["text"] not in _MARKS]
            label = _key(re.sub(r"^\d+[.)]\s*", "", _read_words(words)))
            candidates = []
            for name, field in fields.items():
                option = _key(re.sub(r"^\d+[.)]\s*", "", _OPTION_ALIASES.get(name, field["label"].split(" - ", 1)[-1])))
                if option and (label == option or min(len(label), len(option)) >= 8
                               and (label.startswith(option) or option.startswith(label))):
                    candidates.append(name)
            marks = [word for word in _words(page) if word["text"] in _MARKS and _inside(word, box, .006)]
            if len(candidates) == 1:
                matches.append((candidates[0], bool(marks), marks or words))
        group_answered = any(marked for _, marked, _ in matches)
        for name, marked, words in matches:
            if marked or allow_unchecked or group_answered:
                self.put(name, "1" if marked else "0", page, words, "clinic-checkbox")
            else:
                self.blank(name, page, words, checkbox=True)

    def text_field(self, name, page, region):
        if name not in _fields():
            return
        words = [word for word in _region_words(page, region, answers=True) if word["text"] not in _MARKS]
        value = _read_words(words)
        if not value:
            return
        field = _fields()[name]
        if field["type"] == "date":
            dates = re.findall(r"\b\d{1,2}/\d{1,2}/\d{4}\b", value)
            if len(set(dates)) != 1:
                self.active.add(name)
                self.issues.append(f"{name}: A single source date could not be identified; review manually.")
                return
            value = _iso(dates[0])
        elif field["type"] in {"integer", "number"}:
            if not re.fullmatch(r"[+-]?\d+(?:\.\d+)?", value):
                self.active.add(name)
                self.issues.append(f"{name}: The source number needs manual review.")
                return
        self.put(name, value, page, words, "clinic-answer-region")

    def questionnaire(self, page, patient=False):
        suffix = "_v2" if patient else ""
        positions = []
        for base, pattern, kind in _QUESTION_SPECS:
            line = _find(page, pattern)
            if line:
                positions.append((base, line, kind))
        boundaries = [_box(line["words"])["y"] for _, line, _ in positions]
        boundaries.extend(_box(line["words"])["y"] for line in page.get("lines", [])
                          if re.search(r"^(?:Section \d|Medication |Prior procedures|Patient signature|Clinician signature|HA-2)", normalized(line["text"])))
        for base, line, kind in positions:
            name = base + suffix
            if name not in _fields():
                continue
            top = _box(line["words"])["y"]
            bottom = min([y for y in boundaries if y > top + .007] or [min(.94, top + .1)])
            region = {"x": .04, "y": top - .004, "width": .92, "height": max(.015, bottom - top)}
            if kind == "radio":
                options = _RADIO_ALIASES.get(name, _fields()[name].get("choices", {}))
                self.radio(name, page, region, options, words=line["words"])
            else:
                self.text_field(name, page, region)
        self.questionnaire_days(page, suffix)
        groups = [
            ("headache_location", r"(?:Headache location|Where are your headaches\?)", r"Other location:"),
            ("headache_quality", r"Quality of headache", r"^Other:"),
            ("headache_pattern", r"Any pattern to the headache", r"^Other:"),
            ("headache_associated", r"Which non-headache symptoms", r"Other symptoms:"),
            ("all_associated_pain", r"Do you have pain in any of these locations", r"Previous evaluations"),
        ]
        if not patient:
            groups += [
                ("headache_change_categories", r"If changed, how\?", r"Other change"),
                ("sleep_frequency", r"If it wakes you from sleep", r"HA-210C"),
                ("other_specialists", r"Specialists seen for headache", r"Other specialists:"),
                ("personal_ctdisorder_opt", r"Personal history of connective tissue", r"If other:"),
                ("family_ctdisorder_opt", r"Family history of connective tissue", r"If other:"),
            ]
        for base, start, stop in groups:
            self.checkbox_group(page, base + suffix, start, stop)
        other_regions = [
            ("headache_location_other", r"Other location:", r"Quality of headache"),
            ("headache_assocaited_other", r"Other symptoms:", r"Do you have pain"),
        ]
        if not patient:
            other_regions.append(("other_specialists_other", r"Other specialists:", r"HA-210C"))
        for base, start_pattern, end_pattern in other_regions:
            start, stop = _find(page, start_pattern), _find(page, end_pattern)
            if start and stop:
                top, bottom = _box(start["words"])["y"], _box(stop["words"])["y"]
                if bottom > top:
                    self.text_field(base + suffix, page, {"x": .04, "y": top - .005, "width": .92, "height": bottom - top})
        self.questionnaire_tables(page, suffix)

    def questionnaire_days(self, page, suffix):
        severe = next((word for word in _words(page) if word["text"] == "Severe"), None)
        if severe is None:
            return
        header_y = severe["y"]
        columns = []
        for base, label in (("severe_past28", "Severe"), ("moderate_past28", "Moderate"),
                            ("mild_past28", "Mild"), ("none_past28", "No")):
            matches = [w for w in _words(page) if w["text"] == label and abs(w["y"] - header_y) < .015]
            if matches:
                word = matches[0]
                columns.append((base + suffix, word["x"] + word["width"] / 2))
        answers = [word for word in _words(page) if _ANSWER_FONT.search(word.get("font", ""))
                   and header_y + .015 < word["y"] < header_y + .08 and re.fullmatch(r"\d+", word["text"])]
        for name, x in columns:
            candidates = [word for word in answers if abs(word["x"] + word["width"] / 2 - x) < .07]
            if len(candidates) == 1:
                self.put(name, candidates[0]["text"], page, candidates, "clinic-table-column")

    def matrix(self, page, header, row_specs, codes, suffix):
        line = _find(page, header)
        if not line:
            return
        header_words = line["words"]
        columns = []
        for label, code in codes:
            word = next((word for word in header_words if word["text"].casefold() == label.casefold()), None)
            if word:
                columns.append((code, word["x"] + word["width"] / 2))
        if len(columns) != len(codes):
            return
        rows = [(name, _find(page, pattern)) for name, pattern in row_specs]
        rows = [(name, row) for name, row in rows if row]
        for name, row in rows:
            top = _box(row["words"])["y"]
            bottom = min([_box(other["words"])["y"] for _, other in rows
                          if _box(other["words"])["y"] > top + .006] or [top + .035])
            marks = [word for word in _words(page) if word["text"] in _MARKS
                     and top - .008 <= word["y"] < bottom - .002
                     and word["x"] > min(x for _, x in columns) - .05]
            target = name + suffix
            if target not in _fields():
                continue
            if len(marks) == 1:
                x = marks[0]["x"] + marks[0]["width"] / 2
                code = min(columns, key=lambda item: abs(item[1] - x))[0]
                self.put(target, code, page, marks, "clinic-table-column")
            elif not marks:
                self.blank(target, page, row["words"])
            else:
                self.active.add(target)
                self.issues.append(f"{target}: Multiple matrix marks need review.")

    def questionnaire_tables(self, page, suffix):
        rows = [("cough", r"^Coughing or sneezing"), ("bending", r"^Bending forward"),
                ("standing_up", r"^Standing up"), ("lying_down", r"^Lying down"),
                ("plane_altitude", r"^Higher altitude"), ("periods", r"^During your period")]
        if suffix:
            rows.append(("intercourse", r"^Physical activity / exertion"))
        self.matrix(page, r"^Situation\s+Better", rows, [("Better", "1"), ("Worse", "2"), ("No", "3")], suffix)
        med_rows = [("med_caf", r"^Caffeine products"), ("med_topiramate", r"^Topiramate"),
                    ("med_triptan", r"^Triptans"), ("med_emgality", r"^CGRP medicines"),
                    ("med_diamox", r"^Acetazolamide"), ("med_glp1a", r"^GLP-1 agonists")]
        med_codes = [("Helped", "1"), ("No", "3" if suffix else "2"),
                     ("Made", "5" if suffix else "3"), ("Never", "6" if suffix else "4")]
        if not suffix:
            med_codes.append(("Not", "5"))
        self.matrix(page, r"^Medication\s+Helped", med_rows, med_codes, suffix)
        eval_rows = [("ct_previous", "ct_prev_date", r"^CT scan of the brain"),
                     ("mri_previous", "mri_prev_date", r"^MRI scan of the brain"),
                     ("spinal_tap_previous", "spinal_tap_prev_date", r"^Lumbar puncture \(spinal tap\)")]
        found = [(choice, date, _find(page, pattern)) for choice, date, pattern in eval_rows]
        found = [(choice, date, line) for choice, date, line in found if line]
        for choice, date, line in found:
            top = _box(line["words"])["y"]
            bottom = min([_box(other["words"])["y"] for _, _, other in found
                          if _box(other["words"])["y"] > top + .006] or [top + .025])
            region = {"x": .04, "y": top - .005, "width": .92, "height": bottom - top}
            self.radio(choice + suffix, page, region, {"1": "Yes", "0": "No"}, words=line["words"])
            self.text_field(date + suffix, page, region)
            if choice == "spinal_tap_previous":
                pressure = [word for word in _region_words(page, region, answers=True)
                            if re.fullmatch(r"\d+(?:\.\d+)?", word["text"])]
                if len(pressure) == 1:
                    self.put("spinal_tap_prev_pressure" + suffix, pressure[0]["text"], page, pressure)
        self.procedure_history(page, suffix)

    def procedure_history(self, page, suffix):
        header = _find(page, r"^Procedure\s+Had it")
        if header is None:
            return
        words = header["words"]
        date_word = next((word for word in words if word["text"].startswith("Date")), None)
        did_word = next((word for word in words if word["text"] == "Did"), None)
        if date_word is None or did_word is None:
            return
        date_x, help_x = date_word["x"], did_word["x"]
        had_word = next((word for word in words if word["text"] == "Had"), None)
        if had_word is None:
            return
        date_center = date_word["x"] + date_word["width"] / 2
        date_left = (had_word["x"] + had_word["width"] / 2 + date_center) / 2
        date_right = (date_center + did_word["x"] + did_word["width"] / 2) / 2
        rows = [("prior_bloodpatches", "prior_bloodpatches_dates", "prev_bloodpatches_improv", r"^Epidural blood patch"),
                ("prior_fibrin_glue", "prior_fibrin_glue_dates", "prior_fibrin_glue_success", r"^Fibrin glue patch"),
                ("prior_surgeries", "prior_surgeries_dates", "prior_surgeries_success", r"^Surgery for CSF leak"),
                ("prior_tves", "prior_tves_date", "prior_tve_success", r"^Transvenous embolization")]
        located = [(had, dates, helped, _find(page, pattern)) for had, dates, helped, pattern in rows]
        located = [(had, dates, helped, line) for had, dates, helped, line in located if line]
        for had, dates, helped, line in located:
            top = _box(line["words"])["y"]
            bottom = min([_box(other["words"])["y"] for _, _, _, other in located
                          if _box(other["words"])["y"] > top + .005] or [top + .025])
            left = {"x": .04, "y": top - .005, "width": max(.1, date_x - .05), "height": bottom - top}
            right = {"x": help_x - .015, "y": top - .005, "width": .97 - help_x, "height": bottom - top}
            self.radio(had + suffix, page, left, {"1": "Yes", "0": "No"}, words=line["words"])
            self.radio(helped + suffix, page, right, {"1": "Yes", "0": "No"}, words=line["words"])
            self.text_field(dates + suffix, page, {"x": date_left, "y": top - .005,
                                                  "width": date_right - date_left, "height": bottom - top})

    def hit6(self, page):
        text = _text(page)
        date = re.search(r"(?:^|\n)Date\s+(\d{1,2}/\d{1,2}/\d{4})", text)
        if date:
            self.put("hit6_date", _iso(date[1]), page, _proof_words(page, date[1]))
        names = ("severity", "limitactivities", "liedown", "tired", "irritated", "limitconcentration")
        self.active.update("hit6_" + suffix for suffix in names)
        columns, headers = [], []
        for code, label in (("6", "Never"), ("8", "Rarely"), ("10", "Sometimes"), ("11", "Very"), ("13", "Always")):
            matches = [word for word in _words(page) if word["text"] == label]
            if len(matches) == 1:
                word = matches[0]
                columns.append((code, word["x"] + word["width"] / 2))
                headers.append(word)
        if (len(columns) != 5 or [x for _, x in columns] != sorted(x for _, x in columns)
                or any(right - left < .02 for (_, left), (_, right) in zip(columns, columns[1:]))
                or max(word["y"] for word in headers) - min(word["y"] for word in headers) > .025):
            self.context["blockingIssues"].append("HIT-6 frequency headers are missing, ambiguous or misaligned; use a complete matching table.")
            return
        question_anchors = ("painsevere", "limityourabilitytodousualdailyactivities", "wishyoucouldliedown",
                            "felttootired", "feduporirritated", "limityourabilitytoconcentrate")
        row_words = [word for word in _words(page) if word["text"] in {str(i) for i in range(1, 7)} and word["x"] < .1]
        if len(row_words) != 6 or {word["text"] for word in row_words} != {str(i) for i in range(1, 7)}:
            self.context["blockingIssues"].append("HIT-6 must contain all six uniquely numbered question rows.")
            return
        centers = sorted(word["y"] + word["height"] / 2 for word in row_words)
        left_edge = columns[0][1] - (columns[1][1] - columns[0][1]) / 2
        right_edge = columns[-1][1] + (columns[-1][1] - columns[-2][1]) / 2
        for index, suffix in enumerate(names, 1):
            marker = next((word for word in row_words if word["text"] == str(index)), None)
            center = marker["y"] + marker["height"] / 2
            previous = max([y for y in centers if y < center - .005] or [center - .05])
            following = min([y for y in centers if y > center + .005] or [center + .05])
            row_region = {"x": .04, "y": (previous + center) / 2,
                          "width": min(x for _, x in columns) - .06, "height": (following - previous) / 2}
            name = "hit6_" + suffix
            if question_anchors[index - 1] not in _key(_read_words(_region_words(page, row_region))):
                self.context["blockingIssues"].append(f"{name}: The printed question label is missing or changed; no table answer selected.")
                continue
            marks = [word for word in _words(page) if word["text"] in _MARKS
                     and (previous + center) / 2 <= word["y"] + word["height"] / 2 < (center + following) / 2]
            if len(marks) == 1:
                mark_x = marks[0]["x"] + marks[0]["width"] / 2
                if not left_edge <= mark_x <= right_edge:
                    self.context["blockingIssues"].append(f"{name}: A row-aligned mark lies outside the printed frequency columns.")
                    continue
                code = min(columns, key=lambda column: abs(column[1] - mark_x))[0]
                self.put(name, code, page, marks, "clinic-table-column")
            elif not marks:
                self.blank(name, page, _region_words(page, row_region) + headers)
            else:
                self.active.add(name)
                self.issues.append(f"{name}: Multiple marked table cells need source review.")

    def finish(self):
        for instrument, declarations in self.declared_pages.items():
            total = declarations[0][1]
            if (any(count != total for _, count in declarations) or len(declarations) != total
                    or [number for number, _ in declarations] != list(range(1, total + 1))):
                self.context["blockingIssues"].append(
                    f"{instrument}: Printed page numbers are incomplete, repeated or out of order; include every original page in order.")
        for name, items in self.candidates.items():
            distinct = {value for value, _ in items}
            if len(distinct) == 1:
                self.values[name] = items[0][0]
                self.evidence[name] = copy.deepcopy(items[0][1])
                self.evidence[name]["occurrences"] = [copy.deepcopy(proof) for _, proof in items]
                if name in self.context["unansweredFields"]:
                    self.context["unansweredFields"].remove(name)
            else:
                self.context["blockingIssues"].append(f"{name}: Repeated clinic source values conflict.")
        anchors = self.context["registrationAnchors"]
        anchor_ids = {anchor["recordId"] for anchor in anchors if anchor["recordId"]}
        self.context["recordIds"] = sorted({identity["recordId"] for identity in self.context["identities"] if identity["recordId"]})
        if len(anchors) != 1 or len(anchor_ids) != 1:
            self.context["blockingIssues"].append("Include exactly one registration with its printed Research Study ID in this patient bundle.")
        if anchor_ids and set(self.context["recordIds"]) != anchor_ids:
            self.context["blockingIssues"].append("A printed clinic study record ID conflicts with registration.")
        self.context["unansweredFields"].sort()
        self.context["blockingIssues"] = list(dict.fromkeys(self.context["blockingIssues"]))
        return {"values": self.values, "evidence": self.evidence,
                "issues": list(dict.fromkeys(self.issues + self.context["blockingIssues"])),
                "applicableFields": sorted(self.active), "sourceContext": self.context}


_OPTION_ALIASES = {
    "headache_location_v2___2": "Unilateral Forehead", "headache_location_v2___3": "Bilateral Forehead",
    "headache_location_v2___8": "Bilateral, Cheek", "headache_location_v2___11": "Unilateral, Temporomandibular joint",
    "headache_location_v2___12": "Bilateral, Temporomandibular joint", "headache_location_v2___13": "Unilateral, Temple",
    "headache_location_v2___14": "Bilateral, Temple", "headache_location_v2___15": "Unilateral, Occipital",
    "headache_location_v2___16": "Bilateral, Occipital", "headache_location_v2___21": "Variable / migratory",
    "headache_quality_v2___3": "jabbing/piercing/knife-like/sharp shooting",
    "headache_quality___3": "jabbing/piercing/knife-like/sharp shooting",
    "headache_location___4": "Periorbital/retro-orbital (Around/Behind the eyes)",
}

_QUESTION_SPECS = (
    ("headaches_yn", r"^\d+\.\s*(?:Is the patient currently experiencing headaches|Have you had headaches within the last 3 months)", "radio"),
    ("ha_prev_yn", r"^\d+\.\s*Have you previously had headaches", "radio"),
    ("headache_start", r"^\d+\.\s*When did your current headaches first start", "text"),
    ("headaches_description", r"^\d+\.\s*Briefly describe your current headache", "text"),
    ("diff_headaches", r"^\d+\.\s*Have you had prior headaches of a different pattern", "radio"),
    ("diff_headache_start", r"^\d+\.\s*Have you had prior headaches of a different pattern", "text"),
    ("headache_change", r"^\d+\.\s*Any recent change to the pattern", "radio"),
    ("headache_change_desc", r"^\d+\.\s*(?:Describe how your headaches have changed|Other change \(describe\))", "text"),
    ("headaches_every_start", r"^\d+\.\s*When did everyday / recurrent headaches begin", "text"),
    ("headache_every_char", r"^\d+\.\s*Did your headaches begin", "radio"),
    ("headaches_every_other", r"^\d+\.\s*Did your headaches begin", "text"),
    ("headache_localization", r"^\d+\.\s*My headaches are", "radio"),
    ("headache_laterality", r"^\d+\.\s*Is it localized to one side or both", "radio"),
    ("headache_other", r"^\d+\.\s*Quality of headache", "text"),
    ("headache_pattern_other", r"^\d+\.\s*Any pattern to the headache", "text"),
    ("standing_up_time", r"^\d+\.\s*If better lying down: how many minutes", "text"),
    ("lying_down_improve_time", r"^\d+\.\s*If better lying down: how long", "radio"),
    ("lying_down_improve_qual", r"^\d+\.\s*If better lying down: how much better", "radio"),
    ("personal_connective_tissue", r"^\d+\.\s*(?:Personal history of connective tissue|Have you ever been diagnosed with a connective tissue)", "radio"),
    ("personal_ctdisorder", r"^\d+\.\s*(?:Personal history of connective tissue|Have you ever been diagnosed with a connective tissue)", "text"),
    ("family_connective_tissue", r"^\d+\.\s*(?:Family history of connective tissue|Has anyone in your family been diagnosed with one)", "radio"),
    ("family_ctdisorder", r"^\d+\.\s*(?:Family history of connective tissue|Has anyone in your family been diagnosed with one)", "text"),
    ("pots", r"^\d+\.\s*Diagnosed with POTS", "radio"),
    ("mcas", r"^\d+\.\s*Diagnosed with Mast Cell Activation", "radio"),
    ("med_other_improve", r"^\d+\.\s*Any other medications that improved your symptoms", "radio"),
    ("meds_other_improve_list", r"^\d+\.\s*Any other medications that improved your symptoms", "text"),
    ("med_other_worsen", r"^\d+\.\s*Any other medications that worsened your symptoms", "radio"),
    ("meds_other_worsen_list", r"^\d+\.\s*Any other medications that worsened your symptoms", "text"),
)

_RADIO_ALIASES = {
    "headache_laterality": {"1": "Bilateral", "2": "Unilateral", "3": "Mix of both"},
}


def extract(pages):
    reader = _Reader()
    for page in pages:
        text = _text(page)
        if page["page"] == 1 and "Source bundle for one study record" in text:
            continue
        instrument, start = _recognize(page)
        if instrument is None:
            reader.context["blockingIssues"].append(f"Page {page['page']}: Unsupported SIH clinic layout; use a matching reader or custom masks.")
            continue
        if instrument not in reader.context["instruments"]:
            reader.context["instruments"].append(instrument)
        if start:
            reader.context["instrumentStarts"].append({"instrument": instrument, "page": page["page"]})
        if instrument in FORM_INSTRUMENTS.values():
            declaration = re.search(r"\bPage\s+(\d+)\s+of\s+(\d+)\b", text, re.I)
            if declaration:
                reader.declared_pages.setdefault(instrument, []).append((int(declaration[1]), int(declaration[2])))
        identity, identity_issues = _identity(page, instrument == "patient_records")
        reader.context["blockingIssues"].extend(f"Page {page['page']}: {issue}" for issue in identity_issues)
        reader.context["identities"].append(identity)
        if not all(identity[key] for key in ("firstName", "lastName", "dob", "mrn")):
            reader.context["blockingIssues"].append(f"Page {page['page']}: Clinic source name, birth date or MRN is missing or ambiguous.")
        if instrument == "patient_records":
            reader.context["registrationAnchors"].append(copy.deepcopy(identity))
            reader.registration(page, identity)
        elif instrument == "hit6":
            reader.hit6(page)
        elif instrument.startswith("duke_neuroradiology_headache_questionnaire"):
            reader.questionnaire(page, instrument.endswith("_patient"))
        elif instrument == "csf_volume_provocation_form":
            reader.issues.extend(extract_procedure(page, reader.put))
        elif instrument.startswith("image_information_"):
            reader.issues.extend(extract_radiology(page, reader.put))
        else:
            reader.issues.append(f"Page {page['page']}: Review the clinic source; only source-backed fields are proposed.")
    return reader.finish()
