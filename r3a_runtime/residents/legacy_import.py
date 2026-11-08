"""Read-only, explicitly scoped importer for public legacy HR record fields."""

# R3 CONTROLLED SOURCE
# File: r3a_runtime/residents/legacy_import.py
# Component: R3A-RESIDENT-DOSSIERS
# File Revision: 1.0.0
# Created: 2026-11-08 UTC (exact creation time not captured)
# Created By: Codex GPT-6
# Purpose: Prepare auditable import candidates from selected legacy HR identity fields.
# Execution Model: Read-only SQLite URI; caller supplies exact approved record IDs.
# Observability: Candidate metadata records source ID, source revision and extraction timestamp.
# Dependencies: Python standard library; legacy SQLite HR v1 record shape.
# Authority: Does not import confidential fields, establish identity equivalence, or update any store.
# Changed: 2026-11-08 UTC | CHARACTER-ARCHITECTURE | Codex GPT-6 | Add safe HR candidate extraction utility.
# Supersedes: None
# Contracts: r3a.resident.legacy-hr-import-candidate.v1
# Tests: tests/test_r3a_resident_dossiers.py
# History/Predecessor: New file.

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


def extract_legacy_hr_candidates(database: str | Path,
                                 approved_record_ids: Iterable[str]) -> list[dict]:
    """Return only allowlisted public identity/office fields; never mutate the source DB."""
    approved = tuple(dict.fromkeys(approved_record_ids))
    if not approved or any(not isinstance(item, str) or not item for item in approved):
        raise ValueError("an explicit nonempty set of approved legacy record IDs is required")
    uri = Path(database).resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        placeholders = ",".join("?" for _ in approved)
        rows = connection.execute(
            f"SELECT resident_id, revision, payload FROM hr_records WHERE resident_id IN ({placeholders})",
            approved,
        ).fetchall()
    finally:
        connection.close()
    by_id = {row[0]: row for row in rows}
    missing = sorted(set(approved) - set(by_id))
    if missing:
        raise KeyError(f"approved legacy HR record not found: {missing[0]}")
    extracted_at = datetime.now(timezone.utc).isoformat()
    candidates = []
    for resident_id in sorted(approved):
        record_id, revision, payload = by_id[resident_id]
        record = json.loads(payload)
        candidates.append({
            "contract_id": "r3a.resident.legacy-hr-import-candidate",
            "contract_version": "1.0.0",
            "resident_id": record_id,
            "display_name": record.get("display_name"),
            "office": record.get("office"),
            "lifecycle_status": record.get("status"),
            "source_ref": f"r3.legacy.hr.sqlite3#hr_records/{record_id}",
            "source_revision": revision,
            "extracted_at": extracted_at,
            "approval_status": "proposed",
            "classification": "institutional",
        })
    return candidates
