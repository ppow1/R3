# R3 CONTROLLED SOURCE
# File: runtime/capability_authority.py
# Component: R3-CANONICAL-CAPABILITY-AUTHORITY
# File Revision: 2.1.1
# Created: 2026-11-04 UTC (original file date; exact creation time unknown)
# Created By: Unknown (original provenance not independently established)
# Purpose: The one R3-native grant database, additive migration, exact effective-grant checks and audit.
# Execution Model: SQLite authority adapter; no web/session handling or automatic grants.
# Observability: Canonical capability_audit and append-only management audit.
# Dependencies: Python stdlib and R3-owned SQLite database only.
# Authority: Steward unified integration; Website #16 / Grace #28 authority contract.
# Changed: 2026-11-04 UTC | R3-GRACE-AUTH-001 | Original exact-grant verifier and empty schema.
# Changed: 2026-11-04 UTC | R3-GRACE-AUTH-009 | Add resource/read-write/revocation/parent grant fields without new database.
# Changed: 2026-11-04 UTC | R3-GRACE-AUTH-014 | Retain actual delegation reason with separate idempotency key.
# Changed: 2026-11-04 UTC | R3-GRACE-ID-001 | Store separate resident service credentials in same canonical R3 DB.
# Changed: 2026-11-04 UTC | R3-GRACE-ID-003 | Make credential issuance idempotent, no credential auto-provision.
# Supersedes: Earlier untyped R3 schema; existing grant rows retained but NOT auto-authorized.
# Contracts: docs/r3-native-tool-contract.md; issues #16 and #28.
# Tests: tests/test_capability_authority.py; tests/test_grant_management.py
# History/Predecessor: Git blob 70ca2da5b42c405be4ad30abce265078a7230778
"""One canonical R3 authority store; untyped predecessor grants are DENIED."""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from runtime.capabilities import CapabilityDenied, AuthorityUnavailable

GRANT_COLUMNS = {
    "resource_ref": "TEXT",
    "operation": "TEXT",
    "issued_by": "TEXT",
    "approved_by": "TEXT",
    "parent_grant_id": "TEXT",
    "created_at": "REAL",
    "effective_at": "REAL",
    "revoked_at": "REAL",
    "reason": "TEXT",
    "delegable": "INTEGER NOT NULL DEFAULT 0",
    "idempotency_key": "TEXT",
}
AUDIT_COLUMNS = {"resource_ref": "TEXT", "operation": "TEXT"}


def _add_missing_columns(db: sqlite3.Connection, table: str, columns: dict) -> None:
    existing = {row[1] for row in db.execute("PRAGMA table_info(" + table + ")")}
    for name, column_type in columns.items():
        if name not in existing:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {column_type}")


