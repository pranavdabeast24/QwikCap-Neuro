"""Opt-in, literal-label staging profile for five synthetic neurology forms.

This is a document staging schema, not an unknown REDCap project's contract.
No patient, filename, expected answer, or source hash is an extraction lookup.
All clinical suggestions come from visible source text and page geometry.
"""
from __future__ import annotations

from datetime import datetime
import re
import unicodedata

PROFILE = "neurology-training-v1"
FAMILIES = {"101": "intake", "210": "hit6", "215": "midas", "330": "nihss", "410": "seizure"}
NIHSS_ITEMS = {
    "1a": ("Level of Consciousness", 3), "1b": ("LOC Questions", 2),
    "1c": ("LOC Commands", 2), "2": ("Best Gaze", 2),
    "3": ("Visual Fields", 3), "4": ("Facial Palsy", 3),
    "5a": ("Motor Arm — Left", 4), "5b": ("Motor Arm — Right", 4),
    "6a": ("Motor Leg — Left", 4), "6b": ("Motor Leg — Right", 4),
    "7": ("Limb Ataxia", 2), "8": ("Sensory", 2),
    "9": ("Best Language", 3), "10": ("Dysarthria", 2),
    "11": ("Extinction & Inattention", 2),
}
COMMON = {"document_id", "patient_mrn", "patient_name", "patient_dob", "form_date", "instrument_family"}
MARK = re.compile(r"^(?:[✓✔✗✘☑☒×]|[Xx])$")


def _field(name, label, kind="text", **kwargs):
    return {"name": name, "label": label, "type": kind, "required": True, **kwargs}


def profile_schema():
    fields = [
        _field("document_id", "Source document ID", profile=PROFILE),
        _field("patient_mrn", "Patient MRN"), _field("patient_name", "Patient name"),
        _field("patient_dob", "Date of birth", "date"), _field("form_date", "Header form date", "date"),
        _field("instrument_family", "Instrument family", "choice", choices={v: v.upper() for v in FAMILIES.values()}),
        _field("intake_chief_complaint", "Chief complaint"),
        _field("intake_allergies", "Allergies and reactions"),
        _field("intake_medications", "Current medications, dose and frequency"),
    ]
    fields += [_field(f"hit6_q{i}", f"HIT-6 question {i} points", "integer", min=6, max=13) for i in range(1, 7)]
    fields += [_field("hit6_total", "HIT-6 source total", "integer", min=36, max=78)]
    fields += [_field(f"midas_q{i}", f"MIDAS question {i} days", "integer", min=0, max=92) for i in range(1, 6)]
    fields += [_field("midas_total", "MIDAS source total", "integer", min=0, max=460),
               _field("midas_headache_days", "MIDAS headache days", "integer", min=0, max=92),
               _field("midas_pain", "MIDAS average pain", "integer", min=0, max=10),
               _field("nihss_exam_datetime", "NIHSS source exam date and time")]
    for code, (label, maximum) in NIHSS_ITEMS.items():
        # UN is an explicit source option for the motor/ataxia/dysarthria items.
        choices = {str(n): str(n) for n in range(maximum + 1)}
        if code in {"5a", "5b", "6a", "6b", "7", "10"}:
            choices["UN"] = "Untestable / source UN"
        fields.append(_field(f"nihss_{code}", f"NIHSS {code}: {label}", "choice", choices=choices))
    fields += [_field("nihss_total", "NIHSS source total", "integer", min=0, max=42),
               _field("seizure_last_3_months", "Seizures in the last 3 months", "integer", min=0),
               _field("seizure_most_recent", "Most recent seizure date", "date"),
               _field("seizure_frequency", "Typical seizure frequency"),
               _field("seizure_medications", "Anti-seizure medications, dose, frequency and side effects")]
    return fields


def is_profile(schema):
    return bool(isinstance(schema, list) and schema and isinstance(schema[0], dict) and schema[0].get("profile") == PROFILE)


def applicable_fields(schema, values):
    names = {f["name"] for f in schema}
    if not is_profile(schema):
        return names
    family = values.get("instrument_family", "")
    return names & (COMMON | {name for name in names if family in FAMILIES.values() and name.startswith(family + "_")})


def normalized(value):
    return " ".join(unicodedata.normalize("NFKC", str(value)).split())


def _iso(value):
    value = normalized(value)
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%Y %H:%M", "%Y-%m-%d %H:%M"):
        try:
            parsed = datetime.strptime(value, fmt)
            return parsed.strftime("%Y-%m-%d %H:%M" if "%H" in fmt else "%Y-%m-%d")
        except ValueError:
            pass
    return ""


