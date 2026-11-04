# R3 CONTROLLED SOURCE
# File: runtime/resident_personnel.py
# Purpose: Validate reusable institutional resident personnel metadata without granting authority.
# Changed: 2026-11-04 UTC | R3-HR-SCOPE-001 | Validate all resident IDs, not just Grace.
"""Institution-wide personnel schema; metadata never grants resident capabilities."""
from __future__ import annotations
import json
from pathlib import Path

REQUIRED = ("resident_id", "display_name", "office", "role", "onboarding_status",
            "authority_principal", "authority_source", "history")

def read_personnel_record(path: str | Path) -> dict:
    record = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(record, dict) or any(key not in record for key in REQUIRED):
        raise ValueError("Incomplete R3 personnel record")
    if record["authority_source"] != "r3-shared-authority":
        raise ValueError("Personnel records cannot substitute for R3 authority")
    resident_id = record["resident_id"]
    if (not isinstance(resident_id, str) or not resident_id.strip()
            or not isinstance(record["authority_principal"], str)
            or record["authority_principal"] != "resident:" + resident_id):
        raise ValueError("Resident personnel identity and authority principal mismatch")
    if "grants" in record or "permissions" in record:
        raise ValueError("Personnel record cannot issue grants")
    return record
