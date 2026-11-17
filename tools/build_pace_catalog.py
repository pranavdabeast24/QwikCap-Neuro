"""Build the PACE field catalog from the supplied blank REDCap references."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
from collections import Counter
from pathlib import Path

from pypdf import PdfReader


REFERENCE_HASHES = {
    "codebook": "8e21c33ca9ce810d8f1247b23e40ee46f5a56d2cdeaa5ccd35f5d1f00a693160",
    "template": "22c0ceb518059faaff0a5546ade586089c83768a561b5a59880763685c3b46b5",
}
INSTRUMENTS = [
    ("patient_records", "Patient Records", False, 1, 9),
    ("duke_neuroradiology_headache_questionnaire", "Duke Neuro-radiology Headache Questionnaire", False, 10, 88),
    ("hit6", "HIT-6", True, 89, 97),
    ("csf_volume_provocation_form", "CSF Volume Provocation Form", True, 98, 140),
    ("image_information_brain_scan", "Image Information Brain Scan", True, 141, 152),
    ("image_information_spine_mri", "Image Information Spine MRI", True, 153, 161),
    ("image_information_ct_myelogram", "Image Information CT Myelogram", True, 162, 170),
    ("image_information_ct_dsm_or_fluroscopic_guided", "Image Information CT DSM or Fluroscopic Guided", True, 171, 179),
    ("duke_neuroradiology_headache_questionnaire_patient", "Duke Neuro-radiology Headache Questionnaire Patient Facing", False, 180, 253),
]
CONTEXT = {
    "record_id": ("Record ID", "Record identifier supplied manually for the intended REDCap record. Codebook field 1 is text; no identifier is generated."),
    "redcap_repeat_instrument": ("REDCap repeat instrument", "Export/import metadata absent from the codebook. Supply the exact repeating instrument context manually when applicable."),
    "redcap_repeat_instance": ("REDCap repeat instance", "Export/import metadata absent from the codebook. Supply the repeat instance manually when applicable; no instance is inferred."),
    "redcap_data_access_group": ("REDCap data access group", "Export/import metadata absent from the codebook. Supply the permitted data access group manually when applicable."),
}
TYPE_START = re.compile(r"(?<!\w)(?:text(?:\s*\([^\n]*\))?|radio(?:\s*\(Matrix\))?|checkbox|yesno|dropdown|calc|descriptive)(?=,|$|\s)")
ROW_START = re.compile(r"^\s*(\d+)\s*\[")
NOTE_STARTS = (
    "Confirm that this is a Unique MRN", "As identified in Epic,", "If you do not know the exact date,",
    "This value should be 28,", "Choose all that apply", "choose all that apply",
    "If it varies,", "enter most recent if multiple", "separate specialists via comma",
    "list all your medications separated", "Use month/day/year format", "Measured in cm H2O",
    "Enter a negative value", "as measured in mm",
)


def compact(parts):
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def read_codebook(path):
    reader = PdfReader(path)
    if len(reader.pages) != 30:
        raise ValueError("Expected the supplied 30-page PACE codebook")
    fields = []
    current = None
    for page_number, page in enumerate(reader.pages, 1):
        lines = page.extract_text(extraction_mode="layout").splitlines()
        attr_starts = []
        label_starts = []
        for line in lines:
            for match in TYPE_START.finditer(line):
                if match.start() > 80:
                    attr_starts.append(match.start())
            if ROW_START.match(line):
                candidate = re.search(r"\S", line[34:60])
                if candidate and candidate.start() + 34 >= 37:
                    label_starts.append(candidate.start() + 34)
        if page_number == 1:
            label_start = next(line.index("Field Label") for line in lines if "Field Label" in line)
            attr_start = next(line.index("Field Attributes") for line in lines if "Field Attributes" in line)
        else:
            attr_start = Counter(attr_starts).most_common(1)[0][0]
            label_start = Counter(label_starts).most_common(1)[0][0]
        for line in lines:
            if line.lstrip().startswith(("Instrument:", "Enabled as survey", "Facing      (duke_neuroradiology_headache_questionnaire_patient)")):
                continue
            left = line[:label_start].strip()
            label = line[label_start:attr_start].strip()
            attributes = line[attr_start:].strip()
            start = ROW_START.match(left)
            if start:
                current = {"number": int(start[1]), "page": page_number, "left": [], "label": [], "attributes": []}
                fields.append(current)
                left = left[start.end() - 1:]
            if current:
                if label and attributes and not TYPE_START.match(attributes) and not re.match(r"(?:-?\d+|nausea)\s", attributes):
                    label = line[label_start:].strip()
                    attributes = ""
                current["left"].append(left)
                current["label"].append(label)
                current["attributes"].append(attributes)
    if [field["number"] for field in fields] != list(range(1, 254)):
        raise ValueError("Codebook field sequence is not exactly 1 through 253")
    result = {}
    for raw in fields:
        left = "\n".join(item for item in raw["left"] if item)
        name_match = re.match(r"\[([^]]+)\]", left)
        if not name_match:
            raise ValueError(f"Cannot parse codebook field {raw['number']}")
        name = re.sub(r"\s+", "", name_match[1])
        branch = left[name_match.end():].strip()
        branch = re.sub(r"^Show the field ONLY if:\s*", "", branch)
        labels = [item for item in raw["label"] if item]
        section = ""
        if labels and labels[0].startswith("Section Header:"):
            section = labels.pop(0)
            if raw["number"] in (19, 188) and labels and labels[0] == "Days":
                section += " " + labels.pop(0)
            if raw["number"] in (36, 207) and labels and labels[0] == "influenced by or do you notice changes:":
                section += " " + labels.pop(0)
            if raw["number"] in (66, 231) and labels and labels[0] == "changed your symptoms?":
                section += " " + labels.pop(0)
        note_index = next((index for index, item in enumerate(labels) if item.startswith(NOTE_STARTS)), len(labels))
        field_note = compact(labels[note_index:])
        labels = labels[:note_index]
        attributes = [item for item in raw["attributes"] if item]
        if not attributes or not TYPE_START.match(attributes[0]):
            raise ValueError(f"Cannot parse attributes for {name}: {attributes[:2]}")
        instrument = next(item[0] for item in INSTRUMENTS if item[3] <= raw["number"] <= item[4])
        result[name] = {
            "number": raw["number"], "sourcePage": raw["page"],
            "label": compact(labels), "attributes": attributes,
            "branching": branch, "section": section, "fieldNote": field_note, "instrument": instrument,
        }
    return result


def option_labels(source, source_name):
    attributes = source["attributes"]
    options = {}
    current_code = None
    for line in attributes[1:]:
        if line.startswith(("Field Annotation:", "Calculation:", "(Attachment:")):
            current_code = None
            continue
        if attributes[0].startswith("checkbox"):
            match = re.match(r"(\S+)\s+" + re.escape(source_name) + r"___([a-z0-9]+)\s*(.*)$", line)
            if match:
                if match[1] != match[2]:
                    raise ValueError(f"Checkbox code mismatch for {source_name}")
                current_code = match[2]
                options[current_code] = match[3]
            elif current_code:
                options[current_code] = compact([options[current_code], line])
        else:
            match = re.match(r"(-?\d+)\s+(.+)$", line)
            if match:
                current_code = match[1]
                options[current_code] = match[2]
            elif current_code:
                options[current_code] = compact([options[current_code], line])
    return options


def uncertain_option(base, code):
    if base.startswith(("baseline_associated_symptoms", "prov_associated_symptoms")):
        return True
    if base == "baseline_pain_localization":
        return code in {"4", "5", "6", "7"}
    if base.startswith("baseline_pain_localization_"):
        return code in {"1", "4", "5", "6", "7"}
    if base == "baseline_pain_quality":
        return code in {"2", "3"}
    if base.startswith("baseline_pain_quality_"):
        return code in {"1", "2", "3"}
    if base == "headache_location_v2":
        return code in {"2", "3", "8", "11", "12", "13", "14", "15", "16", "21"}
    return base == "headache_quality_v2" and code == "3"


def catalog_field(column, sources):
    if column in CONTEXT:
        label, note = CONTEXT[column]
        return {"name": column, "label": label, "type": "text", "required": False,
                "instrument": "record_context", "sourceField": column, "sourcePage": 0,
                "branching": "", "validation": "", "notes": note}
    base, separator, code = column.partition("___")
    source = sources.get(base)
    if source is None:
        return {"name": column, "label": column, "type": "text", "required": False,
                "instrument": "record_context", "sourceField": base, "sourcePage": 0,
                "branching": "", "validation": "", "notes": "Unverified field. No matching codebook definition was found."}
    validation = source["attributes"][0]
    field = {"name": column, "label": source["label"] or base,
             "type": "text", "required": "Required" in validation,
             "instrument": source["instrument"], "sourceField": base,
             "sourcePage": source["sourcePage"], "branching": source["branching"],
             "validation": validation, "notes": ""}
    notes = [source["section"]] if source["section"] else []
    if source["fieldNote"]:
        notes.append("Field note: " + source["fieldNote"])
    if source["branching"]:
        notes.append("Branching is retained as source reference only and is not evaluated.")
    if "Identifier" in validation:
        notes.append("Codebook marks this field as an identifier.")
    if separator:
        options = option_labels(source, base)
        if code not in options:
            notes.append("Unverified checkbox code. Retained as text; no meaning or binary value is inferred.")
        else:
            option = options[code]
            uncertain = uncertain_option(base, code)
            if not option:
                option = f"option {code} (label unreadable in supplied codebook)"
            elif uncertain:
                option += " (source label clipped)"
            field["label"] += " - " + option
            field["type"] = "choice"
            field["choices"] = {"0": "Unchecked", "1": "Checked"}
            notes.append(f"Expanded REDCap checkbox option code {code}. Blank means missing; it is never converted to 0.")
            if uncertain:
                notes.append("Uncertain option label: the supplied PDF clips or omits the option wording. Verify the wording in REDCap; no missing wording was reconstructed.")
    elif validation.startswith(("radio", "dropdown", "yesno")):
        options = option_labels(source, base)
        if options:
            field["type"] = "choice"
            field["choices"] = options
        else:
            notes.append("Unverified choice codes. Retained as text.")
    elif "date_mdy" in validation:
        field["type"] = "date"
        field["sourceDateFormat"] = "mdy"
    elif "integer" in validation:
        field["type"] = "integer"
    elif "number" in validation:
        field["type"] = "number"
    for bound in ("Min", "Max"):
        match = re.search(bound + r":\s*(-?\d+(?:\.\d+)?)", validation)
        if match:
            value = float(match[1])
            field[bound.lower()] = int(value) if value.is_integer() else value
    if "Max: today" in validation:
        notes.append("Codebook maximum is today; retained as reference without evaluating a moving date limit.")
    for line in source["attributes"][1:]:
        if line.startswith("Field Annotation:"):
            notes.append(line)
    if base.endswith("_complete"):
        notes.append("Completion status is supplied explicitly. No completion value is defaulted.")
    if not source["label"]:
        notes.append("No field label is printed in the supplied codebook; the variable name is displayed.")
    if len(field["label"]) > 200:
        notes.append("Full source label: " + field["label"])
        field["label"] = field["label"][:197] + "..."
        notes.append("Display label truncated to 200 characters.")
    field["notes"] = compact(notes)[:2000]
    if len(field["branching"]) > 1000:
        raise ValueError(f"Branching exceeds supported bound for {column}")
    return field


def build_catalog(codebook, template):
    hashes = {"codebook": hashlib.sha256(codebook.read_bytes()).hexdigest(),
              "template": hashlib.sha256(template.read_bytes()).hexdigest()}
    if hashes != REFERENCE_HASHES:
        raise ValueError("References differ from the reviewed PACE codebook and blank import template")
    rows = list(csv.reader(io.StringIO(template.read_text(encoding="utf-8-sig"))))
    if len(rows) != 1 or len(rows[0]) != 513 or rows[0][-1] != "":
        raise ValueError("Expected a header-only template with 512 names and one trailing empty header")
    columns = rows[0][:-1]
    if len(set(columns)) != 512 or any(not re.fullmatch(r"[a-z][a-z0-9_]*", item) for item in columns):
        raise ValueError("Template column names are not unique valid REDCap names")
    sources = read_codebook(codebook)
    fields = [catalog_field(column, sources) for column in columns]
    return {
        "format": "quickcap-field-catalog-v1", "id": "pace-2026-11-17",
        "name": "Intracranial Hypotension PACE", "columns": columns,
        "instruments": [{"name": item[0], "label": item[1], "repeatable": item[2]} for item in INSTRUMENTS],
        "fields": fields,
        "provenance": {"codebookSHA256": hashes["codebook"],
                       "templateSHA256": hashes["template"],
                       "referenceDate": "2026-11-17"},
        "warnings": [
            "The source template has one trailing empty header cell. It is omitted; all 512 named columns retain their exact names and order.",
            "The supplied references are blank reference materials confirmed fictional by the user. This catalog contains definitions, not patient answers.",
            "The codebook defines 253 base fields across nine instruments. Calculated and descriptive fields absent from the template are not added.",
            "Some checkbox option labels are clipped or unreadable in the supplied PDF. Affected fields carry uncertainty notes; no missing wording is invented.",
            "Baseline and patient-facing medication matrices have different codes. Each field retains its own codebook mapping.",
            "Branching expressions are source reference only. Potential source inconsistencies are preserved for manual verification.",
            "Record, repeat, group, and completion metadata require explicit review. Missing checkbox values are not unchecked values.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codebook", required=True, type=Path)
    parser.add_argument("--template", required=True, type=Path)
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--output-template", required=True, type=Path)
    args = parser.parse_args()
    catalog = build_catalog(args.codebook, args.template)
    args.catalog.parent.mkdir(parents=True, exist_ok=True)
    args.catalog.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n")
    args.output_template.parent.mkdir(parents=True, exist_ok=True)
    with args.output_template.open("w", newline="") as handle:
        csv.writer(handle).writerow(catalog["columns"])
    print(json.dumps({"columns": len(catalog["columns"]), "fields": len(catalog["fields"]),
                      "instruments": len(catalog["instruments"]),
                      "uncertainLabels": sum("Uncertain option label:" in field["notes"] for field in catalog["fields"]),
                      "types": dict(Counter(field["type"] for field in catalog["fields"]))}, indent=2))


if __name__ == "__main__":
    main()
