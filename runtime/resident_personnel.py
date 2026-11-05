# R3 CONTROLLED SOURCE
# File: runtime/resident_personnel.py
# Purpose: Read R3 resident personnel metadata without granting authority.
"""Personnel records describe residents; only R3 authority grants permissions."""
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
    if record["resident_id"] != "grace" or record["authority_principal"] != "resident:grace":
        raise ValueError("Unexpected Grace identity")
    if "grants" in record or "permissions" in record:
        raise ValueError("Personnel record cannot issue grants")
    return record
