"""Automatic PACE source recognition, independent identity and reusable rules."""
from __future__ import annotations

import copy
from functools import lru_cache
import json
import math
import re

import clinic_profile as clinic
import neurology_profile as neurology
import pace_profile as pace
from limits import MAX_FIELDS, MAX_PAGES


PROFILE = "pace-auto-v1"
LOADOUT_FORMAT = "qwikcap-pace-loadout-v1"
IDENTITY_FIELDS = {"mrn": "mrn", "patient_first": "firstName", "patient_last": "lastName", "patient_dob": "dob"}
_HIT6_FIELDS = ("hit6_severity", "hit6_limitactivities", "hit6_liedown", "hit6_tired", "hit6_irritated", "hit6_limitconcentration")
_CLINIC_TITLES = {
    "patient_records": ("REG-100", "Patient Registration Form"),
    "duke_neuroradiology_headache_questionnaire": ("HA-210C", "Headache History", "Clinician Intake"),
    "duke_neuroradiology_headache_questionnaire_patient": ("HA-220P", "Headache History", "Patient Questionnaire"),
    "hit6": ("HA-230", "HIT-6", "Headache Impact Test", "Pain severe", "Limit your ability to do usual daily activities", "Wish you could lie down", "Felt too tired", "Fed up or irritated", "Limit your ability to concentrate"),
    "csf_volume_provocation_form": ("PROC-310", "CSF", "Provocation"),
    "image_information_brain_scan": ("EXAM", "MRI BRAIN", "CT HEAD", "FINDINGS", "IMPRESSION"),
    "image_information_spine_mri": ("EXAM", "MRI TOTAL SPINE", "FINDINGS", "IMPRESSION"),
    "image_information_ct_myelogram": ("EXAM", "CT MYELOGRAM", "FINDINGS", "IMPRESSION"),
    "image_information_ct_dsm_or_fluroscopic_guided": ("EXAM", "DIGITAL SUBTRACTION MYELOGRAM", "FINDINGS", "IMPRESSION"),
}


@lru_cache(maxsize=1)
def _fields():
    return {field["name"]: field for field in pace._catalog()["fields"]}


def profile_schema():
    fields = pace.profile_schema()
    fields[0]["profile"] = PROFILE
    return fields


def _text(page):
    return "\n".join(pace.normalized(line.get("text", "")) for line in page.get("lines", []))


def _anchors(layout, instrument):
    if layout == "clinic":
        return _CLINIC_TITLES.get(instrument, ())
    if layout == "neu-hit6":
        return ("Form NEU-210", "Points per response", "HIT-6", "Headache Impact Test")
    if layout == "pace":
        entry = next((item for item in pace._catalog()["instruments"] if item["name"] == instrument), None)
        if entry:
            return (entry["label"], entry["name"], "Intracranial Hypotension_PACE", "Record ID", *(
                field["label"] for field in _fields().values() if field["instrument"] == instrument))
    return ()


def _present_anchors(page, layout, instrument):
    text = pace._key(_text(page))
    return list(dict.fromkeys(anchor for anchor in _anchors(layout, instrument) if pace._key(anchor) in text))


def _anchor_regions(page, anchors):
    result = {}
    for anchor in anchors:
        target, matched = pace._key(anchor), []
        for line in page.get("lines", []):
            words = line.get("words", [])
            for start in range(len(words)):
                literal = ""
                for end in range(start, len(words)):
                    literal += pace._key(words[end]["text"])
                    if literal == target:
                        matched.extend(words[start:end + 1])
                    if len(literal) >= len(target):
                        break
        if matched:
            result[anchor] = clinic._box(matched)
    return result


