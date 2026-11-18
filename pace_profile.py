"""Opt-in local extraction of printed PACE rows and visible native controls."""
from __future__ import annotations

import copy
from datetime import datetime
from functools import lru_cache
from pathlib import Path
import re
import unicodedata

from field_catalog import load_catalog, extraction_rule

PROFILE = "pace-printed-v1"
_MARKS = {"●", "✓", "✔", "✗", "✘", "☑", "☒", "×", "X", "x"}
_PRINTED_OPTION_LABELS = {
    "scan_findings___3": "venous distension",
    "prov_associated_symptoms___nausea": "Nausea / vomiting",
    "prov_associated_symptoms___1": "Numbness / tingling in limbs",
    "prov_associated_symptoms___5": "Clouding of consciousness",
    **{f"baseline_pain_localization{suffix}___{code}": label
       for suffix in ("", "_2", "_3", "_4")
       for code, label in (("4", "Periorbital/retro-orbital (Around/Behind the eyes)"),
                           ("5", "Vertex (Top of Head)"))},
}


def normalized(value):
    return " ".join(unicodedata.normalize("NFKC", str(value)).split())


def _key(value):
    return re.sub(r"[^a-z0-9]", "", normalized(value).casefold())


@lru_cache(maxsize=1)
def _catalog():
    return load_catalog(Path(__file__).resolve().parent / "study_profiles" / "pace.json")


def profile_schema():
    fields = [extraction_rule(field) for field in _catalog()["fields"]]
    for field, source in zip(fields, _catalog()["fields"]):
        field["required"] = source["required"] or field["name"] == "record_id"
    fields[0]["profile"] = PROFILE
    return fields


def is_profile(schema):
    return bool(isinstance(schema, list) and schema and isinstance(schema[0], dict)
                and schema[0].get("name") == "record_id" and schema[0].get("profile") == PROFILE)


def _iso(value):
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    return ""


def _center(box):
    return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2


def _box(words):
    left, top = min(w["x"] for w in words), min(w["y"] for w in words)
    right = max(w["x"] + w["width"] for w in words)
    bottom = max(w["y"] + w["height"] for w in words)
    return {"x": left, "y": top, "width": right - left, "height": bottom - top}


def _text(words):
    return normalized(" ".join(w["text"] for w in words))


def _label_matches(printed, catalog):
    printed, catalog = _key(printed), _key(catalog)
    return bool(catalog and (printed == catalog or printed.startswith(catalog)))


def _option_matches(printed, catalog, code=""):
    printed = normalized(printed)
    if code:
        printed = re.sub(r"^" + re.escape(code) + r"[.)]\s*", "", printed)
        catalog = re.sub(r"^" + re.escape(code) + r"[.)]\s*", "", catalog)
    clipped = catalog.endswith("(source label clipped)")
    catalog = re.sub(r"\s*\(source label clipped\)\s*$", "", catalog)
    if "label unreadable in supplied codebook" in catalog:
        catalog = catalog.split(" (", 1)[0]
    a, b = _key(printed), _key(catalog)
    if a and b and (a == b or len(b) >= 15 and a.startswith(b)):
        return True
    if clipped:
        terms = lambda value: re.findall(r"[a-z0-9]+", normalized(value).casefold().replace("(s)", "s"))
        actual, reference = terms(printed), terms(catalog)
        return bool(len(actual) == len(reference) and all(a.startswith(b) for a, b in zip(actual, reference)))
    return False


@lru_cache(maxsize=1)
def _sources():
    sources = {}
    section = {}
    for field in _catalog()["fields"]:
        instrument = field["instrument"]
        if instrument == "record_context" and field["name"] != "record_id":
            continue
        notes = field["notes"]
        if match := re.search(r"Section Header: (.*?)(?= Field note:| Branching | Completion | Expanded |$)", notes):
            section[instrument] = match.group(1)
        source = sources.setdefault((instrument, field["sourceField"]), {
            "name": field["sourceField"], "instrument": instrument,
            "label": field["label"].split(" - ", 1)[0] if "___" in field["name"] else field["label"],
            "fields": [], "section": section.get(instrument, ""), "branching": field["branching"],
        })
        source["fields"].append(field)
    for source in sources.values():
        source["checkbox"] = any("___" in field["name"] for field in source["fields"])
    return tuple(sources.values())


