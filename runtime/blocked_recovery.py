# R3 CONTROLLED SOURCE
# File: runtime/blocked_recovery.py
# Component: R3-AUTHORIZED-BLOCKED-RECOVERY
# File Revision: 1.0.0
# Created: 2026-11-05 UTC (date only; exact time unverified)
# Created By: ChatGPT GPT-6
# Purpose: Authorize durable blocked-activity successors against the canonical R3 grant store.
# Execution Model: Internal service invoked only after a trusted caller authenticates context.
# Observability: Canonical capability audit and durable resident_inbox successor lineage.
# Dependencies: runtime.capability_authority; runtime.resident_inference; SQLite.
# Authority: R3 canonical grant policy; no default grants and no public HTTP route.
# Changed: 2026-11-05 UTC | R3-GRACE-RECOVERY-006 | Add fail-closed authority-validated recovery boundary.
# Supersedes: None
# Superseded By: None
# Contracts: hints/development-governance.md; hints/file-provenance.md
# Tests: tests/test_blocked_recovery.py
# History/Predecessor: New file; none
"""Internal resumption boundary. A supplied authority reference is not itself authorization."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Callable

from runtime.capabilities import CapabilityDenied
from runtime.capability_authority import R3Authority
from runtime.resident_inference import Inbox


class BlockedResumptionService:
    """Use only from a trusted, separately authenticated institutional entry point.

    No HTTP endpoint is registered here. The injected verifier must derive a principal
    from trusted server-side authentication, not an untrusted body or identity header.
    """

    ACTION = "resident.activity.resume"

    def __init__(self, database: str | Path, authority: R3Authority,
                 authenticate_context: Callable[[object], str]):
        if not isinstance(authority, R3Authority) or not callable(authenticate_context):
            raise TypeError("Canonical R3 authority and trusted principal verifier required")
        self.database = Path(database)
        self.authority = authority
        self.authenticate_context = authenticate_context

    def resume(self, root_event_id: int, blocked_event_id: int, *,
               authenticated_context: object, resolution_evidence: str,
               correlation_id: str) -> int:
        if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0
               for value in (root_event_id, blocked_event_id)):
            raise ValueError("Positive root and blocked event IDs required")
        if not isinstance(resolution_evidence, str) or not resolution_evidence.strip():
            raise ValueError("Verified dependency-resolution evidence required")
        if not isinstance(correlation_id, str) or not correlation_id.strip():
            raise ValueError("Correlation ID required")
        principal = self.authenticate_context(authenticated_context)
        if not isinstance(principal, str) or not principal.startswith(
                ("human:steward:", "resident:")) or principal in (
                    "human:steward:", "resident:"):
            raise CapabilityDenied("Trusted caller identity required")

        # Verify this blocked activity belongs to the selected assignment;
        # do not allow using an unrelated blocked inbox event as a successor root.
        with sqlite3.connect(str(self.database), timeout=10) as db:
            assignment = db.execute(
                "SELECT assignment_id,resident FROM assignment_intake_assignments "
                "WHERE event_id=?", (root_event_id,)).fetchone()
            if assignment is None:
                raise ValueError("Unknown root assignment")
            assignment_id, resident = assignment
            cursor = blocked_event_id
            visited = set()
            while cursor not in visited:
                visited.add(cursor)
                row = db.execute(
                    "SELECT resident,event_type,status,payload FROM resident_inbox WHERE id=?",
                    (cursor,)).fetchone()
                if row is None or row[0] != resident or row[1] != "RESIDENT_ACTIVITY":
                    raise ValueError("Blocked event does not belong to assignment")
                if cursor == blocked_event_id and row[2] != "BLOCKED":
                    raise ValueError("Only BLOCKED activity may be resumed")
                if cursor == root_event_id:
                    break
                previous = json.loads(row[3]).get("previous_event_id")
                if not isinstance(previous, int) or isinstance(previous, bool):
                    raise ValueError("Blocked event lacks assignment lineage")
                cursor = previous
            else:
                raise ValueError("Cyclic assignment lineage")
            if cursor != root_event_id:
                raise ValueError("Blocked event does not descend from assignment")

        resource_ref = "r3:assignment:" + assignment_id
        scope_ref = "resident:" + resident
        grant = self.authority.authorize(
            principal=principal, action=self.ACTION, resource_id=resource_ref,
            operation="write", scope_ref=scope_ref,
        )
        # Fail closed if durable authorization auditing is unavailable.
        self.authority.audit({
            "principal": principal, "capability": self.ACTION,
            "action": self.ACTION, "scope_ref": scope_ref,
            "correlation_id": correlation_id,
            "grant_id": grant["grant_id"], "outcome": "AUTHORIZED",
            "resource_ref": resource_ref, "operation": "write",
        })
        with sqlite3.connect(str(self.database), timeout=10) as db:
            return Inbox(db).resume_blocked(
                blocked_event_id, authority_ref=grant["grant_id"],
                resolution_evidence=resolution_evidence,
            )
