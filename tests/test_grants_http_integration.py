"""Permanent HTTP security regressions for R3 Grants & Delegations.

Uses an isolated canonical authority database. No production grants.
"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from runtime.capability_authority import initialize_empty_schema


class GrantsHTTPIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "authority.sqlite"
        initialize_empty_schema(self.db)

        self.env = patch.dict(
            os.environ,
            {"R3_CANONICAL_AUTHORITY_DB": str(self.db)}
        )
        self.env.start()
        self.addCleanup(self.env.stop)

        from r3_app import app
        self.client = TestClient(
            app, raise_server_exceptions=False
        )
        self.client.__enter__()
        self.addCleanup(
            self.client.__exit__, None, None, None
        )

    def test_anonymous_administration_denied(self):
        for path in (
            "/api/v1/steward-authority/capabilities",
            "/api/v1/steward-authority/inventory",
            "/api/v1/steward-authority/pending",
            "/api/v1/steward-authority/active",
            "/api/v1/steward-authority/history",
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 401)

    def test_anonymous_mutations_denied(self):
        for path in ("request", "decide", "revoke"):
            with self.subTest(path=path):
                response = self.client.post(
                    "/api/v1/steward-authority/" + path,
                    json={},
                )
                self.assertEqual(response.status_code, 401)

    def test_resident_delegation_requires_bearer(self):
        response = self.client.post(
            "/api/v1/steward-authority/delegate",
            json={
                "parent_grant_id": "missing",
                "target_principal": "resident:test",
                "reason": "isolated rejection test",
                "idempotency_key": "reject-anonymous",
            },
        )
        self.assertEqual(response.status_code, 401)

    def test_spoofed_principal_header_denied(self):
        response = self.client.get(
            "/api/v1/steward-authority/inventory",
            headers={
                "X-R3-Principal": "human:steward:spoofed",
                "X-Riverview-Principal": "human:steward:spoofed",
            },
        )
        self.assertEqual(response.status_code, 401)

    def test_invalid_resident_bearer_denied(self):
        response = self.client.post(
            "/api/v1/steward-authority/delegate",
            headers={"Authorization": "Bearer invalid-token"},
            json={
                "parent_grant_id": "missing",
                "target_principal": "resident:test",
                "reason": "invalid credential rejection",
                "idempotency_key": "reject-invalid",
            },
        )
        self.assertIn(response.status_code, (401, 403))

    def test_no_implicit_grants_created(self):
        import sqlite3

        with sqlite3.connect(self.db) as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM capability_grants"
            ).fetchone()[0]

        self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