def _rows(page):
    rules = [r for r in page.get("rules", []) if r["width"] > r["height"] * 10]
    maximum = max((r["width"] for r in rules), default=0)
    left = min((r["x"] for r in rules if r["width"] >= maximum * .9), default=0)
    boundaries = sorted(r["y"] + r["height"] / 2 for r in rules
                        if maximum and abs(r["x"] - left) < .005 and r["width"] >= maximum * .3)
    unique = [0.0]
    for y in boundaries:
        if y - unique[-1] > .002:
            unique.append(y)
    unique.append(1.0)
    words = [w for line in page.get("lines", []) for w in line.get("words", [])]
    result = []
    for top, bottom in zip(unique, unique[1:]):
        rowwords = [w for w in words if top <= _center(w)[1] < bottom]
        controls = [c for c in page.get("controls", []) if top <= _center(c)[1] < bottom]
        if rowwords:
            result.append({"top": top, "bottom": bottom, "words": rowwords, "controls": controls})
    return result


def _control_label(control, controls, words):
    cx, cy = _center(control)
    right = min((c["x"] for c in controls if c["x"] > control["x"] + control["width"] and abs(_center(c)[1] - cy) < .01), default=1)
    bottom = min((_center(c)[1] - .005 for c in controls if abs(_center(c)[0] - cx) < .01 and _center(c)[1] > cy + .008), default=1)
    selected = [w for w in words if w["text"] not in _MARKS
                and w["x"] >= control["x"] + control["width"] - .002
                and _center(w)[0] < right and cy - .012 <= _center(w)[1] < bottom]
    return _text(selected), selected


def _selected(control, words):
    x, y = _center(control)
    return [w for w in words if normalized(w["text"]) in _MARKS
            and abs(_center(w)[0] - x) <= control["width"] * .7
            and abs(_center(w)[1] - y) <= control["height"] * .8]


def _section_key(value):
    value = normalized(value)
    if match := re.match(r"^([ABCD])\.?\s+(?:Baseline|Provocation)\b", value, re.I):
        return match.group(1).upper()
    return _key(value)


def _labels(source):
    labels = [source["label"]]
    if source["name"] == "hit6_date":
        labels.append("Date")
    if source["name"] in {"prov_1_yn", "prov_2_yn", "prov_3_yn"}:
        labels.append(source["label"].replace("Provocation #", "Provocation Headache #"))
    return labels


def _field_for_row(row, candidates, answer_left, section, history):
    labelwords = [w for w in row["words"] if w["x"] < answer_left]
    label = _text(labelwords)
    matches = []
    for source in candidates:
        tails = [_text(labelwords[index:]) for index in range(len(labelwords))]
        if any(_label_matches(tail, candidate) for candidate in _labels(source) for tail in tails):
            matches.append(source)
    if not matches:
        return None
    if row["controls"]:
        checkbox = any(c["kind"] == "square" for c in row["controls"])
        typed = [source for source in matches if source["checkbox"] == checkbox]
        matches = typed or matches
    longest = max(len(_key(s["label"])) for s in matches)
    matches = [s for s in matches if len(_key(s["label"])) == longest]
    if len(matches) > 1 and section:
        contextual = [s for s in matches if _section_key(s["section"]) == section]
        matches = contextual or matches
    if len(matches) > 1:
        kind = bool(any(c["kind"] == "square" for c in row["controls"]))
        typed = [s for s in matches if s["checkbox"] == kind]
        matches = typed or matches
    if len(matches) > 1:
        referenced = []
        for source in matches:
            reference = re.sub(r"\s+", "", source["branching"])
            names = re.findall(r"\[([a-z0-9_]+)(?:\([^]]*\))?\]", reference)
            latest = max((index for index, name in enumerate(history) if name in names), default=-1)
            referenced.append((latest, source))
        latest = max(index for index, _ in referenced)
        if latest >= 0:
            matches = [s for index, s in referenced if index == latest]
    return matches[0] if len(matches) == 1 else None