def _revision(page, layout, instrument):
    for line in page.get("lines", []):
        text = pace.normalized(line.get("text", ""))
        codes = _CLINIC_TITLES.get(instrument, ())[:1] if layout == "clinic" else ("Form NEU-210",) if layout == "neu-hit6" else (instrument,)
        if any(pace._key(code) in pace._key(text) for code in codes):
            match = re.search(r"\bRev(?:ision)?\.?\s+([0-9]{1,2}/[0-9]{4}|[0-9]{4}-[0-9]{1,2}|[A-Za-z0-9][A-Za-z0-9_.-]{0,19})(?=\s|$)", text, re.I)
            if match:
                return match[1]
    return ""


def _recognize(page, previous=None):
    instrument, start = clinic._recognize(page)
    if instrument:
        return instrument, "clinic", start
    text = _text(page)
    if re.search(r"\bForm\s+NEU[- ]?210\b", text, re.I) and re.search(r"\bPoints per response\b", text, re.I):
        return "hit6", "neu-hit6", True
    found, headers = set(), set()
    for line in page.get("lines", []):
        key = pace._key(line.get("text", ""))
        for entry in pace._catalog()["instruments"]:
            if key == pace._key(entry["label"]):
                found.add(entry["name"])
                headers.add(entry["name"])
            if key == pace._key(entry["name"]) or key.startswith("confidential") and key.endswith(pace._key(entry["name"])):
                found.add(entry["name"])
    if len(found) == 1:
        return next(iter(found)), "pace", bool(headers)
    if not found and previous and previous[1] == "pace" and not re.search(r"\b(?:Record ID|Patient|DOB|MRN)\s*:", text, re.I):
        return previous[0], "pace", False
    return None, None, False


def _page_declaration(page):
    declarations = re.findall(r"\bPage\s+(\d+)\s+of\s+(\d+)\b", _text(page), re.I)
    if len(set(declarations)) == 1:
        number, count = map(int, declarations[0])
        if 1 <= number <= count <= MAX_PAGES:
            return number, count
    return None


def _identity(page, registration=False):
    identity, ignored = clinic._identity(page, registration)
    text = _text(page)
    issues = []
    mrns = []
    for line in page.get("lines", []):
        literal = pace.normalized(line.get("text", ""))
        match = re.search(r"\bMRN\s*:?\s*(.+?)(?=\s+(?:Research Study ID|Record ID|Ordering|DOB|Sex|Date|Verified by|Photo ID|Accession)\b|$)", literal, re.I)
        if match:
            value = match[1].strip()
            if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_. /-]{0,79}", value):
                mrns.append(value)
            else:
                mrns.append("")
                issues.append("Patient sticker MRN contains unsupported text. No partial MRN was selected.")
    studies = []
    for line in page.get("lines", []):
        match = re.search(r"\b(?:Research\s+Study\s+ID|Record\s+ID)\s*:\s*(.+?)(?=\s+(?:Verified by|Photo ID|Ins\.? card|Patient|DOB|MRN)\b|$)", pace.normalized(line.get("text", "")), re.I)
        if match:
            value = match[1].strip()
            if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", value):
                studies.append(value)
            else:
                studies.append("")
                issues.append("A printed source study ID is invalid or ambiguous; no partial ID was selected.")
    dates = [clinic._iso(value) for value in re.findall(r"\bDOB\s*:?\s*(\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2})", text, re.I)]
    names = []
    dob_lines = [line for line in page.get("lines", []) if re.search(r"\bDOB\s*:?\s*\d", line.get("text", ""), re.I) and line.get("words")]
    for line in page.get("lines", []):
        literal = pace.normalized(line.get("text", ""))
        inline = re.search(r"\bPatient(?:\s+Name)?\s*:?\s*(.*?)\s+DOB\s*:?", literal, re.I)
        if inline and "," in inline[1]:
            last, first = inline[1].split(",", 1)
            names.append((pace.normalized(first), pace.normalized(last)))
        elif inline:
            parts = inline[1].split()
            if len(parts) >= 2:
                names.append((" ".join(parts[:-1]), parts[-1]))
        else:
            name = re.fullmatch(r"(?:Patient\s*:?\s*)?([^,]+),\s*([^,]+)", literal, re.I)
            if name and line.get("words") and all(part[0].isalpha() and all(char.isalpha() or char in " .’'-" for char in part) for part in name.groups()):
                box = clinic._box(line["words"])
                if any(0 < clinic._box(dob_line["words"])["y"] - box["y"] < .055 and abs(clinic._box(dob_line["words"])["x"] - box["x"]) < .035 for dob_line in dob_lines):
                    names.append((pace.normalized(name[2]), pace.normalized(name[1])))
    if identity["firstName"] and identity["lastName"]:
        names.append((identity["firstName"], identity["lastName"]))
    if names:
        distinct = {(first.casefold(), last.casefold()) for first, last in names}
        if len(distinct) == 1:
            identity.update(firstName=names[0][0], lastName=names[0][1])
        else:
            identity.update(firstName="", lastName="")
            issues.append("Patient sticker names conflict within this page.")
    for key, candidates in (("mrn", mrns), ("recordId", studies), ("dob", dates)):
        if candidates:
            distinct = set(candidates)
            if len(distinct) == 1 and next(iter(distinct)):
                identity[key] = candidates[0]
            else:
                identity[key] = ""
                issues.append(f"Patient sticker {key} is invalid or conflicting within this page.")
    return identity, issues


