# R3 CONTROLLED SOURCE
# File: tests/test_sitewide_auth_boundary.py
# Component: R3-SITEWIDE-AUTH-REGRESSION
# File Revision: 1.0.0
# Created: 2026-11-04 UTC
# Purpose: Fail closed on anonymous access to the estate and institutional telemetry.
# Execution Model: Permanent source regression; unittest with FastAPI TestClient
# Authority: Steward website-wide authentication requirement
# Changed: 2026-11-04 UTC | R3-AUTH-GATE-001 | Add permanent anonymous access regression
# Tests: Not executed; expected to FAIL against currently unprotected R3 source; dependencies mandatory
"""Regression gate: sensitive R3 content must not be anonymously accessible.

This test intentionally fails until a real authenticated session boundary is
integrated. It does not mock a successful login or accept a browser-only gate.
Production reverse-proxy access control also requires separate HTTP acceptance.
"""
import unittest

try:
    from fastapi.testclient import TestClient
    from r3_app import app
except ImportError as exc:
    raise RuntimeError("R3 authentication regression requires FastAPI and httpx; missing dependencies are not a pass") from exc


class SitewideAuthBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app, follow_redirects=False)
        self.addCleanup(self.client.close)

    def test_anonymous_estate_home_is_not_served(self):
        response = self.client.get("/")
        self.assertIn(response.status_code, (302, 303, 307, 308, 401),
                      "Anonymous requests must not receive the estate HTML")

    def test_anonymous_institution_runtime_is_not_disclosed(self):
        response = self.client.get("/api/v1/institution/runtime")
        self.assertEqual(response.status_code, 401,
                         "Authentication must run before reading runtime telemetry")

    def test_anonymous_engineering_metadata_is_not_disclosed(self):
        for route in ("/api/v1/engineering/branches",
                      "/api/v1/engineering/worktrees",
                      "/api/v1/snapshot"):
            with self.subTest(route=route):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 401,
                                 f"Authentication must precede {route}")

    def test_anonymous_artwork_index_is_not_disclosed(self):
        response = self.client.get("/api/v1/artwork")
        self.assertEqual(response.status_code, 401,
                         "Artwork metadata is institutional content")

    def test_anonymous_snapshot_cannot_be_written(self):
        response = self.client.post("/api/v1/snapshot", json={})
        self.assertEqual(response.status_code, 401,
                         "Authentication must precede request validation or mutation")


if __name__ == "__main__":
    unittest.main()
