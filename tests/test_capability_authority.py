# R3 CONTROLLED SOURCE
# File: tests/test_capability_authority.py
# Component: R3-CANONICAL-AUTHORITY-REGRESSION
# File Revision: 2.0.0
# Created: 2026-11-04 UTC (original time unknown)
# Created By: Unknown (original provenance not independently established)
# Purpose: Permanent single-store exact read/write, expiry, revocation, inheritance and audit tests.
# Execution Model: Isolated temporary canonical R3 SQLite database.
# Observability: Assert grant resolution and durable audit.
# Dependencies: Python stdlib, runtime/capability_authority.py
# Authority: Steward unified integration #16 and #28.
# Changed: 2026-11-04 UTC | R3-GRACE-AUTH-001 | Initial exact-grant regressions.
# Changed: 2026-11-04 UTC | R3-GRACE-AUTH-010 | Enforce canonical resource/read-write schema and delegation.
# Supersedes: Untyped predecessor assertions; no automatic privilege migration.
# Contracts: docs/r3-native-tool-contract.md
# Tests: python -m unittest tests.test_capability_authority -v
# History/Predecessor: Git blob 24a71a7f4e47aa6b451b5dcc42833d168f01f586
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from runtime.capability_authority import R3Authority, initialize_empty_schema
from runtime.capabilities import CapabilityDenied, AuthorityUnavailable


class AuthorityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "authority.db"
        initialize_empty_schema(self.path)
        self.authority = R3Authority(self.path)

    def grant(self, *, grant_id="g1", principal="resident:grace",
              scope="office:grace", operation="write", active=1,
              expiry=None, effective_at=None, parent=None,
              issued_by="human:steward:1", delegable=0):
        with sqlite3.connect(self.path) as db:
            db.execute("""INSERT INTO capability_grants
                  (grant_id, principal, action, scope_ref, active, expires_at,
                   resource_ref, operation, approved_by, issued_by, created_at,
                   effective_at, revoked_at, parent_grant_id, delegable)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (grant_id, principal, "office.update", scope, active, expiry,
                 "resource:office", operation, "human:steward:1", issued_by,
                 time.time(), effective_at, None, parent, delegable))

    def check(self, *, principal="resident:grace", scope="office:grace",
              operation="write"):
        return self.authority.authorize(
            principal=principal, resource_id="resource:office",
            action="office.update", operation=operation, scope_ref=scope)

    def test_empty_store_denies(self):
        with self.assertRaises(CapabilityDenied):
            self.check()

    def test_exact_grant(self):
        self.grant()
        self.assertEqual(self.check()["grant_id"], "g1")
        with self.assertRaises(CapabilityDenied):
            self.check(scope="office:other")

    def test_independent_read_and_write(self):
        self.grant(operation="read")
        self.assertEqual(self.check(operation="read")["grant_id"], "g1")
        with self.assertRaises(CapabilityDenied):
            self.check(operation="write")

    def test_revocation(self):
        self.grant()
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE capability_grants SET active=0,revoked_at=?", (time.time(),))
        with self.assertRaises(CapabilityDenied):
            self.check()

    def test_expiration(self):
        self.grant(expiry=time.time()-1)
        with self.assertRaises(CapabilityDenied):
            self.check()

    def test_future_effective_time(self):
        self.grant(effective_at=time.time()+500)
        with self.assertRaises(CapabilityDenied):
            self.check()

    def test_missing_database_fails_closed(self):
        with self.assertRaises(AuthorityUnavailable):
            R3Authority(self.path.parent / "missing.db")

    def test_legacy_untyped_row_never_inherits_read_or_write(self):
        with sqlite3.connect(self.path) as db:
            db.execute("""INSERT INTO capability_grants
              (grant_id,principal,action,scope_ref,active,expires_at)
              VALUES (?,?,?,?,?,?)""", ("legacy", "resident:grace", "office.update",
                                        "office:grace", 1, None))
        with self.assertRaises(CapabilityDenied):
            self.check(operation="read")
        with self.assertRaises(CapabilityDenied):
            self.check(operation="write")

    def test_untyped_invocation_signature_fails_closed(self):
        self.grant()
        with self.assertRaises(CapabilityDenied):
            self.authority.authorize(principal="resident:grace",
                  action="office.update", scope_ref="office:grace")

    def test_parent_delegation_and_revoked_parent(self):
        self.grant(grant_id="parent", operation="read", delegable=1)
        self.grant(grant_id="child", principal="resident:helen",
                   operation="read", parent="parent", issued_by="resident:grace")
        self.assertEqual(self.check(principal="resident:helen",operation="read")["grant_id"], "child")
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE capability_grants SET active=0 WHERE grant_id='parent'")
        with self.assertRaises(CapabilityDenied):
            self.check(principal="resident:helen",operation="read")

    def test_delegate_cannot_outlive_parent(self):
        self.grant(grant_id="parent", operation="read",
                   delegable=1, expiry=time.time()+100)
        self.grant(grant_id="child", principal="resident:helen",
                   operation="read", parent="parent", issued_by="resident:grace",
                   expiry=time.time()+200)
        with self.assertRaises(CapabilityDenied):
            self.check(principal="resident:helen",operation="read")

    def test_durable_audit(self):
        self.authority.audit({"principal": "resident:grace",
            "capability": "r3.example", "action": "office.update",
            "resource_id": "resource:office", "operation": "write",
            "scope_ref": "office:grace", "correlation_id": "call-1",
            "outcome": "DENIED"})
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute(
                "SELECT outcome FROM capability_audit").fetchone()[0], "DENIED")
            self.assertEqual(db.execute(
                "SELECT resource_ref,operation FROM capability_audit").fetchone(),
                ("resource:office","write"))


if __name__ == "__main__":
    unittest.main()
