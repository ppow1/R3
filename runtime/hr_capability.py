# R3 CONTROLLED SOURCE
# File: runtime/hr_capability.py
# Component: HR-CAPABILITY
# File Revision: 1.4.0
# Created: 2026-11-05 UTC (date precision)
# Created By: ChatGPT GPT-6
# Purpose: Shared authenticated capability contract for HR adapters
# Execution Model: Python calls, transport-neutral
# Observability: Structured allow/deny decisions without sensitive values
# Dependencies: runtime/hr_store.py; runtime/hr_records.py
# Authority: Caller-supplied verifier must be server-side Comms grant enforcement
# Changed: 2026-11-05 UTC | HR-003 | Add reusable authorization-gated capability
# Supersedes: None
# Contracts: hints/architecture.md; runtime/hr_store.py
# Tests: tests/test_hr_capability.py
# Changed: 2026-11-05 UTC | HR-008 | Discover stored residents without caller-supplied IDs
# Changed: 2026-11-05 UTC | HR-009 | Add reusable create/update capability
# Changed: 2026-11-05 UTC | HR-CREDENTIAL-IDENTITY-002 | Codex | Add revision-checked HR principal association operation
# Changed: 2026-11-05 UTC | HR-CREDENTIAL-IDENTITY-002 | Codex | Add authorized server-side principal resolution without directory disclosure
# Changed: 2026-11-05 UTC | HR-CREDENTIAL-IDENTITY-002 | Codex | Add authorized server-side principal resolution without directory disclosure
# History/Predecessor: 4230ff21be26f1f078e8254bca4cfb1e1da575e0
"""One HR capability for HTTP, MCP, stdio and Python adapters.

Transport adapters must authenticate their peer, map that identity to an R/3
principal and supply the verified principal to the grant checker. No role or
principal may be accepted from an untrusted request body.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable
from runtime.hr_store import HRStore
from runtime.hr_records import (
    AUTHORITY_PRINCIPAL_FIELD,
    AUTHORITY_PRINCIPAL_PATTERN,
    HRField,
    ResidentHRRecord,
)

@dataclass(frozen=True)
class VerifiedPrincipal:
    principal_id: str
    role: str

class HRCapability:
    def __init__(self, store: HRStore, authorize: Callable[[VerifiedPrincipal, str, str], bool]):
        if not callable(authorize):
            raise TypeError("server-side grant checker required")
        self._store = store
        self._authorize = authorize

    def read(self, principal: VerifiedPrincipal, resident_id: str,
             *, approved_fields: frozenset[str] = frozenset()) -> dict | None:
        if not isinstance(principal, VerifiedPrincipal) or not principal.principal_id:
            raise PermissionError("verified principal required")
        if not self._authorize(principal, "hr.read", resident_id):
            raise PermissionError("hr.read denied")
        found = self._store.get(resident_id)
        if found is None:
            return None
        record, revision = found
        # A request approval is scoped to each field, not the whole personnel file.
        allowed_fields = frozenset(
            name for name in approved_fields
            if self._authorize(principal, "hr.field.read", f"{resident_id}:{name}")
        )
        result = record.view(role=principal.role, approved_fields=allowed_fields)
        result["revision"] = revision
        return result

    def save(self, principal: VerifiedPrincipal, record: ResidentHRRecord,
             *, expected_revision: int | None = None) -> int:
        """Create or revise an HR record with existing host authorization."""
        if not isinstance(principal, VerifiedPrincipal) or not principal.principal_id:
            raise PermissionError("verified principal required")
        if not isinstance(record, ResidentHRRecord):
            raise TypeError("HR record required")
        if not self._authorize(principal, "hr.write", record.resident_id):
            raise PermissionError("hr.write denied")
        return self._store.put(record, expected_revision=expected_revision)

    def associate_authority_principal(
        self, principal: VerifiedPrincipal, resident_id: str,
        authority_principal: str, *, expected_revision: int,
    ) -> int:
        """Add an explicitly supplied authority link without replacing HR data."""
        if not isinstance(principal, VerifiedPrincipal) or not principal.principal_id:
            raise PermissionError("verified principal required")
        if not isinstance(resident_id, str) or not resident_id.strip():
            raise ValueError("resident ID required")
        if type(expected_revision) is not int or expected_revision < 1:
            raise ValueError("revision conflict")
        if not self._authorize(principal, "hr.write", resident_id):
            raise PermissionError("hr.write denied")
        if (not isinstance(authority_principal, str) or
                not AUTHORITY_PRINCIPAL_PATTERN.fullmatch(authority_principal)):
            raise ValueError("invalid authority principal")

        found = self._store.get(resident_id)
        if found is None:
            raise ValueError("HR resident not found")
        record, revision = found
        if expected_revision != revision:
            raise ValueError("revision conflict")
        existing = record.extensions.get(AUTHORITY_PRINCIPAL_FIELD)
        if existing is not None:
            if existing.value == authority_principal:
                return revision
            raise ValueError("authority principal association already exists")

        extensions = dict(record.extensions)
        extensions[AUTHORITY_PRINCIPAL_FIELD] = HRField(
            authority_principal, "confidential"
        )
        updated = ResidentHRRecord(
            resident_id=record.resident_id,
            display_name=record.display_name,
            office=record.office,
            status=record.status,
            schema_version=record.schema_version,
            fields=dict(record.fields),
            extensions=extensions,
            history_refs=list(record.history_refs),
        )
        return self._store.put(updated, expected_revision=revision)

    def resolve_authority_principal(
        self, principal: VerifiedPrincipal, resident_id: str,
    ) -> str:
        """Resolve a link for trusted server code; never part of HR directory output."""
        if not isinstance(principal, VerifiedPrincipal) or not principal.principal_id:
            raise PermissionError("verified principal required")
        if not isinstance(resident_id, str) or not resident_id.strip():
            raise ValueError("resident ID required")
        if not self._authorize(principal, "hr.read", resident_id):
            raise PermissionError("hr.read denied")
        found = self._store.get(resident_id)
        if found is None:
            raise ValueError("HR resident not found")
        record, _ = found
        association = record.extensions.get(AUTHORITY_PRINCIPAL_FIELD)
        if association is None:
            raise ValueError("authority principal association missing")
        for other_id in self._store.resident_ids():
            if other_id == resident_id:
                continue
            other = self._store.get(other_id)
            if other is None:
                continue
            other_association = other[0].extensions.get(AUTHORITY_PRINCIPAL_FIELD)
            if (other_association is not None and
                    other_association.value == association.value):
                raise ValueError("duplicate authority principal association")
        return association.value

    def directory(self, principal: VerifiedPrincipal,
                  resident_ids: list[str] | None = None) -> list[dict]:
        # Directory access uses the same read operation and disclosure filtering.
        results = []
        for resident_id in (self._store.resident_ids() if resident_ids is None else resident_ids):
            item = self.read(principal, resident_id)
            if item is not None:
                results.append(item)
        return results
