"""Canonical extraction profiles and source-backed review constraints."""
from __future__ import annotations

import unicodedata
from functools import lru_cache
from pathlib import Path

import neurology_profile as neurology
import pace_profile as pace
import clinic_profile as clinic
import pace_auto as auto
from field_catalog import load_catalog
from limits import MAX_PAGES


PROFILES = {neurology.PROFILE: neurology, pace.PROFILE: pace, clinic.PROFILE: clinic, auto.PROFILE: auto}
PATIENT_PROFILES = frozenset({pace.PROFILE, clinic.PROFILE, auto.PROFILE})


def profile_id(schema):
    if isinstance(schema, list) and schema and isinstance(schema[0], dict):
        marker = schema[0].get("profile")
        return marker if marker in PROFILES else None
    return None


def is_profile(schema):
    return profile_id(schema) is not None


def is_pace_profile(schema):
    return profile_id(schema) == pace.PROFILE


def is_clinic_profile(schema):
    return profile_id(schema) == clinic.PROFILE


def is_auto_profile(schema):
    return profile_id(schema) == auto.PROFILE


def is_patient_profile(schema):
    return profile_id(schema) in PATIENT_PROFILES


def canonical_schema(marker):
    return PROFILES[marker].profile_schema()


def applicable_fields(schema, values, record=None):
    if not is_patient_profile(schema):
        return neurology.applicable_fields(schema, values)
    names = {field["name"] for field in schema}
    supplied = record.get("applicableFields") if record is not None else None
    if not isinstance(supplied, list) or any(not isinstance(name, str) for name in supplied):
        return {schema[0]["name"]}
    return names & set(supplied)


def _normalized(value):
    return " ".join(unicodedata.normalize("NFKC", value).split()).casefold()


def _identity_key(key, value):
    return " ".join(unicodedata.normalize("NFKC", value).split()) if key == "mrn" else _normalized(value)


@lru_cache(maxsize=1)
def _pace_instruments():
    catalog = load_catalog(Path(__file__).resolve().parent / "study_profiles" / "pace.json")
    return frozenset(instrument["name"] for instrument in catalog["instruments"])


@lru_cache(maxsize=1)
def _pace_field_types():
    return {field["name"]: field["type"] for field in pace.profile_schema()}


def _source_context(record, expected_profile=None):
    context = record.get("sourceContext") if record is not None else None
    if (not isinstance(context, dict) or context.get("profile") not in PATIENT_PROFILES
            or expected_profile is not None and context.get("profile") != expected_profile):
        return None
    if any(not isinstance(context.get(key), list) for key in ("recordIds", "identities", "instruments", "instrumentStarts", "unansweredFields", "blockingIssues")):
        return None
    if any(not isinstance(value, str) for key in ("recordIds", "instruments", "blockingIssues") for value in context[key]):
        return None
    if any(instrument not in _pace_instruments() for instrument in context["instruments"]):
        return None
    for start in context["instrumentStarts"]:
        if not isinstance(start, dict) or set(start) != {"instrument", "page"}:
            return None
        if not isinstance(start["instrument"], str) or start["instrument"] not in _pace_instruments() or start["instrument"] not in context["instruments"]:
            return None
        if type(start["page"]) is not int or not 1 <= start["page"] <= MAX_PAGES:
            return None
    for identity in context["identities"]:
        if not isinstance(identity, dict) or type(identity.get("page")) is not int or identity["page"] < 1:
            return None
        if any(not isinstance(identity.get(key), str) for key in ("recordId", "firstName", "lastName", "dob", "mrn")):
            return None
    if context["profile"] == clinic.PROFILE:
        anchors = context.get("registrationAnchors")
        if not isinstance(anchors, list):
            return None
        for anchor in anchors:
            if (not isinstance(anchor, dict) or type(anchor.get("page")) is not int
                    or anchor not in context["identities"]
                    or any(not isinstance(anchor.get(key), str) for key in ("recordId", "firstName", "lastName", "dob", "mrn"))):
                return None
            if not any(start["page"] == anchor["page"] and start["instrument"] == "patient_records"
                       for start in context["instrumentStarts"]):
                return None
    active = record.get("applicableFields", [])
    evidence = record.get("evidence", {})
    if not isinstance(active, list) or any(not isinstance(name, str) for name in active):
        return None
    for name in context["unansweredFields"]:
        if not isinstance(name, str) or name not in active or _pace_field_types().get(name) != "choice":
            return None
        proof = evidence.get(name) if isinstance(evidence, dict) else None
        mappings = {"clinic-unmarked-radio", "pace-unmarked-radio"} if context["profile"] == auto.PROFILE else {"clinic-unmarked-radio" if context["profile"] == clinic.PROFILE else "pace-unmarked-radio"}
        if not isinstance(proof, dict) or proof.get("mapping") not in mappings:
            return None
    if len(context["unansweredFields"]) != len(set(context["unansweredFields"])):
        return None
    return context


