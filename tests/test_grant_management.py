# R3 CONTROLLED SOURCE
# File: tests/test_grant_management.py
# Component: R3-CANONICAL-GRANT-MANAGEMENT-TESTS
# File Revision: 1.0.1
# Created: 2026-11-04 UTC (date precision only)
# Created By: ChatGPT GPT-6
# Purpose: Permanent Steward-authenticated request/approve/revoke/delegate and single-store tests.
# Execution Model: Temporary local SQLite DB and deterministic credential verifier.
# Observability: Effective exact grants and canonical append-only audit.
# Dependencies: Python stdlib, runtime/capability_authority.py, runtime/grant_management.py
# Authority: Steward unified R3 integration contract issues #16 and #28.
# Changed: 2026-11-04 UTC | R3-GRACE-AUTH-013 | Cover canonical management lifecycle and fail-closed identity.
# Changed: 2026-11-04 UTC | R3-GRACE-RECOVERY-002 | Permanent tests for idempotent delegation after revocation.
# Supersedes: None
# Contracts: docs/r3-native-tool-contract.md
# Tests: python -m unittest tests.test_grant_management -v
# History/Predecessor: New controlled test.
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path

from runtime.capabilities import CapabilityDenied
from runtime.capability_authority import R3Authority, initialize_empty_schema
from runtime.grant_management import R3GrantManagement


class ManagementTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "canonical-r3.db"
        initialize_empty_schema(self.db)
        self.authority = R3Authority(self.db)
        def human(context):
            if context != "valid-human-session":
                raise CapabilityDenied("R3 human session denied")
            return "human:steward:owner"
        def resident(context):
            if context != "valid-resident-credential":
                raise CapabilityDenied("R3 resident credential denied")
            return "resident:grace"
        self.service = R3GrantManagement(self.authority, human, resident)

    def request(self, *, operation="read", key="request-1", delegable=False,
                expires_at=None, principal="resident:grace"):
        return self.service.request(
            steward_context="valid-human-session",
            target_principal=principal, resource_ref="registry:local",
            action="inventory.snapshot", operation=operation,
            scope_ref="institution:r3", reason="Operational authorization review",
            idempotency_key=key, delegable=delegable, expires_at=expires_at)

    def approve(self, request_id):
        return self.service.decide(
            steward_context="valid-human-session", request_id=request_id,
            approve=True, reason="Explicit Steward approval")

    def effective(self, *, operation="read", principal="resident:grace"):
        return self.authority.authorize(
            principal=principal, resource_id="registry:local",
            action="inventory.snapshot", operation=operation,
            scope_ref="institution:r3")

    def test_no_default_grant_on_schema_creation(self):
        with self.assertRaises(CapabilityDenied):
            self.effective()
        with sqlite3.connect(self.db) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM capability_grants").fetchone()[0], 0)

    def test_request_pending_is_not_authority(self):
        req = self.request()
        self.assertEqual(req["status"], "PENDING")
        self.assertEqual(len(self.service.list_requests(
            steward_context="valid-human-session", status="PENDING")), 1)
        with self.assertRaises(CapabilityDenied):
            self.effective()

    def test_approved_exact_read_not_write(self):
        req = self.request()
        decision = self.approve(req["request_id"])
        self.assertEqual(decision["status"], "APPROVED")
        self.assertEqual(self.effective()["grant_id"], decision["grant_id"])
        with self.assertRaises(CapabilityDenied):
            self.effective(operation="write")

    def test_explicit_write_approval_independent_of_read(self):
        req = self.request(operation="write")
        decision = self.approve(req["request_id"])
        self.assertEqual(self.effective(operation="write")["grant_id"], decision["grant_id"])
        with self.assertRaises(CapabilityDenied):
            self.effective(operation="read")

    def test_rejection_never_creates_grant(self):
        req = self.request()
        result = self.service.decide(
            steward_context="valid-human-session",
            request_id=req["request_id"], approve=False, reason="Not needed")
        self.assertIsNone(result["grant_id"])
        with self.assertRaises(CapabilityDenied):
            self.effective()
        with sqlite3.connect(self.db) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM capability_grants").fetchone()[0], 0)

    def test_revocation_immediately_denies(self):
        grant = self.approve(self.request()["request_id"])
        self.service.revoke(steward_context="valid-human-session",
                            grant_id=grant["grant_id"], reason="No longer needed")
        with self.assertRaises(CapabilityDenied):
            self.effective()
        self.assertEqual([item["event"] for item in self.service.history(
            steward_context="valid-human-session")], ["REQUESTED", "APPROVED", "REVOKED"])

    def test_human_admin_credential_required(self):
        with self.assertRaises(CapabilityDenied):
            self.service.request(
                steward_context="human:steward:owner", target_principal="resident:grace",
                resource_ref="registry:local", action="inventory.snapshot",
                operation="write", scope_ref="institution:r3",
                reason="Spoofing principal string", idempotency_key="invalid")
        with self.assertRaises(CapabilityDenied):
            self.service.list_grants(steward_context="invalid-session")

    def test_request_idempotency_and_conflict(self):
        a = self.request()
        b = self.request()
        self.assertEqual(a["request_id"], b["request_id"])
        with self.assertRaises(CapabilityDenied):
            self.request(operation="write")
        self.approve(a["request_id"])
        self.assertEqual(self.approve(a["request_id"])["status"], "APPROVED")
        with sqlite3.connect(self.db) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM capability_grants").fetchone()[0], 1)

    def test_expired_grant_denied(self):
        expiry = time.time() + 10
        self.approve(self.request(expires_at=expiry)["request_id"])
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE capability_grants SET expires_at=?", (time.time()-1,))
        with self.assertRaises(CapabilityDenied):
            self.effective()

    def test_delegation_subset_and_parent_revocation(self):
        expiry = time.time() + 60
        parent = self.approve(self.request(
            delegable=True, expires_at=expiry)["request_id"])["grant_id"]
        child = self.service.delegate(
            resident_credential="valid-resident-credential",
            parent_grant_id=parent, target_principal="resident:helen",
            expires_at=expiry-10, reason="Delegated status observation",
            idempotency_key="delegate-1")
        self.assertEqual(self.effective(principal="resident:helen")["grant_id"],
                         child["grant_id"])
        self.service.revoke(steward_context="valid-human-session",grant_id=parent,
                            reason="Parent permission revoked")
        with self.assertRaises(CapabilityDenied):
            self.effective(principal="resident:helen")

    def test_idempotent_delegation_retry_after_parent_revocation_denied(self):
        expiry = time.time() + 60
        parent = self.approve(self.request(
            delegable=True, expires_at=expiry)["request_id"])["grant_id"]
        kwargs = dict(resident_credential="valid-resident-credential",
            parent_grant_id=parent, target_principal="resident:helen",
            expires_at=expiry-10, reason="Delegated status observation",
            idempotency_key="delegate-retry-revoked-parent")
        first = self.service.delegate(**kwargs)
        self.assertEqual(self.service.delegate(**kwargs)["grant_id"], first["grant_id"])
        self.service.revoke(steward_context="valid-human-session",grant_id=parent,
                            reason="Parent revoked before retry")
        with self.assertRaises(CapabilityDenied):
            self.service.delegate(**kwargs)

    def test_idempotent_delegation_retry_after_child_revocation_denied(self):
        expiry = time.time() + 60
        parent = self.approve(self.request(
            delegable=True, expires_at=expiry)["request_id"])["grant_id"]
        kwargs = dict(resident_credential="valid-resident-credential",
            parent_grant_id=parent, target_principal="resident:helen",
            expires_at=expiry-10, reason="Delegated status observation",
            idempotency_key="delegate-retry-revoked-child")
        first = self.service.delegate(**kwargs)
        self.service.revoke(steward_context="valid-human-session",
                            grant_id=first["grant_id"],reason="Child revoked")
        with self.assertRaises(CapabilityDenied):
            self.service.delegate(**kwargs)

    def test_nondelegable_grant_cannot_delegate(self):
        parent = self.approve(self.request()["request_id"])["grant_id"]
        with self.assertRaises(CapabilityDenied):
            self.service.delegate(
                resident_credential="valid-resident-credential",
                parent_grant_id=parent, target_principal="resident:helen",
                expires_at=None, reason="No delegation allowed",
                idempotency_key="delegate-rejected")

    def test_delegation_expiry_cannot_exceed_parent(self):
        expiry = time.time() + 60
        parent = self.approve(self.request(
            delegable=True, expires_at=expiry)["request_id"])["grant_id"]
        with self.assertRaises(CapabilityDenied):
            self.service.delegate(
                resident_credential="valid-resident-credential",
                parent_grant_id=parent, target_principal="resident:helen",
                expires_at=expiry+10, reason="Exceeds parent",
                idempotency_key="delegate-expired")

    def test_canonical_audit_is_same_database(self):
        self.approve(self.request()["request_id"])
        self.assertEqual(len(self.service.history(steward_context="valid-human-session")), 2)
        with sqlite3.connect(self.db) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM capability_management_audit").fetchone()[0],2)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM capability_requests").fetchone()[0],1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM capability_grants").fetchone()[0],1)


if __name__ == "__main__":
    unittest.main()
