"""Synchronous local desktop adapter; callers serialize mutations on one thread.

No listener is created. Original sources live only in the canonical Workspace and
its private, temporary asset root until an explicit project save.
"""
from __future__ import annotations

import base64
import binascii
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import threading
import uuid
from typing import Callable

from branding import PRODUCT_NAME
from server import (Workspace, InputError, ConflictError, MAX_BODY, MAX_FILE,
                    MAX_RECORDS, MAX_VALUE_BYTES, MAX_SESSION_BYTES, parse_schema, schema_from_csv,
                    strict_json_loads, validate_values, now, ROOT, source_bytes, public_record, project_record)
from neurology_profile import is_profile as is_neurology_profile, profile_schema, patient_groups
from extraction_profiles import (is_profile, is_patient_profile, is_clinic_profile, profile_id, canonical_schema,
                                 applicable_fields, source_blocking_issues, bundle_identity_issues)
from pace_profile import PROFILE as PACE_PROFILE
from clinic_profile import PROFILE as CLINIC_PROFILE
from form_types import (new_draft, validate_draft, compile_draft, parse_form_type,
                        page_geometry, compatibility_issues, RULE_KEYS)
from field_catalog import CatalogError, catalog_for_columns, extraction_rule, REPEATING_EXPORT_WARNING
from limits import MAX_SCHEMA_BYTES, MAX_PAGES, MAX_BUNDLE_DOCUMENTS


class Cancelled(InputError):
    pass


def bounded_read(path: str | Path, maximum: int) -> bytes:
    """Check a regular file's size before reading and cap the actual read too."""
    path = Path(path)
    try:
        if not path.is_file():
            raise InputError("Choose a regular file.")
        if path.stat().st_size > maximum:
            raise InputError(f"This file exceeds the {maximum // 1024 // 1024 or 1} MB size limit.")
        with path.open("rb") as stream:
            data = stream.read(maximum + 1)
        if len(data) > maximum:
            raise InputError("The file grew beyond its size limit while being read.")
        return data
    except OSError as exc:
        raise InputError("The file could not be read. Check its permissions and availability.") from exc


