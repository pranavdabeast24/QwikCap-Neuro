"""Literal clinic report assertions and native procedure-table measurements."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
import unicodedata


def _norm(value):
    return " ".join(unicodedata.normalize("NFKC", str(value)).replace("\ufffe", "-").split())


def _words(page):
    return [word for line in page.get("lines", []) for word in line.get("words", [])]


def _text(page):
    return "\n".join(_norm(line["text"]) for line in page.get("lines", []))


def _date(value):
    for pattern in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, pattern).date().isoformat()
        except ValueError:
            pass
    return ""


def _proof(page, pattern):
    matched = [word for line in page.get("lines", [])
               if re.search(pattern, _norm(line["text"]), re.I)
               for word in line.get("words", [])]
    return matched


@dataclass
class _Section:
    text: str
    spans: list

    def proof(self, start, end):
        return [word for left, right, words in self.spans if left < end and right > start for word in words]


def _section(page, title, end):
    lines, spans, parts = page.get("lines", []), [], []
    active = False
    length = 0
    for line in lines:
        value = _norm(line["text"])
        if re.match(r"^" + end + r"\s*:", value, re.I):
            break
        if re.match(r"^" + title + r"\s*:", value, re.I):
            active = True
            value = re.sub(r"^" + title + r"\s*:\s*", "", value, flags=re.I)
        if active and value:
            parts.append(value)
            spans.append((length, length + len(value), line.get("words", [])))
            length += len(value) + 1
    return _Section(" ".join(parts), spans)


def _uncertain(text, start, end):
    before = list(re.finditer(r"[.!?]\s+", text[:start]))
    left = before[-1].end() if before else max(0, start - 100)
    following = re.search(r"[.!?](?:\s|$)", text[end:])
    right = end + following.end() if following else min(len(text), end + 100)
    return bool(re.search(r"\b(?:possible|suspected|equivocal|(?:may|might|could)\s+(?:be|represent)|cannot(?:\s+be)?\s+excluded?|does not exclude|do not exclude|not excluded|question of)\b",
                          text[left:right], re.I))


def _unhandled_negation(text, start, end):
    before = list(re.finditer(r"[.!?]\s+", text[:start]))
    left = before[-1].end() if before else max(0, start - 100)
    following = re.search(r"[.!?](?:\s|$)", text[end:])
    right = end + following.end() if following else min(len(text), end + 80)
    return bool(re.search(r"\b(?:no|without|absence of|negative for|not)\b", text[left:start], re.I)
                or re.search(r"\b(?:not\s+(?:identified|seen|present|demonstrated)|absent)\b", text[end:right], re.I))


def _unresolved_descriptor(text, match):
    left = max(text.rfind(",", 0, match.start()), text.rfind(";", 0, match.start())) + 1
    stops = [position for separator in (",", ";")
             if (position := text.find(separator, match.end())) != -1]
    right = min(stops) if stops else len(text)
    clause = text[left:right]
    start, end = match.start() - left, match.end() - left
    return _uncertain(clause, start, end) or _unhandled_negation(clause, start, end)


def _assertion(section, name, positive, negative, page, put, issues):
    no = [match for match in re.finditer(negative, section.text, re.I)
          if not _uncertain(section.text, match.start(), match.end())] if negative else []
    positive_matches = [match for match in re.finditer(positive, section.text, re.I)
                        if not any(match.start() < other.end() and match.end() > other.start() for other in no)] if positive else []
    ambiguous = [match for match in positive_matches
                 if _uncertain(section.text, match.start(), match.end())
                 or _unhandled_negation(section.text, match.start(), match.end())]
    if ambiguous:
        issues.append(f"{name}: Uncertain or unresolved negative wording needs source review.")
        return None
    yes = positive_matches
    if yes and no:
        issues.append(f"{name}: Contradictory narrative assertions need source review.")
        return None
    selected = yes or no
    if selected:
        value = "1" if yes else "0"
        proof = [word for match in selected for word in section.proof(match.start(), match.end())]
        put(name, value, page, proof, "clinic-narrative-assertion")
        return value, proof
    return None


_BRAIN_FINDINGS = (
    (1, r"(?:pachymeningeal(?:\s*\(dural\))?|dural)\s+enhancement", r"\b(?:no|without|absence of)\s+(?:abnormal\s+)?(?:pachymeningeal(?:\s*\(dural\))?|dural)\s+enhancement"),
    (2, r"\bsubdural\s+(?:fluid\s+)?collections?\b", r"\b(?:no|without|absence of)\s+subdural\s+(?:fluid\s+)?collections?\b"),
    (3, r"(?:transverse|venous)\s+sinuses.{0,70}?\b(?:distended|engorged)\b|\bpositive venous distension sign\b", r"(?:dural\s+)?venous\s+sinuses\s+(?:are\s+)?normal in caliber|\bno venous (?:distension|engorgement)"),
    (4, r"pituitary(?:\s+gland)?\s+(?:is\s+)?(?:enlarged|swollen)|\bpituitary\s+(?:enlargement|swelling)\b", r"pituitary(?:\s+gland)?\s+(?:is\s+)?normal in size|\bno pituitary\s+(?:enlargement|swelling)"),
    (5, r"pre[- ]?pontine\s+cistern.{0,80}?\b(?:effaced|decreased|narrowed)\b", r"pre[- ]?pontine\s+cistern\s+(?:is\s+)?(?:normal|preserved)|no (?:effacement|narrowing) of (?:the )?pre[- ]?pontine cistern"),
    (6, r"suprasellar\s+cistern.{0,80}?\b(?:effaced|decreased|narrowed)\b", r"suprasellar\s+cistern\s+(?:is\s+)?(?:normal|preserved)|no (?:effacement|narrowing) of (?:the )?suprasellar cistern"),
    (7, r"ma[mn]?[mi]+llo[- ]?pontine\s+distance.{0,80}?\b(?:decreased|narrowed|reduced)\b", r"ma[mn]?[mi]+llo[- ]?pontine\s+distance\s+(?:is\s+)?normal|no (?:decrease|narrowing) in (?:the )?ma[mn]?[mi]+llo[- ]?pontine distance"),
    (8, r"\btonsillar ectopia\b|\blow[- ]lying cerebellar tonsils\b", r"cerebellar tonsils\s+(?:are\s+)?normally positioned|\bno tonsillar ectopia\b"),
    (9, r"\bbrain sag(?:ging)?\b|\bsagging of the brain\b", r"\bno (?:evidence of )?(?:brain sag(?:ging)?|sagging of the brain)\b"),
    (10, r"\b(?:partially )?empty sella\b", r"\bno (?:partially )?empty sella\b"),
    (11, r"\boptic nerve sheath\s+(?:dilatation|dilation|enlargement)\b", r"\bno optic nerve sheath\s+(?:dilatation|dilation|enlargement)\b"),
    (12, r"\benlarged Meckel['’]?s caves?\b|\bMeckel['’]?s caves?\s+(?:are\s+)?enlarged\b", r"\bno (?:enlarged|enlargement of) Meckel['’]?s caves?\b"),
    (13, r"\b(?:base of skull|skull base) pits\b", r"\bno (?:base of skull|skull base) pits\b"),
    (14, r"\b(?:base of skull|skull base) (?:CSF )?leaks?\b", r"\bno (?:base of skull|skull base) (?:CSF )?leaks?\b"),
    (15, r"\bvenous stenoses?\b|\bvenous stenosis\b", r"\bno venous (?:stenoses|stenosis)\b"),
)

_SPINE_FINDINGS = (
    (1, 2, r"(?:ventral\s+)?(?:extradural(?:\s*\(extrathecal\))?|extrathecal)\s+(?:longitudinal\s+)?fluid collection", r"\bno\s+(?:extradural(?:\s*\(extrathecal\))?|extrathecal)\s+(?:longitudinal\s+)?fluid collection"),
    (3, 4, r"\b(?:meningeal or )?nerve root\s+(?:sleeve\s+)?diverticula\b", r"\bno\s+(?:meningeal or )?nerve root\s+(?:sleeve\s+)?diverticula\b"),
    (5, 6, r"\bdisc disease\s*:|\bcalcified disc protrusion\b", r"\bno\s+(?:significant\s+)?disc disease\b"),
)

_MYELOGRAM_FINDINGS = (
    (1, r"\badequate\s+(?:distribution of intrathecal contrast|intrathecal contrast distribution)\b", r"\b(?:inadequate|poor)\s+(?:distribution of intrathecal contrast|intrathecal contrast distribution)\b"),
    (2, r"\bperineural\s+(?:\(Tarlov\)\s+)?cysts?\b", r"\bno\s+perineural\s+(?:\(Tarlov\)\s+)?cysts?\b"),
    (3, r"\bcervical degenerative changes\b", r"\bno\s+(?:significant\s+)?cervical degenerative changes\b"),
    (4, r"\bCSF[- ]venous fistula\b", r"\bno\s+(?:evidence of (?:a )?)?CSF[- ]venous fistula\b"),
    (5, r"\bruptured\s+nerve[- ]root diverticula?\b", r"\bno\s+ruptured\s+nerve[- ]root diverticula?\b"),
    (6, r"\b(?:calcified\s+)?disc\s+(?:protrusion\s+)?penetrating.{0,100}?\b(?:contrast )?leak\b|\bpenetrating\s+(?:calcified\s+)?disc.{0,100}?\bleak\b", r"\bno\s+penetrating\s+(?:calcified\s+)?disc\b"),
)


def _contrast(text):
    exam = re.sub(r"with and without(?:\s+IV)?\s+contrast", "with contrast", text, flags=re.I)
    yes = bool(re.search(r"\bwith(?:\s+(?:IV|intravenous|intrathecal))?\s+contrast\b|\b(?:before and after|intrathecal administration of)\b|\biohexol\b|\bgadobutrol\b|\bintravenous gadolinium\b", exam, re.I))
    no = bool(re.search(r"\bwithout(?:\s+(?:IV|intravenous|intrathecal))?\s+contrast\b", exam, re.I))
    return None if yes == no else "1" if yes else "2"


def extract_radiology(page, put):
    text, issues = _text(page), []
    exam = re.search(r"\bEXAM:\s*([^\n]+)", text, re.I)
    if not exam:
        return ["Clinic radiology EXAM header is missing; review this source manually."]
    label = exam[1].upper()
    if "DIGITAL SUBTRACTION MYELOGRAM" in label:
        suffix, finding_prefix, scan_code = "_v2_v2_dsm", "scan_findings_dsm", "1"
    elif "CT MYELOGRAM" in label:
        suffix, finding_prefix, scan_code = "_v2_v2", "scan_findings_v2_v2", "1"
    elif "MRI TOTAL SPINE" in label:
        suffix, finding_prefix, scan_code = "_v2", "scan_findings_v2", "1"
    elif "MRI BRAIN" in label or "CT HEAD" in label:
        suffix, finding_prefix, scan_code = "", "scan_findings", "2" if "MRI BRAIN" in label else "1"
    else:
        return ["Unsupported clinic radiology EXAM; review this source manually."]
    put("scan_type" + suffix, scan_code, page, _proof(page, r"\bEXAM:"), "clinic-report-header")
    accession = re.search(r"\bAccession\s*#\s*([A-Za-z0-9][A-Za-z0-9_.-]*)", text, re.I)
    if accession:
        put("scan_id" + suffix, accession[1], page, _proof(page, r"\bAccession\s*#"), "clinic-report-header")
    exam_date = re.search(r"\bExam date\s+(\d{1,2}/\d{1,2}/\d{4})", text, re.I)
    if exam_date and _date(exam_date[1]):
        put("scan_date" + suffix, _date(exam_date[1]), page, _proof(page, r"\bExam date"), "clinic-report-header")
    technique = _section(page, "TECHNIQUE", "COMPARISON")
    contrast = _contrast(exam[1] + " " + technique.text)
    if contrast:
        put("scan_contrast" + suffix, contrast, page, _proof(page, r"EXAM:|contrast|iohexol|gadobutrol|gadolinium"), "clinic-report-technique")
    else:
        issues.append("scan_contrast" + suffix + ": Contrast is absent or contradictory; verify the source.")
    history = _section(page, "CLINICAL HISTORY", "TECHNIQUE")
    before = bool(re.search(r"\bpre[- ]procedure\b", history.text, re.I))
    after = bool(re.search(r"\bpost[- ]procedure\b", history.text, re.I))
    if before != after:
        put("scan_pre_post" + suffix, "1" if before else "2", page,
            history.proof(0, len(history.text)), "clinic-report-history")
    findings = _section(page, "FINDINGS", "IMPRESSION")
    if not findings.text:
        return [*issues, "Clinic report has no readable FINDINGS section."]
    if not suffix:
        for code, yes, no in _BRAIN_FINDINGS:
            _assertion(findings, f"scan_findings___{code}", yes, no, page, put, issues)
        for name, label in (("mpd", r"ma[mn]?[mi]+llo[- ]?pontine distance"),
                            ("scd", r"suprasellar cistern"), ("ppcd", r"pre[- ]?pontine cistern")):
            measurements = list(re.finditer(label + r"\s+measures\s+(\d+(?:\.\d+)?)\s*mm\b", findings.text, re.I))
            if len({match[1] for match in measurements}) == 1:
                match = measurements[0]
                put(name, match[1], page, findings.proof(match.start(), match.end()), "clinic-report-measurement")
            elif measurements:
                issues.append(f"{name}: Repeated report measurements conflict.")
        other = re.search(r"\bScattered nonspecific T2/FLAIR white matter hyperintensities\b\.?", findings.text, re.I)
        if other:
            words = findings.proof(other.start(), other.end())
            put("scan_findings___16", "1", page, words, "clinic-narrative-assertion")
            put("scan_findings_other", other[0], page, words, "clinic-report-literal")
    elif suffix == "_v2":
        for present, absent, yes, no in _SPINE_FINDINGS:
            result = _assertion(findings, f"{finding_prefix}___{present}", yes, no, page, put, issues)
            if result:
                value, words = result
                put(f"{finding_prefix}___{absent}", "0" if value == "1" else "1", page, words, "clinic-narrative-assertion")
    else:
        assertions = {}
        for code, yes, no in _MYELOGRAM_FINDINGS:
            assertions[code] = _assertion(findings, f"{finding_prefix}___{code}", yes, no, page, put, issues)
        # The coded fistula flag cannot preserve the report's side, vertebral
        # level and drainage description. Keep that explicitly stated detail in
        # the instrument's free-text findings field, with its literal evidence.
        if assertions.get(4) and assertions[4][0] == "1":
            descriptions = list(re.finditer(
                r"\b(?:Left|Right)\s+(?:C|T|L|S)\d{1,2}\s+CSF[- ]venous fistula\s+draining\b[^.!?]*\.?",
                findings.text, re.I))
            descriptions = [match for match in descriptions
                            if not _uncertain(findings.text, match.start(), match.end())
                            and not _unhandled_negation(findings.text, match.start(), match.end())]
            if descriptions:
                words = [word for match in descriptions for word in findings.proof(match.start(), match.end())]
                put("scan_findings_other" + suffix, " ".join(match[0] for match in descriptions),
                    page, words, "clinic-report-literal")
    issues.append("Clinic report findings not explicitly asserted remain blank. Review uncaptured findings; report signatures do not supply REDCap reader or completion codes.")
    return issues


def _cell_words(page, left, right, top, bottom):
    return [word for word in _words(page)
            if left <= word["x"] + word["width"] / 2 < right
            and top <= word["y"] + word["height"] / 2 < bottom]


def _cell_text(words):
    return _norm(" ".join(word["text"] for word in sorted(words, key=lambda word: (round(word["y"], 2), word["x"]))))


def _procedure_columns(page, stage):
    header = [word for word in _words(page) if stage["y"] - .04 <= word["y"] <= stage["y"] + .035]
    def center(pattern):
        matches = [word for word in header if re.search(pattern, _norm(word["text"]), re.I)]
        return None if len(matches) != 1 else matches[0]["x"] + matches[0]["width"] / 2
    found = [center(r"^CSF\b"), center(r"^Opening\b"), center(r"^Manometer$"),
             None, center(r"^location$|^Pain location$"), center(r"^quality$|^Pain quality$"),
             center(r"^Other(?: symptoms)?$")]
    pains = sorted([word for word in header if _norm(word["text"]) == "Pain"], key=lambda word: word["x"])
    if pains:
        found[3] = pains[0]["x"] + pains[0]["width"] / 2
    if any(value is None for value in found) or found != sorted(found):
        return None
    stage_center = stage["x"] + stage["width"] / 2
    return [(stage_center + found[0]) / 2] + [(left + right) / 2 for left, right in zip(found, found[1:])] + [.98]


_LOCATION_TERMS = {
    1: r"\bno headache\b", 2: r"\bfrontal\b", 3: r"\btemporal\b", 4: r"\b(?:retro[- ]?orbital|periorbital)\b",
    5: r"\bvertex\b", 6: r"\bparietal\b", 7: r"\boccipital\b", 8: r"\bneck\b", 9: r"\bjaw\b",
    10: r"\bnose\b", 11: r"\bchin\b", 12: r"\bcheek\b", 13: r"\bear\b", 14: r"\bmouth\b",
}
_QUALITY_TERMS = {1: r"\b(?:throbbing|pounding)\b", 2: r"\b(?:pressure|aching|squeezing)\b",
                  3: r"\b(?:jabbing|piercing|knife[- ]like|sharp|shooting)\b", 4: r"\bburning\b"}

# The operator-supplied TRAIN reference dictionary explicitly names these two
# otherwise clipped catalog labels. These are field-code aliases, never patient
# answers. Require a positive literal assertion in the corresponding source cell.
_PROCEDURE_SYMPTOM_ALIASES = {
    "prov_associated_symptoms___2": r"\bphotophobia\b",
    "prov_associated_symptoms___6": r"\bvisual\s+aura(?:\s*/\s*halos)?\b|\bhalos\b",
}


def extract_procedure(page, put):
    text, issues = _text(page), []
    date = re.search(r"\bDate of procedure\s+(\d{1,2}/\d{1,2}/\d{4})", text, re.I)
    if date and _date(date[1]):
        put("form_date", _date(date[1]), page, _proof(page, r"Date of procedure"), "clinic-procedure-date")
    stage = next((word for word in _words(page) if _norm(word["text"]) == "Stage"), None)
    markers = {word["text"][0]: word for word in _words(page) if re.fullmatch(r"[A-D]\.", word["text"])}
    if stage is None or set(markers) != set("ABCD"):
        return [*issues, "Clinic procedure table headers or stage labels are incomplete; review measurements manually."]
    boundaries = _procedure_columns(page, stage)
    if boundaries is None:
        return [*issues, "Clinic procedure column layout is unsupported; review measurements manually."]
    centers = []
    for index, code in enumerate("ABCD"):
        marker = markers[code]
        end = markers["ABCD"[index + 1]]["y"] if index < 3 else marker["y"] + .035
        labels = [word for word in _words(page) if word["x"] < boundaries[0]
                  and marker["y"] - .001 <= word["y"] < end - .001
                  and re.fullmatch(r"[A-D]\.|Baseline|Provocation|#[1-3]", _norm(word["text"]), re.I)]
        top = min(word["y"] for word in labels) if labels else marker["y"]
        bottom = max(word["y"] + word["height"] for word in labels) if labels else marker["y"] + marker["height"]
        centers.append((top + bottom) / 2)
    rows = [centers[0] - (centers[1] - centers[0]) / 2]
    rows += [(a + b) / 2 for a, b in zip(centers, centers[1:])]
    rows += [centers[-1] + (centers[-1] - centers[-2]) / 2]
    for index in range(4):
        cells = [_cell_words(page, left, right, rows[index], rows[index + 1])
                 for left, right in zip(boundaries, boundaries[1:])]
        strings = [_cell_text(words) for words in cells]
        suffix = "" if index == 0 else "_" + str(index + 1)
        if index and re.search(r"\bnot performed\b", " ".join(strings), re.I):
            put(f"prov_{index}_yn", "0", page, cells[0], "clinic-procedure-stage")
            continue
        pressure = re.fullmatch(r"\d+(?:\.\d+)?", strings[1])
        pain = re.fullmatch(r"(\d+(?:\.\d+)?)\s*/\s*10", strings[3])
        mode = {"analog": "1", "digital": "2"}.get(strings[2].casefold())
        if index and any((pressure, pain, mode)):
            put(f"prov_{index}_yn", "1", page, [word for cell in cells for word in cell], "clinic-procedure-stage")
        if pressure:
            put("baseline_opening_pressure" + suffix, pressure[0], page, cells[1], "clinic-procedure-cell")
        if mode:
            put("opening_headache_aod" + suffix, mode, page, cells[2], "clinic-procedure-cell")
        if pain:
            put("baseline_headache_pain" + suffix, pain[1], page, cells[3], "clinic-procedure-cell")
        if index:
            volume = re.fullmatch(r"([+−-]?\d+(?:\.\d+)?)\s*mL\s*(CSF|Elliot[t]?['’]?s?\s*B)", strings[0], re.I)
            if volume:
                extension = "" if index == 1 else "_" + str(index)
                put("csf_volume_delta" + extension, volume[1].replace("−", "-"), page, cells[0], "clinic-procedure-cell")
                put("css_change_unit" + extension, "1" if volume[2].upper() == "CSF" else "2", page, cells[0], "clinic-procedure-cell")
            elif strings[0]:
                issues.append(f"Provocation {index}: Volume or unit needs source review.")
        for number, pattern in _LOCATION_TERMS.items():
            matches = list(re.finditer(pattern, strings[4], re.I))
            name = f"baseline_pain_localization{suffix}___{number}"
            if matches:
                if any(_unresolved_descriptor(strings[4], match) for match in matches):
                    issues.append(f"{name}: Uncertain or negated location needs source review.")
                else:
                    put(name, "1", page, cells[4], "clinic-procedure-literal")
        quality_mentioned = False
        for number, pattern in _QUALITY_TERMS.items():
            matches = list(re.finditer(pattern, strings[5], re.I))
            name = f"baseline_pain_quality{suffix}___{number}"
            if matches:
                quality_mentioned = True
                if any(_unresolved_descriptor(strings[5], match) for match in matches):
                    issues.append(f"{name}: Uncertain or negated quality needs source review.")
                else:
                    put(name, "1", page, cells[5], "clinic-procedure-literal")
        if strings[5] and not quality_mentioned:
            put(f"baseline_pain_quality{suffix}___5", "1", page, cells[5], "clinic-procedure-literal")
            put("baseline_pain_other" + suffix, strings[5], page, cells[5], "clinic-procedure-literal")
        other_name = "baseline_other" if index == 0 else "prov_other" + ("" if index == 1 else "_" + str(index))
        if strings[6]:
            none = bool(re.fullmatch(r"none|no other symptoms", strings[6], re.I))
            put(other_name, "0" if none else "1", page, cells[6], "clinic-procedure-literal")
            prefix = "baseline_associated_symptoms" if index == 0 else "prov_associated_symptoms" + ("" if index == 1 else "_" + str(index))
            terms = {prefix + "___nausea": r"\bnausea\b"}
            if index == 1:
                terms.update(_PROCEDURE_SYMPTOM_ALIASES)
            remaining = strings[6]
            for name, pattern in terms.items():
                matches = list(re.finditer(pattern, strings[6], re.I))
                if matches and all(not _uncertain(strings[6], match.start(), match.end())
                                   and not _unhandled_negation(strings[6], match.start(), match.end())
                                   for match in matches):
                    put(name, "1", page, cells[6], "clinic-procedure-dictionary-alias" if name in _PROCEDURE_SYMPTOM_ALIASES else "clinic-procedure-literal")
                    remaining = re.sub(pattern, "", remaining, flags=re.I)
            if not none and re.sub(r"[,;\s]", "", remaining):
                issues.append(f"Stage {'ABCD'[index]}: Other-symptom terms need review against the study's coded labels.")
    issues.append("Procedure descriptors not explicitly named remain blank; no unmentioned location, quality or symptom option is assumed negative.")
    return issues
