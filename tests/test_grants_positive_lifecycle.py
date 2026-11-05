"""Permanent native-session HTTP grant lifecycle regression.

All accounts, credentials and grants are isolated test fixtures.
No production database or production service is accessed.
"""
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from r3_native_sessions import (
    NativeSessions,
    initialize_empty_schema as init_sessions,
)
from r3_native_auth_api import build_native_auth_router
from r3_steward_authority_api import build_steward_authority_router
from runtime.capability_authority import (
    R3Authority,
    initialize_empty_schema as init_authority,
)
from runtime.capabilities import CapabilityDenied
from runtime.grant_management import R3GrantManagement
from runtime.resident_identity import R3ResidentIdentity

ORIGIN = "https://riverview.ionoge.com"
BASE = "/api/v1/steward-authority"


class PositiveGrantLifecycleTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)

        auth_db = root / "native.sqlite"
        authority_db = root / "authority.sqlite"
        init_sessions(auth_db)
        init_authority(authority_db)

        self.sessions = NativeSessions(auth_db)
        self.sessions.bootstrap_steward(
            "steward@example.test",
            "Strong-test-password-123",
        )
        self.authority = R3Authority(authority_db)

        environment = patch.dict(
            os.environ,
            {"R3_CANONICAL_AUTHORITY_DB": str(authority_db)},
        )
        environment.start()
        self.addCleanup(environment.stop)

        native_store_patch = patch(
            "r3_native_auth_api.native_store",
            return_value=self.sessions,
        )
        native_store_patch.start()
        self.addCleanup(native_store_patch.stop)

        app = FastAPI()
        app.include_router(
            build_native_auth_router(
                store_factory=lambda: self.sessions,
                allowed_origins=(ORIGIN,),
            )
        )
        app.include_router(build_steward_authority_router(root))

        self.client = TestClient(app, base_url=ORIGIN)
        self.addCleanup(self.client.close)

        login = self.client.post(
            "/api/v1/native-auth/login",
            headers={"Origin": ORIGIN},
            json={
                "email": "steward@example.test",
                "password": "Strong-test-password-123",
            },
        )
        self.assertEqual(login.status_code, 200, login.text)

        self.csrf = self.client.cookies.get("r3_steward_csrf")
        self.assertTrue(self.csrf)

    def mutation(self, path, body):
        return self.client.post(
            BASE + "/" + path,
            headers={
                "Origin": ORIGIN,
                "X-Riverview-CSRF": self.csrf,
            },
            json=body,
        )

    def authorize(self, principal):
        return self.authority.authorize(
            principal=principal,
            resource_id="office:grace",
            action="office.update",
            operation="write",
            scope_ref="office:grace",
        )

    def test_authenticated_approval_delegation_revocation(self):
        request_body = {
            "target_principal": "resident:grace",
            "resource_ref": "office:grace",
            "action": "office.update",
            "operation": "write",
            "scope_ref": "office:grace",
            "reason": "isolated lifecycle acceptance",
            "idempotency_key": "positive-http-request-001",
            "expires_at": time.time() + 3600,
            "delegable": True,
        }

        # An authenticated request does not itself confer authority.
        requested = self.mutation("request", request_body)
        self.assertEqual(requested.status_code, 200, requested.text)
        request_id = requested.json()["request_id"]
        self.assertEqual(requested.json()["status"], "PENDING")

        with self.assertRaises(CapabilityDenied):
            self.authorize("resident:grace")

        pending = self.client.get(BASE + "/pending")
        self.assertEqual(pending.status_code, 200, pending.text)
        self.assertTrue(
            any(item["request_id"] == request_id for item in pending.json())
        )

        # Approval must pass the native Steward session and CSRF boundary.
        approved = self.mutation(
            "decide",
            {
                "request_id": request_id,
                "approve": True,
                "reason": "isolated Steward approval",
            },
        )
        self.assertEqual(approved.status_code, 200, approved.text)
        self.assertEqual(approved.json()["status"], "APPROVED")
        parent_id = approved.json()["grant_id"]
        self.assertEqual(self.authorize("resident:grace")["grant_id"], parent_id)

        # Credential provisioning is intentionally service-only here.
        # This is an isolated test fixture, not a production API grant.
        credential_service = R3GrantManagement(
            self.authority,
            authenticate_steward=lambda context: "human:steward:test-fixture",
            authenticate_delegator=R3ResidentIdentity(
                self.authority
            ).authenticate,
        )
        issued = credential_service.issue_resident_credential(
            steward_context=object(),
            resident_principal="resident:grace",
            expires_at=time.time() + 1800,
            reason="isolated resident identity fixture",
            idempotency_key="positive-resident-credential-001",
        )
        token = issued["credential"]

        # The HTTP delegation must independently authenticate the resident.
        delegated = self.client.post(
            BASE + "/delegate",
            headers={"Authorization": "Bearer " + token},
            json={
                "parent_grant_id": parent_id,
                "target_principal": "resident:reviewer",
                "expires_at": time.time() + 900,
                "reason": "isolated bounded delegation",
                "idempotency_key": "positive-delegation-001",
            },
        )
        self.assertEqual(delegated.status_code, 200, delegated.text)
        child_id = delegated.json()["grant_id"]
        self.assertEqual(
            self.authorize("resident:reviewer")["grant_id"],
            child_id,
        )

        inventory = self.client.get(BASE + "/inventory")
        self.assertEqual(inventory.status_code, 200, inventory.text)
        self.assertTrue(
            {parent_id, child_id}.issubset(
                {row["grant_id"] for row in inventory.json()}
            )
        )

        revoked = self.mutation(
            "revoke",
            {
                "grant_id": parent_id,
                "reason": "isolated lifecycle revocation",
            },
        )
        self.assertEqual(revoked.status_code, 200, revoked.text)
        self.assertEqual(revoked.json()["status"], "REVOKED")

        with self.assertRaises(CapabilityDenied):
            self.authorize("resident:grace")
        with self.assertRaises(CapabilityDenied):
            self.authorize("resident:reviewer")

        history = self.client.get(BASE + "/history")
        self.assertEqual(history.status_code, 200, history.text)
        events = {row["event"] for row in history.json()}
        self.assertTrue(
            {
                "REQUESTED",
                "APPROVED",
                "RESIDENT_CREDENTIAL_ISSUED",
                "DELEGATED",
                "REVOKED",
            }.issubset(events),
            events,
        )

    def test_active_inventory_excludes_expired_and_future_grants(self):
        """Release regression: Active reflects effective time, inventory retains history."""
        now = time.time()
        with self.authority._connect() as db:
            def row(suffix, effective_at, expires_at, active=1, revoked_at=None):
                db.execute(
                    """INSERT INTO capability_grants
                       (grant_id, principal, action, scope_ref, active,
                        expires_at, resource_ref, operation, issued_by, approved_by,
                        created_at, effective_at, revoked_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    ("test-" + suffix, "resident:test", "office.read", "office:test",
                     active, expires_at, "office:test", "read",
                     "human:steward:fixture", "human:steward:fixture",
                     now, effective_at, revoked_at),
                )
            row("active", now - 60, now + 3600)
            row("expired", now - 3600, now - 60)
            row("future", now + 3600, now + 7200)
            row("revoked", now - 60, now + 3600, revoked_at=now - 10)
            row("inactive", now - 60, now + 3600, active=0)

        active = self.client.get(BASE + "/active")
        inventory = self.client.get(BASE + "/inventory")
        self.assertEqual(active.status_code, 200, active.text)
        self.assertEqual(inventory.status_code, 200, inventory.text)
        self.assertEqual(
            {r["grant_id"] for r in active.json()},
            {"test-active"},
        )
        self.assertEqual(
            {r["grant_id"] for r in inventory.json()},
            {"test-active", "test-expired", "test-future",
             "test-revoked", "test-inactive"},
        )

    def test_missing_csrf_cannot_approve(self):
        response = self.client.post(
            BASE + "/decide",
            headers={"Origin": ORIGIN},
            json={
                "request_id": "nonexistent",
                "approve": True,
                "reason": "must be rejected before lookup",
            },
        )
        self.assertEqual(response.status_code, 401)

    def test_cross_origin_mutation_denied(self):
        response = self.client.post(
            BASE + "/request",
            headers={
                "Origin": "https://attacker.example",
                "X-Riverview-CSRF": self.csrf,
            },
            json={
                "target_principal": "resident:grace",
                "resource_ref": "office:grace",
                "action": "office.update",
                "operation": "write",
                "scope_ref": "office:grace",
                "reason": "must be rejected",
                "idempotency_key": "cross-origin-rejection",
            },
        )
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