def _legacy_identity_issue(issue):
    return any(fragment in issue for fragment in (
        "Printed sources do not share exactly one record ID", "Printed record ID is missing or conflicting",
        "Printed patient identity", "Clinic source name, birth date or MRN is missing or ambiguous",
        "Include exactly one registration with its printed Research Study ID", "A printed clinic study record ID conflicts with registration",
    ))


def extract(pages):
    preferred = {}
    for page in pages:
        current = preferred.get(page["page"])
        if current is None or page.get("method") == "pdf-text":
            preferred[page["page"]] = page
    ordered = [preferred[number] for number in sorted(preferred)]
    context = {"profile": PROFILE, "recordIds": [], "identities": [], "instruments": [], "instrumentStarts": [],
               "unansweredFields": [], "blockingIssues": [], "pageLayouts": []}
    groups, previous, offset = {"clinic": [], "pace": [], "neu-hit6": []}, None, 0
    previous_declaration, previous_identity = None, None
    for page in ordered:
        literals = {pace.normalized(line.get("text", "")) for line in page.get("lines", [])}
        if page["page"] == 1 and {"Source bundle for one study record", "No patient identity was inferred."} <= literals:
            continue
        instrument, layout, start = _recognize(page, previous)
        identity, problems = _identity(page, instrument == "patient_records" and layout == "clinic")
        declaration = _page_declaration(page)
        continuation = (previous == (instrument, layout) and declaration is not None and previous_declaration is not None
                        and declaration[1] == previous_declaration[1] and declaration[0] == previous_declaration[0] + 1)
        if continuation:
            start = False
            if not problems and previous_identity is not None and not any(identity[key] for key in ("recordId", "firstName", "lastName", "dob", "mrn")):
                identity = {**previous_identity, "page": page["page"], "inheritedFromPage": previous_identity.get("inheritedFromPage", previous_identity["page"])}
        context["identities"].append(identity)
        context["blockingIssues"].extend(f"Page {page['page']}: {problem}" for problem in problems)
        if not instrument:
            context["blockingIssues"].append(f"Page {page['page']}: No supported PACE instrument layout was recognized.")
            previous = None
            previous_declaration, previous_identity = None, None
            continue
        if start or previous != (instrument, layout):
            offset = 0
            context["instrumentStarts"].append({"instrument": instrument, "page": page["page"]})
        else:
            offset += 1
        previous = instrument, layout
        previous_declaration, previous_identity = declaration, identity
        if instrument not in context["instruments"]:
            context["instruments"].append(instrument)
        anchors = _present_anchors(page, layout, instrument)
        anchor_regions = _anchor_regions(page, anchors)
        anchors = [anchor for anchor in anchors if anchor in anchor_regions]
        context["pageLayouts"].append({"page": page["page"], "instrument": instrument, "layout": layout,
                                       "anchors": anchors, "anchorRegions": anchor_regions,
                                       "revision": _revision(page, layout, instrument), "pageOffset": offset})
        groups[layout].append(page)
    values = {name: "" for name in _fields()}
    evidence, issues, active, candidates = {}, [], {"record_id", *IDENTITY_FIELDS}, {}
    for layout, selected in groups.items():
        if not selected:
            continue
        if layout == "neu-hit6":
            result = neurology.extract(selected, "0" * 64)
            translated = {"hit6_date": result["values"].get("form_date", "")}
            proof = {"hit6_date": result["evidence"].get("form_date", {})}
            for index, name in enumerate(_HIT6_FIELDS, 1):
                item = result["evidence"].get(f"hit6_q{index}", {})
                box = item.get("region", {})
                source_page = next((page for page in selected if page["page"] == item.get("page")), {})
                nearby = " ".join(line.get("text", "") for line in source_page.get("lines", [])
                                  if line.get("words") and box and abs(clinic._box(line["words"])["y"] - box["y"]) < .02)
                anchor = _CLINIC_TITLES["hit6"][index + 2]
                if pace._key(anchor) in pace._key(nearby):
                    translated[name] = result["values"].get(f"hit6_q{index}", "")
                    proof[name] = item
                else:
                    translated[name] = ""
                    result["issues"].append(f"{name}: The matching printed HIT-6 question was not localized; review it manually.")
            result = {"values": translated, "evidence": proof, "issues": result["issues"], "applicableFields": list(translated),
                      "sourceContext": {"blockingIssues": [], "unansweredFields": []}}
        else:
            result = (clinic if layout == "clinic" else pace).extract(selected)
        if layout == "pace":
            for source_identity in result["sourceContext"]["identities"]:
                identity = next((item for item in context["identities"] if item["page"] == source_identity["page"]), None)
                if identity is None:
                    continue
                for key in ("recordId", "firstName", "lastName", "dob", "mrn"):
                    observed = source_identity[key]
                    existing = identity[key]
                    if existing and observed and (existing if key == "mrn" else pace.normalized(existing).casefold()) != (observed if key == "mrn" else pace.normalized(observed).casefold()):
                        context["blockingIssues"].append(f"Page {identity['page']}: Printed patient {key} conflicts with the source identity.")
                    elif observed and not existing:
                        identity[key] = observed
        active.update(result["applicableFields"])
        for name, value in result["values"].items():
            if name in values and name != "record_id" and value:
                candidates.setdefault(name, []).append((value, result["evidence"].get(name, {})))
        for name, proof in result["evidence"].items():
            if name in values and name != "record_id":
                evidence.setdefault(name, copy.deepcopy(proof))
        context["unansweredFields"].extend(result["sourceContext"]["unansweredFields"])
        context["blockingIssues"].extend(issue for issue in result["sourceContext"]["blockingIssues"] if not _legacy_identity_issue(issue))
        issues.extend(issue for issue in result["issues"] if not _legacy_identity_issue(issue))
    starts = {start["page"] for start in context["instrumentStarts"]}
    layouts = {page["page"]: page for page in context["pageLayouts"]}
    previous_identity = None
    for identity in context["identities"]:
        page_number = identity["page"]
        layout = layouts.get(page_number, {})
        new_header = re.search(r"\b(?:Record\s+ID|Patient|DOB|MRN)\s*:", _text(preferred[page_number]), re.I)
        if (layout.get("layout") == "pace" and previous_identity is not None and page_number == previous_identity["page"] + 1
                and layouts.get(previous_identity["page"], {}).get("instrument") == layout.get("instrument")
                and page_number not in starts and not new_header
                and not any(identity[key] for key in ("recordId", "firstName", "lastName", "dob", "mrn"))):
            identity.update({key: previous_identity[key] for key in ("recordId", "firstName", "lastName", "dob", "mrn")})
            identity["inheritedFromPage"] = previous_identity.get("inheritedFromPage", previous_identity["page"])
        previous_identity = identity
    for name, items in candidates.items():
        if len({value for value, _ in items}) == 1:
            values[name], evidence[name] = items[0][0], copy.deepcopy(items[0][1])
        else:
            context["blockingIssues"].append(f"{name}: Repeated source answers conflict; no value was selected.")
    context["recordIds"] = sorted({identity["recordId"] for identity in context["identities"] if identity["recordId"]})
    for name, key in IDENTITY_FIELDS.items():
        identities = [identity for identity in context["identities"] if identity[key]]
        distinct = {identity[key] if key == "mrn" else identity[key].casefold() for identity in identities}
        if len(distinct) == 1:
            existing = values[name]
            if existing and (existing if key == "mrn" else pace.normalized(existing).casefold()) == next(iter(distinct)):
                continue
            values[name] = identities[0][key]
            page = preferred[identities[0]["page"]]
            words = clinic._proof_words(page, values[name])
            if words:
                evidence[name] = {"text": values[name], "page": page["page"], "region": clinic._box(words),
                                  "method": page.get("method", "pdf-text"), "mapping": "pace-sticker-identity"}
        else:
            values[name] = ""
    context["unansweredFields"] = sorted(set(context["unansweredFields"]) - {name for name, value in values.items() if value})
    context["blockingIssues"] = list(dict.fromkeys(context["blockingIssues"]))
    record = {"values": values, "evidence": evidence, "issues": issues, "applicableFields": sorted(active), "sourceContext": context}
    identity_problems = identity_issues(record)
    context["blockingIssues"] = list(dict.fromkeys(context["blockingIssues"] + identity_problems))
    record["issues"] = list(dict.fromkeys(issues + context["blockingIssues"]))
    return record