def _box(words):
    left, top = min(w["x"] for w in words), min(w["y"] for w in words)
    right, bottom = max(w["x"] + w["width"] for w in words), max(w["y"] + w["height"] for w in words)
    return {"x": left, "y": top, "width": right - left, "height": bottom - top}


def extract(pages, datahash):
    """Return values/evidence/issues; pages are bounded pipeline text layers."""
    values = {f["name"]: "" for f in profile_schema()}
    evidence, issues, candidates = {}, [], {}

    def put(name, raw, page, lines, value=None, mapping="profile-label"):
        value = normalized(raw) if value is None else value
        if not value:
            return
        words = [w for line in lines for w in line.get("words", [])]
        if not words:
            return
        candidates.setdefault(name, []).append((value, {"text": raw, "page": page["page"], "region": _box(words), "method": page["method"], "mapping": mapping}))

    for page in pages:
        lines = page.get("lines", [])
        for line in lines:
            text = normalized(line["text"])
            for match in re.finditer(r"\bForm\s+NEU[- ]?(101|210|215|330|410)\b", text, re.I):
                put("instrument_family", match.group(), page, [line], FAMILIES[match.group(1)])
            if text.startswith("Patient Name "):
                # A repeated page header is independent corroborating evidence.
                header = text[len("Patient Name "):]
                labels = list(re.finditer(r"\b(DOB|MRN|Date)\b\s*:?\s*", header))
                if labels:
                    put("patient_name", header[:labels[0].start()].strip(), page, [line])
                for i, label in enumerate(labels):
                    raw = header[label.end():labels[i + 1].start() if i + 1 < len(labels) else len(header)].strip()
                    name = {"DOB": "patient_dob", "MRN": "patient_mrn", "Date": "form_date"}[label.group(1)]
                    value = _iso(raw) if name in {"patient_dob", "form_date"} else normalized(raw)
                    if name == "patient_dob" and raw and (not value or len(value) != 10):
                        issues.append("patient_dob: Invalid source date in a patient header; resolve identity against the source.")
                    put(name, raw, page, [line], value)

        # Clinical parsing is gated on an explicit known form code in this layer.
        codes = {m.group(1) for line in lines for m in re.finditer(r"\bForm\s+NEU[- ]?(101|210|215|330|410)\b", normalized(line["text"]), re.I)}
        if len(codes) != 1:
            continue
        code = next(iter(codes))
        if code == "210":
            point_line = next((l for l in lines if normalized(l["text"]).startswith("Points per response ")), None)
            anchors = []
            if point_line:
                anchors = [(w["x"] + w["width"] / 2, normalized(w["text"])) for w in point_line["words"] if normalized(w["text"]) in {"6", "8", "10", "11", "13"}]
            rows = [(int(m.group(1)), l) for l in lines if (m := re.match(r"^([1-6])(?:\s|$)", normalized(l["text"]))) and l["x"] < .15 and l["y"] > .2]
            marks = [(w, l) for l in lines for w in l["words"] if MARK.fullmatch(normalized(w["text"]))]
            for number, row in rows:
                # Wrapped questions use the same row center as the leading digit.
                rowmarks = [(w, l) for w, l in marks if abs(w["y"] + w["height"] / 2 - row["y"] - row["height"] / 2) < .018 and w["x"] > .6]
                if len(rowmarks) == 1 and len(anchors) == 5:
                    word, markline = rowmarks[0]
                    anchor, points = min(anchors, key=lambda a: abs(a[0] - word["x"] - word["width"] / 2))
                    if abs(anchor - word["x"] - word["width"] / 2) < .035:
                        put(f"hit6_q{number}", normalized(markline["text"]), page, [{"words": [word]}], points, "profile-checkbox-column")
            for line in lines:
                if m := re.search(r"TOTAL SCORE\s*\(36[–-]78\)\s*:\s*(\d+)\s*$", normalized(line["text"])):
                    put("hit6_total", m.group(1), page, [line])
        elif code == "215":
            for line in lines:
                text = normalized(line["text"])
                if m := re.match(r"^MIDAS TOTAL\s*\(Questions 1[–-]5\)\s+(\d+)\s+days$", text):
                    put("midas_total", m.group(1), page, [line])
            for label in ("1", "2", "3", "4", "5", "A", "B"):
                rows = [l for l in lines if re.match(r"^" + label + r"(?:\s|$)", normalized(l["text"])) and l["x"] < .15 and l["y"] > .2]
                for row in rows:
                    answers = []
                    for line in lines:
                        if abs(line["y"] + line["height"] / 2 - row["y"] - row["height"] / 2) > .018:
                            continue
                        words = [w for w in line["words"] if w["x"] > .8]
                        answer = normalized(" ".join(w["text"] for w in words))
                        if m := re.fullmatch(r"(\d+)\s*(?:days|/\s*10)", answer):
                            answers.append((m.group(1), {"words": words}))
                    if len(answers) == 1:
                        name = "midas_headache_days" if label == "A" else "midas_pain" if label == "B" else f"midas_q{label}"
                        put(name, answers[0][0], page, [answers[0][1]], mapping="profile-answer-column")
        elif code == "330":
            for line in lines:
                text = normalized(line["text"])
                if m := re.match(r"NIHSS exam time\s+(.+?)\s+CT/CTA time\b", text):
                    put("nihss_exam_datetime", m.group(1), page, [line], _iso(m.group(1)))
                if m := re.match(r"TOTAL NIHSS\s*\(0[–-]42\)\s*:\s*(\d+)\s*$", text):
                    put("nihss_total", m.group(1), page, [line])
            for item, (label, _) in NIHSS_ITEMS.items():
                headers = [l for l in lines if normalized(l["text"]).startswith(item + " " + normalized(label)) and l["x"] < .2]
                for header in headers:
                    # The printed score column is centered on the category row.
                    answers = [l for l in lines if l["x"] > .82 and abs(l["y"] + l["height"] / 2 - header["y"] - header["height"] / 2) < .014 and re.fullmatch(r"[0-4]|UN", normalized(l["text"]))]
                    if len(answers) == 1:
                        put(f"nihss_{item}", normalized(answers[0]["text"]), page, answers, mapping="profile-score-column")
        elif code == "410":
            for line in lines:
                text = normalized(line["text"])
                if m := re.search(r"Most recent seizure\s+(.+?)\s+# seizures last 3 months\s+(\d+)\s*$", text):
                    put("seizure_most_recent", m.group(1), page, [line], _iso(m.group(1)))
                    put("seizure_last_3_months", m.group(2), page, [line])
                if text.startswith("Typical frequency:"):
                    matches = re.findall(r"(?:[✓✔✗✘☑☒×]|\b[Xx])\s*(Daily|Weekly|Monthly|Every few months|Yearly or less)\b", text)
                    if len(matches) == 1:
                        put("seizure_frequency", text, page, [line], matches[0], "profile-checked-label")
            _section(lines, page, "CURRENT ANTI-SEIZURE MEDICATIONS", "Rescue medication", "seizure_medications", put, skip=("Medication Dose Frequency Side effects",))
        elif code == "101":
            _section(lines, page, "Chief complaint — describe in your own words:", "Current symptoms", "intake_chief_complaint", put)
            _section(lines, page, "CURRENT MEDICATIONS (INCLUDE OTC & SUPPLEMENTS)", "ALLERGIES", "intake_medications", put, skip=("# Medication Dose Frequency",), numbered=True)
            for line in lines:
                text = normalized(line["text"])
                if "Allergies & reaction" in text:
                    before, raw = text.split("Allergies & reaction", 1)
                    nkda = bool(re.search(r"(?:[✓✔✗✘☑☒×]|\b[Xx])\s*No known drug allergies", before))
                    if raw.strip() and nkda:
                        issues.append("intake_allergies: Source marks NKDA and also lists an allergy; resolve against the source.")
                    elif raw.strip() or nkda:
                        put("intake_allergies", raw.strip() or "No known drug allergies (NKDA)", page, [line])

    for name, choices in candidates.items():
        # Native PDF text is authoritative when available for this field. Local
        # OCR is only a fallback for unresolved fields, never a duplicate vote.
        native = [c for c in choices if c[1]["method"] in {"pdf-text", "plain-text"}]
        choices = native or choices
        distinct = {normalized(v).casefold() if name == "patient_name" else v for v, _ in choices}
        if len(distinct) == 1:
            values[name], evidence[name] = choices[0]
            evidence[name]["occurrences"] = [dict(e) for _, e in choices]
        else:
            issues.append(f"{name}: Repeated source values conflict; no suggestion selected.")
    values["document_id"] = "DOC" + datahash[:24]
    evidence["document_id"] = {"text": "DOC + first 24 characters of source SHA-256", "method": "source-sha256", "mapping": "derived-document-id"}
    family = values["instrument_family"]
    if not family:
        issues.append("instrument_family: No unique supported Form NEU code found; use generic categories or review the form manually.")
    if values["form_date"] and values["nihss_exam_datetime"] and values["form_date"] != values["nihss_exam_datetime"][:10]:
        issues.append("form_date / nihss_exam_datetime: Header date differs from the NIHSS exam date. Both source dates are preserved; confirm each against the source.")
    for name in applicable_fields(profile_schema(), values):
        if not values[name]:
            issues.append(f"{name}: Applicable source value was missing or ambiguous; verify manually.")
    return values, evidence, issues


