# R3 CONTROLLED SOURCE
# File: runtime/hr_identity_association.py
# Component: R3-HR-IDENTITY-CROSSWALK-READER
# File Revision: 1.1.0
# Created: 2026-11-06 UTC (exact time not independently established)
# Created By: Grace Autonomy engineering
# Purpose: Resolve the exact authenticated R3 principal through the authoritative HR crosswalk.
# Execution Model: Read-only lookup in the existing HR store.
# Observability: Fail-closed identity resolution; no HR writes or aliases.
# Dependencies: runtime.hr_store; runtime.capabilities.
# Authority: HR owns identity association and mutations; R3 consumes the stored association.
# Changed: 2026-11-06T23:58:00Z | GRACE-AUTHORITY-ARCH-002 | Remove resident-facing HR association writer and its extra R3 grant gate.
# Supersedes: Revision 1.0.0's local `hr.associate_principal` capability.
# Contracts: docs/architecture/RESIDENT_AUTHORITY_AND_CAPABILITIES.md; HR contract in Issue #41.
# Tests: tests/test_hr_identity_association.py; tests/test_internal_proposal_tool_integration.py.
# History/Predecessor: Current branch predecessor `cb162499a5ae94b801cbdbf9e5aa2dcd4c75ebaf`.
"""Read-only resolver for the authoritative HR identity crosswalk."""
from __future__ import annotations

import re
from pathlib import Path

from runtime.capabilities import CapabilityDenied
from runtime.hr_store import HRStore


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
            record, _revision = found
            r3_entry = record.extensions.get("r3_principal")
            authority_entry = record.extensions.get("authority_principal")
            if (r3_entry is not None and r3_entry.value == r3_principal and
                    authority_entry is not None):
                value = authority_entry.value
                if (not isinstance(value, str) or not re.fullmatch(
                        r"resident:[A-Za-z0-9_.:-]+", value)):
                    raise CapabilityDenied("HR identity association is malformed")
                matches.append(value)
        if len(matches) != 1:
            raise CapabilityDenied("A unique authoritative HR identity association is required")
        return matches[0]
    finally:
        store.close()
