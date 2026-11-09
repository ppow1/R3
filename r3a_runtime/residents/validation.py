"""Standard-library validation for resident dossiers and epistemic spans."""

# R3 CONTROLLED SOURCE
# File: r3a_runtime/residents/validation.py
# Component: R3A-RESIDENT-DOSSIERS
# File Revision: 1.0.0
# Created: 2026-11-08 UTC (exact time not independently captured)
# Created By: Codex GPT-6
# Purpose: Validate dossier structures, provenance, settings, and epistemic evidence.
# Execution Model: Pure functions; no network or persistence.
# Observability: Raises DossierValidationError with stable field-oriented messages.
# Dependencies: Python standard library; schemas/resident-dossier.v1.schema.json.
# Authority: Steward directive; evidence and authority must not be inferred from labels.
# Changed: 2026-11-08 UTC (exact time not independently captured) | CHARACTER-ARCHITECTURE | Codex GPT-6 | Add dossier and epistemic validation.
# Supersedes: None
# Contracts: r3a.resident.dossier.v1; r3a.resident.epistemic-spans.v1
# Tests: tests/test_r3a_resident_dossiers.py
# History/Predecessor: New file.

from __future__ import annotations

import re
from datetime import datetime
from typing import Any


class DossierValidationError(ValueError):
    """A dossier or epistemic span violates its versioned contract."""


DIMENSIONS = {
    "warmth", "humor", "formality", "assertiveness", "curiosity",
    "spontaneity", "empathy", "expressiveness", "professional_directness",
}
EPISTEMIC_CLASSES = {"VERIFIED", "CANON", "REASONED", "GENERAL", "CREATIVE", "UNKNOWN"}
APPROVAL_STATES = {"proposed", "in_review", "approved", "published", "active", "superseded", "rejected", "retired"}
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_.:-]{1,127}$")


def _require(condition: bool, path: str, message: str) -> None:
    if not condition:
        raise DossierValidationError(f"{path}: {message}")


