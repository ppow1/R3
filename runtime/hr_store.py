# R3 CONTROLLED SOURCE
# File: runtime/hr_store.py
# Component: HR-PERSISTENCE
# File Revision: 1.1.0
# Created: 2026-11-05 UTC (date precision)
# Created By: ChatGPT GPT-6
# Purpose: Local persistent, versioned, extensible R/3 personnel records
# Execution Model: SQLite transactions, explicit local path, no network
# Observability: Revision counters; no sensitive values logged
# Dependencies: Python 3.10+ standard library; runtime/hr_records.py
# Authority: Internal storage only; callers must authenticate and authorize
# Changed: 2026-11-05 UTC | HR-002 | Add transactional isolated storage
# Supersedes: None
# Contracts: runtime/hr_records.py; hints/file-provenance.md
# Tests: tests/test_hr_store.py
# Changed: 2026-11-05 UTC | HR-008 | Discover stored residents without caller-supplied IDs
# History/Predecessor: f13859dd677d8c665e5beca98624b9bcbebd3f3a
"""R/3-only local HR storage. No cross-institution dependencies or HTTP surface.

Never place the database in a web-served directory or a Git checkout.
This module intentionally does not grant read/write permissions to a caller.
An authenticated server-side adapter must enforce Comms authority first.
"""
from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from runtime.hr_records import HRField, ResidentHRRecord

def _encode(record: ResidentHRRecord) -> str:
    def pack(fields):
        return {key: {"value": entry.value, "classification": entry.classification}
                for key, entry in fields.items()}
    return json.dumps({"resident_id": record.resident_id,
                       "display_name": record.display_name, "office": record.office,
                       "status": record.status, "schema_version": record.schema_version,
                       "fields": pack(record.fields), "extensions": pack(record.extensions),
                       "history_refs": record.history_refs}, sort_keys=True)

def _decode(payload: str) -> ResidentHRRecord:
    raw = json.loads(payload)
    def unpack(fields):
        return {key: HRField(**entry) for key, entry in fields.items()}
    return ResidentHRRecord(resident_id=raw["resident_id"],
                            display_name=raw["display_name"], office=raw["office"],
                            status=raw["status"], schema_version=raw["schema_version"],
                            fields=unpack(raw["fields"]),
                            extensions=unpack(raw["extensions"]),
                            history_refs=list(raw["history_refs"]))

class HRStore:
    def __init__(self, db_path: str | Path):
        path = Path(db_path).expanduser().resolve()
        if str(path) == ":memory:" or path.is_dir():
            raise ValueError("explicit database file path required")
        if not path.parent.is_dir():
            raise ValueError("database parent must already exist")
        self._db = sqlite3.connect(str(path))
        self._db.execute("""CREATE TABLE IF NOT EXISTS hr_records (
            resident_id TEXT PRIMARY KEY, revision INTEGER NOT NULL,
            payload TEXT NOT NULL)""")
        self._db.commit()

    def close(self):
        self._db.close()

    def put(self, record: ResidentHRRecord, *, expected_revision: int | None = None) -> int:
        """Create with expected_revision=None; update with exact revision."""
        encoded = _encode(record)
        with self._db:
            current = self._db.execute(
                "SELECT revision FROM hr_records WHERE resident_id=?",
                (record.resident_id,)).fetchone()
            if current is None:
                if expected_revision is not None:
                    raise ValueError("revision conflict")
                self._db.execute("INSERT INTO hr_records VALUES (?, ?, ?)",
                                 (record.resident_id, 1, encoded))
                return 1
            if expected_revision != current[0]:
                raise ValueError("revision conflict")
            revision = current[0] + 1
            self._db.execute("UPDATE hr_records SET revision=?, payload=? WHERE resident_id=?",
                             (revision, encoded, record.resident_id))
            return revision

    def resident_ids(self) -> list[str]:
        """Discover all stored R/3 resident IDs without a fixed roster or limit."""
        return [row[0] for row in self._db.execute(
            "SELECT resident_id FROM hr_records ORDER BY resident_id")]

    def get(self, resident_id: str) -> tuple[ResidentHRRecord, int] | None:
        row = self._db.execute(
            "SELECT payload, revision FROM hr_records WHERE resident_id=?",
            (resident_id,)).fetchone()
        return (_decode(row[0]), row[1]) if row else None
