"""
R3 CONTROLLED SOURCE
File: tests/test_r3a_capability_grants.py
Component: R3A-CME-CAPABILITY-GRANT-TESTS
File Revision: 1.0.0
Created: 2026-11-10T00:34:18Z
Created By: R3A Coordinator
Purpose: Verify exact capability grant revocation and durable audit behavior.
Execution Model: unittest with a focused asynchronous PostgreSQL connection fake.
Observability: Assertions cover exact grant identity, idempotent repeat, and audit event.
Dependencies: r3a_runtime.cme; r3a_runtime.db; unittest.
Authority: Steward-directed exact-grant revocation support; no grant authority is created by these tests.
Changed: 2026-11-10T00:34:18Z | R3A-GRACE-CHAT-AUTH | R3A Coordinator | Add focused tests for audited exact-grant revocation.
Supersedes: None
Contracts: r3a.capability-grant.v1; capability.revoke; capability.revoked.
Tests: python -m unittest tests.test_r3a_capability_grants.
History/Predecessor: New file; initial revision recorded in Git.
"""
from __future__ import annotations

import asyncio
import unittest
import uuid
from unittest.mock import AsyncMock

from r3a_runtime.cme import CME
from r3a_runtime.db import Store


class _Result:
    def __init__(self, row):
        self._row = row

    async def fetchone(self):
        return self._row


class _Transaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False


class _Connection:
    def __init__(self, row, updated=None):
        self.row = row
        self.updated = updated
        self.statements = []

    def transaction(self):
        return _Transaction()

    async def execute(self, statement, params=()):
        self.statements.append((statement, params))
        if statement.lstrip().startswith("SELECT"):
            return _Result(self.row)
        if statement.lstrip().startswith("UPDATE"):
            return _Result(self.updated)
        raise AssertionError(f"unexpected SQL in focused revoke test: {statement}")


class _ConnectionContext:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, *_args):
        return False


class _Pool:
    def __init__(self, connection):
        self._connection = connection

    def connection(self):
        return _ConnectionContext(self._connection)


class CapabilityGrantRevocationTests(unittest.TestCase):
    def store(self, connection):
        store = Store.__new__(Store)
        store.pool = _Pool(connection)
        store._event = AsyncMock(return_value=uuid.uuid4())
        return store

    def test_revokes_exact_grant_and_writes_audit_event(self):
        grant_id = uuid.uuid4()
        row = {"grant_id": grant_id, "module_id": "resident.grace",
               "capability_id": "resident.objective.execute", "scope": {},
               "revoked_at": None}
        connection = _Connection(row, {"revoked_at": "2026-11-10T00:34:18Z"})
        store = self.store(connection)

        result = asyncio.run(store.revoke_capability(str(grant_id), "Steward revocation test"))

        self.assertEqual(result["grant_id"], str(grant_id))
        self.assertEqual(result["module_id"], "resident.grace")
        self.assertEqual(result["capability_id"], "resident.objective.execute")
        self.assertEqual(result["scope"], {})
        self.assertFalse(result["already_revoked"])
        self.assertTrue(any(sql.lstrip().startswith("UPDATE") for sql, _ in connection.statements))
        store._event.assert_awaited_once()
        event_args = store._event.await_args.args
        self.assertEqual(event_args[1:5], ("capability.revoked", "capability",
                                          "resident.objective.execute", None))
        self.assertEqual(event_args[8], "Steward revocation test")
        self.assertEqual(event_args[9]["grant_id"], str(grant_id))

    def test_repeated_revocation_is_idempotent_and_does_not_duplicate_audit(self):
        grant_id = uuid.uuid4()
        row = {"grant_id": grant_id, "module_id": "resident.grace",
               "capability_id": "resident.objective.execute", "scope": {},
               "revoked_at": "2026-11-10T00:30:00Z"}
        connection = _Connection(row)
        store = self.store(connection)

        result = asyncio.run(store.revoke_capability(str(grant_id), "repeat request"))

        self.assertTrue(result["already_revoked"])
        self.assertEqual(len(connection.statements), 1)
        store._event.assert_not_awaited()

    def test_unknown_grant_is_not_silently_accepted(self):
        connection = _Connection(None)
        store = self.store(connection)
        with self.assertRaises(KeyError):
            asyncio.run(store.revoke_capability(str(uuid.uuid4()), "unknown grant test"))
        store._event.assert_not_awaited()

    def test_cme_operator_control_revokes_one_exact_grant(self):
        grant_id = str(uuid.uuid4())
        cme = CME.__new__(CME)
        cme.store = type("RevokeStore", (), {
            "revoke_capability": AsyncMock(return_value={
                "grant_id": grant_id, "module_id": "resident.grace",
                "capability_id": "resident.objective.execute", "scope": {},
                "revoked_at": "2026-11-10T00:34:18Z", "already_revoked": False})
        })()

        result = asyncio.run(CME._control_request(cme, "capability.revoke", {
            "grant_id": grant_id, "reason": "Steward revocation test"}, "revoke-key"))

        self.assertEqual(result["operation"], "capability.revoke")
        self.assertEqual(result["grant_id"], grant_id)
        cme.store.revoke_capability.assert_awaited_once_with(grant_id, "Steward revocation test")


if __name__ == "__main__":
    unittest.main()