def initialize_empty_schema(database: str | Path) -> None:
    """Idempotent additive R3 migration; never issues a grant or elevates legacy rows."""
    path = Path(database)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(path), timeout=5) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS capability_grants (
            grant_id TEXT PRIMARY KEY, principal TEXT NOT NULL,
            action TEXT NOT NULL, scope_ref TEXT NOT NULL,
            active INTEGER NOT NULL CHECK(active IN (0,1)),
            expires_at REAL, resource_ref TEXT, operation TEXT,
            issued_by TEXT, approved_by TEXT, parent_grant_id TEXT,
            created_at REAL, effective_at REAL, revoked_at REAL,
            reason TEXT, delegable INTEGER NOT NULL DEFAULT 0,
            idempotency_key TEXT)""")
        _add_missing_columns(db, "capability_grants", GRANT_COLUMNS)
        db.execute("""CREATE UNIQUE INDEX IF NOT EXISTS capability_grant_idempotency_unique
                   ON capability_grants(idempotency_key) WHERE idempotency_key IS NOT NULL""")
        db.execute("""CREATE INDEX IF NOT EXISTS capability_grant_exact_lookup
                   ON capability_grants(principal,resource_ref,action,operation,scope_ref,active)""")
        db.execute("""CREATE TABLE IF NOT EXISTS capability_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            at REAL NOT NULL, principal TEXT NOT NULL,
            capability TEXT NOT NULL, action TEXT NOT NULL,
            scope_ref TEXT NOT NULL, correlation_id TEXT NOT NULL,
            grant_id TEXT, outcome TEXT NOT NULL,
            resource_ref TEXT, operation TEXT)""")
        _add_missing_columns(db, "capability_audit", AUDIT_COLUMNS)
        db.execute("""CREATE TABLE IF NOT EXISTS capability_requests (
            request_id TEXT PRIMARY KEY,
            requester TEXT NOT NULL, principal TEXT NOT NULL,
            resource_ref TEXT NOT NULL, action TEXT NOT NULL,
            operation TEXT NOT NULL CHECK(operation IN ('read','write')),
            scope_ref TEXT NOT NULL, requested_at REAL NOT NULL,
            effective_at REAL, expires_at REAL, delegable INTEGER NOT NULL DEFAULT 0,
            reason TEXT NOT NULL, status TEXT NOT NULL,
            decided_by TEXT, decision_at REAL, grant_id TEXT,
            idempotency_key TEXT NOT NULL UNIQUE)""")
        db.execute("""CREATE TABLE IF NOT EXISTS resident_credentials (
            credential_id TEXT PRIMARY KEY, principal TEXT NOT NULL,
            secret_hash TEXT NOT NULL UNIQUE, created_at REAL NOT NULL,
            expires_at REAL NOT NULL, revoked_at REAL, issued_by TEXT NOT NULL,
            idempotency_key TEXT NOT NULL UNIQUE)""")
        db.execute("""CREATE TABLE IF NOT EXISTS capability_management_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT, at REAL NOT NULL,
            actor TEXT NOT NULL, event TEXT NOT NULL,
            request_id TEXT, grant_id TEXT, detail TEXT NOT NULL)""")


class R3Authority:
    """Exact-grant verifier. Writes to this DB are managed through the R3 service."""

    def __init__(self, database: str | Path):
        self.database = str(database)
        if not Path(database).is_file():
            raise AuthorityUnavailable("Canonical R3 authority database is not provisioned")
        try:
            with self._connect() as db:
                db.execute("""SELECT grant_id,principal,resource_ref,action,operation,scope_ref,
                           active,expires_at,effective_at,revoked_at,approved_by,
                           parent_grant_id,issued_by,delegable FROM capability_grants LIMIT 0""")
                db.execute("""SELECT at,principal,capability,action,scope_ref,
                           correlation_id,grant_id,outcome,resource_ref,operation
                           FROM capability_audit LIMIT 0""")
                db.execute("SELECT request_id FROM capability_requests LIMIT 0")
                db.execute("SELECT credential_id FROM resident_credentials LIMIT 0")
                db.execute("SELECT id FROM capability_management_audit LIMIT 0")
        except sqlite3.Error as exc:
            raise AuthorityUnavailable("R3 canonical authority schema unavailable") from exc

    def _connect(self):
        return sqlite3.connect(
            "file:" + str(Path(self.database).resolve()) + "?mode=rw",
            uri=True, timeout=5)

    def authorize(self, *, principal: str, action: str, scope_ref: str,
                  resource_id: str | None = None,
                  operation: str | None = None) -> dict:
        """Require exact principal/resource/action/read-or-write/scope and valid parent chain.

        resource_id is the Python gateway field for canonical resource_ref.
        Calls using the predecessor three-field signature are denied, never upgraded.
        """
        if (not all(isinstance(v, str) and v for v in (
                principal, resource_id, action, operation, scope_ref))
                or operation not in ("read", "write")):
            raise CapabilityDenied("Exact R3 resource and read/write operation required")
        now = time.time()
        try:
            with self._connect() as db:
                db.row_factory = sqlite3.Row
                rows = db.execute("""SELECT * FROM capability_grants WHERE
                    principal=? AND resource_ref=? AND action=? AND operation=? AND scope_ref=?
                    AND active=1 AND revoked_at IS NULL
                    AND (effective_at IS NULL OR effective_at<=?)
                    AND (expires_at IS NULL OR expires_at>?)""",
                    (principal, resource_id, action, operation, scope_ref, now, now)).fetchall()
                if len(rows) != 1:
                    raise CapabilityDenied("No unique effective exact R3 grant")
                grant = rows[0]
                if not isinstance(grant["approved_by"], str) or not (
                        grant["approved_by"].startswith("human:steward:")):
                    raise CapabilityDenied("Missing authenticated Steward approval evidence")
                self._verify_parent_chain(db, grant, now)
                return {"grant_id": grant["grant_id"]}
        except sqlite3.Error as exc:
            raise AuthorityUnavailable("Canonical R3 authority unavailable") from exc

    @staticmethod
    def _verify_parent_chain(db: sqlite3.Connection, grant: sqlite3.Row, now: float):
        seen = {grant["grant_id"]}
        child = grant
        while child["parent_grant_id"] is not None:
            parent_id = child["parent_grant_id"]
            if parent_id in seen:
                raise CapabilityDenied("Cyclic grant delegation")
            seen.add(parent_id)
            parent = db.execute(
                "SELECT * FROM capability_grants WHERE grant_id=?", (parent_id,)).fetchone()
            if parent is None or parent["active"] != 1 or parent["revoked_at"] is not None:
                raise CapabilityDenied("Delegation parent inactive or missing")
            if (parent["expires_at"] is not None and parent["expires_at"] <= now):
                raise CapabilityDenied("Delegation parent expired")
            if (parent["effective_at"] is not None and parent["effective_at"] > now):
                raise CapabilityDenied("Delegation parent not effective")
            if (not isinstance(parent["approved_by"], str) or
                not parent["approved_by"].startswith("human:steward:") or
                parent["principal"] != child["issued_by"] or
                parent["resource_ref"] != child["resource_ref"] or
                parent["action"] != child["action"] or
                parent["operation"] != child["operation"] or
                parent["scope_ref"] != child["scope_ref"] or
                parent["delegable"] != 1 or
                (parent["expires_at"] is not None and
                 (child["expires_at"] is None or child["expires_at"] > parent["expires_at"]))):
                raise CapabilityDenied("Delegation exceeds effective parent grant")
            child = parent

    def audit(self, event: dict) -> None:
        try:
            with self._connect() as db:
                db.execute("""INSERT INTO capability_audit
                   (at,principal,capability,action,scope_ref,correlation_id,grant_id,
                    outcome,resource_ref,operation)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                   (time.time(), event["principal"], event["capability"],
                    event["action"], event["scope_ref"], event["correlation_id"],
                    event.get("grant_id"), event["outcome"],
                    event.get("resource_ref", event.get("resource_id")),
                    event.get("operation")))
        except (sqlite3.Error, KeyError) as exc:
            raise AuthorityUnavailable("R3 durable authority audit unavailable") from exc
