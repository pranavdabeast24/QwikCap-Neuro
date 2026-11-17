"""Pure validation and geometry for reusable, rules-only extraction types."""
from __future__ import annotations

import copy
import math
import uuid
import json

from branding import PRODUCT_NAME
from limits import MAX_FIELDS, MAX_SCHEMA_BYTES, MAX_PAGES
from server import InputError, parse_schema

FORMAT = "formbridge-form-type-v1"
RULE_KEYS = {"name", "label", "type", "required", "aliases", "choices", "min", "max", "region", "sourceDateFormat"}
DRAFT_KEYS = {"name", "identifierField", "fields", "pages"}


def validate_region(region):
    """One geometry validator for cursor gestures, typed coordinates and files."""
    if not isinstance(region, dict) or set(region) != {"page", "x", "y", "width", "height"}:
        raise InputError("Masks may contain page and normalized coordinates only.")
    return parse_schema([{"name": "mask_geometry", "type": "text", "region": region}])[0]["region"]


def percentage_region(page, x, y, width, height, page_count):
    try:
        page_number = int(page)
        if str(page_number) != str(page).strip() or not 1 <= page_number <= page_count:
            raise ValueError
        region = {"page": page_number, **{key: float(value) / 100 for key, value in
                  (("x", x), ("y", y), ("width", width), ("height", height))}}
    except (TypeError, ValueError, OverflowError) as exc:
        raise InputError("Choose a page in this document and numeric percentages for the mask.") from exc
    return validate_region(region)


def page_geometry(pages):
    return [{"page": p["page"], "aspectRatio": p["width"] / p["height"]} for p in pages
            if p.get("width", 0) > 0 and p.get("height", 0) > 0]


def _pages(raw):
    if not isinstance(raw, list) or len(raw) > MAX_PAGES:
        raise InputError(f"An extraction type supports at most {MAX_PAGES} pages.")
    result = []
    for index, page in enumerate(raw, 1):
        if not isinstance(page, dict) or set(page) != {"page", "aspectRatio"} or type(page["page"]) is not int or page["page"] != index:
            raise InputError("Page geometry must list consecutive pages starting at one.")
        ratio = page["aspectRatio"]
        if isinstance(ratio, bool) or not isinstance(ratio, (int, float)) or not math.isfinite(ratio) or not .02 <= ratio <= 50:
            raise InputError("Page aspect ratios must be finite positive numbers.")
        result.append({"page": index, "aspectRatio": ratio})
    return result


def new_draft(definition=None, pages=None):
    if definition is not None:
        fields = [{"id": uuid.uuid4().hex, **copy.deepcopy(f)} for f in definition["fields"]]
        return {"name": definition["name"], "identifierField": next(f["id"] for f in fields if f["name"] == definition["identifierField"]),
                "pages": copy.deepcopy(definition["pages"]),
                "fields": fields}
    return {"name": "", "identifierField": None, "fields": [], "pages": _pages(pages or [])}


def validate_draft(raw):
    """Retain incomplete editor input, while rejecting payloads outside the rules model."""
    if not isinstance(raw, dict) or set(raw) != DRAFT_KEYS:
        raise InputError("Invalid extraction-type draft.")
    name, identifier, fields = raw["name"], raw["identifierField"], raw["fields"]
    if not isinstance(name, str) or len(name) > 120 or any(ord(c) < 32 for c in name):
        raise InputError("Use an extraction-type name up to 120 characters.")
    if identifier is not None and (not isinstance(identifier, str) or len(identifier) > 80):
        raise InputError("Choose a text field as the record identifier.")
    if not isinstance(fields, list) or len(fields) > MAX_FIELDS:
        raise InputError(f"Use at most {MAX_FIELDS} fields.")
    if len(json.dumps(raw, ensure_ascii=True).encode()) > MAX_SCHEMA_BYTES:
        raise InputError("An extraction-type draft must be at most 1 MiB.")
    ids = set()
    for field in fields:
        if not isinstance(field, dict) or set(field) - RULE_KEYS - {"id"}:
            raise InputError("Draft fields may contain extraction rules only.")
        key = field.get("id")
        if not isinstance(key, str) or not 1 <= len(key) <= 80 or not key.isalnum() or key in ids:
            raise InputError("Each draft field needs a unique internal key.")
        ids.add(key)
        # Full schema validation is deferred to Apply, so partially typed names survive.
        if any(not isinstance(field.get(k, ""), str) or len(field.get(k, "")) > 200 for k in ("name", "label", "type")):
            raise InputError("Field names, labels and types must be short text.")
        if "required" in field and type(field["required"]) is not bool:
            raise InputError("Required must be true or false.")
        if "sourceDateFormat" in field and (field.get("type") != "date" or field["sourceDateFormat"] != "mdy"):
            raise InputError("sourceDateFormat supports only mdy on date fields; omit it for ISO dates.")
        aliases = field.get("aliases", [])
        if not isinstance(aliases, list) or len(aliases) > 20 or any(not isinstance(a, str) or len(a) > 200 for a in aliases):
            raise InputError("Aliases must be short labels only.")
        choices = field.get("choices", {})
        if not isinstance(choices, dict) or len(choices) > 100 or any(not isinstance(k, str) or not isinstance(v, str) or len(k) > 40 or len(v) > 200 for k, v in choices.items()):
            raise InputError("Choices must contain short code and label strings only.")
        for bound in ("min", "max"):
            value = field.get(bound)
            if bound in field and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)):
                raise InputError("Numeric bounds must be finite numbers.")
        if "region" in field:
            validate_region(field["region"])
        if len(str(field)) > 18000:
            raise InputError("A field definition is too large.")
    return {"name": name, "identifierField": identifier, "fields": copy.deepcopy(fields), "pages": _pages(raw["pages"])}