def identity_issues(record):
    context = record.get("sourceContext")
    if not isinstance(context, dict) or context.get("profile", PROFILE) != PROFILE:
        return ["PACE automatic source metadata is missing or invalid. Reprocess the PDFs."]
    identities = context.get("identities")
    if not isinstance(identities, list) or not identities:
        return ["Every source page needs a patient sticker with MRN, name and birth date."]
    issues = []
    for key, label in (("mrn", "MRN"), ("firstName", "first name"), ("lastName", "last name"), ("dob", "birth date")):
        valid = all(isinstance(identity, dict) and isinstance(identity.get(key), str) and identity[key].strip() for identity in identities)
        observed = {identity[key] if key == "mrn" else identity[key].casefold() for identity in identities if isinstance(identity, dict) and isinstance(identity.get(key), str) and identity[key].strip()}
        if not valid or len(observed) != 1:
            issues.append(f"Source patient {label} is missing or conflicting. Check every sticker.")
    if any(isinstance(identity, dict) and identity.get("dob") and clinic._iso(identity["dob"]) != identity["dob"] for identity in identities):
        issues.append("Source patient birth date is invalid. Check every sticker.")
    if any(not isinstance(identity, dict) or type(identity.get("page")) is not int or not 1 <= identity["page"] <= MAX_PAGES for identity in identities):
        issues.append("Source patient identity page metadata is invalid.")
    if any(not isinstance(identity, dict) or not isinstance(identity.get("recordId"), str) for identity in identities):
        issues.append("Source patient study ID metadata is invalid.")
    ids = {identity["recordId"] for identity in identities if isinstance(identity, dict) and isinstance(identity.get("recordId"), str) and identity["recordId"]}
    if len(ids) > 1:
        issues.append("Printed source study IDs conflict. Export row IDs cannot resolve a source identity conflict.")
    return issues