def atomic_write(path: str | Path, data: bytes) -> None:
    """Replace only after a complete same-directory write; leave old files intact."""
    destination = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(prefix=".formbridge-", dir=destination.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
        temporary = None
    except OSError as exc:
        raise InputError("The file could not be saved. Check the destination folder, permissions and free space.") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _new_workspace():
    temporary = tempfile.TemporaryDirectory(prefix="formbridge-desktop-")
    try:
        os.chmod(temporary.name, 0o700)
    except OSError:
        pass
    workspace = Workspace(temporary.name, schema=[])
    return temporary, workspace


class DesktopSession:
    """Canonical synchronous API. Do not call mutations concurrently.

    snapshot() returns detached dictionaries. cancel() alone is thread-safe and
    may interrupt a running worker. close() runs after the active job returns.
    """
    def __init__(self):
        self._temporary, self.workspace = _new_workspace()
        self._active_workspace = self.workspace
        self._cancel = threading.Event()
        self._operation_done = threading.Event()
        self._operation_done.set()
        self.generation = 1
        self.dirty = False
        self.project_path: str | None = None
        self.closed = False
        self.form_type = None
        self.draft = None

    @property
    def phase(self):
        return "design" if self.draft is not None else "review" if self.workspace.schema else "empty"

    def _require_review(self, record=None):
        if self.phase != "review":
            raise InputError("Apply a valid extraction type before reviewing, approving or using a spreadsheet.")
        if record is not None and record.get("formTypeIssues"):
            raise InputError(record["formTypeIssues"][0])

    def start_design(self, record_id=None):
        if self.draft is None:
            reference = self._record(record_id) if record_id is not None else self.workspace.records[0] if self.workspace.records else None
            pages = reference.get("pages", []) if reference else []
            self.draft = new_draft(self.form_type, page_geometry(pages))
            if reference is not None:
                self.draft["pages"] = page_geometry(pages)
            if self.form_type is None and self.workspace.schema:
                self.draft["fields"] = [{"id": uuid.uuid4().hex, **{k: copy.deepcopy(v) for k, v in f.items() if k in RULE_KEYS}} for f in self.workspace.schema]
                self.draft["identifierField"] = self.draft["fields"][0]["id"]
            self.dirty = True
        return copy.deepcopy(self.draft)

    def replace_draft(self, draft):
        self.draft = validate_draft(draft)
        self.dirty = True

    def discard_draft(self):
        self.draft = None
        self.dirty = True

    def _check_layouts(self):
        for record in self.workspace.records:
            issues = compatibility_issues(self.form_type, record.get("pages", []))
            if self.form_type is None and any("region" in f for f in self.workspace.schema):
                issues = ["This mask schema has no saved page geometry. Open Design masks and apply a named extraction type before review."]
            record["formTypeIssues"] = issues
            if issues:
                record.update(values={f["name"]: "" for f in self.workspace.schema}, evidence={},
                              confirmed=[], status="review", reviewedBy="")
                record["validationErrors"] = validate_values(self.workspace.schema, record["values"])

    def apply_draft(self):
        if self.draft is None:
            raise InputError("Start designing an extraction type first.")
        definition = compile_draft(self.draft)
        self.workspace.set_schema(definition["fields"], cancel_check=self._check_cancel)
        self.form_type, self.draft = definition, None
        self._check_layouts()
        self.dirty = True

    def save_form_type(self, path):
        definition = compile_draft(self.draft) if self.draft is not None else self.form_type
        if definition is None:
            raise InputError("Design and name an extraction type first.")
        data = json.dumps(definition, ensure_ascii=True, indent=2).encode()
        if len(data) > MAX_SCHEMA_BYTES:
            raise InputError("The saved extraction type would exceed the 1 MiB import limit.")
        atomic_write(path, data)

    def load_form_type(self, path):
        try:
            definition = parse_form_type(strict_json_loads(bounded_read(path, MAX_SCHEMA_BYTES)))
        except (json.JSONDecodeError, UnicodeError) as exc:
            raise InputError("Choose a valid UTF-8 extraction-type JSON file.") from exc
        self.workspace.set_schema(definition["fields"], cancel_check=self._check_cancel)
        self.form_type, self.draft = definition, None
        self._check_layouts()
        self.dirty = True

    def begin_operation(self):
        self._cancel.clear()
        self._operation_done.clear()

    def end_operation(self):
        self._operation_done.set()

    def _check_cancel(self):
        if self._cancel.is_set():
            raise Cancelled("Processing cancelled. Completed documents remain in the queue.")

    def cancel(self):
        self._cancel.set()
        # Repeat until the owner acknowledges completion: cancellation can race
        # the tiny interval between a subprocess launch and its registration.
        while True:
            self._active_workspace.stop_jobs()
            if self._operation_done.wait(.05):
                return

    def snapshot(self) -> dict:
        ws = self.workspace
        state = {"schema": ws.schema, "records": [public_record(r) for r in ws.records],
                 "reviewer": ws.reviewer, "schemaWarnings": ws.schema_warnings,
                 "template": ws.template, "templatePreview": ws.template_preview(),
                 "generation": self.generation, "dirty": self.dirty, "projectPath": self.project_path}
        state.update(phase=self.phase, draft=self.draft, formType=self.form_type)
        catalog = self._expected_catalog()
        selected = {field.get("name") for field in (self.draft["fields"] if self.draft is not None else ws.schema)}
        repeatable = {instrument["name"] for instrument in catalog["instruments"] if instrument["repeatable"]}
        repeating_selected = any(field["name"] in selected and field["instrument"] in repeatable for field in catalog["fields"])
        if repeating_selected:
            catalog["warnings"] = [*catalog["warnings"], REPEATING_EXPORT_WARNING]
            if ws.template is not None:
                state["template"] = {**ws.template, "warnings": [*ws.template.get("warnings", []), REPEATING_EXPORT_WARNING]}
        state.update(expectedFields=catalog["fields"], expectedInstruments=catalog["instruments"],
                     expectedWarnings=catalog["warnings"], expectedCatalogName=catalog["name"],
                     patientRowExportWarning=REPEATING_EXPORT_WARNING if repeating_selected else "")
        state["profile"] = profile_id(ws.schema)
        state["patientGroups"] = patient_groups(ws.records) if is_neurology_profile(ws.schema) else []
        for record in state["records"]:
            if is_profile(ws.schema):
                record["applicableFields"] = sorted(applicable_fields(ws.schema, record["values"], record))
                record["groupConflict"] = any(g["conflict"] and record["id"] in g["recordIds"] for g in state["patientGroups"])
                record["groupConflicts"] = ["The same MRN has conflicting patient names or birth dates."] if record["groupConflict"] else []
                if is_patient_profile(ws.schema):
                    record["profileBlockingIssues"] = source_blocking_issues(ws.schema, record, record["values"])
            paths = {}
            for page in record.get("pages", []):
                path = self.page_path(record["id"], page["page"])
                if path is not None:
                    paths[str(page["page"])] = str(path)
            record["pagePaths"] = paths
        return copy.deepcopy(state)

    def add_document(self, data: bytes, filename: str) -> dict:
        self._check_cancel()
        record = self.workspace.add(data, filename)
        self._check_layouts()
        if not self.workspace.schema:
            self.start_design()
            if not self.draft["pages"]:
                self.draft["pages"] = page_geometry(record.get("pages", []))
        self.dirty = True
        return copy.deepcopy(public_record(record))

    def _bundle_job(self, workspace, record_id, documents):
        result = workspace.local_job("bundle_worker.py", {"recordId": record_id, "documents": documents}, 180)
        if not isinstance(result, dict) or set(result) != {"data", "manifest", "identifierField"} or not isinstance(result["data"], str) or len(result["data"]) > MAX_FILE * 1.4:
            raise InputError("The local bundle worker returned an invalid result.")
        try:
            data = base64.b64decode(result["data"], validate=True)
        except (ValueError, binascii.Error) as exc:
            raise InputError("The local bundle worker returned invalid PDF encoding.") from exc
        if not data.startswith(b"%PDF-") or len(data) > MAX_FILE:
            raise InputError("The combined patient PDF exceeds the 12 MiB limit or is invalid.")
        rule = parse_schema([result["identifierField"]])[0]
        if rule["name"] != "record_id" or rule["type"] != "text" or rule.get("region", {}).get("page") != 1:
            raise InputError("The patient bundle needs its operator-entered study record ID on the cover.")
        manifest = result["manifest"]
        if not isinstance(manifest, list) or len(manifest) != len(documents):
            raise InputError("The patient bundle source manifest is invalid.")
        expected_page = 2
        for source, original in zip(manifest, documents):
            if not isinstance(source, dict) or set(source) != {"filename", "sha256", "pages", "firstPage", "lastPage"} or source["filename"] != original["filename"] or source["sha256"] != hashlib.sha256(base64.b64decode(original["data"], validate=True)).hexdigest() or type(source["pages"]) is not int or not 1 <= source["pages"] < MAX_PAGES or type(source["firstPage"]) is not int or type(source["lastPage"]) is not int or source["firstPage"] != expected_page or source["lastPage"] != expected_page + source["pages"] - 1 or source["lastPage"] > MAX_PAGES:
                raise InputError("The patient bundle source order or checksums are invalid.")
            expected_page = source["lastPage"] + 1
        return data, manifest, rule

    def add_patient_bundle(self, paths, record_id, confirmed_same_patient=False):
        if confirmed_same_patient is not True:
            raise InputError("Explicitly confirm that these ordered PDFs belong to the same patient.")
        if not isinstance(record_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", record_id):
            raise InputError("Enter a study record ID of 1 to 80 letters, digits, underscores, periods or hyphens, starting with a letter or digit.")
        ws = self.workspace
        pace_mode = is_patient_profile(ws.schema)
        if len(ws.records) >= MAX_RECORDS:
            raise InputError("This session supports at most 60 patient rows.")
        if any("bundleSources" not in record for record in ws.records) or (ws.schema and self.form_type is None and not pace_mode) or (ws.records and self.draft is not None):
            raise InputError("Save this project and start a new project before combining patient PDFs. Reuse an applied patient-bundle extraction type for later patients.")
        if any(record.get("bundleRecordId") == record_id for record in ws.records):
            raise InputError("That study record ID already has a patient source bundle in this project.")
        try:
            paths = list(paths)
        except TypeError as exc:
            raise InputError("Choose an ordered list of patient PDF paths.") from exc
        if not 1 <= len(paths) <= MAX_BUNDLE_DOCUMENTS:
            raise InputError(f"Choose 1 to {MAX_BUNDLE_DOCUMENTS} PDFs in the intended source order.")
        documents, original_bytes = [], 0
        for path in paths:
            self._check_cancel()
            if Path(path).suffix.lower() != ".pdf":
                raise InputError("Patient source bundles currently accept PDFs only.")
            data = bounded_read(path, MAX_FILE)
            original_bytes += len(data)
            if original_bytes > MAX_FILE:
                raise InputError("The original patient PDFs together must be at most 12 MiB.")
            documents.append({"filename": Path(path).name, "data": base64.b64encode(data).decode()})
        if source_bytes(ws.records) + original_bytes > MAX_SESSION_BYTES:
            raise InputError("Original and combined patient sources exceed the 20 MiB session limit.")
        temporary, staged = _new_workspace()
        self._active_workspace = staged
        try:
            data, manifest, cover_rule = self._bundle_job(staged, record_id, documents)
            self._check_cancel()
            if source_bytes(ws.records) + original_bytes + len(data) > MAX_SESSION_BYTES:
                raise InputError("Original and combined patient sources exceed the 20 MiB session limit.")
            staged.schema = copy.deepcopy(ws.schema)
            record = staged.add(data, "patient-source-bundle.pdf", origin="patient-bundle")
            self._check_cancel()
            pages = page_geometry(record.get("pages", []))
            if len(pages) != manifest[-1]["lastPage"]:
                raise InputError("The combined PDF does not match its ordered source manifest.")
            draft = copy.deepcopy(self.draft)
            if pace_mode:
                issues = bundle_identity_issues(record, record_id, manifest)
                if record["values"].get("record_id") != record_id:
                    issues.append("The source record ID differs from the operator-confirmed study record ID.")
                if issues:
                    raise InputError(" ".join(issues))
                draft = None
            elif self.form_type is not None:
                if self.form_type["identifierField"] != "record_id" or ws.schema[0].get("region") != cover_rule["region"]:
                    raise InputError("Use a patient-bundle extraction type with its record_id mask on the operator cover, or start a new project.")
                issues = compatibility_issues(self.form_type, record.get("pages", []))
                if issues:
                    raise InputError(issues[0])
                if record["values"].get("record_id") != record_id:
                    raise InputError("Review the extraction type's cover identifier mask before adding this bundle.")
            else:
                draft = draft if draft is not None else new_draft(pages=pages)
                if draft["pages"] and compatibility_issues({"pages": draft["pages"]}, record.get("pages", [])):
                    raise InputError("The combined sources differ from the unfinished draft's page layout. Save this project and start a new project.")
                draft["pages"] = pages
                identifier = next((field for field in draft["fields"] if field.get("name") == "record_id"), None)
                if identifier is None:
                    identifier = {"id": uuid.uuid4().hex, **cover_rule}
                    draft["fields"].insert(0, identifier)
                elif identifier.get("type") != "text" or ("region" in identifier and identifier["region"] != cover_rule["region"]):
                    raise InputError("The draft record_id must use the operator cover mask for a patient source bundle.")
                else:
                    identifier.update(cover_rule)
                if draft["identifierField"] not in {None, identifier["id"]}:
                    raise InputError("The patient bundle uses the operator-entered record_id as its explicit identifier. Start a new draft to use that cover.")
                draft["identifierField"] = identifier["id"]
                draft = validate_draft(draft)
            record["bundleSources"] = [{**source, "sourceData": original["data"]} for source, original in zip(manifest, documents)]
            record["bundleRecordId"] = record_id
            record["formTypeIssues"] = []
            record["validationErrors"] = validate_values(ws.schema, record["values"], record)
            if len(json.dumps([r["values"] for r in ws.records] + [record["values"]], ensure_ascii=True).encode()) > MAX_VALUE_BYTES:
                raise InputError("Extracted review text exceeds the 4 MiB session limit.")
            shutil.move(str(staged.assets / record["id"]), str(ws.assets / record["id"]))
            ws.records.append(record)
            self.draft = draft
            ws.touch_template_preview()
            ws.log("Ordered patient PDF sources combined with an operator-entered study record ID. Review required.")
            self.dirty = True
            return copy.deepcopy(public_record(record))
        finally:
            self._active_workspace = ws
            staged.stop_jobs()
            temporary.cleanup()

    def import_documents(self, paths, progress: Callable[[int, int], None] | None = None) -> dict:
        added, failed = [], []
        paths = list(paths)
        for index, path in enumerate(paths):
            self._check_cancel()
            if progress:
                progress(index + 1, len(paths))
            try:
                record = self.add_document(bounded_read(path, MAX_FILE), Path(path).name)
                added.append(record["id"])
            except Cancelled:
                raise
            except (InputError, ValueError, OSError) as exc:
                self._check_cancel()
                failed.append({"filename": Path(path).name, "error": str(exc)[:350]})
        return {"added": added, "failed": failed}

    def review_record(self, record_id: str, values: dict, confirmed: list,
                      reviewer: str = "", approve: bool = False,
                      expected_revision: int | None = None) -> dict:
        record = self._record(record_id)
        self._require_review(record)
        if not isinstance(values, dict) or not isinstance(confirmed, list):
            raise InputError("Provide field values and an explicit confirmation list.")
        # A changed value must be saved before it can be confirmed again.
        changed = {name for name, value in values.items() if value.strip() != record["values"].get(name)} if all(isinstance(v, str) for v in values.values()) else set()
        confirmations = [name for name in confirmed if name not in changed]
        self.workspace.review({"id": record_id, "values": values, "confirmed": confirmations,
                               "reviewer": reviewer, "approve": approve,
                               "expectedRevision": record["revision"] if expected_revision is None else expected_revision})
        self.dirty = True
        return copy.deepcopy(public_record(record))

    def _restore_bundle_sources(self, record, data, workspace):
        sources = record.get("bundleSources")
        record_id = record.get("bundleRecordId")
        if not isinstance(record_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", record_id) or not isinstance(sources, list) or not 1 <= len(sources) <= MAX_BUNDLE_DOCUMENTS:
            raise InputError("Invalid saved patient source bundle.")
        documents, original_bytes = [], 0
        for source in sources:
            if not isinstance(source, dict) or set(source) != {"filename", "sha256", "pages", "firstPage", "lastPage", "sourceData"} or not isinstance(source["sourceData"], str) or len(source["sourceData"]) > MAX_FILE * 1.4:
                raise InputError("Each saved patient bundle needs its bounded original PDFs and manifest.")
            try:
                original = base64.b64decode(source["sourceData"], validate=True)
            except (ValueError, binascii.Error) as exc:
                raise InputError("A saved patient source has invalid encoding.") from exc
            original_bytes += len(original)
            if original_bytes > MAX_FILE or hashlib.sha256(original).hexdigest() != source["sha256"]:
                raise InputError("A saved original patient source exceeds its bound or does not match its checksum.")
            documents.append({"filename": source["filename"], "data": source["sourceData"]})
        if source_bytes(workspace.records) + len(data) + original_bytes > MAX_SESSION_BYTES:
            raise InputError("Original and combined patient sources exceed the 20 MiB session limit.")
        rebuilt, manifest, _ = self._bundle_job(workspace, record_id, documents)
        saved_manifest = [{key: value for key, value in source.items() if key != "sourceData"} for source in sources]
        if manifest != saved_manifest or rebuilt != data:
            raise InputError("The saved combined PDF does not match its original patient sources and operator ID.")
        return copy.deepcopy(sources), record_id

    def _record(self, record_id):
        record = next((r for r in self.workspace.records if r["id"] == record_id), None)
        if record is None:
            raise InputError("Select a document first.")
        return record

    def remove_document(self, record_id: str):
        self._record(record_id)
        self.workspace.records = [r for r in self.workspace.records if r["id"] != record_id]
        self.workspace.prune_assets()
        self.workspace.touch_template_preview()
        self.dirty = True

    def set_schema(self, schema):
        fields = parse_schema(schema)
        definition = None
        # Older dictionaries may explicitly supply one-page geometry. Preserve it
        # as a regular form type rather than silently dropping its layout contract.
        if isinstance(schema, dict) and isinstance(schema.get("page_size_points"), dict) and all("region" in f for f in fields):
            size = schema["page_size_points"]
            width, height = size.get("width"), size.get("height")
            if isinstance(width, (int, float)) and isinstance(height, (int, float)) and width > 0 and height > 0:
                definition = parse_form_type({"format": "formbridge-form-type-v1", "name": schema.get("name", "Imported extraction type"),
                                              "identifierField": fields[0]["name"], "fields": fields,
                                              "pages": [{"page": 1, "aspectRatio": width / height}]})
        self.workspace.set_schema(fields, cancel_check=self._check_cancel)
        self.form_type, self.draft = definition, None
        self._check_layouts()
        self.dirty = True

    def use_neurology_profile(self):
        """Explicitly opt into the built-in synthetic neurology staging schema.

        Existing sources are reprocessed atomically and approvals/mappings are
        cleared by the same schema-change path used by custom categories.
        """
        self.set_schema(profile_schema())
        return self.snapshot()

    def use_pace_profile(self):
        """Opt into printed PACE forms without changing custom-mask extraction."""
        self.set_schema(canonical_schema(PACE_PROFILE))
        return self.snapshot()

    def use_sih_clinic_profile(self):
        """Select the clinic layout reader and its source registration contract."""
        self.set_schema(canonical_schema(CLINIC_PROFILE))
        return self.snapshot()

    def import_dictionary(self, path: str | Path):
        raw = bounded_read(path, MAX_SCHEMA_BYTES)
        try:
            text = raw.decode("utf-8-sig")
            raw = None if Path(path).suffix.lower() == ".csv" else strict_json_loads(text)
            fields, warnings = schema_from_csv(text) if raw is None else (parse_schema(raw), [])
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise InputError("Use a UTF-8 CSV dictionary or valid JSON category definition.") from exc
        self.set_schema(raw if raw is not None else fields)
        self.workspace.schema_warnings = warnings

    def import_template(self, path: str | Path, sheet=None, header_row=None):
        self.workspace.import_template(bounded_read(path, 4 * 1024 * 1024), Path(path).name, sheet, header_row,
                                       spec_validator=self._validate_expected_spec)
        self.dirty = True

    def _validate_expected_spec(self, spec):
        try:
            return catalog_for_columns(spec["columns"], ROOT / "study_profiles" / "pace.json")
        except CatalogError as exc:
            raise InputError(str(exc)) from exc

    def _expected_catalog(self):
        if self.workspace.template is None:
            return {"fields": [], "instruments": [], "warnings": [], "name": "Expected fields"}
        return self._validate_expected_spec(self.workspace.template)

    def load_expected_fields(self, path: str | Path):
        """Load a blank destination without adding masks or choosing an identifier."""
        self.import_template(path)
        return self.snapshot()

    def use_pace_template(self):
        return self.load_expected_fields(ROOT / "spreadsheets" / "pace-import-template.csv")

    def add_expected_field(self, export_name, field_id=None):
        entry = next((field for field in self._expected_catalog()["fields"] if field["name"] == export_name), None)
        if entry is None:
            raise InputError("Choose a field from the loaded expected destinations.")
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,99}", export_name):
            raise InputError("This destination name cannot be used as an extraction field. Use lowercase REDCap variable names.")
        if field_id is not None and (self.draft is None or not any(field["id"] == field_id for field in self.draft["fields"])):
            raise InputError("Choose an existing draft field to assign this destination.")
        if self.draft is not None and any(field.get("name") == export_name and field["id"] != field_id for field in self.draft["fields"]):
            raise InputError("That expected field is already selected. Choose its existing mask.")
        if self.draft is None and any(field["name"] == export_name for field in self.workspace.schema):
            raise InputError("That expected field is already selected. Open Design masks to edit it.")
        self.start_design()
        staged = copy.deepcopy(self.draft)
        existing = next((field for field in staged["fields"] if field["id"] == field_id), None)
        field = {"id": existing["id"] if existing else uuid.uuid4().hex, **extraction_rule(entry)}
        if existing is not None and "region" in existing:
            field["region"] = copy.deepcopy(existing["region"])
        if existing is None:
            staged["fields"].append(field)
        else:
            staged["fields"][staged["fields"].index(existing)] = field
        self.replace_draft(staged)
        return copy.deepcopy(field)

    def leave_remaining_columns_blank(self, expected_revision):
        self.workspace.check_template_revision(expected_revision)
        template = self.workspace.template
        mappings = {column["name"]: None for column in template["columns"]}
        mappings.update(template["mappings"])
        self.workspace.set_template_mapping(mappings, False, expected_revision)
        self.dirty = True
        return self.snapshot()

    def load_sample_template(self, name: str):
        names = {"friendly": "friendly-template.xlsx", "raw": "redcap-template.xlsx", "csv": "redcap-template.csv"}
        if name not in names:
            raise InputError("Choose a fictional example template.")
        self.import_template(ROOT / "spreadsheets" / names[name])

    def configure_template(self, sheet: str, header_row: int, expected_revision: int):
        self.workspace.check_template_revision(expected_revision)
        ws = self.workspace
        ws.import_template(ws.template_data, ws.template["name"], sheet, header_row, spec_validator=self._validate_expected_spec)
        self.dirty = True

    def use_categories_as_columns(self):
        self._require_review()
        from openpyxl import Workbook
        workbook = Workbook()
        try:
            sheet = workbook.active
            sheet.title = ("Neurology staging" if is_neurology_profile(self.workspace.schema) else "SIH clinic patient rows"
                           if is_clinic_profile(self.workspace.schema) else "PACE patient rows"
                           if is_patient_profile(self.workspace.schema) else "Category columns")
            sheet.append([f["name"] for f in self.workspace.schema])
            sheet.freeze_panes = "A2"
            output = io.BytesIO()
            workbook.save(output)
            filename = ("neurology-staging-columns.xlsx" if is_neurology_profile(self.workspace.schema) else "sih-clinic-patient-columns.xlsx"
                        if is_clinic_profile(self.workspace.schema) else "pace-patient-columns.xlsx"
                        if is_patient_profile(self.workspace.schema) else "category-columns.xlsx")
            self.workspace.import_template(output.getvalue(), filename, spec_validator=self._validate_expected_spec)
        finally:
            workbook.close()
        self.set_mapping({f["name"]: f["name"] for f in self.workspace.schema}, False)

    def set_mapping(self, mappings: dict, confirmed: bool = False, expected_revision: int | None = None):
        self._require_review()
        if not self.workspace.template:
            raise InputError("Load a spreadsheet template first.")
        self.workspace.set_template_mapping(mappings, confirmed, self.workspace.template["revision"] if expected_revision is None else expected_revision)
        self.dirty = True

    def export(self, export_format: str, path: str | Path | None = None,
               expected_revision: int | None = None, mapped: bool = True) -> bytes:
        self._check_cancel()
        self._require_review()
        for record in self.workspace.records:
            if record["status"] == "approved":
                self._require_review(record)
        if mapped:
            if expected_revision is None:
                raise ConflictError("Refresh the spreadsheet preview before exporting.")
            self.workspace.check_template_revision(expected_revision)
            data = self.workspace.template_export(export_format)
        else:
            if export_format != "csv":
                raise InputError("Category exports use CSV.")
            data = self.workspace.export()
        self._check_cancel()
        if path is not None:
            atomic_write(path, data)
        return data

    def page_path(self, record_id: str, page: int) -> Path | None:
        record = self._record(record_id)
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", record_id) or type(page) is not int or not 1 <= page <= MAX_PAGES:
            raise InputError("Invalid page selection.")
        if not any(p["page"] == page for p in record.get("pages", [])):
            return None
        path = self.workspace.assets / record_id / f"page-{page}.png"
        return path if path.is_file() else None

    def project_bytes(self) -> bytes:
        ws = self.workspace
        project = {"format": "formbridge-project-v2", "schema": ws.schema,
                   "formType": self.form_type, "draft": self.draft,
                   "records": [project_record(r) for r in ws.records],
                   "exportedAt": now()}
        if ws.template:
            project["template"] = {"filename": ws.template["name"], "sourceData": base64.b64encode(ws.template_data).decode(),
                                   "sheet": ws.template["sheet"], "headerRow": ws.template["headerRow"], "mappings": ws.template["mappings"]}
        data = json.dumps(project, ensure_ascii=True, indent=2).encode()
        if len(data) > MAX_BODY:
            raise InputError("The saved project would exceed the 40 MB import limit.")
        return data

    def save_project(self, path: str | Path):
        atomic_write(path, self.project_bytes())
        self.project_path, self.dirty = str(Path(path)), False

    def open_project(self, path: str | Path):
        try:
            body = strict_json_loads(bounded_read(path, MAX_BODY))
        except (json.JSONDecodeError, UnicodeError) as exc:
            raise InputError("This project is not valid UTF-8 JSON.") from exc
        if not isinstance(body, dict) or body.get("format") not in {"formbridge-project-v1", "formbridge-project-v2"}:
            raise InputError(f"Choose a {PRODUCT_NAME} project (v1 or v2).")
        schema = [] if body.get("schema") == [] else parse_schema(body.get("schema"))
        definition, draft = None, None
        if body["format"] == "formbridge-project-v2":
            definition = parse_form_type(body["formType"]) if body.get("formType") is not None else None
            draft = validate_draft(body["draft"]) if body.get("draft") is not None else None
            if definition is not None and schema != definition["fields"]:
                raise InputError("The saved extraction type does not match the project fields.")
        records = body.get("records")
        if not isinstance(records, list) or len(records) > MAX_RECORDS:
            raise InputError("Invalid project document list.")
        temporary, staged = _new_workspace()
        self._active_workspace = staged
        staged.schema = schema
        try:
            for record in records:
                self._check_cancel()
                if not isinstance(record, dict) or not isinstance(record.get("sourceData"), str) or len(record["sourceData"]) > MAX_FILE * 1.4:
                    raise InputError("Each project document needs its original bounded source.")
                try:
                    data = base64.b64decode(record["sourceData"], validate=True)
                except (ValueError, binascii.Error) as exc:
                    raise InputError("A project source has invalid encoding.") from exc
                if "sourceHash" in record and record["sourceHash"] != hashlib.sha256(data).hexdigest():
                    raise InputError("A project source does not match its saved checksum.")
                bundle = self._restore_bundle_sources(record, data, staged) if "bundleSources" in record or "bundleRecordId" in record else None
                values = record.get("values")
                if not isinstance(values, dict) or set(values) != {f["name"] for f in schema} or any(not isinstance(v, str) or len(v) > 4000 for v in values.values()):
                    raise InputError("Invalid project review values.")
                added = staged.add(data, record.get("filename", ""))
                if bundle is not None:
                    added.update(bundleSources=bundle[0], bundleRecordId=bundle[1], origin="patient-bundle")
                    if is_patient_profile(schema):
                        issues = bundle_identity_issues(added, bundle[1], bundle[0])
                        if issues:
                            raise InputError(" ".join(issues))
                added.update(values=dict(values), validationErrors=validate_values(schema, values, added), confirmed=[], status="review", reviewedBy="")
                if len(json.dumps([r["values"] for r in staged.records], ensure_ascii=True).encode()) > MAX_VALUE_BYTES:
                    raise InputError("Project review text exceeds the 4 MB session limit.")
            template = body.get("template")
            if template is not None:
                self._check_cancel()
                if not isinstance(template, dict) or not isinstance(template.get("sourceData"), str) or len(template["sourceData"]) > 6 * 1024 * 1024:
                    raise InputError("Invalid saved spreadsheet template.")
                try:
                    data = base64.b64decode(template["sourceData"], validate=True)
                except (ValueError, binascii.Error) as exc:
                    raise InputError("The saved template has invalid encoding.") from exc
                staged.import_template(data, template.get("filename", ""), template.get("sheet"), template.get("headerRow"), spec_validator=self._validate_expected_spec)
                staged.set_template_mapping(template.get("mappings", {}), False, staged.template["revision"])
            self._check_cancel()
        except BaseException:
            staged.stop_jobs()
            temporary.cleanup()
            raise
        finally:
            self._active_workspace = self.workspace
        old_temporary = self._temporary
        self._temporary, self.workspace = temporary, staged
        self.form_type, self.draft = definition, draft
        self._check_layouts()
        self._active_workspace = staged
        self.generation += 1
        self.project_path, self.dirty = str(Path(path)), False
        old_temporary.cleanup()

    def reset(self):
        temporary, workspace = _new_workspace()
        old_temporary = self._temporary
        self._temporary, self.workspace, self._active_workspace = temporary, workspace, workspace
        self.generation += 1
        self.project_path, self.dirty = None, False
        self.form_type, self.draft = None, None
        old_temporary.cleanup()

    def close(self):
        if not self.closed:
            self.workspace.stop_jobs()
            self._temporary.cleanup()
            self.closed = True