def confirmed_source_blank(schema, field_name, record):
    if not is_patient_profile(schema) or record is None:
        return False
    context = _source_context(record, profile_id(schema))
    return bool(context is not None and field_name in context["unansweredFields"]
                and field_name in record.get("confirmed", []))


def _instrument_issues(context):
    instruments = [start["instrument"] for start in context["instrumentStarts"]]
    issues = []
    if not instruments:
        issues.append("No complete supported source instrument was identified.")
    if len(instruments) != len(set(instruments)):
        issues.append("Repeated instrument assessments cannot be combined into one patient row. Keep each assessment separate.")
    return issues


def _identity_issues(identities, expected_id=None):
    issues = []
    ids = {identity["recordId"] for identity in identities if identity["recordId"]}
    if len(ids) != 1 or (expected_id is not None and ids != {expected_id}):
        issues.append("Source patient record IDs are missing, conflicting or different from the confirmed study record ID.")
    for key, label in (("firstName", "first name"), ("lastName", "last name"), ("dob", "birth date"), ("mrn", "MRN")):
        values = {_identity_key(key, identity[key]) for identity in identities if identity[key].strip()}
        if len(values) != 1:
            issues.append(f"Source patient {label} is missing or conflicting.")
    return issues


def _clinic_identity_issues(context, identities=None, expected_id=None):
    anchors = context["registrationAnchors"]
    issues = []
    ids = {anchor["recordId"] for anchor in anchors if anchor["recordId"]}
    if len(anchors) != 1 or len(ids) != 1 or (expected_id is not None and ids != {expected_id}):
        issues.append("Include one registration whose printed Research Study ID matches the confirmed study record ID.")
    if ids != set(context["recordIds"]):
        issues.append("Clinic study ID metadata does not match its registration anchor.")
    selected = context["identities"] if identities is None else identities
    if not selected:
        issues.append("Every original clinic PDF needs a source name, birth date and MRN.")
    for key, label in (("firstName", "first name"), ("lastName", "last name"), ("dob", "birth date"), ("mrn", "MRN")):
        anchor_values = {_identity_key(key, anchor[key]) for anchor in anchors if anchor[key].strip()}
        values = {_identity_key(key, identity[key]) for identity in selected if identity[key].strip()}
        if (len(anchor_values) != 1 or values != anchor_values
                or any(not identity[key].strip() for identity in selected)):
            issues.append(f"Clinic source patient {label} is missing or differs from registration.")
    if any(identity["recordId"] and identity["recordId"] not in ids for identity in selected):
        issues.append("A printed clinic study record ID conflicts with registration.")
    return issues