def compile_draft(raw):
    draft = validate_draft(raw)
    if not draft["name"].strip():
        raise InputError("Name this extraction type before applying or saving it.")
    if not draft["fields"]:
        raise InputError("Draw at least one field mask.")
    identifier = next((f for f in draft["fields"] if f["id"] == draft["identifierField"]), None)
    if identifier is None or identifier.get("type") != "text":
        raise InputError("Explicitly choose a text field as the record identifier.")
    ordered = [identifier] + [f for f in draft["fields"] if f is not identifier]
    rules = [{k: copy.deepcopy(v) for k, v in f.items() if k in RULE_KEYS} for f in ordered]
    if not draft["pages"] or any("region" not in f for f in rules):
        raise InputError("Each field needs a drawn page mask on a PDF or image.")
    fields = parse_schema(rules)
    if any(f["region"]["page"] > len(draft["pages"]) for f in fields):
        raise InputError("A field mask refers to a page outside this extraction type.")
    return {"format": FORMAT, "name": draft["name"].strip(), "identifierField": identifier["name"],
            "pages": draft["pages"], "fields": fields}


def parse_form_type(raw):
    if not isinstance(raw, dict) or set(raw) != {"format", *DRAFT_KEYS} or raw.get("format") != FORMAT:
        raise InputError(f"Choose a rules-only {PRODUCT_NAME} extraction type (formbridge-form-type-v1).")
    fields = raw.get("fields")
    if not isinstance(fields, list) or any(not isinstance(f, dict) or set(f) - RULE_KEYS for f in fields):
        raise InputError("Extraction types may contain field rules only; source documents and answers are not allowed.")
    draft = {"name": raw["name"], "identifierField": None, "pages": raw["pages"], "fields": []}
    for field in fields:
        key = uuid.uuid4().hex
        draft["fields"].append({"id": key, **field})
        if field.get("name") == raw["identifierField"]:
            draft["identifierField"] = key
    return compile_draft(draft)


def compatibility_issues(definition, pages):
    if definition is None:
        return []
    expected = definition["pages"]
    if len(pages) != len(expected):
        return ["This document has a different page count from the extraction type. Load or design the correct type before review."]
    for saved, actual in zip(expected, pages):
        if actual.get("width", 0) <= 0 or actual.get("height", 0) <= 0:
            return ["This extraction type requires rendered PDF or image pages; text-only sources cannot use masks."]
        ratio = actual["width"] / actual["height"]
        if abs(ratio / saved["aspectRatio"] - 1) > .035:
            return ["This document has a different page shape from the extraction type. Load or design the correct type before review."]
    return []


def normalized_drag(start, end, width, height, page, offset=12, minimum=4):
    """Convert scrolled canvas coordinates to a clipped, direction-independent mask."""
    if width <= 0 or height <= 0:
        raise InputError("Render a source page before drawing a mask.")
    x1, x2 = sorted(max(0, min(width, p[0] - offset)) for p in (start, end))
    y1, y2 = sorted(max(0, min(height, p[1] - offset)) for p in (start, end))
    if x2 - x1 < minimum or y2 - y1 < minimum:
        raise InputError("Draw a mask at least four display pixels wide and high.")
    return validate_region({"page": page, "x": x1 / width, "y": y1 / height,
                            "width": (x2 - x1) / width, "height": (y2 - y1) / height})
