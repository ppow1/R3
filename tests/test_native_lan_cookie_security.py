"""Native authentication cookies remain secure on LAN and HTTPS."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from r3_native_sessions import NativeSessions, initialize_empty_schema


class NativeLANCookieSecurity(unittest.TestCase):
    def test_http_lan_does_not_downgrade_cookies(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "sessions.sqlite"
            initialize_empty_schema(db)
            NativeSessions(db).bootstrap_steward(
                "steward@example.test",
                "Strong-test-password-123",
            )

            with patch.dict(os.environ, {
                "R3_NATIVE_AUTH_DB": str(db),
            }):
                from r3_app import app

                with TestClient(
                    app,
                    base_url="http://192.168.1.155:8303",
                ) as client:
                    response = client.post(
                        "/api/v1/native-auth/login",
                        headers={
                            "Origin": "http://192.168.1.155:8303"
                        },
                        json={
                            "email": "steward@example.test",
                            "password": "Strong-test-password-123",
                        },
                    )

                    self.assertEqual(
                        response.status_code, 403, response.text
                    )

                    cookies = response.headers.get_list(
                        "set-cookie"
                    )
                    self.assertFalse(
                        any(
                            "r3_steward_session=" in cookie.lower()
                            for cookie in cookies
                        ),
                        "Rejected HTTP login must not issue a session",
                    )

                    protected = client.get(
                        "/api/v1/steward-authority/inventory"
                    )
                    self.assertEqual(
                        protected.status_code, 401,
                        protected.text,
                    )


if __name__ == "__main__":
    unittest.main()