def validate_dossier(dossier: dict[str, Any]) -> None:
    """Validate core invariants; JSON Schema remains the interchange contract."""
    _require(isinstance(dossier, dict), "$", "must be an object")
    required = {"schema_id", "schema_version", "revision", "identity", "office", "mission",
                "qualifications", "authority_boundaries", "character", "personality",
                "prompt_components", "memory", "relationships", "implementation",
                "governance", "sources", "open_questions"}
    _require(required <= dossier.keys(), "$", "missing required dossier fields")
    _require(dossier.get("schema_id") == "r3a.resident.dossier", "$.schema_id", "unsupported schema")
    _require(dossier.get("schema_version") == 1, "$.schema_version", "unsupported schema version")
    identity = dossier.get("identity")
    _require(isinstance(identity, dict), "$.identity", "must be an object")
    resident_id = identity.get("resident_id")
    _require(isinstance(resident_id, str) and ID_PATTERN.fullmatch(resident_id) is not None,
             "$.identity.resident_id", "must be a stable identifier")
    _require(isinstance(identity.get("display_name"), str) and bool(identity["display_name"].strip()),
             "$.identity.display_name", "must be nonempty")
    _require(identity.get("identity_status") in {"authoritative", "provisional_legacy_record_id", "provisional_unconfirmed"},
             "$.identity.identity_status", "invalid identity status")
    _require(isinstance(identity.get("source_ids"), list), "$.identity.source_ids", "must be a list")
    for index, source_id in enumerate(identity["source_ids"]):
        _require(isinstance(source_id, dict) and all(isinstance(source_id.get(key), str) and source_id[key]
                                                     for key in ("source_id", "value")),
                 f"$.identity.source_ids[{index}]", "requires source_id and value")
        _require(source_id.get("link_status") in {"confirmed", "unconfirmed", "rejected"},
                 f"$.identity.source_ids[{index}].link_status", "invalid link status")
    _require(isinstance(dossier.get("revision"), str) and bool(dossier["revision"]),
             "$.revision", "must be a version string")
    _require(re.fullmatch(r"\d+\.\d+\.\d+", dossier["revision"]) is not None,
             "$.revision", "must use numeric semantic version syntax")
    governance = dossier.get("governance", {})
    _require(governance.get("approval_status") in APPROVAL_STATES,
             "$.governance.approval_status", "invalid approval status")
    settings = dossier.get("personality", {}).get("settings", {})
    _require(isinstance(settings, dict) and set(settings) == DIMENSIONS,
             "$.personality.settings", "must contain every supported personality dimension")
    for name, value in settings.items():
        _require(isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 100,
                 f"$.personality.settings.{name}", "must be an integer from 0 through 100")
    seen_components: set[tuple[str, str]] = set()
    for index, component in enumerate(dossier.get("prompt_components", [])):
        path = f"$.prompt_components[{index}]"
        _require(isinstance(component.get("component_id"), str) and component["component_id"],
                 path + ".component_id", "must be nonempty")
        _require(isinstance(component.get("version"), str) and component["version"],
                 path + ".version", "must be nonempty")
        _require(component.get("approval_status") in APPROVAL_STATES,
                 path + ".approval_status", "invalid approval status")
        _require(component.get("classification") in {"public", "institutional", "personnel_sensitive", "protected"},
                 path + ".classification", "invalid information classification")
        _require(isinstance(component.get("text"), str), path + ".text", "must be text")
        _require(isinstance(component.get("sources"), list), path + ".sources", "must be a source list")
        key = (component["component_id"], component["version"])
        _require(key not in seen_components, path, "duplicate component ID/version")
        seen_components.add(key)
    _require(isinstance(dossier.get("memory"), dict), "$.memory", "must be an object")
    _require(isinstance(dossier.get("relationships"), list), "$.relationships", "must be a list")
    _require(isinstance(dossier.get("authority_boundaries"), list)
             and all(isinstance(value, str) and value for value in dossier["authority_boundaries"]),
             "$.authority_boundaries", "must be nonempty text entries")
    implementation = dossier.get("implementation", {})
    _require(implementation.get("identity_binding_authority") == "authoritative_hr_system",
             "$.implementation.identity_binding_authority", "provider configuration cannot define identity")


def validate_epistemic_span(span: dict[str, Any]) -> None:
    """Require traceable evidence for verified or canonical institutional claims."""
    _require(isinstance(span, dict), "$", "must be an object")
    _require(span.get("classification") in EPISTEMIC_CLASSES, "$.classification", "unsupported class")
    _require(isinstance(span.get("text"), str) and bool(span["text"].strip()), "$.text", "must be nonempty")
    start, end = span.get("start"), span.get("end")
    _require(isinstance(start, int) and not isinstance(start, bool) and start >= 0,
             "$.start", "must be a nonnegative integer")
    _require(isinstance(end, int) and not isinstance(end, bool) and end > start,
             "$.end", "must be an integer greater than start")
    _require(isinstance(span.get("span_id"), str) and bool(span["span_id"]), "$.span_id", "must be nonempty")
    _require(isinstance(span.get("classified_by"), str) and bool(span["classified_by"]),
             "$.classified_by", "must identify the classifier")
    try:
        datetime.fromisoformat(span.get("classified_at", "").replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise DossierValidationError("$.classified_at: must be an ISO timestamp") from exc
    _require(span.get("audit_status") in {"pending", "passed", "mismatch", "indeterminate"},
             "$.audit_status", "invalid audit status")
    sources = span.get("sources", [])
    _require(isinstance(sources, list), "$.sources", "must be a list")
    if span["classification"] in {"VERIFIED", "CANON"}:
        _require(bool(sources), "$.sources", f"{span['classification']} requires supporting source references")
        for index, source in enumerate(sources):
            _require(isinstance(source, dict) and isinstance(source.get("source_id"), str)
                     and bool(source["source_id"]), f"$.sources[{index}]", "requires source_id")
            _require(isinstance(source.get("locator"), str) and bool(source["locator"]),
                     f"$.sources[{index}].locator", "requires a record/page/span locator")
