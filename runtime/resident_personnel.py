# R3 CONTROLLED SOURCE
# File: runtime/resident_personnel.py
# Component: R3-RESIDENT-PERSONNEL-METADATA
# File Revision: 1.0.0
# Created: Unknown (legacy; exact creation time not independently established)
# Created By: Unknown (legacy)
# Purpose: Validate an R3 personnel projection without hardcoding resident identity or granting authority.
# Execution Model: Read-only JSON projection.
# Observability: Validation errors; no authority mutations.
# Dependencies: Authoritative HR identity association contract.
# Authority: HR owns personnel identity; this projection does not own capability policy or grants.
# Changed: 2026-11-06T23:06:45Z | GRACE-AUTHORITY-ARCH-001 | Remove Grace-only identity checks; keep local personnel metadata non-authoritative for permissions.
# Supersedes: Prior unversioned single-resident reader; preserves no-grant invariant.
# Contracts: docs/architecture/RESIDENT_AUTHORITY_AND_CAPABILITIES.md
# Tests: tests/test_resident_personnel.py
# History/Predecessor: Git blob 473fe88dbc216c20225f11ac40977212482d59f3 at cb162499a5ae94b801cbdbf9e5aa2dcd4c75ebaf.
"""Local R3 personnel projections do not define or grant resident authority."""
from __future__ import annotations
import json
import re
from pathlib import Path

REQUIRED = ("resident_id", "display_name", "office", "role", "onboarding_status",
            "authority_principal", "authority_source", "history")

def read_personnel_record(path: str | Path) -> dict:
    record = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(record, dict) or any(key not in record for key in REQUIRED):
        raise ValueError("Incomplete R3 personnel record")
    if record["authority_source"] != "r3-shared-authority":
        raise ValueError("Personnel records cannot substitute for R3 authority")
    if (not isinstance(record["resident_id"], str) or
            not re.fullmatch(r"[A-Za-z0-9_.:-]+", record["resident_id"]) or
            not isinstance(record["authority_principal"], str) or
            not re.fullmatch(r"resident:[A-Za-z0-9_.:-]+", record["authority_principal"])):
        raise ValueError("Invalid resident identity association")
    # This R3 display projection is not the authoritative HR record. It must not
    # become a second permissions store; assigned capabilities/conditions are
    # obtained from the institutional authority decision path.
    if any(key in record for key in ("grants", "permissions", "capabilities", "restrictions")):
        raise ValueError("R3 personnel projection cannot define authority policy")
    return record
