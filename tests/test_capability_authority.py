"""Permanent native R3 authority storage regressions."""
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

    def grant(self, *, scope="office:grace", active=1, expiry=None):
        with sqlite3.connect(self.path) as db:
            db.execute('INSERT INTO capability_grants (principal, action, scope_ref, expires_at, active, grant_id, resource_ref, operation, approved_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                       ("resident:grace", "office.update", scope, expiry, active, "g1", "office:grace", "write", "human:steward:test"))

    def check(self, scope="office:grace"):
        return self.authority.authorize(principal="resident:grace",
             action="office.update", scope_ref=scope,
              resource_id="office:grace", operation="write")

    def test_empty_store_denies(self):
        with self.assertRaises(CapabilityDenied):
            self.check()

    def test_exact_grant(self):
        self.grant()
        self.assertEqual(self.check()["grant_id"], "g1")
        with self.assertRaises(CapabilityDenied):
            self.check("office:other")

    def test_missing_approval_evidence_denied(self):
        self.grant()
        with sqlite3.connect(self.path) as db:
            db.execute(
                "UPDATE capability_grants SET approved_by=NULL WHERE grant_id=?",
                ("g1",)
            )
        with self.assertRaises(CapabilityDenied):
            self.check()

    def test_revocation(self):
        self.grant()
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE capability_grants SET active=0")
        with self.assertRaises(CapabilityDenied):
            self.check()

    def test_expiration(self):
        self.grant(expiry=time.time()-1)
        with self.assertRaises(CapabilityDenied):
            self.check()

    def test_missing_database_fails_closed(self):
        with self.assertRaises(AuthorityUnavailable):
            R3Authority(self.path.parent / "missing.db")

    def test_durable_audit(self):
        self.authority.audit({"principal": "resident:grace",
            "capability": "r3.example", "action": "office.update",
            "scope_ref": "office:grace", "correlation_id": "call-1",
            "outcome": "DENIED"})
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute(
                "SELECT outcome FROM capability_audit").fetchone()[0], "DENIED")


if __name__ == "__main__":
    unittest.main()