def _instrument_issues(context):
    starts = context.get("instrumentStarts")
    if not isinstance(starts, list) or not starts:
        return ["No complete supported PACE source instrument was identified."]
    names = [start.get("instrument") for start in starts if isinstance(start, dict)]
    if (len(names) != len(starts) or any(not isinstance(name, str) or name not in {item['name'] for item in pace._catalog()['instruments']} for name in names)
            or any(type(start.get("page")) is not int or not 1 <= start["page"] <= MAX_PAGES for start in starts)):
        return ["PACE source instrument metadata is invalid."]
    return ["Repeated instrument assessments cannot share one patient row. Keep each assessment separate."] if len(names) != len(set(names)) else []


def source_issues(record, values=None):
    issues = identity_issues(record)
    context = record.get("sourceContext")
    if not isinstance(context, dict) or context.get("profile") != PROFILE:
        return issues or ["PACE automatic source metadata is missing or invalid. Reprocess the PDFs."]
    blocking = context.get("blockingIssues", [])
    if not isinstance(blocking, list) or any(not isinstance(issue, str) for issue in blocking):
        issues.append("PACE automatic source metadata is invalid.")
    else:
        issues.extend(blocking)
    issues.extend(_instrument_issues(context))
    active = record.get("applicableFields")
    if (not isinstance(active, list) or not {"record_id", *IDENTITY_FIELDS} <= set(name for name in active if isinstance(name, str))
            or any(not isinstance(name, str) or name not in _fields() for name in active)):
        issues.append("PACE source field applicability is missing or invalid. Reprocess the PDFs.")
    layouts = context.get("pageLayouts")
    identities = context.get("identities", [])
    if not isinstance(identities, list):
        identities = []
    instruments, source_ids = context.get("instruments"), context.get("recordIds")
    if (not isinstance(instruments, list) or not instruments or any(not isinstance(instrument, str) or instrument not in {item["name"] for item in pace._catalog()["instruments"]} for instrument in instruments)
            or not isinstance(source_ids, list) or any(not isinstance(source_id, str) for source_id in source_ids)
            or set(source_ids) != {identity["recordId"] for identity in identities if isinstance(identity, dict) and isinstance(identity.get("recordId"), str) and identity["recordId"]}):
        issues.append("PACE source instrument or study ID metadata is invalid.")
    if (not isinstance(layouts, list) or not layouts or any(not isinstance(page, dict) or type(page.get("page")) is not int for page in layouts)
            or {page.get("page") for page in layouts if isinstance(page, dict)} != {identity.get("page") for identity in identities if isinstance(identity, dict)}):
        issues.append("Every source page needs a recognized instrument layout and patient identity.")
    if record.get("paceIdentityConfirmed") is not True:
        issues.append("Check every patient sticker and explicitly confirm the proposed source group before approval.")
    if not record.get("bundleRecordId") or not record.get("bundleSources"):
        issues.append("Confirm the patient group to assign its separate export row ID before approval.")
    if values is not None and record.get("bundleRecordId") and values.get("record_id") != record["bundleRecordId"]:
        issues.append("Keep this patient's confirmed export row ID. MRN and printed study IDs are separate.")
    return list(dict.fromkeys(issues))


