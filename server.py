"""Loopback-only research form prototype with local document workers."""
from __future__ import annotations

import argparse
import base64
import binascii
import copy
import csv
import datetime as dt
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import secrets
import signal
import subprocess
import sys
import tempfile
import threading
import shutil
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs

from pipeline import capabilities
from limits import MAX_FIELDS, MAX_SCHEMA_BYTES, MAX_PAGES
from PIL import Image
from templates import validate_mapping, suggested_mapping
from runtime_paths import worker_command, process_options
from neurology_profile import (is_profile as is_neurology_profile,
                               patient_groups, profile_schema)
from extraction_profiles import (PROFILES, is_profile, profile_id,
                                 canonical_schema, applicable_fields, validate_profile_values,
                                 source_blocking_issues, confirmed_source_blank)

ROOT = Path(__file__).resolve().parent
MAX_BODY = 40 * 1024 * 1024
MAX_FILE = 12 * 1024 * 1024
MAX_RECORDS = 60
MAX_SESSION_BYTES = 20 * 1024 * 1024
MAX_VALUE_BYTES = 4 * 1024 * 1024
FIELD_NAME = re.compile(r"^[a-z][a-z0-9_]{0,99}$")
ASSET = re.compile(r"^/api/assets/([A-Za-z0-9_-]{1,80})/(page-(?:[1-9]|[12][0-9]|3[0-2])\.png)$")
TYPES = {"text", "integer", "number", "date", "choice"}
DECIMAL = re.compile(r"^-?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?$")


class InputError(ValueError):
    pass


class ConflictError(InputError):
    pass


def source_bytes(records):
    def size(encoded):
        return len(encoded) // 4 * 3 - (2 if encoded.endswith("==") else 1 if encoded.endswith("=") else 0)
    return sum(size(record["sourceData"]) + sum(size(source["sourceData"]) for source in record.get("bundleSources", [])) for record in records)


def public_record(record):
    result = {key: value for key, value in record.items() if key != "sourceData"}
    if "bundleSources" in record:
        result["bundleSources"] = [{key: value for key, value in source.items() if key != "sourceData"} for source in record["bundleSources"]]
    return result


def project_record(record):
    result = {key: record[key] for key in ("filename", "sourceData", "sourceHash", "values")}
    for key in ("bundleSources", "bundleRecordId"):
        if key in record:
            result[key] = record[key]
    return result


def strict_json_loads(raw):
    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise InputError("Duplicate JSON keys are not allowed.")
            result[key] = value
        return result

    def invalid_constant(_):
        raise InputError("JSON numbers must be finite.")

    return json.loads(raw, object_pairs_hook=object_pairs, parse_constant=invalid_constant)


