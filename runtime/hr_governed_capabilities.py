# R3 CONTROLLED SOURCE
# File: runtime/hr_governed_capabilities.py
# Purpose: Register persistent R3 HR tools with the existing governed gateway.
# Authority: Existing R3 resident identity, canonical grants, and audit only.
"""Governed HR tools; registration never grants execution authority."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import Callable

from runtime.capabilities import CapabilityDenied
from runtime.governed_tools import GovernedCapability, GovernedToolGateway
from runtime.hr_records import HRField, ResidentHRRecord
from runtime.hr_store import HRStore

RESOURCE = "r3:hr"
ASSOCIATION_CONTRACT = "r3.hr.authority-principal-association.v1"
SNAPSHOT_SHA256 = re.compile(r"^[a-f0-9]{64}$")


def _assert_scope(params, context, expected):
    if params.get("scope_ref") != context.scope_ref or context.scope_ref != expected:
        raise CapabilityDenied("HR scope mismatch")
    if context.resource_id != RESOURCE:
        raise CapabilityDenied("Incorrect HR resource authority")


def _decode_record(raw):
    if not isinstance(raw, dict):
        raise ValueError("HR record must be an object")
    def fields(name):
        values = raw.get(name, {})
        if not isinstance(values, dict):
            raise ValueError("Invalid HR fields")
        return {key: HRField(**entry) for key, entry in values.items()}
    return ResidentHRRecord(
        resident_id=raw["resident_id"], display_name=raw["display_name"],
        office=raw["office"], status=raw.get("status", "onboarding"),
        schema_version=raw.get("schema_version", 1),
        fields=fields("fields"), extensions=fields("extensions"),
        history_refs=list(raw.get("history_refs", [])),
    )


def _context_value(context, name):
    if isinstance(context, dict):
        return context.get(name)
    return getattr(context, name, None)


def _resolved_directory_evidence(raw, *, resident_id: str, office_role: str,
                                 evidence_ref: str, now: datetime) -> dict:
    """Validate the trusted resolver result; caller claims are never accepted."""
    required = {"resident_id", "principal_id", "office_id", "office_role",
                "office_status", "binding_status", "binding_revision",
                "snapshot_sha256", "observed_at", "freshness", "source_refs"}
    if not isinstance(raw, dict) or set(raw) != required:
        raise ValueError("invalid_directory_evidence")
    for key in ("resident_id", "principal_id", "office_id", "office_role",
                "office_status", "binding_status", "observed_at"):
        if not isinstance(raw[key], str) or not raw[key].strip() or len(raw[key]) > 512:
            raise ValueError("invalid_directory_evidence")
    if not isinstance(raw["binding_revision"], (str, int)) or not str(raw["binding_revision"]).strip():
        raise ValueError("invalid_directory_evidence")
    if raw["resident_id"] != resident_id or raw["office_role"] != office_role:
        raise ValueError("directory_assignment_mismatch")
    if raw["office_status"] != "active" or raw["binding_status"] != "active":
        raise ValueError("directory_binding_not_active")
    if (raw["freshness"] != "fresh" or not isinstance(raw["snapshot_sha256"], str) or
            not SNAPSHOT_SHA256.fullmatch(raw["snapshot_sha256"])):
        raise ValueError("stale_directory_evidence")
    if (not isinstance(raw["source_refs"], list) or not raw["source_refs"] or
            len(raw["source_refs"]) > 32 or not all(
                isinstance(ref, str) and ref.strip() and len(ref) <= 512
                for ref in raw["source_refs"])):
        raise ValueError("invalid_directory_evidence")
    try:
        observed_at = datetime.fromisoformat(raw["observed_at"].replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError("stale_directory_evidence") from exc
    if observed_at.tzinfo is None:
        raise ValueError("stale_directory_evidence")
    age = (now - observed_at.astimezone(timezone.utc)).total_seconds()
    if age < -30 or age > 300:
        raise ValueError("stale_directory_evidence")
    return {
        "resident_id": raw["resident_id"], "principal_id": raw["principal_id"],
        "office_id": raw["office_id"], "office_role": raw["office_role"],
        "binding_revision": raw["binding_revision"],
        "snapshot_sha256": raw["snapshot_sha256"],
        "observed_at": raw["observed_at"], "source_refs": raw["source_refs"],
    }


def register_hr_governed_tools(gateway: GovernedToolGateway, database: str | Path,
                               *, directory_evidence_resolver: Callable[[str], dict] | None = None):
    """Register read/directory/write; no grants, credentials, or HTTP endpoints."""
    database = Path(database)
    if not database.is_file():
        raise FileNotFoundError("Existing HR database required")

    def directory(params, context):
        _assert_scope(params, context, "r3:hr:directory")
        store = HRStore(database)
        try:
            result = []
            for resident_id in store.resident_ids():
                found = store.get(resident_id)
                if found is None:
                    continue
                record, revision = found
                public = record.view(role="resident")
                public["revision"] = revision
                result.append(public)
            return result
        finally:
            store.close()

    def read(params, context):
        resident_id = params.get("resident_id")
        if not isinstance(resident_id, str) or not resident_id:
            raise ValueError("resident_id required")
        _assert_scope(params, context, resident_id)
        store = HRStore(database)
        try:
            found = store.get(resident_id)
            if found is None:
                return None
            record, revision = found
            public = record.view(role="resident")
            public["revision"] = revision
            return public
        finally:
            store.close()

    def save(params, context):
        record = _decode_record(params.get("record"))
        _assert_scope(params, context, record.resident_id)
        # Never accept a caller-provided identity, role or grant.
        expected = params.get("expected_revision")
        if expected is not None and (type(expected) is not int or expected < 1):
            raise ValueError("Invalid revision")
        store = HRStore(database)
        try:
            revision = store.put(record, expected_revision=expected)
            return {"resident_id": record.resident_id, "revision": revision}
        finally:
            store.close()

    def associate_authority_principal_with_provenance(params, context):
        scope_ref = params.get("scope_ref")
        if not isinstance(scope_ref, str) or not scope_ref.startswith("r3:"):
            raise ValueError("invalid_resident_scope")
        resident_id = scope_ref
        target_scope = scope_ref
        _assert_scope(params, context, target_scope)
        if (_context_value(context, "action") != "hr.save" or
                _context_value(context, "operation") != "write"):
            raise CapabilityDenied("Incorrect HR write authority")
        expected = params.get("expected_revision")
        if type(expected) is not int or expected < 1:
            raise ValueError("invalid_expected_revision")
        evidence_ref, idempotency_key = params.get("evidence_ref"), params.get("idempotency_key")
        if not isinstance(evidence_ref, str) or not evidence_ref or len(evidence_ref) > 512:
            raise ValueError("invalid_evidence_ref")
        if not isinstance(idempotency_key, str) or not idempotency_key or len(idempotency_key) > 200:
            raise ValueError("invalid_idempotency_key")

        # Authentication, exact r3:hr/hr.save/write/target scope and the
        # authorization audit are enforced by GovernedToolGateway before this
        # executor. Require its server-derived references for our atomic event.
        actor = _context_value(context, "principal_id")
        grant_id = _context_value(context, "grant_id")
        correlation_id = _context_value(context, "correlation_id")
        if not all(isinstance(value, str) and value for value in (actor, grant_id, correlation_id)):
            raise CapabilityDenied("Authenticated authorization context required")

        store = HRStore(database)
        try:
            request_document = {"resident_id": resident_id, "expected_revision": expected,
                                "evidence_ref": evidence_ref, "actor": actor,
                                "grant_id": grant_id, "correlation_id": correlation_id}
            request_sha256 = hashlib.sha256(json.dumps(
                request_document, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            prior = store.association_idempotency_result(idempotency_key, request_sha256)
            if prior is not None:
                return {"contract": ASSOCIATION_CONTRACT, "version": 1, **prior}
            found = store.get(resident_id)
            if found is None:
                raise ValueError("hr_record_not_found")
            record, current_revision = found
            if current_revision != expected:
                raise ValueError("revision_conflict")
            if record.status != "active":
                raise ValueError("personnel_decision_not_active")
            now = datetime.now(timezone.utc)
            # Exact retries are resolved inside the same canonical HR store;
            # changed content under a used key conflicts there.
            try:
                resolved = directory_evidence_resolver(evidence_ref)
            except Exception as exc:
                raise ValueError("directory_evidence_unavailable") from exc
            evidence = _resolved_directory_evidence(
                resolved, resident_id=resident_id, office_role=record.office,
                evidence_ref=evidence_ref, now=now)
            result = store.associate_authority_principal_with_provenance(
                resident_id=resident_id, expected_revision=expected, evidence=evidence,
                evidence_ref=evidence_ref, actor_principal_id=actor, grant_id=grant_id,
                correlation_id=correlation_id, idempotency_key=idempotency_key,
                request_sha256=request_sha256, now=now.isoformat().replace("+00:00", "Z"))
            return {"contract": ASSOCIATION_CONTRACT, "version": 1, **result}
        finally:
            store.close()

    def schema(properties, required=()):
        return {"type": "object", "properties": {
            "scope_ref": {"type": "string"}, **properties},
            "required": ["scope_ref", *required],
            "additionalProperties": False}

    gateway.register(GovernedCapability(
        name="hr.directory", resource_id=RESOURCE,
        action="hr.directory", operation="read",
        description="List public R3 resident HR records",
        parameters=schema({}), executor=directory))
    gateway.register(GovernedCapability(
        name="hr.read", resource_id=RESOURCE,
        action="hr.read", operation="read",
        description="Read a single public R3 resident HR record",
        parameters=schema({"resident_id": {"type": "string"}}, ("resident_id",)),
        executor=read))
    gateway.register(GovernedCapability(
        name="hr.save", resource_id=RESOURCE,
        action="hr.save", operation="write",
        description="Create or update one R3 HR record under exact Steward-approved grant",
        parameters=schema({"record": {"type": "object"},
                           "expected_revision": {"type": "integer", "minimum": 1}},
                          ("record",)), executor=save))
    # The active production service must explicitly inject a trusted, fresh
    # authoritative directory resolver before this operation is discoverable.
    if directory_evidence_resolver is not None:
        if not callable(directory_evidence_resolver):
            raise TypeError("trusted directory evidence resolver required")
        gateway.register(GovernedCapability(
            name="associate_authority_principal_with_provenance", resource_id=RESOURCE,
            action="hr.save", operation="write",
            description="Associate one HR record with a server-resolved active directory principal and provenance",
            parameters=schema({
                "expected_revision": {"type": "integer", "minimum": 1},
                "evidence_ref": {"type": "string", "minLength": 1, "maxLength": 512},
                "idempotency_key": {"type": "string", "minLength": 1, "maxLength": 200},
            }, ("expected_revision", "evidence_ref", "idempotency_key")),
            executor=associate_authority_principal_with_provenance))