def _matrix_codes(source, row, previous_rows):
    choices = source["fields"][0].get("choices", {})
    controls = sorted((c for c in row["controls"] if c["kind"] == "circle"), key=lambda c: c["x"])
    if len(controls) != len(choices):
        return None
    centers = [_center(c)[0] for c in controls]
    for header in reversed(previous_rows):
        if header["controls"]:
            continue
        mapped = {}
        for index, center in enumerate(centers):
            left = (centers[index - 1] + center) / 2 if index else center - (centers[1] - center) / 2
            right = (centers[index + 1] + center) / 2 if index + 1 < len(centers) else center + (center - centers[index - 1]) / 2
            text = _text([w for w in header["words"] if left <= _center(w)[0] < right])
            matches = [code for code, label in choices.items() if _option_matches(text, label, code)]
            if len(matches) == 1:
                mapped[index] = matches[0]
        if len(mapped) == len(choices) and len(set(mapped.values())) == len(choices):
            return [(control, mapped[index]) for index, control in enumerate(controls)]
    return None


def extract(pages):
    catalog = _catalog()
    values = {field["name"]: "" for field in catalog["fields"]}
    evidence, issues, active, candidates = {}, [], {"record_id"}, {}
    radio_states, unmarked_evidence = {}, {}
    context = {"profile": PROFILE, "recordIds": [], "identities": [], "instruments": [],
               "instrumentStarts": [], "unansweredFields": [], "blockingIssues": []}
    instrument_keys = {_key(item["name"]): item["name"] for item in catalog["instruments"]}
    instrument_labels = {_key(item["label"]): item["name"] for item in catalog["instruments"]}
    current_instrument, section, history = None, "", []

    def footer_instruments(line):
        key = _key(line["text"])
        return {name for instrument, name in instrument_keys.items()
                if key == instrument or re.match(r"^Confidential\b", normalized(line["text"]), re.I) and key.endswith(instrument)}

    def put(name, raw, page, words, value=None, mapping="pace-printed-row"):
        active.add(name)
        value = normalized(raw) if value is None else value
        if not words:
            return
        item = {"text": normalized(raw), "page": page["page"], "region": _box(words),
                "method": page.get("method", "pdf-text"), "mapping": mapping}
        candidates.setdefault(name, []).append((value, item))

    for page in pages:
        lines = page.get("lines", [])
        text = "\n".join(normalized(line["text"]) for line in lines)
        found = set()
        header_instruments = set()
        for line in lines:
            key = _key(line["text"])
            found.update(footer_instruments(line))
            if key in instrument_labels:
                found.add(instrument_labels[key])
                header_instruments.add(instrument_labels[key])
        header_ids = re.findall(r"\bRecord ID:\s*([A-Za-z0-9][A-Za-z0-9_.-]{0,79})", text)
        new_demographics = any(re.search(r"\bPatient:\s*.+\bDOB:", normalized(line["text"])) for line in lines)
        if len(found) > 1 or not found and (current_instrument is None or header_ids or new_demographics):
            if "Source bundle for one study record" in text:
                continue
            context["blockingIssues"].append(f"Page {page['page']}: No unique supported PACE instrument was identified.")
            continue
        instrument = next(iter(found)) if found else current_instrument
        if len(header_instruments) == 1 and header_ids:
            context["instrumentStarts"].append({"instrument": instrument, "page": page["page"]})
        if instrument != current_instrument or header_ids:
            section, history = "", []
        current_instrument = instrument
        if instrument not in context["instruments"]:
            context["instruments"].append(instrument)
        if len(set(header_ids)) > 1:
            context["blockingIssues"].append(f"Page {page['page']}: Printed record ID is missing or conflicting.")
        record_id = header_ids[0] if len(set(header_ids)) == 1 else ""
        if record_id:
            if record_id not in context["recordIds"]:
                context["recordIds"].append(record_id)
            line = next(line for line in lines if "Record ID:" in normalized(line["text"]))
            put("record_id", record_id, page, line["words"])
        identity = {"recordId": record_id, "firstName": "", "lastName": "", "dob": "", "mrn": "", "page": page["page"]}
        if match := re.search(r"Patient:\s*(.*?)\s+DOB:\s*(\d{2}/\d{2}/\d{4})\s*MRN:\s*([A-Za-z0-9_.-]+)", text):
            name, dob, mrn = match.groups()
            if "," in name:
                last, first = name.split(",", 1)
                identity.update(firstName=normalized(first), lastName=normalized(last), dob=_iso(dob), mrn=mrn)
            if not identity["dob"]:
                context["blockingIssues"].append(f"Page {page['page']}: Printed patient date of birth is invalid.")
        page_controls = page.get("controls", [])
        footer_only = bool(lines) and all(footer_instruments(line) for line in lines)
        if footer_only:
            continue
        if not page.get("rules") or not page_controls:
            context["blockingIssues"].append(f"Page {page['page']}: Native row/control geometry is unavailable; use masks or manual review.")
            continue
        answer_left = min(c["x"] for c in page_controls) - .003
        source_fields = [source for source in _sources() if source["instrument"] == instrument or source["name"] == "record_id"]
        previous_rows = []
        page_values = {}
        for row in _rows(page):
            rowtext = _text(row["words"])
            if re.match(r"^[ABCD]\.?(?:\s+)(?:Baseline|Provocation)", rowtext, re.I):
                section = _section_key(rowtext)
            row_answer_left = min((control["x"] for control in row["controls"]), default=answer_left + .003) - .003
            source = _field_for_row(row, source_fields, row_answer_left, section, history)
            if source is None:
                if row["controls"]:
                    context["blockingIssues"].append(f"Page {page['page']}: A visible control row at {row['top']:.3f} could not be matched to a PACE source field.")
                previous_rows.append(row)
                continue
            history.append(source["name"])
            if source["checkbox"]:
                controls = [c for c in row["controls"] if c["kind"] == "square"]
                mapped = {}
                for control in controls:
                    label, labelwords = _control_label(control, controls, row["words"])
                    matches = []
                    for field in source["fields"]:
                        option = _PRINTED_OPTION_LABELS.get(field["name"], field["label"].split(" - ", 1)[1])
                        if _option_matches(label, option, field["name"].split("___", 1)[1]):
                            matches.append(field["name"])
                    if len(matches) == 1:
                        mapped.setdefault(matches[0], []).append((control, labelwords))
                complete = len(mapped) == len(source["fields"]) and all(len(items) == 1 for items in mapped.values())
                if not complete:
                    active.update(field["name"] for field in source["fields"])
                    issues.append(f"{source['name']}: Checkbox options were incomplete or ambiguous; unresolved cells remain blank.")
                for name, items in mapped.items():
                    if len(items) == 1:
                        control, labelwords = items[0]
                        marks = _selected(control, row["words"])
                        if not marks and not complete:
                            continue
                        put(name, _text(marks + labelwords), page, [control] + marks + labelwords,
                            "1" if marks else "0", "pace-visible-checkbox")
            else:
                field = source["fields"][0]
                name = field["name"]
                active.add(name)
                if field["type"] == "choice":
                    controls = [c for c in row["controls"] if c["kind"] == "circle"]
                    options = []
                    for control in controls:
                        label, labelwords = _control_label(control, controls, row["words"])
                        matches = [code for code, expected in field["choices"].items() if _option_matches(label, expected, code)]
                        if len(matches) == 1:
                            options.append((control, matches[0]))
                    if len(options) != len(field["choices"]):
                        options = _matrix_codes(source, row, previous_rows) or []
                    marks = [(control, code, _selected(control, row["words"])) for control, code in options]
                    chosen = [(control, code, selected) for control, code, selected in marks if selected]
                    complete = (len(controls) == len(field["choices"]) == len(options)
                                and {code for _, code in options} == set(field["choices"]))
                    states = radio_states.setdefault(name, set())
                    if complete and not chosen and not any(normalized(word["text"]) in _MARKS for word in row["words"]):
                        states.add("unmarked")
                        unmarked_evidence.setdefault(name, []).append({
                            "text": rowtext, "page": page["page"], "region": _box(row["words"] + controls),
                            "method": page.get("method", "pdf-text"), "mapping": "pace-unmarked-radio"})
                    else:
                        states.add("marked" if complete and len(chosen) == 1 else "ambiguous")
                    if len(chosen) == 1 and len(options) == len(field["choices"]):
                        control, code, selected = chosen[0]
                        put(name, _text(selected), page, [control] + selected, code, "pace-visible-radio")
                        page_values[name] = code
                    elif len(chosen) > 1:
                        issues.append(f"{name}: More than one printed radio is selected; no value suggested.")
                    elif not options:
                        issues.append(f"{name}: Printed choice labels or matrix columns were not uniquely identified.")
                else:
                    labels = [w for w in row["words"] if w["x"] < answer_left]
                    anchors = [w["y"] for index, w in enumerate(labels)
                               if any(_label_matches(_text(labels[index:]), label) for label in _labels(source))]
                    top = min(anchors, default=row["top"])
                    words = [w for w in row["words"] if w["x"] >= answer_left
                             and w["y"] >= top - .004 and w["text"] not in _MARKS]
                    raw = _text(words)
                    value = _iso(raw) if field["type"] == "date" else raw
                    if field["type"] in {"integer", "number"}:
                        value = re.sub(r"\s*\(calculated\)\s*$", "", value)
                    if raw:
                        put(name, raw, page, words, value)
                        page_values[name] = value
            previous_rows.append(row)
        if instrument == "patient_records":
            identity.update(firstName=page_values.get("patient_first", ""), lastName=page_values.get("patient_last", ""),
                            dob=page_values.get("patient_dob", ""), mrn=page_values.get("mrn", ""))
        if any(identity[key] for key in ("firstName", "lastName", "dob", "mrn")):
            context["identities"].append(identity)

    for name, items in candidates.items():
        native = [item for item in items if item[1]["method"] == "pdf-text"]
        items = native or items
        distinct = {value for value, _ in items}
        if len(distinct) == 1:
            values[name] = items[0][0]
            evidence[name] = copy.deepcopy(items[0][1])
            evidence[name]["occurrences"] = [copy.deepcopy(item) for _, item in items]
        else:
            issues.append(f"{name}: Repeated source values conflict; no suggestion selected.")
            context["blockingIssues"].append(f"{name}: Repeated printed source values conflict.")
    if len(context["recordIds"]) != 1:
        context["blockingIssues"].append("Printed sources do not share exactly one record ID.")
    identities = context["identities"]
    for key in ("recordId", "firstName", "lastName", "dob", "mrn"):
        if len({normalized(identity[key]).casefold() for identity in identities if identity[key]}) > 1:
            context["blockingIssues"].append(f"Printed patient identity {key} conflicts across source pages.")
    for name, states in radio_states.items():
        if states == {"unmarked"} and not values[name]:
            context["unansweredFields"].append(name)
            evidence[name] = copy.deepcopy(unmarked_evidence[name][0])
            evidence[name]["occurrences"] = copy.deepcopy(unmarked_evidence[name])
    context["unansweredFields"].sort()
    context["blockingIssues"] = list(dict.fromkeys(context["blockingIssues"]))
    issues.extend(context["blockingIssues"])
    return {"values": values, "evidence": evidence, "issues": issues,
            "applicableFields": sorted(active), "sourceContext": context}
