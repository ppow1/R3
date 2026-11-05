"""Full application acceptance: native R3 authentication and authority."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from r3_native_sessions import NativeSessions, initialize_empty_schema
from runtime.capability_authority import initialize_empty_schema as initialize_authority_schema


class NativeSiteAcceptanceTests(unittest.TestCase):

    def test_native_login_site_grants_logout(self):
        origin = "https://riverview.ionoge.com"

        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "native.sqlite"
            initialize_empty_schema(db)
            authority_db = Path(directory) / "authority.sqlite"
            initialize_authority_schema(authority_db)
            NativeSessions(db).bootstrap_steward(
                "steward@example.test",
                "Strong-test-password-123",
            )

            with patch.dict(os.environ, {
                "R3_NATIVE_AUTH_DB": str(db),
                "R3_CANONICAL_AUTHORITY_DB": str(authority_db),
            }):
                from r3_app import app
                from fastapi import HTTPException

                def fixture_principal(request, cfg):
                    token = request.cookies.get("r3_steward_session")
                    if not token:
                        raise HTTPException(401, "Fixture session required")
                    try:
                        identity = NativeSessions(db).authenticate(token)
                    except Exception as exc:
                        raise HTTPException(401, "Fixture session invalid") from exc
                    if identity["role"] != "steward":
                        raise HTTPException(403, "Fixture Steward required")
                    return identity["email"]


                with patch("r3_app._principal", side_effect=fixture_principal), TestClient(app, base_url=origin) as client:
                    anonymous = client.get(
                        "/api/v1/steward-authority/inventory"
                    )
                    self.assertEqual(
                        anonymous.status_code, 401
                    )

                    login = client.post(
                        "/api/v1/native-auth/login",
                        headers={"Origin": origin},
                        json={
                            "email": "steward@example.test",
                            "password": "Strong-test-password-123",
                        },
                    )
                    self.assertEqual(
                        login.status_code, 200, login.text
                    )

                    session = client.get(
                        "/api/v1/native-auth/session"
                    )
                    self.assertEqual(
                        session.status_code, 200, session.text
                    )

                    site = client.get("/")
                    self.assertEqual(
                        site.status_code, 200, site.text
                    )

                    inventory = client.get(
                        "/api/v1/steward-authority/inventory"
                    )
                    self.assertEqual(
                        inventory.status_code, 200,
                        inventory.text
                    )

                    csrf = client.cookies.get(
                        "r3_steward_csrf"
                    )
                    self.assertTrue(csrf)

                    missing_csrf = client.delete(
                        "/api/v1/native-auth/session",
                        headers={"Origin": origin},
                    )
                    self.assertEqual(
                        missing_csrf.status_code, 401
                    )

                    logout = client.delete(
                        "/api/v1/native-auth/session",
                        headers={
                            "Origin": origin,
                            "X-Riverview-CSRF": csrf,
                        },
                    )
                    self.assertEqual(
                        logout.status_code, 200,
                        logout.text
                    )

                    revoked = client.get(
                        "/api/v1/steward-authority/inventory"
                    )
                    self.assertEqual(
                        revoked.status_code, 401
                    )


if __name__ == "__main__":
    unittest.main()