def bundle_issues(record, record_id, manifest):
    issues = identity_issues(record)
    context = record.get("sourceContext")
    if not isinstance(context, dict) or context.get("profile") != PROFILE:
        return issues or ["PACE automatic source metadata is invalid."]
    issues.extend(context.get("blockingIssues", []))
    issues.extend(_instrument_issues(context))
    if not manifest:
        issues.append("The patient group has no original-source manifest.")
    for source in manifest:
        identities = [identity for identity in context.get("identities", []) if source["firstPage"] <= identity.get("page", 0) <= source["lastPage"]]
        issues.extend(identity_issues({"sourceContext": {**context, "identities": identities}}))
        starts = [start for start in context.get("instrumentStarts", []) if start.get("page") == source["firstPage"]]
        if len(starts) != 1:
            issues.append("Every original PDF must start with one recognized instrument. Check its source pages.")
        expected = set(range(source["firstPage"], source["lastPage"] + 1))
        recognized = {page.get("page") for page in context.get("pageLayouts", []) if isinstance(page, dict)}
        identified = {identity.get("page") for identity in identities}
        if not expected <= recognized or not expected <= identified:
            issues.append("Every original source page needs a recognized instrument layout and patient identity.")
        if any(identity.get("inheritedFromPage", identity["page"]) not in expected for identity in identities):
            issues.append("An original PDF cannot inherit patient identity from another source PDF.")
    return list(dict.fromkeys(issues))