def terminate_tree(process):
    if process.poll() is not None:
        return
    if os.name == "nt":
        taskkill = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "taskkill.exe"
        try:
            subprocess.run([str(taskkill), "/PID", str(process.pid), "/T", "/F"], capture_output=True, timeout=10, check=False)
        except (OSError, subprocess.TimeoutExpired):
            process.kill()
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if process.poll() is None:
        process.kill()


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def parse_schema(raw):
    if len(json.dumps(raw, ensure_ascii=True).encode()) > MAX_SCHEMA_BYTES:
        raise InputError("Field mapping must be at most 1 MiB.")
    fields = raw.get("fields", raw.get("schema")) if isinstance(raw, dict) else raw
    if not isinstance(fields, list) or not 1 <= len(fields) <= MAX_FIELDS:
        raise InputError(f"A schema must contain 1 to {MAX_FIELDS} fields.")
    result, names = [], set()
    for index, item in enumerate(fields):
        if not isinstance(item, dict):
            raise InputError("Each field must be an object.")
        name, kind = item.get("name", ""), item.get("type", "text")
        if not isinstance(name, str) or not FIELD_NAME.fullmatch(name) or name in names:
            raise InputError("Use unique REDCap field names with lowercase letters, digits and underscores.")
        if not isinstance(kind, str) or kind not in TYPES:
            raise InputError(f"Unsupported field type for {name}.")
        label = item.get("label", name)
        if not isinstance(label, str) or not 1 <= len(label) <= 200:
            raise InputError("Field labels must contain 1 to 200 characters.")
        if type(item.get("required", False)) is not bool:
            raise InputError("The required property must be true or false.")
        field = {"name": name, "label": label, "type": kind, "required": item.get("required", False)}
        if "sourceDateFormat" in item:
            if kind != "date" or item["sourceDateFormat"] != "mdy":
                raise InputError("sourceDateFormat supports only mdy on date fields; omit it for ISO dates.")
            field["sourceDateFormat"] = "mdy"
        if "profile" in item:
            marker = item["profile"]
            if not isinstance(marker, str) or marker not in PROFILES or index != 0 or name != canonical_schema(marker)[0]["name"]:
                raise InputError("Only the built-in extraction profiles are supported, on their canonical identifier field.")
            field["profile"] = marker
        if item.get("pattern"):
            raise InputError("Regular expression mappings are disabled. Use labels, aliases or a page region.")
        aliases = item.get("aliases", [])
        if not isinstance(aliases, list) or len(aliases) > 20 or any(not isinstance(a, str) or len(a) > 200 for a in aliases):
            raise InputError("Aliases must be a list of at most 20 short labels.")
        field["aliases"] = aliases
        if kind == "choice":
            choices = item.get("choices", {})
            if not isinstance(choices, dict) or not 1 <= len(choices) <= 100:
                raise InputError(f"Add answer codes and labels for {name}.")
            if any(not isinstance(k, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,40}", k) or not isinstance(v, str) or len(v) > 200 for k, v in choices.items()):
                raise InputError("Invalid answer code or label.")
            field["choices"] = choices
        for key in ("min", "max"):
            if key in item:
                value = item[key]
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                    raise InputError("Numeric bounds must be finite numbers.")
                field[key] = value
        if field.get("min", -math.inf) > field.get("max", math.inf):
            raise InputError("Minimum cannot exceed maximum.")
        if "region" in item:
            region = item["region"]
            if not isinstance(region, dict) or type(region.get("page")) is not int or not 1 <= region["page"] <= MAX_PAGES:
                raise InputError(f"Regions need a page number from 1 to {MAX_PAGES}.")
            for key in ("x", "y", "width", "height"):
                n = region.get(key)
                if isinstance(n, bool) or not isinstance(n, (int, float)) or not math.isfinite(n) or not 0 <= n <= 1:
                    raise InputError("Region coordinates must be normalized numbers from 0 to 1.")
            if region["width"] <= 0 or region["height"] <= 0 or region["x"] + region["width"] > 1.000001 or region["y"] + region["height"] > 1.000001:
                raise InputError("Region must fit inside the page.")
            field["region"] = {k: region[k] for k in ("page", "x", "y", "width", "height")}
        names.add(name)
        result.append(field)
    if result[0]["type"] != "text":
        raise InputError("The first field must be the REDCap record identifier with type text.")
    result[0]["required"] = True
    if is_profile(result):
        canonical = {f["name"]: f for f in canonical_schema(profile_id(result))}
        if {f["name"]: f["type"] for f in result} != {name: f["type"] for name, f in canonical.items()}:
            raise InputError("The built-in extraction profile requires its complete canonical field set and types.")
        for field in result:
            builtin = canonical[field["name"]]
            field["label"] = builtin["label"]
            field["aliases"] = []
            field.pop("region", None)
            field["required"] = builtin["required"]
            for key in ("min", "max", "choices", "sourceDateFormat"):
                field.pop(key, None)
                if key in builtin:
                    field[key] = builtin[key]
        indexed = {field["name"]: field for field in result}
        result = [indexed[name] for name in canonical]
    return result


def schema_from_csv(text):
    if not isinstance(text, str) or len(text.encode("utf-8")) > MAX_SCHEMA_BYTES:
        raise InputError("Mapping files must be UTF-8 text of at most 1 MiB.")
    try:
        rows = list(csv.DictReader(io.StringIO(text.lstrip("\ufeff"))))
    except csv.Error as exc:
        raise InputError("Invalid CSV dictionary.") from exc
    if not rows:
        raise InputError("A REDCap data dictionary must contain field rows. Use JSON for a headers-only template.")
    first = rows[0]
    if "Variable / Field Name" not in first:
        raise InputError("Expected a REDCap data dictionary CSV with Variable / Field Name and Field Type columns.")
    fields, warnings = [], []
    for row in rows:
        name, kind = row.get("Variable / Field Name", "").strip(), row.get("Field Type", "").strip()
        if kind in {"descriptive", "file", "calc", "sql"}:
            warnings.append(f"Skipped unsupported {kind} field {name}.")
            continue
        if kind not in {"text", "notes", "radio", "dropdown", "checkbox", "yesno", "truefalse", "slider"}:
            warnings.append(f"Skipped unsupported field type for {name}.")
            continue
        field = {"name": name, "label": row.get("Field Label", name).strip() or name, "required": row.get("Required Field?", "").strip().lower() == "y", "type": "text"}
        validation = row.get("Text Validation Type OR Show Slider Number", "").strip()
        if row.get("Branching Logic (Show field only if...)", "").strip():
            warnings.append(f"Branching logic for {name} is not evaluated. Review applicability manually.")
            field["required"] = False
        if kind in {"radio", "dropdown", "checkbox", "yesno", "truefalse"}:
            if kind in {"yesno", "truefalse"}:
                choices = {"1": "Yes" if kind == "yesno" else "True", "0": "No" if kind == "yesno" else "False"}
            else:
                choices = {}
                for part in row.get("Choices, Calculations, OR Slider Labels", "").split("|"):
                    code, sep, label = part.partition(",")
                    if not sep:
                        raise InputError(f"Invalid choice definition for {name}.")
                    choices[code.strip()] = label.strip()
            if kind == "checkbox":
                for code, label in choices.items():
                    if not re.fullmatch(r"[a-z0-9]+", code):
                        raise InputError("Checkbox codes must contain lowercase letters and digits in this prototype.")
                    fields.append({**field, "name": f"{name}___{code}", "label": f"{field['label']} ({label})", "type": "choice", "choices": {"0": "Unchecked", "1": "Checked"}, "required": False})
                continue
            field.update(type="choice", choices=choices)
        elif validation == "integer":
            field["type"] = "integer"
        elif validation.startswith("number") or kind == "slider":
            field["type"] = "number"
        elif validation in {"date_ymd", "date_mdy"}:
            field["type"] = "date"
            if validation == "date_mdy":
                field["sourceDateFormat"] = "mdy"
        elif validation:
            warnings.append(f"Validation {validation} for {name} uses text. Verify its format manually.")
        for bound, col in (("min", "Text Validation Min"), ("max", "Text Validation Max")):
            if row.get(col, "").strip() and field["type"] in {"integer", "number"}:
                try:
                    field[bound] = float(row[col])
                except ValueError as exc:
                    raise InputError(f"Invalid bound for {name}.") from exc
        fields.append(field)
    return parse_schema(fields), warnings


def validate_values(schema, values, record=None):
    errors = {}
    active = applicable_fields(schema, values, record)
    for field in schema:
        name = field["name"]
        value = values.get(name, "")
        if not isinstance(value, str) or len(value) > 4000:
            errors[name] = "Use text with no more than 4,000 characters."
            continue
        if not value.strip():
            if field["required"] and name in active and not confirmed_source_blank(schema, name, record):
                errors[name] = "This field is required."
            continue
        kind = field["type"]
        if kind in {"integer", "number"}:
            try:
                if (kind == "integer" and not re.fullmatch(r"-?[0-9]+", value)) or (kind == "number" and not DECIMAL.fullmatch(value)):
                    raise ValueError
                number = Decimal(value)
                if not number.is_finite() or ("min" in field and number < Decimal(str(field["min"]))) or ("max" in field and number > Decimal(str(field["max"]))):
                    raise ValueError
            except (ValueError, InvalidOperation):
                errors[name] = "Use a valid number within the configured range."
        elif kind == "date":
            try:
                if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
                    raise ValueError
                dt.date.fromisoformat(value)
            except ValueError:
                errors[name] = "Use a real date in YYYY-MM-DD format."
        elif kind == "choice" and value not in field["choices"]:
            errors[name] = "Select a configured answer code."
        elif kind == "text" and value.lstrip().startswith(("=", "+", "-", "@")):
            errors[name] = "Text cannot start with a spreadsheet formula character."
        if name == schema[0]["name"] and not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,99}", value):
            errors[name] = "Use a record ID with letters, numbers, dots, underscores or hyphens."
        if any(ord(c) < 32 and c not in "\n\r\t" for c in value):
            errors[name] = "Control characters are not allowed."
    errors.update(validate_profile_values(schema, values, record))
    return errors


