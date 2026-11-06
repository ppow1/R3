"""Permanent native R3 authority storage regressions."""
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path

from runtime.capability_authority import R3Authority, initialize_empty_schema
from runtime.capabilities import (AuthorizationExpired, CapabilityDenied,
                                  GrantExpiryMissing, AuthorityUnavailable)


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
        with self.assertRaises(AuthorizationExpired) as caught:
            self.check()
        self.assertEqual(caught.exception.grant["grant_id"], "g1")
        self.assertEqual(caught.exception.grant["state"], "EXPIRED")
        self.assertIn("Steward approval", caught.exception.grant["renewal_action"])

    def test_proposal_grant_diagnostics_are_principal_scoped_and_warn_48_hours_early(self):
        now = time.time()
        with sqlite3.connect(self.path) as db:
            for grant_id, principal, action, operation, expiry in (
                ("draft", "resident:grace", "proposal.draft.submit", "write", now + 24*3600),
                ("status", "resident:grace", "proposal.status.read", "read", now + 8*24*3600),
                ("other", "resident:other", "proposal.draft.submit", "write", now + 3600),
            ):
                db.execute("""INSERT INTO capability_grants
                    (principal,action,scope_ref,expires_at,active,grant_id,resource_ref,
                     operation,approved_by,created_at,delegable)
                    VALUES (?,?,?,?,1,?,?,?,?,?,0)""",
                    (principal, action, "institution:proposal-drafts", expiry, grant_id,
                     "riverview:institutional-proposals", operation,
                     "human:steward:test", now-7*24*3600))
        result = self.authority.authorization_diagnostics(
            principal="resident:grace", now=now)
        self.assertEqual({g["grant_id"] for g in result["grants"]}, {"draft", "status"})
        self.assertEqual(next(g for g in result["grants"] if g["grant_id"] == "draft")["state"],
                         "EXPIRING_SOON")
        self.assertEqual(next(g for g in result["grants"] if g["grant_id"] == "status")["state"],
                         "ACTIVE")

    def test_expiry_warning_scan_returns_exact_grant_evidence(self):
        from runtime.grant_expiry_monitor import scan_once
        now = time.time()
        with sqlite3.connect(self.path) as db:
            db.execute("""INSERT INTO capability_grants
                (principal,action,scope_ref,expires_at,active,grant_id,resource_ref,
                 operation,approved_by,created_at,delegable)
                VALUES (?,?,?,?,1,?,?,?,?,?,0)""",
                ("resident:grace", "proposal.status.read", "institution:proposal-drafts",
                 now+47*3600, "grant-47h", "riverview:institutional-proposals",
                 "read", "human:steward:test", now-7*24*3600))
        grants = scan_once(self.authority, now=now)
        self.assertEqual([g["grant_id"] for g in grants], ["grant-47h"])
        self.assertEqual(grants[0]["expires_at"], now+47*3600)

    def test_missing_expiry_is_an_operational_error_for_temporary_grant(self):
        from runtime.grant_expiry_monitor import scan_once
        now = time.time()
        with sqlite3.connect(self.path) as db:
            db.execute("""INSERT INTO capability_grants
                (principal,action,scope_ref,expires_at,active,grant_id,resource_ref,
                 operation,approved_by,created_at,delegable)
                VALUES (?,?,?,NULL,1,?,?,?,?,?,0)""",
                ("resident:grace", "proposal.draft.submit", "institution:proposal-drafts",
                 "grant-no-expiry", "riverview:institutional-proposals", "write",
                 "human:steward:test", now-10))
        diagnostic = self.authority.authorization_diagnostics(
            principal="resident:grace", now=now)
        self.assertEqual(diagnostic["grants"][0]["state"], "MISSING_EXPIRY")
        self.assertEqual(scan_once(self.authority, now=now)[0]["grant_id"], "grant-no-expiry")
        with self.assertRaises(GrantExpiryMissing) as caught:
            self.authority.authorize(principal="resident:grace",
                action="proposal.draft.submit", operation="write",
                resource_id="riverview:institutional-proposals",
                scope_ref="institution:proposal-drafts")
        self.assertEqual(caught.exception.grant["grant_id"], "grant-no-expiry")

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