def _region(raw):
    if not isinstance(raw, dict) or set(raw) != {"x", "y", "width", "height"}:
        raise ValueError("A layout answer area needs normalized x, y, width and height.")
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1 for value in raw.values()):
        raise ValueError("Layout coordinates must be finite normalized numbers.")
    if raw["width"] <= 0 or raw["height"] <= 0 or raw["x"] + raw["width"] > 1.000001 or raw["y"] + raw["height"] > 1.000001:
        raise ValueError("The layout answer area must fit inside its page.")
    return copy.deepcopy(raw)


def parse_loadout(raw):
    if not isinstance(raw, dict) or set(raw) != {"format", "name", "rules"} or raw.get("format") != LOADOUT_FORMAT:
        raise ValueError("Choose a QwikCap PACE form-layout file containing rules only.")
    if not isinstance(raw["name"], str) or not 1 <= len(raw["name"].strip()) <= 100 or any(ord(char) < 32 for char in raw["name"]):
        raise ValueError("Name the PACE form layout using at most 100 printable characters.")
    if not isinstance(raw["rules"], list) or len(raw["rules"]) > MAX_FIELDS:
        raise ValueError("A PACE layout supports at most 600 answer-area rules.")
    rules, seen = [], set()
    for rule in raw["rules"]:
        if not isinstance(rule, dict) or set(rule) != {"field", "instrument", "layout", "anchors", "anchorRegions", "revision", "pageOffset", "region"}:
            raise ValueError("PACE layouts contain only a field, recognized layout anchors and an answer area.")
        name, instrument, layout = rule["field"], rule["instrument"], rule["layout"]
        if not all(isinstance(value, str) for value in (name, instrument, layout)) or name not in _fields() or name in {"record_id", *IDENTITY_FIELDS} or instrument not in {item["name"] for item in pace._catalog()["instruments"]}:
            raise ValueError("A layout must use a PACE codebook field and supported instrument.")
        if name not in IDENTITY_FIELDS and _fields()[name]["instrument"] != instrument:
            raise ValueError("The PACE field does not belong to this source instrument.")
        anchors = rule["anchors"]
        allowed = _anchors(layout, instrument)
        if not isinstance(anchors, list) or len(anchors) < 2 or len(anchors) > MAX_FIELDS or any(not isinstance(anchor, str) or anchor not in allowed for anchor in anchors) or len(set(anchors)) != len(anchors):
            raise ValueError("A form layout needs at least two recognized public document anchors. Patient text cannot be saved as an anchor.")
        boxes = rule["anchorRegions"]
        if not isinstance(boxes, dict) or set(boxes) != set(anchors):
            raise ValueError("Every public layout anchor needs its source position.")
        for box in boxes.values():
            _region(box)
        if not isinstance(rule["revision"], str) or not re.fullmatch(r"(?:[0-9]{1,2}/[0-9]{4}|[0-9]{4}-[0-9]{1,2}|[A-Za-z0-9][A-Za-z0-9_.-]{0,19})?", rule["revision"]):
            raise ValueError("The form revision must be a bounded public revision token.")
        if type(rule["pageOffset"]) is not int or not 0 <= rule["pageOffset"] < MAX_PAGES:
            raise ValueError("The source-relative page number is invalid.")
        item = {**copy.deepcopy(rule), "anchors": sorted(anchors), "region": _region(rule["region"])}
        key = json.dumps({key: value for key, value in item.items() if key != "region"}, sort_keys=True)
        if key in seen:
            raise ValueError("A PACE layout has duplicate rules for one source field.")
        seen.add(key)
        rules.append(item)
    return {"format": LOADOUT_FORMAT, "name": raw["name"].strip(), "rules": rules}


