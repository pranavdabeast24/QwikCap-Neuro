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
import tempfile
import threading
import uuid
from typing import Callable

from server import (Workspace, InputError, ConflictError, MAX_BODY, MAX_FILE,
                    MAX_RECORDS, MAX_VALUE_BYTES, parse_schema, schema_from_csv,
                    strict_json_loads, validate_values, now, ROOT)
from neurology_profile import PROFILE, is_profile, profile_schema, applicable_fields, patient_groups
from form_types import (new_draft, validate_draft, compile_draft, parse_form_type,
                        page_geometry, compatibility_issues, RULE_KEYS)


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
        atomic_write(path, json.dumps(definition, ensure_ascii=True, indent=2).encode())

    def load_form_type(self, path):
        try:
            definition = parse_form_type(strict_json_loads(bounded_read(path, 200000)))
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
        state = {"schema": ws.schema, "records": [{k: v for k, v in r.items() if k != "sourceData"} for r in ws.records],
                 "reviewer": ws.reviewer, "schemaWarnings": ws.schema_warnings,
                 "template": ws.template, "templatePreview": ws.template_preview(),
                 "generation": self.generation, "dirty": self.dirty, "projectPath": self.project_path}
        state.update(phase=self.phase, draft=self.draft, formType=self.form_type)
        state["profile"] = PROFILE if is_profile(ws.schema) else None
        state["patientGroups"] = patient_groups(ws.records) if is_profile(ws.schema) else []
        for record in state["records"]:
            if is_profile(ws.schema):
                record["applicableFields"] = sorted(applicable_fields(ws.schema, record["values"]))
                record["groupConflict"] = any(g["conflict"] and record["id"] in g["recordIds"] for g in state["patientGroups"])
                record["groupConflicts"] = ["The same MRN has conflicting patient names or birth dates."] if record["groupConflict"] else []
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
        return copy.deepcopy({k: v for k, v in record.items() if k != "sourceData"})

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
        return copy.deepcopy({k: v for k, v in record.items() if k != "sourceData"})

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

    def import_dictionary(self, path: str | Path):
        raw = bounded_read(path, 200000)
        try:
            text = raw.decode("utf-8-sig")
            raw = None if Path(path).suffix.lower() == ".csv" else strict_json_loads(text)
            fields, warnings = schema_from_csv(text) if raw is None else (parse_schema(raw), [])
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise InputError("Use a UTF-8 CSV dictionary or valid JSON category definition.") from exc
        self.set_schema(raw if raw is not None else fields)
        self.workspace.schema_warnings = warnings

    def import_template(self, path: str | Path, sheet=None, header_row=None):
        self._require_review()
        self.workspace.import_template(bounded_read(path, 4 * 1024 * 1024), Path(path).name, sheet, header_row)
        self.dirty = True

    def load_sample_template(self, name: str):
        names = {"friendly": "friendly-template.xlsx", "raw": "redcap-template.xlsx", "csv": "redcap-template.csv"}
        if name not in names:
            raise InputError("Choose a fictional example template.")
        self.import_template(ROOT / "spreadsheets" / names[name])

    def configure_template(self, sheet: str, header_row: int, expected_revision: int):
        self._require_review()
        self.workspace.check_template_revision(expected_revision)
        ws = self.workspace
        ws.import_template(ws.template_data, ws.template["name"], sheet, header_row)
        self.dirty = True

    def use_categories_as_columns(self):
        self._require_review()
        from openpyxl import Workbook
        workbook = Workbook()
        try:
            sheet = workbook.active
            sheet.title = "Neurology staging" if is_profile(self.workspace.schema) else "Category columns"
            sheet.append([f["name"] for f in self.workspace.schema])
            sheet.freeze_panes = "A2"
            output = io.BytesIO()
            workbook.save(output)
            filename = "neurology-staging-columns.xlsx" if is_profile(self.workspace.schema) else "category-columns.xlsx"
            self.workspace.import_template(output.getvalue(), filename)
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
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", record_id) or type(page) is not int or not 1 <= page <= 8:
            raise InputError("Invalid page selection.")
        if not any(p["page"] == page for p in record.get("pages", [])):
            return None
        path = self.workspace.assets / record_id / f"page-{page}.png"
        return path if path.is_file() else None

    def project_bytes(self) -> bytes:
        ws = self.workspace
        project = {"format": "formbridge-project-v2", "schema": ws.schema,
                   "formType": self.form_type, "draft": self.draft,
                   "records": [{k: r[k] for k in ("filename", "sourceData", "sourceHash", "values")} for r in ws.records],
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
            raise InputError("Choose a Formbridge project (v1 or v2).")
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
                values = record.get("values")
                if not isinstance(values, dict) or set(values) != {f["name"] for f in schema} or any(not isinstance(v, str) or len(v) > 4000 for v in values.values()):
                    raise InputError("Invalid project review values.")
                added = staged.add(data, record.get("filename", ""))
                added.update(values=dict(values), validationErrors=validate_values(schema, values), confirmed=[], status="review", reviewedBy="")
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
                staged.import_template(data, template.get("filename", ""), template.get("sheet"), template.get("headerRow"))
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