class Workspace:
    def __init__(self, assets, schema=None):
        self.assets = Path(assets)
        self.schema = parse_schema(json.loads((ROOT / "samples/sample-schema.json").read_text())) if schema is None else schema
        self.records = []
        self.activity = []
        self.reviewer = ""
        self.schema_warnings = []
        self.lock = threading.RLock()
        self.jobs = set()
        self.jobs_lock = threading.Lock()
        self.template = None
        self.template_data = None
        self.template_revision = 0

    def log(self, message):
        self.activity.insert(0, {"time": now(), "message": message})
        self.activity = self.activity[:500]

    def state(self):
        return {"schema": self.schema, "records": self.records, "activity": self.activity, "reviewer": self.reviewer, "schemaWarnings": self.schema_warnings, "capabilities": capabilities(), "template": self.template, "templatePreview": self.template_preview(), "sampleTemplates": self.sample_templates()}

    @staticmethod
    def sample_templates():
        return [{"name": "redcap", "label": "REDCap template", "format": "xlsx"}, {"name": "friendly", "label": "Friendly intake template", "format": "xlsx"}, {"name": "csv", "label": "REDCap CSV template", "format": "csv"}]

    def local_job(self, script, payload, timeout):
        options = process_options()
        kind = {"template_worker.py": "template", "bundle_worker.py": "bundle"}[script]
        process = subprocess.Popen(worker_command(kind), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, **options)
        with self.jobs_lock:
            self.jobs.add(process)
        try:
            stdout, _ = process.communicate(json.dumps(payload), timeout=timeout)
            if process.returncode:
                raise InputError(f"The local {kind} worker failed. Check the file and installed requirements.")
            result = strict_json_loads(stdout)
            if "error" in result:
                raise InputError(result["error"])
            return result["result"]
        except subprocess.TimeoutExpired as exc:
            terminate_tree(process)
            process.communicate()
            raise InputError(f"Local {kind} processing exceeded its {timeout}-second limit.") from exc
        finally:
            with self.jobs_lock:
                self.jobs.discard(process)

    def import_template(self, data, filename, sheet=None, header_row=None, spec_validator=None):
        if not isinstance(filename, str) or len(filename) > 200 or any(c in filename for c in "\x00\r\n"):
            raise InputError("Invalid template filename.")
        filename = filename.replace("\\", "/").split("/")[-1]
        if not data or len(data) > 4 * 1024 * 1024:
            raise InputError("Templates must be nonempty files up to 4 MB.")
        spec = self.local_job("template_worker.py", {"operation": "inspect", "data": base64.b64encode(data).decode(), "filename": filename, "sheet": sheet, "headerRow": header_row}, 30)
        if spec_validator is not None:
            spec_validator(spec)
        self.template_revision += 1
        self.template = {**spec, "id": secrets.token_hex(12), "name": filename, "mappings": {}, "confirmed": False, "revision": self.template_revision, "suggestions": suggested_mapping(spec, self.schema)}
        self.template_data = data
        self.log("Spreadsheet template loaded. Column assignments require review.")

    def clear_template(self):
        self.template_revision += 1
        self.template, self.template_data = None, None

    def check_template_revision(self, expected):
        if not self.template:
            raise InputError("Load a spreadsheet template first.")
        if isinstance(expected, str) and re.fullmatch(r"[0-9]{1,12}", expected):
            expected = int(expected)
        if type(expected) is not int or expected != self.template["revision"]:
            raise ConflictError("This spreadsheet mapping changed. Reload its preview before continuing.")

    def set_template_mapping(self, mappings, confirmed, expected_revision):
        if self.template is None:
            raise InputError("Load a spreadsheet template first.")
        if type(expected_revision) is not int or expected_revision != self.template["revision"]:
            raise ConflictError("This mapping changed in another tab. Reload before saving.")
        if type(confirmed) is not bool:
            raise InputError("Mapping confirmation must be true or false.")
        if not isinstance(mappings, dict) or any(not isinstance(k, str) or (v is not None and not isinstance(v, str)) for k, v in mappings.items()):
            raise InputError("Column assignments must contain field names or explicit blank values.")
        columns = {column["name"] for column in self.template["columns"]}
        source_names = {field["name"] for field in self.schema}
        if set(mappings) - columns or any(value is not None and value not in source_names for value in mappings.values()):
            raise InputError("The column mapping contains unknown fields or columns.")
        result = validate_mapping(self.template, self.schema, mappings)
        if confirmed and not result["valid"]:
            raise InputError("Complete and correct every column assignment before confirmation. " + " ".join(result["errors"])[:300])
        self.template_revision += 1
        self.template.update(mappings=dict(mappings), confirmed=confirmed, revision=self.template_revision)
        self.log("Spreadsheet column mapping confirmed." if confirmed else "Spreadsheet column mapping saved as a draft.")

    def invalidate_template_mapping(self):
        if self.template is not None:
            self.template_revision += 1
            names = {field["name"] for field in self.schema}
            self.template.update(confirmed=False, revision=self.template_revision, mappings={key: value for key, value in self.template["mappings"].items() if value is None or value in names}, suggestions=suggested_mapping(self.template, self.schema))

    def touch_template_preview(self):
        if self.template is not None:
            self.template_revision += 1
            self.template["revision"] = self.template_revision

    def template_preview(self):
        if self.template is None:
            return None
        result = validate_mapping(self.template, self.schema, self.template["mappings"])
        errors = list(result["errors"])
        rows = []
        for record in self.records:
            values = {column["name"]: record["values"].get(self.template["mappings"].get(column["name"]), "") for column in self.template["columns"]}
            record_errors = [f"{name}: {error}" for name, error in validate_values(self.schema, record["values"], record).items()]
            rows.append({"id": record["id"], "status": record["status"], "values": values, "errors": record_errors, "recordId": record["values"].get(self.schema[0]["name"], "") if self.schema else ""})
        if not self.template["confirmed"]:
            errors.append("Review and confirm the column mapping before export.")
        try:
            self.approved_records()
        except InputError as exc:
            errors.append(str(exc))
        return {"columns": self.template["columns"], "rows": rows, "errors": errors, "unmapped": result.get("unmapped", []), "identifierColumn": result.get("identifierColumn"), "ready": not errors, "approvedCount": sum(record["status"] == "approved" for record in self.records)}

    def template_export(self, export_format):
        if not self.template:
            raise InputError("Load a spreadsheet template first.")
        if export_format not in {"csv", "xlsx"}:
            raise InputError("Choose XLSX or CSV export.")
        mapping = validate_mapping(self.template, self.schema, self.template["mappings"])
        if not self.template["confirmed"] or not mapping["valid"]:
            raise InputError("Save and confirm a complete column mapping before export.")
        records = self.approved_records()
        output = self.local_job("template_worker.py", {"operation": "fill", "data": base64.b64encode(self.template_data).decode(), "filename": self.template["name"], "spec": self.template, "mappings": self.template["mappings"], "schema": self.schema, "rows": [record["values"] for record in records], "exportFormat": export_format}, 30)
        data = base64.b64decode(output["data"], validate=True)
        self.log(f"Exported {len(records)} approved records into the spreadsheet template.")
        return data

    def clear_assets(self):
        for path in self.assets.iterdir():
            if path.is_dir():
                shutil.rmtree(path)

    def prune_assets(self):
        active = {r["id"] for r in self.records}
        for path in self.assets.iterdir():
            if path.is_dir() and path.name not in active:
                shutil.rmtree(path)

    def process(self, data, filename, schema, rid):
        request = {"data": base64.b64encode(data).decode(), "filename": filename, "schema": schema, "assetDir": str(self.assets), "recordId": rid}
        process = None
        try:
            options = process_options()
            process = subprocess.Popen(worker_command("document"), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, **options)
            with self.jobs_lock:
                self.jobs.add(process)
            stdout, _ = process.communicate(json.dumps(request), timeout=180)
            if process.returncode:
                raise InputError("Document processing failed within the local worker. Check the file and try again.")
            output = json.loads(stdout)
            if "error" in output:
                raise InputError(output["error"])
            return output
        except subprocess.TimeoutExpired as exc:
            terminate_tree(process)
            process.communicate()
            raise InputError("Document processing exceeded the 180-second limit.") from exc
        finally:
            if process is not None:
                with self.jobs_lock:
                    self.jobs.discard(process)
            if sys.exc_info()[0] and (self.assets / rid).is_dir():
                shutil.rmtree(self.assets / rid)

    def stop_jobs(self):
        with self.jobs_lock:
            for process in list(self.jobs):
                terminate_tree(process)

    def add(self, data, filename, origin="upload"):
        if len(self.records) >= MAX_RECORDS:
            raise InputError("This session supports at most 60 documents. Save a project and start a new session.")
        if not isinstance(filename, str) or len(filename) > 200 or any(c in filename for c in "\x00\r\n"):
            raise InputError("Invalid filename.")
        filename = filename.replace("\\", "/").split("/")[-1]
        if len(data) > MAX_FILE:
            raise InputError("Each document must be 12 MB or smaller.")
        source_hash = hashlib.sha256(data).hexdigest()
        if is_profile(self.schema) and any(r["sourceHash"] == source_hash for r in self.records):
            raise InputError("This exact source document is already in the queue; duplicate files are not added.")
        if source_bytes(self.records) + len(data) > MAX_SESSION_BYTES:
            raise InputError("This session is limited to 20 MB of source documents. Save this project before starting another batch.")
        rid = secrets.token_hex(12)
        output = self.process(data, filename, self.schema, rid)
        record = {**output, "id": rid, "filename": filename, "origin": origin, "status": "review", "confirmed": [], "updatedAt": now(), "sourceHash": source_hash, "sourceData": base64.b64encode(data).decode(), "reviewedBy": "", "revision": 1}
        record["values"] = {f["name"]: str(output.get("values", {}).get(f["name"], "")) for f in self.schema}
        if len(json.dumps([r["values"] for r in self.records] + [record["values"]], ensure_ascii=True).encode()) > MAX_VALUE_BYTES:
            shutil.rmtree(self.assets / rid, ignore_errors=True)
            raise InputError("Extracted review text exceeds the 4 MB session limit.")
        record["validationErrors"] = validate_values(self.schema, record["values"], record)
        self.records.append(record)
        self.touch_template_preview()
        self.log("Document added for review.")
        return record

    def review(self, body):
        if not self.schema:
            raise InputError("Apply an extraction type before reviewing or approving documents.")
        record = next((r for r in self.records if r["id"] == body.get("id")), None)
        if not record:
            raise InputError("Document not found.")
        if "expectedRevision" in body and (type(body["expectedRevision"]) is not int or body["expectedRevision"] != record["revision"]):
            raise ConflictError("This record changed in another tab. Reload before saving.")
        supplied = body.get("values")
        names = {f["name"] for f in self.schema}
        if not isinstance(supplied, dict) or set(supplied) != names:
            raise InputError("Values must include exactly the configured fields.")
        confirmed = body.get("confirmed", [])
        if not isinstance(confirmed, list) or any(not isinstance(f, str) or f not in names for f in confirmed):
            raise InputError("Invalid field confirmation list.")
        if any(not isinstance(v, str) or len(v) > 4000 for v in supplied.values()):
            raise InputError("Field values must be text up to 4,000 characters.")
        values = {k: v.strip() for k, v in supplied.items()}
        others = [r["values"] for r in self.records if r["id"] != record["id"]]
        if len(json.dumps(others + [values], ensure_ascii=True).encode()) > MAX_VALUE_BYTES:
            raise InputError("Review text exceeds the 4 MB session limit.")
        active = applicable_fields(self.schema, values, record)
        review_context = {**record, "confirmed": sorted(set(confirmed) & active)}
        errors = validate_values(self.schema, values, review_context)
        if is_neurology_profile(self.schema) and values.get("document_id") != "DOC" + record["sourceHash"][:24]:
            errors["document_id"] = "Keep this source document's derived identifier."
        if is_neurology_profile(self.schema) and values.get("instrument_family") != record.get("sourceInstrumentFamily", ""):
            errors["instrument_family"] = "Keep the instrument family identified by the source form code; changing it cannot hide required fields."
        reviewer = body.get("reviewer", "")
        if not isinstance(reviewer, str) or len(reviewer) > 100:
            raise InputError("Reviewer name must contain no more than 100 characters.")
        approve = body.get("approve") is True
        if approve:
            if errors:
                raise InputError("Correct invalid or missing values before approval.")
            if not active <= set(confirmed):
                raise InputError("Confirm every field against the source before approval.")
            if not reviewer.strip():
                raise InputError("Enter a reviewer name before approval.")
            if is_neurology_profile(self.schema):
                if record.get("profileBlockingIssues"):
                    raise InputError("Conflicting patient identity values occur within this source; resolve the source before approval.")
                if any(g["conflict"] and record["id"] in g["recordIds"] for g in patient_groups(self.records, (record["id"], values))):
                    raise InputError("This MRN group has conflicting patient names or birth dates. Resolve identity against the sources before approval.")
            if source_blocking_issues(self.schema, record, values):
                raise InputError("PACE source identity or instrument issues prevent approval. Review the original sources.")
            identifier = self.schema[0]["name"]
            if any(r["id"] != record["id"] and r["status"] == "approved" and r["values"][identifier] == values[identifier] for r in self.records):
                raise InputError("Another approved document has this record ID.")
        record.update(values=values, confirmed=sorted(set(confirmed) & active), validationErrors=errors, status="approved" if approve else "review", reviewedBy=reviewer.strip() if approve else "", updatedAt=now(), revision=record["revision"] + 1)
        if is_profile(self.schema):
            record["applicableFields"] = sorted(active)
        self.touch_template_preview()
        self.reviewer = reviewer.strip()
        self.log("Record approved for export." if approve else "Review draft saved. Approval cleared.")

    def set_schema(self, schema, warnings=None, cancel_check=None):
        staged = []
        try:
            for record in self.records:
                if cancel_check:
                    cancel_check()
                new_id = secrets.token_hex(12)
                output = self.process(base64.b64decode(record["sourceData"]), record["filename"], schema, new_id)
                changed = {key: value for key, value in record.items() if key not in {"applicableFields", "sourceContext", "sourceInstrumentFamily", "profileBlockingIssues"}}
                changed.update(output, id=new_id, status="review", confirmed=[], reviewedBy="", updatedAt=now())
                changed["validationErrors"] = validate_values(schema, changed["values"], changed)
                staged.append(changed)
            if len(json.dumps([r["values"] for r in staged], ensure_ascii=True).encode()) > MAX_VALUE_BYTES:
                raise InputError("Remapped review text exceeds the 4 MB session limit.")
            if cancel_check:
                cancel_check()
        except Exception:
            self.prune_assets()
            raise
        self.schema, self.records = schema, staged
        self.prune_assets()
        self.schema_warnings = warnings or []
        self.invalidate_template_mapping()
        self.log("Field mapping changed. Documents reprocessed and approvals cleared.")

    def approved_records(self):
        if not self.schema:
            raise InputError("Apply an extraction type before exporting documents.")
        records = [r for r in self.records if r["status"] == "approved"]
        if not records:
            raise InputError("Approve at least one record before export.")
        seen = set()
        if is_neurology_profile(self.schema) and any(group["conflict"] for group in patient_groups(self.records)):
            raise InputError("Conflicting patient identities in an MRN group prevent export; resolve them against the sources.")
        source_hashes = set()
        for record in records:
            if validate_values(self.schema, record["values"], record) or set(record["confirmed"]) != applicable_fields(self.schema, record["values"], record) or not record["reviewedBy"]:
                raise InputError("A record no longer satisfies the approval requirements.")
            if is_neurology_profile(self.schema):
                if record.get("profileBlockingIssues") or record["values"]["document_id"] != "DOC" + record["sourceHash"][:24] or record["values"].get("instrument_family") != record.get("sourceInstrumentFamily", ""):
                    raise InputError("A document no longer satisfies its source identity requirements.")
            if is_profile(self.schema):
                if source_blocking_issues(self.schema, record, record["values"]):
                    raise InputError("A patient no longer satisfies its PACE source identity requirements.")
                if record["sourceHash"] in source_hashes:
                    raise InputError("Duplicate source documents cannot be exported.")
                source_hashes.add(record["sourceHash"])
            identifier = record["values"][self.schema[0]["name"]]
            if identifier in seen:
                raise InputError("Duplicate record IDs cannot be exported.")
            seen.add(identifier)
        return records

    def export(self):
        records = self.approved_records()
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=[f["name"] for f in self.schema], lineterminator="\r\n")
        writer.writeheader()
        writer.writerows(r["values"] for r in records)
        self.log(f"Exported {len(records)} approved records to CSV.")
        return output.getvalue().encode("utf-8-sig")