def source_blocking_issues(schema, record, values=None):
    if not is_patient_profile(schema):
        return []
    if is_auto_profile(schema):
        if _source_context(record, auto.PROFILE) is None:
            return ["PACE automatic source metadata is missing or invalid. Reprocess the original PDFs."]
        return auto.source_issues(record, values)
    context = _source_context(record, profile_id(schema))
    if context is None:
        return ["PACE source identity metadata is missing or invalid. Reprocess the original PDFs."]
    issues = list(context["blockingIssues"])
    issues.extend(_instrument_issues(context))
    if not context["instruments"]:
        issues.append("No supported source instrument was identified.")
    ids = set(context["recordIds"])
    if len(ids) != 1:
        issues.append("Source patient record IDs are missing or conflicting.")
    if is_clinic_profile(schema):
        issues.extend(_clinic_identity_issues(context))
        if record.get("bundleRecordId") is None or not record.get("bundleSources"):
            issues.append("Combine this patient's original clinic PDFs with their registration before review and export.")
    else:
        issues.extend(_identity_issues(context["identities"], next(iter(ids)) if len(ids) == 1 else None))
    active = record.get("applicableFields")
    names = {field["name"] for field in schema}
    if not isinstance(active, list) or any(not isinstance(name, str) or name not in names for name in active) or schema[0]["name"] not in active:
        issues.append("PACE source field applicability is missing or invalid. Reprocess the original PDFs.")
    if values is not None and len(ids) == 1 and values.get("record_id") not in ids:
        issues.append("Keep the patient record ID identified in the original source.")
    if record.get("bundleRecordId") is not None:
        issues.extend(bundle_identity_issues(record, record["bundleRecordId"], record.get("bundleSources", [])))
        if values is not None and values.get("record_id") != record["bundleRecordId"]:
            issues.append("Keep the operator-confirmed patient bundle record ID.")
    return list(dict.fromkeys(issues))


def bundle_identity_issues(record, record_id, manifest):
    if isinstance(record.get("sourceContext"), dict) and record["sourceContext"].get("profile") == auto.PROFILE:
        return auto.bundle_issues(record, record_id, manifest)
    context = _source_context(record)
    if context is None:
        return ["The patient bundle has no valid PACE source identity metadata."]
    clinic_mode = context["profile"] == clinic.PROFILE
    identity_issues = (_clinic_identity_issues(context, expected_id=record_id) if clinic_mode
                       else _identity_issues(context["identities"], record_id))
    issues = [*context["blockingIssues"], *identity_issues]
    issues.extend(_instrument_issues(context))
    if not manifest:
        issues.append("The patient bundle has no original-source manifest.")
    for source in manifest:
        starts = [start for start in context["instrumentStarts"] if start["page"] == source["firstPage"]]
        if len(starts) != 1:
            issues.append("Every original patient PDF must begin with exactly one recognized instrument header.")
        identities = [identity for identity in context["identities"] if source["firstPage"] <= identity["page"] <= source["lastPage"]]
        issues.extend(_clinic_identity_issues(context, identities, record_id) if clinic_mode
                      else _identity_issues(identities, record_id))
    return list(dict.fromkeys(issues))


def validate_profile_values(schema, values, record=None):
    if not is_patient_profile(schema):
        return neurology.validate_profile_values(schema, values)
    active = applicable_fields(schema, values, record)
    errors = {name: "This field is absent from the source; leave it blank." for name, value in values.items() if value and name not in active}
    issues = source_blocking_issues(schema, record, values)
    if issues:
        errors[schema[0]["name"]] = " ".join(issues)
    context = _source_context(record, profile_id(schema))
    if context is not None:
        for field, key in (("mrn", "mrn"), ("patient_first", "firstName"), ("patient_last", "lastName"), ("patient_dob", "dob")):
            observed = {_identity_key(key, identity[key]) for identity in context["identities"] if identity[key].strip()}
            if field in active and len(observed) == 1 and _identity_key(key, values.get(field, "")) not in observed:
                errors[field] = "Keep the patient identity shown in the original sources."
    return errors
