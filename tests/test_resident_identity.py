# R3 CONTROLLED SOURCE
# File: tests/test_resident_identity.py
# Component: R3-RESIDENT-SERVICE-CREDENTIAL-REGRESSION
# File Revision: 1.0.0
# Created: 2026-11-04 UTC (date precision only)
# Created By: ChatGPT GPT-6
# Purpose: Permanent independent resident credential issuance, validation, rotation/revocation tests.
# Execution Model: Isolated canonical R3 SQLite database; no production identities.
# Observability: Assertions on credential hashes, authenticated principals and management audit.
# Dependencies: Python stdlib; runtime/resident_identity.py; runtime/grant_management.py.
# Authority: Shared Website #16 / Grace #28 contract, no R2.
# Changed: 2026-11-04 UTC | R3-GRACE-ID-005 | Test secure credential lifecycle.
# Supersedes: None
# Contracts: docs/r3-native-tool-contract.md
# Tests: python -m unittest tests.test_resident_identity -v
# History/Predecessor: New controlled test.
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path

from runtime.capabilities import CapabilityDenied
from runtime.capability_authority import R3Authority, initialize_empty_schema
from runtime.grant_management import R3GrantManagement
from runtime.resident_identity import R3ResidentIdentity


class ResidentIdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "canonical.db"
        initialize_empty_schema(self.db)
        self.authority = R3Authority(self.db)
        def steward(context):
            if context != "valid-r3-human-session":
                raise CapabilityDenied("Not authenticated Steward")
            return "human:steward:unit"
        self.management = R3GrantManagement(self.authority, steward)
        self.identity = R3ResidentIdentity(self.authority)

    def issue(self, *, expires=None, key="resident-issue-1"):
        return self.management.issue_resident_credential(
            steward_context="valid-r3-human-session",
            resident_principal="resident:grace",
            expires_at=expires if expires is not None else time.time()+3600,
            reason="Independently authorized resident service",
            idempotency_key=key)

    def test_no_default_resident_authentication(self):
        with sqlite3.connect(self.db) as conn:
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM resident_credentials").fetchone()[0], 0)
        with self.assertRaises(CapabilityDenied):
            self.identity.authenticate("steward-session-cookie")

    def test_provisioned_independent_resident_token_authenticates(self):
        result = self.issue()
        self.assertEqual(result["status"], "ISSUED")
        self.assertEqual(self.identity.authenticate(result["credential"]), "resident:grace")
        with sqlite3.connect(self.db) as conn:
            stored = conn.execute("SELECT secret_hash FROM resident_credentials").fetchone()[0]
            self.assertNotEqual(stored, result["credential"])
            self.assertNotIn(result["credential"], str(self.management.history(
                steward_context="valid-r3-human-session")))

    def test_wrong_token_and_browser_cookie_denied(self):
        result = self.issue()
        with self.assertRaises(CapabilityDenied):
            self.identity.authenticate(result["credential"][:-1] + "x")
        with self.assertRaises(CapabilityDenied):
            self.identity.authenticate("human:steward:unit")
        with self.assertRaises(CapabilityDenied):
            self.identity.authenticate("r3_session=valid-r3-human-session")

    def test_revoke_credential_denies_future_requests(self):
        result = self.issue()
        self.management.revoke_resident_credential(
            steward_context="valid-r3-human-session",
            credential_id=result["credential_id"], reason="Security rotation")
        with self.assertRaises(CapabilityDenied):
            self.identity.authenticate(result["credential"])

    def test_expiry_denies(self):
        result = self.issue()
        with sqlite3.connect(self.db) as conn:
            conn.execute(
                "UPDATE resident_credentials SET expires_at=? WHERE credential_id=?",
                (time.time()-1, result["credential_id"]))
        with self.assertRaises(CapabilityDenied):
            self.identity.authenticate(result["credential"])

    def test_idempotent_issuance_does_not_expose_same_secret_twice(self):
        expiry = time.time()+3600
        first = self.issue(expires=expiry)
        second = self.issue(expires=expiry)
        self.assertEqual(second["credential_id"], first["credential_id"])
        self.assertEqual(second["status"], "ALREADY_ISSUED")
        self.assertNotIn("credential", second)
        with sqlite3.connect(self.db) as conn:
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM resident_credentials").fetchone()[0], 1)

    def test_unauthenticated_human_cannot_issue_or_revoke(self):
        with self.assertRaises(CapabilityDenied):
            self.management.issue_resident_credential(
                steward_context="fake",
                resident_principal="resident:grace",
                expires_at=time.time()+3600, reason="Untrusted",
                idempotency_key="fake-key")


if __name__ == "__main__":
    unittest.main()
