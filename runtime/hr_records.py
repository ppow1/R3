# R3 CONTROLLED SOURCE
# File: runtime/hr_records.py
# Component: HR-FOUNDATION
# File Revision: 0.2.0
# Created: 2026-11-05 UTC
# Created By: ChatGPT GPT-6
# Purpose: Local, isolated, extensible resident HR record and disclosure foundation
# Execution Model: Pure Python; no service, database, or network dependency
# Observability: Explicit decisions and versioned record data
# Dependencies: Python 3.10+ standard library
# Authority: Steward full access; Helen HR administration; no grant issuance
# Changed: 2026-11-05 UTC | HR-001 | Initial isolated foundation
# Changed: 2026-11-05 UTC | HR-CREDENTIAL-IDENTITY-002 | Codex | Validate confidential authority-principal extensions and filter disclosure
# Supersedes: None
# Contracts: R3 approved charter; docs/PUNCH_LIST.md; hints/file-provenance.md
# Tests: tests/test_hr_records.py
# History/Predecessor: R3 integration candidate source at 88526f126a847a6d49186ff870924929bd8bdcb1
"""R/3-only HR records. Historical institutions are provenance, never live dependencies.

This module does NOT authenticate callers. Production callers must supply a
server-verified principal and must enforce existing Comms/tool-server grants.
Do not store confidential record instances in Git or expose them in logs.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Any, Mapping

LEVELS = frozenset({"public", "request", "confidential"})
ROLES = frozenset({"steward", "helen", "resident", "approved_requester"})
AUTHORITY_PRINCIPAL_FIELD = "authority_principal"
AUTHORITY_PRINCIPAL_PATTERN = re.compile(r"resident:[A-Za-z0-9_.:-]+\Z")

@dataclass(frozen=True)
class HRField:
    value: Any
    classification: str = "confidential"
    def __post_init__(self):
        if self.classification not in LEVELS:
            raise ValueError("unknown HR classification: deny")

@dataclass
class ResidentHRRecord:
    resident_id: str
    display_name: str
    office: str
    status: str = "onboarding"
    schema_version: int = 1
    fields: dict[str, HRField] = field(default_factory=dict)
    extensions: dict[str, HRField] = field(default_factory=dict)
    history_refs: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not all(isinstance(x, str) and x.strip() for x in
                   (self.resident_id, self.display_name, self.office)):
            raise ValueError("resident ID, name and office required")
        if self.schema_version != 1:
            raise ValueError("unsupported HR record version")
        if set(self.fields) & set(self.extensions):
            raise ValueError("duplicate field names")
        if AUTHORITY_PRINCIPAL_FIELD in self.fields:
            raise ValueError("authority principal must be a confidential extension")
        if AUTHORITY_PRINCIPAL_FIELD in self.extensions:
            association = self.extensions[AUTHORITY_PRINCIPAL_FIELD]
            if (not isinstance(association, HRField) or
                    association.classification != "confidential" or
                    not isinstance(association.value, str) or
                    not AUTHORITY_PRINCIPAL_PATTERN.fullmatch(association.value)):
                raise ValueError("invalid confidential authority-principal association")

    def view(self, *, role: str, approved_fields: frozenset[str] = frozenset()) -> dict[str, Any]:
        """Role is trusted ONLY when supplied by an authenticated server-side adapter."""
        if role not in ROLES:
            raise PermissionError("unknown principal role")
        visible: dict[str, Any] = {}
        for name, entry in {**self.fields, **self.extensions}.items():
            if name == AUTHORITY_PRINCIPAL_FIELD:
                continue
            if not isinstance(entry, HRField):
                raise ValueError("unclassified field: deny")
            allowed = (role in {"steward", "helen"} or
                       entry.classification == "public" or
                       (entry.classification == "request" and name in approved_fields
                        and role == "approved_requester"))
            if allowed:
                visible[name] = entry.value
        return {"resident_id": self.resident_id, "display_name": self.display_name,
                "office": self.office, "status": self.status,
                "schema_version": self.schema_version, "fields": visible}

def initial_acceptance_records() -> tuple[ResidentHRRecord, ResidentHRRecord]:
    """Non-sensitive R/3 templates; NOT appointment, activation or authentication."""
    return (
        ResidentHRRecord("r3:grace", "Grace", "Director of Operations",
                         fields={"role": HRField("Director of Operations", "public")}),
        ResidentHRRecord("r3:marie", "Marie", "Research / Independent Review",
                         fields={"role": HRField("Research / Independent Review", "public")}),
    )