def _section(lines, page, start, end, name, put, skip=(), numbered=False):
    starts = [i for i, l in enumerate(lines) if normalized(l["text"]) == start]
    for index in starts:
        selected, parts = [], []
        for line in lines[index + 1:]:
            text = normalized(line["text"])
            if text.startswith(end):
                break
            if text in skip or not text:
                continue
            if numbered:
                text = re.sub(r"^\d+\s*", "", text)
            if text:
                parts.append(text)
                selected.append(line)
        if parts:
            text = (" " if name == "intake_chief_complaint" else "\n").join(parts)
            put(name, text, page, selected, text, "profile-section")


def validate_profile_values(schema, values):
    if not is_profile(schema):
        return {}
    errors = {}
    applicable = applicable_fields(schema, values)
    for name, value in values.items():
        if name not in applicable and value:
            errors[name] = "This field is inactive for the selected instrument; leave it blank."
    if values.get("patient_mrn") and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", values["patient_mrn"]):
        errors["patient_mrn"] = "Use the literal source MRN with letters, numbers, dots, underscores or hyphens."
    if values.get("document_id") and not re.fullmatch(r"DOC[0-9a-f]{24}", values["document_id"]):
        errors["document_id"] = "Keep the document ID derived from this source's SHA-256."
    if values.get("nihss_exam_datetime"):
        try:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", values["nihss_exam_datetime"]):
                raise ValueError("format")
            datetime.strptime(values["nihss_exam_datetime"], "%Y-%m-%d %H:%M")
        except ValueError:
            errors["nihss_exam_datetime"] = "Use a real YYYY-MM-DD HH:MM from the source exam time."
    for prefix, count, total in (("hit6_q", 6, "hit6_total"), ("midas_q", 5, "midas_total")):
        components = [values.get(f"{prefix}{i}", "") for i in range(1, count + 1)]
        if values.get(total, "").isdigit() and all(v.isdigit() for v in components) and sum(map(int, components)) != int(values[total]):
            errors[total] = "The source total differs from the entered item sum; resolve against the source."
    for i in range(1, 7):
        if values.get(f"hit6_q{i}") and values[f"hit6_q{i}"] not in {"6", "8", "10", "11", "13"}:
            errors[f"hit6_q{i}"] = "Use a printed HIT-6 response point value (6, 8, 10, 11 or 13)."
    if values.get("seizure_frequency") and values["seizure_frequency"] not in {"Daily", "Weekly", "Monthly", "Every few months", "Yearly or less"}:
        errors["seizure_frequency"] = "Use the literal checked frequency label from the source."
    subscores = [values.get("nihss_" + item, "") for item in NIHSS_ITEMS]
    if all(v.isdigit() for v in subscores) and values.get("nihss_total", "").isdigit() and sum(map(int, subscores)) != int(values["nihss_total"]):
        errors["nihss_total"] = "The source NIHSS total differs from the entered item sum; resolve against the source."
    return errors


def patient_groups(records, replacement=None):
    groups = {}
    for record in records:
        values = replacement[1] if replacement and record["id"] == replacement[0] else record["values"]
        mrn = normalized(values.get("patient_mrn", "")).casefold()
        if not mrn:
            continue
        group = groups.setdefault(mrn, {"mrn": values["patient_mrn"], "recordIds": [], "names": set(), "birthDates": set()})
        group["recordIds"].append(record["id"])
        if values.get("patient_name"):
            group["names"].add(normalized(values["patient_name"]).casefold())
        if values.get("patient_dob"):
            group["birthDates"].add(values["patient_dob"])
    result = []
    for group in groups.values():
        group["conflict"] = len(group["names"]) > 1 or len(group["birthDates"]) > 1
        group["names"], group["birthDates"] = sorted(group["names"]), sorted(group["birthDates"])
        group["identityConfirmed"] = all(COMMON - {"document_id", "form_date", "instrument_family"} <= set(r.get("confirmed", [])) for r in records if r["id"] in group["recordIds"])
        result.append(group)
    return result
