# R3 CONTROLLED SOURCE
# File: tests/test_r3_native_auth_api.py
# Component: R3-NATIVE-AUTH-HTTP-REGRESSION
# File Revision: 1.0.0
# Created: 2026-11-04 UTC | ChatGPT GPT-6
# Purpose: Permanent native authentication HTTP contract tests.
# Authority: Steward; Website Development #16
# Supersedes: None

import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from r3_native_sessions import NativeSessions, initialize_empty_schema
from r3_native_auth_api import build_native_auth_router


ORIGIN = "https://riverview.ionoge.com"


class NativeAuthHTTPTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)

        db = Path(tmp.name) / "auth.sqlite"
        initialize_empty_schema(db)

        self.store = NativeSessions(db)
        self.store.bootstrap_steward(
            "steward@example.test",
            "Strong-test-password-123",
        )

        app = FastAPI()
        app.include_router(
            build_native_auth_router(
                store_factory=lambda: self.store,
                allowed_origins=(ORIGIN,),
            )
        )

        self.client = TestClient(
            app,
            base_url=ORIGIN,
        )
        self.addCleanup(self.client.close)

    def login(self):
        return self.client.post(
            "/api/v1/native-auth/login",
            headers={"Origin": ORIGIN},
            json={
                "email": "steward@example.test",
                "password": "Strong-test-password-123",
            },
        )

    def test_login_and_session(self):
        response = self.login()
        self.assertEqual(response.status_code, 200)

        session = self.client.get(
            "/api/v1/native-auth/session"
        )
        self.assertEqual(session.status_code, 200)
        self.assertEqual(
            session.json()["identity"]["roles"],
            ["steward"],
        )

    def test_anonymous_session_denied(self):
        response = self.client.get(
            "/api/v1/native-auth/session"
        )
        self.assertEqual(response.status_code, 401)

    def test_invalid_password_denied(self):
        response = self.client.post(
            "/api/v1/native-auth/login",
            headers={"Origin": ORIGIN},
            json={
                "email": "steward@example.test",
                "password": "wrong",
            },
        )
        self.assertEqual(response.status_code, 401)

    def test_cross_origin_login_denied(self):
        response = self.client.post(
            "/api/v1/native-auth/login",
            headers={"Origin": "https://other.example"},
            json={
                "email": "steward@example.test",
                "password": "Strong-test-password-123",
            },
        )
        self.assertEqual(response.status_code, 403)

    def test_session_cookie_is_secure_and_httponly(self):
        response = self.login()
        self.assertEqual(response.status_code, 200)
        cookies = response.headers.get_list("set-cookie")
        session_cookie = next(
            c for c in cookies
            if c.startswith("r3_steward_session=")
        )
        self.assertIn("secure", session_cookie.lower())
        self.assertIn("httponly", session_cookie.lower())
        self.assertIn("samesite=strict", session_cookie.lower())

    def test_logout_requires_csrf(self):
        self.login()
        response = self.client.delete(
            "/api/v1/native-auth/session",
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(response.status_code, 401)

    def test_logout_revokes_session(self):
        self.login()
        csrf = self.client.cookies.get("r3_steward_csrf")

        response = self.client.delete(
            "/api/v1/native-auth/session",
            headers={
                "Origin": ORIGIN,
                "X-Riverview-CSRF": csrf,
            },
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.get(
            "/api/v1/native-auth/session"
        )
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
