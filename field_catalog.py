"""Bounded study reference metadata, separate from executable extraction rules."""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path
import re

from limits import MAX_COLUMNS, MAX_SCHEMA_BYTES

FORMAT = "quickcap-field-catalog-v1"
REPEATING_EXPORT_WARNING = "One patient review row. Repeating REDCap instruments require separate instrument/instance rows before upload; this export is not validated for that import."
NAME = re.compile(r"[a-z][a-z0-9_]{0,99}")
TYPES = {"text", "integer", "number", "date", "choice"}
FIELD_KEYS = {"name", "label", "type", "required", "instrument", "sourceField", "sourcePage",
              "branching", "validation", "notes", "choices", "min", "max", "sourceDateFormat"}
REQUIRED_KEYS = FIELD_KEYS - {"choices", "min", "max", "sourceDateFormat"}


class CatalogError(ValueError):
    pass


def _text(value, maximum, label, empty=True):
    if not isinstance(value, str) or len(value) > maximum or (not empty and not value) or any(ord(c) < 32 and c not in "\n\r\t" for c in value):
        raise CatalogError(f"Invalid {label} in the study field catalog.")
    return value


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CatalogError("Duplicate keys in the study field catalog.")
        result[key] = value
    return result


def parse_catalog(raw):
    keys = {"format", "id", "name", "columns", "instruments", "fields", "provenance", "warnings"}
    if not isinstance(raw, dict) or set(raw) != keys or raw.get("format") != FORMAT:
        raise CatalogError("Invalid study field catalog format.")
    _text(raw["id"], 120, "catalog identifier", False)
    _text(raw["name"], 200, "catalog name", False)
    columns = raw["columns"]
    if not isinstance(columns, list) or not 1 <= len(columns) <= MAX_COLUMNS or any(not isinstance(n, str) or not NAME.fullmatch(n) for n in columns) or len(set(columns)) != len(columns):
        raise CatalogError("The study field catalog needs unique, bounded destination names.")
    instruments = raw["instruments"]
    if not isinstance(instruments, list) or len(instruments) > 100:
        raise CatalogError("Invalid study instrument list.")
    names = set()
    for instrument in instruments:
        if not isinstance(instrument, dict) or set(instrument) != {"name", "label", "repeatable"} or type(instrument["repeatable"]) is not bool:
            raise CatalogError("Invalid study instrument metadata.")
        name = _text(instrument["name"], 120, "instrument name", False)
        if name in names:
            raise CatalogError("Duplicate study instrument name.")
        names.add(name)
        _text(instrument["label"], 200, "instrument label", False)
    fields = raw["fields"]
    if not isinstance(fields, list) or len(fields) != len(columns):
        raise CatalogError("Every study destination needs one metadata entry.")
    for field, column in zip(fields, columns):
        if not isinstance(field, dict) or set(field) - FIELD_KEYS or REQUIRED_KEYS - set(field) or field.get("name") != column:
            raise CatalogError("Study metadata must follow the exact destination order.")
        if not isinstance(field["type"], str) or field["type"] not in TYPES or type(field["required"]) is not bool:
            raise CatalogError("Invalid study field type or required flag.")
        for key, maximum in (("label", 200), ("instrument", 120), ("sourceField", 100), ("branching", 8000), ("validation", 8000), ("notes", 8000)):
            _text(field[key], maximum, key, key in {"branching", "validation", "notes"})
        if field["instrument"] not in names | {"record_context"}:
            raise CatalogError("Unknown instrument in the study field catalog.")
        if type(field["sourcePage"]) is not int or not 0 <= field["sourcePage"] <= 30:
            raise CatalogError("Invalid codebook reference page.")
        if "sourceDateFormat" in field and (field["type"] != "date" or field["sourceDateFormat"] != "mdy"):
            raise CatalogError("Invalid source date format in the study field catalog.")
        choices = field.get("choices")
        if choices is not None:
            if field["type"] != "choice" or not isinstance(choices, dict) or not 1 <= len(choices) <= 100:
                raise CatalogError("Invalid study field choices.")
            for code, label in choices.items():
                if not isinstance(code, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,40}", code):
                    raise CatalogError("Invalid study answer code.")
                _text(label, 200, "choice label")
        elif field["type"] == "choice":
            raise CatalogError("Choice metadata needs exact answer codes.")
        for key in ("min", "max"):
            if key in field and (isinstance(field[key], bool) or not isinstance(field[key], (int, float)) or not math.isfinite(field[key])):
                raise CatalogError("Invalid study numeric bound.")
        if field.get("min", -math.inf) > field.get("max", math.inf):
            raise CatalogError("Invalid study numeric range.")
    provenance = raw["provenance"]
    if not isinstance(provenance, dict) or set(provenance) != {"codebookSHA256", "templateSHA256", "referenceDate"} or any(not isinstance(provenance[key], str) or not re.fullmatch(r"[a-f0-9]{64}", provenance[key]) for key in ("codebookSHA256", "templateSHA256")) or not isinstance(provenance["referenceDate"], str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", provenance["referenceDate"]):
        raise CatalogError("Invalid study catalog provenance.")
    warnings = raw["warnings"]
    if not isinstance(warnings, list) or len(warnings) > 100:
        raise CatalogError("Invalid study catalog warnings.")
    for warning in warnings:
        _text(warning, 2000, "catalog warning", False)
    return copy.deepcopy(raw)


def load_catalog(path):
    path = Path(path)
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_SCHEMA_BYTES:
            raise CatalogError("The bundled study field catalog is missing or exceeds 1 MiB.")
        with path.open("rb") as stream:
            data = stream.read(MAX_SCHEMA_BYTES + 1)
        if len(data) > MAX_SCHEMA_BYTES:
            raise CatalogError("The study field catalog exceeds 1 MiB.")
        raw = json.loads(data, object_pairs_hook=_unique_object, parse_constant=lambda value: (_ for _ in ()).throw(CatalogError("Invalid numeric constant in the study field catalog.")))
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise CatalogError("The bundled study field catalog could not be read.") from exc
    return parse_catalog(raw)


def catalog_for_columns(columns, profile_path):
    """Only an exact, ordered header match enables verified study metadata."""
    names = [column["name"] for column in columns]
    profile = load_catalog(profile_path)
    if names == profile["columns"]:
        return {"fields": [{**field, "metadataVerified": True} for field in profile["fields"]],
                "instruments": profile["instruments"], "warnings": profile["warnings"],
                "id": profile["id"], "name": profile["name"]}
    return {"fields": [{"name": name, "label": name, "type": "text", "required": False,
                        "instrument": "", "sourceField": name, "sourcePage": 0, "branching": "",
                        "validation": "", "notes": "Header only. Confirm the type and rules against your study reference.",
                        "metadataVerified": False} for name in names],
            "instruments": [], "warnings": ["These headers do not exactly match the bundled PACE destination order. Study metadata is unavailable."],
            "id": None, "name": "Expected fields"}


def extraction_rule(field):
    rule = {key: copy.deepcopy(field[key]) for key in ("name", "label", "type", "required", "choices", "min", "max", "sourceDateFormat") if key in field}
    if field.get("branching"):
        rule["required"] = False
    return rule
