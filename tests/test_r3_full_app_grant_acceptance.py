"""Permanent isolated full-application R3 grant lifecycle acceptance.

Uses the actual r3_app.app with temporary native-session and authority
databases. Never uses production credentials, grants, or services.
"""

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from r3_native_sessions import NativeSessions
from r3_native_sessions import initialize_empty_schema as init_sessions
from runtime.capability_authority import R3Authority
from runtime.capability_authority import initialize_empty_schema as init_authority
from runtime.capabilities import CapabilityDenied


ORIGIN = "https://riverview.ionoge.com"
BASE = "/api/v1/steward-authority"


class FullApplicationGrantAcceptance(unittest.TestCase):

    def test_authenticated_grant_lifecycle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session_db = root / "sessions.sqlite"
            authority_db = root / "authority.sqlite"

            init_sessions(session_db)
            init_authority(authority_db)

            sessions = NativeSessions(session_db)
            sessions.bootstrap_steward(
                "steward@example.test",
                "Strong-test-password-123",
            )

            with patch.dict(os.environ, {
                "R3_NATIVE_AUTH_DB": str(session_db),
                "R3_CANONICAL_AUTHORITY_DB": str(authority_db),
            }):
                from r3_app import app

                authority = R3Authority(authority_db)

                with TestClient(app, base_url=ORIGIN) as client:
                    self.assertEqual(
                        client.get(BASE + "/inventory").status_code,
                        401,
                    )

                    login = client.post(
                        "/api/v1/native-auth/login",
                        headers={"Origin": ORIGIN},
                        json={
                            "email": "steward@example.test",
                            "password": "Strong-test-password-123",
                        },
                    )
                    self.assertEqual(login.status_code, 200, login.text)

                    csrf = client.cookies.get("r3_steward_csrf")
                    self.assertTrue(csrf)

                    inventory = client.get(BASE + "/inventory")
                    self.assertEqual(
                        inventory.status_code, 200, inventory.text
                    )

                    headers = {
                        "Origin": ORIGIN,
                        "X-Riverview-CSRF": csrf,
                    }

                    def mutate(endpoint, payload):
                        response = client.post(
                            BASE + "/" + endpoint,
                            headers=headers,
                            json=payload,
                        )
                        self.assertEqual(
                            response.status_code, 200, response.text
                        )
                        return response.json()

                    principal = "resident:grace"
                    resource = "office:grace"

                    def authorize():
                        return authority.authorize(
                            principal=principal,
                            resource_id=resource,
                            action="office.update",
                            operation="write",
                            scope_ref=resource,
                        )

                    requested = mutate("request", {
                        "target_principal": principal,
                        "resource_ref": resource,
                        "action": "office.update",
                        "operation": "write",
                        "scope_ref": resource,
                        "reason": "permanent isolated acceptance",
                        "idempotency_key": "full-app-permanent-001",
                        "expires_at": time.time() + 3600,
                        "delegable": True,
                    })
                    self.assertEqual(requested["status"], "PENDING")

                    with self.assertRaises(CapabilityDenied):
                        authorize()

                    approved = mutate("decide", {
                        "request_id": requested["request_id"],
                        "approve": True,
                        "reason": "isolated Steward approval",
                    })
                    self.assertEqual(approved["status"], "APPROVED")

                    grant_id = approved["grant_id"]
                    self.assertEqual(
                        authorize()["grant_id"], grant_id
                    )

                    active = client.get(BASE + "/active")
                    self.assertEqual(
                        active.status_code, 200, active.text
                    )
                    self.assertTrue(any(
                        row["grant_id"] == grant_id
                        for row in active.json()
                    ))

                    revoked = mutate("revoke", {
                        "grant_id": grant_id,
                        "reason": "isolated acceptance revocation",
                    })
                    self.assertEqual(revoked["status"], "REVOKED")

                    with self.assertRaises(CapabilityDenied):
                        authorize()

                    history = client.get(BASE + "/history")
                    self.assertEqual(
                        history.status_code, 200, history.text
                    )
                    events = {
                        row["event"] for row in history.json()
                    }
                    self.assertTrue({
                        "REQUESTED", "APPROVED", "REVOKED"
                    }.issubset(events))

                    logout = client.delete(
                        "/api/v1/native-auth/session",
                        headers=headers,
                    )
                    self.assertEqual(
                        logout.status_code, 200, logout.text
                    )
                    self.assertEqual(
                        client.get(BASE + "/inventory").status_code,
                        401,
                    )


if __name__ == "__main__":
    unittest.main()