def make_rule(record, field_name, region):
    if not isinstance(field_name, str) or field_name not in _fields():
        raise ValueError("Choose a canonical PACE field for this answer area.")
    if not isinstance(region, dict) or set(region) != {"page", "x", "y", "width", "height"} or type(region["page"]) is not int:
        raise ValueError("Select one source page and draw an answer area.")
    layouts = [item for item in record.get("sourceContext", {}).get("pageLayouts", []) if item.get("page") == region["page"]]
    if len(layouts) != 1:
        raise ValueError("This source page has no uniquely recognized PACE instrument layout.")
    page = layouts[0]
    anchors = page["anchors"]
    if field_name in IDENTITY_FIELDS:
        raise ValueError("Patient stickers move. Verify the dynamically detected identity instead of saving a fixed identity box.")
    rule = {"field": field_name, "instrument": page["instrument"], "layout": page["layout"], "anchors": anchors,
            "anchorRegions": page["anchorRegions"], "revision": page["revision"],
            "pageOffset": page["pageOffset"], "region": {key: region[key] for key in ("x", "y", "width", "height")}}
    return parse_loadout({"format": LOADOUT_FORMAT, "name": "PACE layouts", "rules": [rule]})["rules"][0]


def apply_rules(record, rules):
    parsed = parse_loadout({"format": LOADOUT_FORMAT, "name": "PACE layouts", "rules": rules})
    from pipeline import _map_fields
    applied, matching = [], {}
    for rule in parsed["rules"]:
        layouts = [page for page in record.get("sourceContext", {}).get("pageLayouts", [])
                   if page.get("instrument") == rule["instrument"] and page.get("layout") == rule["layout"]
                   and page.get("pageOffset") == rule["pageOffset"] and set(rule["anchors"]) == set(page.get("anchors", []))
                   and page.get("revision") == rule["revision"]
                   and all(anchor in page.get("anchorRegions", {}) and all(abs(page["anchorRegions"][anchor][key] - box[key]) <= .015 for key in ("x", "y", "width", "height")) for anchor, box in rule["anchorRegions"].items())]
        if not layouts:
            continue
        if len(layouts) != 1:
            record.setdefault("issues", []).append(f"{rule['field']}: More than one source page matches the saved layout; no correction was applied.")
            continue
        matching.setdefault(rule["field"], []).append((rule, layouts[0]))
    for name, matches in matching.items():
        if len(matches) != 1:
            record.setdefault("issues", []).append(f"{name}: More than one saved layout rule matches this source; no correction was applied.")
            continue
        rule, layout = matches[0]
        page_number = layout["page"]
        pages = [page for page in record.get("pacePages", []) if page.get("page") == page_number]
        if not pages:
            record.setdefault("issues", []).append(f"{rule['field']}: Source text is unavailable for this answer area. Reprocess the PDF.")
            continue
        field = next(field for field in profile_schema() if field["name"] == rule["field"])
        field.pop("profile", None)
        field["region"] = {"page": page_number, **rule["region"]}
        values, evidence, problems = _map_fields([field], pages)
        record["values"][name] = values[name]
        context = record.get("sourceContext", {})
        context["unansweredFields"] = [field for field in context.get("unansweredFields", []) if field != name]
        record.setdefault("evidence", {}).pop(name, None)
        record["evidence"].update(evidence)
        if name in record["evidence"]:
            record["evidence"][name]["mapping"] = "pace-layout-answer-area"
        record["applicableFields"] = sorted(set(record.get("applicableFields", [])) | {name})
        record.setdefault("issues", []).extend(problems)
        record["confirmed"] = [item for item in record.get("confirmed", []) if item != name]
        record["status"] = "review"
        record["reviewedBy"] = ""
        applied.append(name)
    return sorted(set(applied))