class Server(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 8

    def __init__(self, address, workspace):
        super().__init__(address, Handler)
        self.workspace = workspace
        self.csrf = secrets.token_urlsafe(32)
        self.session = secrets.token_urlsafe(32)
        self.request_slots = threading.BoundedSemaphore(16)

    def process_request(self, request, address):
        if not self.request_slots.acquire(blocking=False):
            try:
                request.sendall(b"HTTP/1.1 503 Service Unavailable\r\nConnection: close\r\nContent-Length: 0\r\n\r\n")
            finally:
                self.shutdown_request(request)
            return
        try:
            super().process_request(request, address)
        except Exception:
            self.request_slots.release()
            raise

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.request_slots.release()


class Handler(BaseHTTPRequestHandler):
    server_version = "Formbridge"
    sys_version = ""

    def log_message(self, *_):
        pass

    def setup(self):
        super().setup()
        self.connection.settimeout(30)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' blob:; frame-src 'self' blob:; object-src 'none'; connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        super().end_headers()

    def respond(self, payload, status=200, content_type="application/json", filename=None):
        if isinstance(payload, (dict, list)):
            payload = json.dumps(payload, ensure_ascii=True).encode()
        elif isinstance(payload, str):
            payload = payload.encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        try:
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def guard(self, mutation=False):
        target = urlsplit(self.path)
        if target.scheme or target.netloc or not self.path.startswith("/"):
            self.respond({"error": "Invalid request target."}, 400)
            return False
        port = self.server.server_port
        allowed = {f"127.0.0.1:{port}", f"localhost:{port}"}
        if self.headers.get("Host") not in allowed:
            self.respond({"error": "Only local requests are allowed."}, 403)
            return False
        origin = self.headers.get("Origin")
        if origin and origin not in {f"http://{h}" for h in allowed}:
            self.respond({"error": "Foreign origins are blocked."}, 403)
            return False
        if self.headers.get("Sec-Fetch-Site") == "cross-site":
            self.respond({"error": "Cross-site requests are blocked."}, 403)
            return False
        if self.path.split("?")[0].startswith("/api/"):
            cookie = SimpleCookie()
            try:
                cookie.load(self.headers.get("Cookie", ""))
            except Exception:
                self.respond({"error": "Invalid session."}, 403)
                return False
            token = cookie.get("formbridge_session")
            if not token or not secrets.compare_digest(token.value, self.server.session):
                self.respond({"error": "Open the app to start a local session."}, 403)
                return False
        if mutation and not secrets.compare_digest(self.headers.get("X-CSRF-Token", ""), self.server.csrf):
            self.respond({"error": "Invalid session token. Reload the app."}, 403)
            return False
        return True

    def state(self):
        state = self.server.workspace.state()
        state = {**state, "records": [public_record(r) for r in state["records"]], "csrfToken": self.server.csrf}
        return state

    def do_GET(self):
        if not self.guard():
            return
        path = urlsplit(self.path).path
        ws = self.server.workspace
        try:
            with ws.lock:
                if path == "/api/state":
                    return self.respond(self.state())
                if path == "/api/health":
                    caps = capabilities()
                    return self.respond({**caps, "ocrAvailable": caps.get("ocr", False)})
                if path == "/api/export":
                    return self.respond(ws.export(), content_type="text/csv; charset=utf-8", filename="redcap-reviewed.csv")
                if path == "/api/templates/samples":
                    return self.respond(ws.sample_templates())
                if path == "/api/template/export":
                    query = parse_qs(urlsplit(self.path).query)
                    ws.check_template_revision(query.get("expectedRevision", [None])[0])
                    export_format = query.get("format", [ws.template["format"]])[0]
                    payload = ws.template_export(export_format)
                    kind = "text/csv; charset=utf-8" if export_format == "csv" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    return self.respond(payload, content_type=kind, filename=f"mapped-reviewed.{export_format}")
                if path == "/api/template/original":
                    if not ws.template:
                        raise InputError("Load a spreadsheet template first.")
                    return self.respond(ws.template_data, content_type="application/octet-stream", filename=f"blank-template.{ws.template['format']}")
                if path == "/api/project":
                    records = [project_record(r) for r in ws.records]
                    project = {"format": "formbridge-project-v1", "schema": ws.schema, "records": records, "exportedAt": now()}
                    if ws.template:
                        project["template"] = {"filename": ws.template["name"], "sourceData": base64.b64encode(ws.template_data).decode(), "sheet": ws.template["sheet"], "headerRow": ws.template["headerRow"], "mappings": ws.template["mappings"]}
                    if len(json.dumps(project, ensure_ascii=True).encode()) > MAX_BODY:
                        raise InputError("The saved project would exceed the import limit. Export a smaller batch.")
                    return self.respond(project, filename="formbridge-project.json")
                if path.startswith("/api/source/"):
                    record = next((r for r in ws.records if r["id"] == path.rsplit("/", 1)[-1]), None)
                    if record:
                        return self.respond(base64.b64decode(record["sourceData"]), content_type="application/octet-stream", filename="source" + Path(record["filename"]).suffix.lower())
                if path.startswith("/api/crop/"):
                    parts = path.split("/")
                    if len(parts) == 5:
                        rid, field_name = parts[3:]
                        record = next((r for r in ws.records if r["id"] == rid), None)
                        field = next((f for f in ws.schema if f["name"] == field_name), None)
                        if record and field:
                            evidence = record.get("evidence", {}).get(field_name)
                            region = evidence["region"] if evidence else field.get("region")
                            page = evidence["page"] if evidence else (region or {}).get("page")
                            if region and page:
                                image_path = ws.assets / rid / f"page-{page}.png"
                                if image_path.is_file():
                                    with Image.open(image_path) as image:
                                        w, h = image.size
                                        box = (max(0, int(region["x"] * w) - 6), max(0, int(region["y"] * h) - 6), min(w, int((region["x"] + region["width"]) * w) + 6), min(h, int((region["y"] + region["height"]) * h) + 6))
                                        output = io.BytesIO()
                                        image.crop(box).save(output, "PNG")
                                    return self.respond(output.getvalue(), content_type="image/png", filename=f"region-{field_name}.png")
                match = ASSET.fullmatch(path)
                if match and any(r["id"] == match[1] for r in ws.records):
                    asset = ws.assets / match[1] / match[2]
                    if asset.is_file():
                        return self.respond(asset.read_bytes(), content_type="image/png")
                if path.startswith("/api/demo-source/"):
                    record = next((r for r in ws.records if r["id"] == path.rsplit("/", 1)[-1]), None)
                    if record and record.get("previewUrl"):
                        asset = ws.assets / record["id"] / "page-1.png"
                        return self.respond(asset.read_bytes(), content_type="image/png")
                static = {"/": ("index.html", "text/html; charset=utf-8"), "/index.html": ("index.html", "text/html; charset=utf-8"), "/app.js": ("app.js", "text/javascript; charset=utf-8"), "/styles.css": ("styles.css", "text/css; charset=utf-8"), "/regions.css": ("regions.css", "text/css; charset=utf-8"), "/template-ui.js": ("template-ui.js", "text/javascript; charset=utf-8"), "/template-ui.css": ("template-ui.css", "text/css; charset=utf-8")}
                if path in static:
                    file, kind = static[path]
                    payload = (ROOT / "static" / file).read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", kind)
                    self.send_header("Content-Length", str(len(payload)))
                    if kind.startswith("text/html"):
                        self.send_header("Set-Cookie", f"formbridge_session={self.server.session}; HttpOnly; SameSite=Strict; Path=/")
                    self.end_headers()
                    self.wfile.write(payload)
                    return
                self.respond({"error": "Not found."}, 404)
        except InputError as exc:
            self.respond({"error": str(exc)}, 409 if isinstance(exc, ConflictError) else 400)
        except Exception:
            self.respond({"error": "The request could not be completed."}, 500)

    def do_POST(self):
        if not self.guard(mutation=True):
            self.close_connection = True
            return
        try:
            if self.headers.get("Transfer-Encoding") or len(self.headers.get_all("Content-Length", [])) != 1:
                self.close_connection = True
                return self.respond({"error": "Use one explicit Content-Length header without transfer encoding."}, 400)
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY:
                self.close_connection = True
                return self.respond({"error": "Request must be between 1 byte and 40 MB."}, 413)
            if self.headers.get_content_type() != "application/json":
                return self.respond({"error": "Use JSON requests."}, 415)
            body = strict_json_loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise InputError("Expected a JSON object.")
            ws = self.server.workspace
            path = urlsplit(self.path).path
            with ws.lock:
                if path == "/api/upload":
                    encoded = body.get("data", "")
                    if not isinstance(encoded, str) or len(encoded) > MAX_FILE * 1.4:
                        raise InputError("Document is too large.")
                    ws.add(base64.b64decode(encoded, validate=True), body.get("filename", ""))
                elif path == "/api/record":
                    if "expectedRevision" not in body:
                        raise ConflictError("Reload this record before saving so its current revision is included.")
                    ws.review(body)
                elif path == "/api/template/import":
                    encoded = body.get("data")
                    if not isinstance(encoded, str) or len(encoded) > 6 * 1024 * 1024:
                        raise InputError("Templates must be 4 MB or smaller.")
                    ws.import_template(base64.b64decode(encoded, validate=True), body.get("filename", ""), body.get("sheet"), body.get("headerRow"))
                elif path == "/api/template/sample":
                    samples = {"redcap": "redcap-template.xlsx", "friendly": "friendly-template.xlsx", "csv": "redcap-template.csv"}
                    name = body.get("name")
                    if not isinstance(name, str) or name not in samples:
                        raise InputError("Choose a built-in spreadsheet template.")
                    filename = samples[name]
                    ws.import_template((ROOT / "spreadsheets" / filename).read_bytes(), filename)
                elif path == "/api/template/configure":
                    if not ws.template:
                        raise InputError("Load a spreadsheet template first.")
                    ws.check_template_revision(body.get("expectedRevision"))
                    ws.import_template(ws.template_data, ws.template["name"], body.get("sheet"), body.get("headerRow"))
                elif path == "/api/template/mapping":
                    ws.set_template_mapping(body.get("mappings"), body.get("confirmed", False), body.get("expectedRevision"))
                elif path == "/api/template/clear":
                    ws.check_template_revision(body.get("expectedRevision"))
                    ws.clear_template()
                    ws.log("Spreadsheet template cleared.")
                elif path == "/api/demo":
                    if len(ws.records) + 10 > MAX_RECORDS:
                        raise InputError("Not enough room for ten practice forms.")
                    original = list(ws.records)
                    try:
                        for sample in sorted((ROOT / "samples").glob("practice-*.pdf")):
                            ws.add(sample.read_bytes(), sample.name, "demo")
                    except Exception:
                        ws.records = original
                        ws.prune_assets()
                        raise
                    ws.log("Ten fictional practice forms processed through the document pipeline.")
                elif path == "/api/schema":
                    ws.set_schema(parse_schema(body.get("schema", body)))
                elif path == "/api/schema/import":
                    text, filename = body.get("text"), body.get("filename", "")
                    if not isinstance(text, str) or len(text.encode("utf-8")) > MAX_SCHEMA_BYTES:
                        raise InputError("Mapping files must be UTF-8 text of at most 1 MiB.")
                    if filename.lower().endswith(".csv"):
                        fields, warnings = schema_from_csv(text)
                    else:
                        fields, warnings = parse_schema(strict_json_loads(text)), []
                    ws.set_schema(fields, warnings)
                elif path == "/api/project":
                    self.import_project(body, ws)
                elif path == "/api/reset":
                    ws.records = []
                    ws.reviewer = ""
                    ws.activity = []
                    ws.clear_template()
                    ws.clear_assets()
                    ws.log("Workspace reset. Temporary source images removed.")
                else:
                    return self.respond({"error": "Not found."}, 404)
                self.respond(self.state())
        except (InputError, ValueError, binascii.Error, UnicodeError) as exc:
            self.respond({"error": str(exc)[:500]}, 409 if isinstance(exc, ConflictError) else 400)
        except Exception:
            self.respond({"error": "Document processing failed. Use a supported PDF, PNG, JPEG or UTF-8 text file."}, 400)

    def import_project(self, body, ws):
        if body.get("format") != "formbridge-project-v1":
            raise InputError("Unrecognized project format.")
        schema = parse_schema(body.get("schema"))
        records = body.get("records")
        if not isinstance(records, list) or len(records) > MAX_RECORDS:
            raise InputError("Invalid project document list.")
        staged = Workspace(ws.assets)
        staged.schema = schema
        try:
            for record in records:
                if not isinstance(record, dict) or not isinstance(record.get("sourceData"), str):
                    raise InputError("Each project document needs its original source.")
                if "bundleSources" in record or "bundleRecordId" in record:
                    raise InputError("Open patient source bundle projects in the native desktop app.")
                added = staged.add(base64.b64decode(record["sourceData"], validate=True), record.get("filename", ""))
                values = record.get("values", {})
                if not isinstance(values, dict) or set(values) != {f["name"] for f in schema} or any(not isinstance(v, str) or len(v) > 4000 for v in values.values()):
                    raise InputError("Invalid project values.")
                added["values"] = values
                added["validationErrors"] = validate_values(schema, values, added)
                if len(json.dumps([r["values"] for r in staged.records], ensure_ascii=True).encode()) > MAX_VALUE_BYTES:
                    raise InputError("Project review text exceeds the 4 MB session limit.")
            template = body.get("template")
            if template is not None:
                if not isinstance(template, dict) or not isinstance(template.get("sourceData"), str) or len(template["sourceData"]) > 6 * 1024 * 1024:
                    raise InputError("Invalid saved spreadsheet template.")
                staged.import_template(base64.b64decode(template["sourceData"], validate=True), template.get("filename", ""), template.get("sheet"), template.get("headerRow"))
                staged.set_template_mapping(template.get("mappings", {}), False, staged.template["revision"])
        except Exception:
            ws.prune_assets()
            raise
        ws.schema, ws.records = staged.schema, staged.records
        ws.template_revision += 1
        ws.template, ws.template_data = staged.template, staged.template_data
        if ws.template:
            ws.template.update(revision=ws.template_revision, confirmed=False)
        ws.prune_assets()
        ws.schema_warnings = []
        ws.reviewer = ""
        ws.log("Project loaded. All fields require fresh confirmation and approval.")


def main():
    parser = argparse.ArgumentParser(description="Local fictional-data form review prototype")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Use a port from 1024 to 65535.")
    with tempfile.TemporaryDirectory(prefix="formbridge-") as directory:
        try:
            os.chmod(directory, 0o700)
        except OSError:
            pass
        workspace = Workspace(directory)
        server = Server(("127.0.0.1", args.port), workspace)
        print(f"Formbridge is ready at http://127.0.0.1:{args.port}", flush=True)
        print("Fictional data only. Press Ctrl+C to stop and remove temporary files.", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            workspace.stop_jobs()
            server.server_close()


if __name__ == "__main__":
    main()
