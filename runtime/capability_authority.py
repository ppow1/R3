# R3 CONTROLLED SOURCE
# File: runtime/capability_authority.py
# Purpose: Independent R3 exact-grant authority and durable audit storage.
"""Fail-closed R3 capability authority. No implicit grants or R2 dependencies."""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from runtime.capabilities import CapabilityDenied, AuthorityUnavailable


class R3Authority:
    """Read-only verifier over explicitly provisioned R3 grants.

    Provisioning is deliberately not exposed through the tool server. Grant
    issuance requires a separately authenticated Steward administration path.
    """

    def __init__(self, database: str | Path):
        self.database = str(database)
        if not Path(database).is_file():
            raise AuthorityUnavailable("R3 authority database is not provisioned")
        try:
            with self._connect() as db:
                db.execute("SELECT principal,action,scope_ref,grant_id,active,expires_at FROM capability_grants LIMIT 0")
                db.execute("SELECT at,principal,capability,action,scope_ref,correlation_id,grant_id,outcome FROM capability_audit LIMIT 0")
        except sqlite3.Error as exc:
            raise AuthorityUnavailable("R3 authority schema unavailable") from exc

    def _connect(self):
        return sqlite3.connect(f"file:{Path(self.database).resolve()}?mode=rw",
                               uri=True, timeout=5)

    def authorize(self, *, principal: str, action: str, scope_ref: str) -> dict:
        if not all(isinstance(x, str) and x for x in (principal, action, scope_ref)):
            raise CapabilityDenied("Invalid authority request")
        try:
            with self._connect() as db:
                rows = db.execute(
                    """SELECT grant_id FROM capability_grants
                       WHERE principal=? AND action=? AND scope_ref=?
                         AND active=1 AND (expires_at IS NULL OR expires_at>?)""",
                    (principal, action, scope_ref, time.time())).fetchall()
        except sqlite3.Error as exc:
            raise AuthorityUnavailable("R3 authority unavailable") from exc
        if len(rows) != 1:
            raise CapabilityDenied("No unique active exact grant")
        return {"grant_id": rows[0][0]}

    def audit(self, event: dict) -> None:
        try:
            with self._connect() as db:
                db.execute(
                    """INSERT INTO capability_audit
                       (at,principal,capability,action,scope_ref,correlation_id,grant_id,outcome)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (time.time(), event["principal"], event["capability"],
                     event["action"], event["scope_ref"], event["correlation_id"],
                     event.get("grant_id"), event["outcome"]))
        except (sqlite3.Error, KeyError) as exc:
            raise AuthorityUnavailable("R3 durable authority audit unavailable") from exc


def initialize_empty_schema(database: str | Path) -> None:
    """Create an EMPTY native R3 authority store; never issue a grant."""
    path = Path(database)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(path)) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS capability_grants (
            grant_id TEXT PRIMARY KEY, principal TEXT NOT NULL,
            action TEXT NOT NULL, scope_ref TEXT NOT NULL,
            active INTEGER NOT NULL CHECK(active IN (0,1)),
            expires_at REAL)""")
        db.execute("""CREATE TABLE IF NOT EXISTS capability_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            at REAL NOT NULL, principal TEXT NOT NULL,
            capability TEXT NOT NULL, action TEXT NOT NULL,
            scope_ref TEXT NOT NULL, correlation_id TEXT NOT NULL,
            grant_id TEXT, outcome TEXT NOT NULL)""")
