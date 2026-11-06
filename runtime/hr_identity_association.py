"""Narrow resident identity crosswalk operation on the existing R3 HR store."""
from __future__ import annotations

import re
from pathlib import Path

from runtime.capabilities import CapabilityDenied
from runtime.governed_tools import GovernedCapability
from runtime.hr_records import HRField
from runtime.hr_store import HRStore

RESOURCE = "r3:hr"


def association_scope(resident_id: str, r3_principal: str,
                      authority_principal: str) -> str:
    """Bind authorization to the exact record and both canonical identities."""
    return ("r3:hr:identity-association/" + resident_id + "/" +
            r3_principal + "/" + authority_principal)


def resolve_authority_principal(database: str | Path, r3_principal: str) -> str:
    """Resolve the explicit HR crosswalk; never case-fold or infer an alias."""
    if not isinstance(r3_principal, str) or not re.fullmatch(
            r"resident:[A-Za-z0-9_.:-]+", r3_principal):
        raise CapabilityDenied("Authenticated R3 resident principal required")
    store = HRStore(database)
    try:
        matches = []
        for resident_id in store.resident_ids():
            found = store.get(resident_id)
            if found is None:
                continue
            record, revision = found
            r3_entry = record.extensions.get("r3_principal")
            authority_entry = record.extensions.get("authority_principal")
            if (r3_entry is not None and r3_entry.value == r3_principal and
                    authority_entry is not None):
                value = authority_entry.value
                if (not isinstance(value, str) or not re.fullmatch(
                        r"resident:[A-Za-z0-9_.:-]+", value)):
                    raise CapabilityDenied("HR identity association is malformed")
                matches.append((value, resident_id, revision))
        if len(matches) != 1:
            raise CapabilityDenied("A unique authoritative HR identity association is required")
        return matches[0][0]
    finally:
        store.close()


def register_hr_identity_association(gateway, database: str | Path) -> None:
    """Register one exact, self-bound association operation; issue no grant."""
    database = Path(database)
    if not database.is_file():
        raise FileNotFoundError("Existing authoritative HR database required")

    def associate(params, context):
        required = {"scope_ref", "resident_id", "r3_principal",
                    "authority_principal", "expected_revision"}
        if set(params) != required:
            raise ValueError("HR identity association parameters are invalid")
        resident_id = params["resident_id"]
        r3_principal = params["r3_principal"]
        authority_principal = params["authority_principal"]
        expected = params["expected_revision"]
        if (not isinstance(resident_id, str) or not re.fullmatch(r"r3:[A-Za-z0-9_.:-]+", resident_id)
                or not isinstance(r3_principal, str)
                or not re.fullmatch(r"resident:[A-Za-z0-9_.:-]+", r3_principal)
                or not isinstance(authority_principal, str)
                or not re.fullmatch(r"resident:[A-Za-z0-9_.:-]+", authority_principal)
                or type(expected) is not int or expected < 1):
            raise ValueError("HR identity association values are invalid")
        exact_scope = association_scope(resident_id, r3_principal, authority_principal)
        if (params["scope_ref"] != exact_scope or context.scope_ref != exact_scope
                or context.resource_id != RESOURCE
                or context.action != "hr.associate_principal"
                or context.operation != "write"
                or context.principal != r3_principal):
            raise CapabilityDenied("Exact self-bound HR identity association authority required")
        store = HRStore(database)
        try:
            found = store.get(resident_id)
            if found is None:
                raise CapabilityDenied("Authoritative HR record not found")
            record, revision = found
            current_r3 = record.extensions.get("r3_principal")
            current_authority = record.extensions.get("authority_principal")
            if current_r3 is not None or current_authority is not None:
                if (current_r3 is not None and current_authority is not None
                        and current_r3.value == r3_principal
                        and current_authority.value == authority_principal):
                    return {"resident_id": resident_id, "revision": revision,
                            "r3_principal": r3_principal,
                            "authority_principal": authority_principal,
                            "persisted": True, "idempotent_replay": True}
                raise CapabilityDenied("HR identity record already has a different or partial association")
            if revision != expected:
                raise ValueError("HR record revision conflict")
            record.extensions["r3_principal"] = HRField(r3_principal, "confidential")
            record.extensions["authority_principal"] = HRField(authority_principal, "confidential")
            new_revision = store.put(record, expected_revision=expected)
            return {"resident_id": resident_id, "revision": new_revision,
                    "r3_principal": r3_principal,
                    "authority_principal": authority_principal,
                    "persisted": True, "idempotent_replay": False}
        finally:
            store.close()

    gateway.register(GovernedCapability(
        name="hr.associate_principal", resource_id=RESOURCE,
        action="hr.associate_principal", operation="write",
        description=("Bind the authenticated R3 resident identity and exact institutional "
                     "principal to one HR record. Requires a separate exact Steward grant."),
        parameters={"type": "object", "properties": {
            "scope_ref": {"type": "string"},
            "resident_id": {"type": "string", "pattern": r"^r3:[A-Za-z0-9_.:-]+$"},
            "r3_principal": {"type": "string", "pattern": r"^resident:[A-Za-z0-9_.:-]+$"},
            "authority_principal": {"type": "string", "pattern": r"^resident:[A-Za-z0-9_.:-]+$"},
            "expected_revision": {"type": "integer", "minimum": 1}},
            "required": ["scope_ref", "resident_id", "r3_principal",
                         "authority_principal", "expected_revision"],
            "additionalProperties": False},
        executor=associate,
    ))
