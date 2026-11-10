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
import uuid
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
        # Principal associations and their audit/history share the canonical
        # HR database and transaction with the revision update.
        self._db.execute("""CREATE TABLE IF NOT EXISTS hr_authority_associations (
            resident_id TEXT PRIMARY KEY, principal_id TEXT NOT NULL UNIQUE,
            office_id TEXT NOT NULL, office_role TEXT NOT NULL,
            binding_revision TEXT NOT NULL, snapshot_sha256 TEXT NOT NULL,
            observed_at TEXT NOT NULL, evidence_ref TEXT NOT NULL,
            source_refs_json TEXT NOT NULL, association_ref TEXT NOT NULL UNIQUE,
            revision INTEGER NOT NULL)""")
        self._db.execute("""CREATE TABLE IF NOT EXISTS hr_association_events (
            event_ref TEXT PRIMARY KEY, resident_id TEXT NOT NULL,
            principal_id TEXT NOT NULL, association_ref TEXT NOT NULL,
            actor_principal_id TEXT NOT NULL, grant_id TEXT NOT NULL,
            correlation_id TEXT NOT NULL, idempotency_key TEXT NOT NULL,
            expected_revision INTEGER NOT NULL, successor_revision INTEGER NOT NULL,
            evidence_ref TEXT NOT NULL, snapshot_sha256 TEXT NOT NULL,
            observed_at TEXT NOT NULL, created_at TEXT NOT NULL,
            payload_json TEXT NOT NULL)""")
        self._db.execute("""CREATE TABLE IF NOT EXISTS hr_association_idempotency (
            idempotency_key TEXT PRIMARY KEY, payload_sha256 TEXT NOT NULL,
            response_json TEXT NOT NULL)""")
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

    def association_idempotency_result(self, idempotency_key: str,
                                       request_sha256: str) -> dict | None:
        row = self._db.execute(
            "SELECT payload_sha256,response_json FROM hr_association_idempotency WHERE idempotency_key=?",
            (idempotency_key,)).fetchone()
        if row is None:
            return None
        if row[0] != request_sha256:
            raise ValueError("idempotency_conflict")
        return json.loads(row[1])

    def associate_authority_principal_with_provenance(
            self, *, resident_id: str, expected_revision: int,
            evidence: dict, evidence_ref: str, actor_principal_id: str,
            grant_id: str, correlation_id: str, idempotency_key: str,
            request_sha256: str, now: str) -> dict:
        """Atomically append one verified association, provenance and audit row."""
        required = (resident_id, actor_principal_id, grant_id, correlation_id,
                    idempotency_key, evidence_ref, request_sha256)
        if not all(isinstance(value, str) and value for value in required):
            raise ValueError("association_context_required")
        if type(expected_revision) is not int or expected_revision < 1:
            raise ValueError("invalid_expected_revision")
        with self._db:
            prior = self._db.execute(
                "SELECT payload_sha256,response_json FROM hr_association_idempotency WHERE idempotency_key=?",
                (idempotency_key,)).fetchone()
            if prior:
                if prior[0] != request_sha256:
                    raise ValueError("idempotency_conflict")
                return json.loads(prior[1])
            current = self._db.execute(
                "SELECT revision FROM hr_records WHERE resident_id=?", (resident_id,)).fetchone()
            if current is None:
                raise ValueError("hr_record_not_found")
            if current[0] != expected_revision:
                raise ValueError("revision_conflict")
            principal_id = evidence["principal_id"]
            if self._db.execute(
                    "SELECT 1 FROM hr_authority_associations WHERE resident_id=? OR principal_id=?",
                    (resident_id, principal_id)).fetchone():
                raise ValueError("association_conflict")
            successor_revision = expected_revision + 1
            association_ref = "hr-association:" + uuid.uuid4().hex
            event_ref = "hr-association-event:" + uuid.uuid4().hex
            sources = json.dumps(evidence["source_refs"], sort_keys=True, separators=(",", ":"))
            try:
                self._db.execute(
                    """INSERT INTO hr_authority_associations
                   (resident_id,principal_id,office_id,office_role,binding_revision,
                    snapshot_sha256,observed_at,evidence_ref,source_refs_json,
                    association_ref,revision) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (resident_id, principal_id, evidence["office_id"], evidence["office_role"],
                     str(evidence["binding_revision"]), evidence["snapshot_sha256"],
                     evidence["observed_at"], evidence_ref, sources, association_ref,
                     successor_revision))
            except sqlite3.IntegrityError as exc:
                raise ValueError("association_conflict") from exc
            cursor = self._db.execute(
                "UPDATE hr_records SET revision=? WHERE resident_id=? AND revision=?",
                (successor_revision, resident_id, expected_revision))
            if cursor.rowcount != 1:
                raise ValueError("revision_conflict")
            event = {
                "resident_id": resident_id, "principal_id": principal_id,
                "office_id": evidence["office_id"], "office_role": evidence["office_role"],
                "binding_revision": str(evidence["binding_revision"]),
                "snapshot_sha256": evidence["snapshot_sha256"],
                "observed_at": evidence["observed_at"], "evidence_ref": evidence_ref,
                "source_refs": evidence["source_refs"], "association_ref": association_ref,
                "event_ref": event_ref, "actor_principal_id": actor_principal_id,
                "grant_id": grant_id, "correlation_id": correlation_id,
                "idempotency_key": idempotency_key,
                "expected_revision": expected_revision,
                "successor_revision": successor_revision, "created_at": now,
            }
            self._db.execute(
                """INSERT INTO hr_association_events
                   (event_ref,resident_id,principal_id,association_ref,actor_principal_id,
                    grant_id,correlation_id,idempotency_key,expected_revision,
                    successor_revision,evidence_ref,snapshot_sha256,observed_at,
                    created_at,payload_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (event_ref, resident_id, principal_id, association_ref,
                 actor_principal_id, grant_id, correlation_id, idempotency_key,
                 expected_revision, successor_revision, evidence_ref,
                 evidence["snapshot_sha256"], evidence["observed_at"], now,
                 json.dumps(event, sort_keys=True, separators=(",", ":"))))
            response = {"resident_id": resident_id, "principal_id": principal_id,
                        "revision": successor_revision, "association_ref": association_ref,
                        "evidence_ref": evidence_ref, "audit_event_ref": event_ref,
                        "authorization_ref": grant_id}
            try:
                self._db.execute(
                    "INSERT INTO hr_association_idempotency VALUES (?,?,?)",
                    (idempotency_key, request_sha256,
                     json.dumps(response, sort_keys=True, separators=(",", ":"))))
            except sqlite3.IntegrityError as exc:
                raise ValueError("idempotency_conflict") from exc
            return response
