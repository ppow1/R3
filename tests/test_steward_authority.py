"""Permanent Steward Authority integration contract regressions.

The authority is an authenticated, canonical grant-management API.
No anonymous access, implicit grants, or direct website grant writes.
"""
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from r3_app import app
from r3_steward_authority_api import build_steward_authority_router

ROOT = Path(__file__).resolve().parents[1]
BASE = "/api/v1/steward-authority"


class StewardAuthorityRegressionTests(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(
            app, raise_server_exceptions=False
        )
        self.addCleanup(self.client.close)

    def test_canonical_routes_registered(self):
        router = build_steward_authority_router(ROOT)
        routes = {
            (route.path, method)
            for route in router.routes
            for method in route.methods
        }

        expected = {
            ("GET", "capabilities"),
            ("GET", "inventory"),
            ("GET", "pending"),
            ("GET", "active"),
            ("GET", "history"),
            ("POST", "request"),
            ("POST", "decide"),
            ("POST", "revoke"),
            ("POST", "delegate"),
        }

        for method, name in expected:
            with self.subTest(method=method, name=name):
                self.assertIn((BASE + "/" + name, method), routes)

    def test_anonymous_inventory_fails_closed(self):
        for name in (
            "capabilities", "inventory", "pending",
            "active", "history",
        ):
            with self.subTest(name=name):
                response = self.client.get(BASE + "/" + name)
                self.assertEqual(response.status_code, 401)

    def test_anonymous_mutations_fail_closed(self):
        for name in ("request", "decide", "revoke"):
            with self.subTest(name=name):
                response = self.client.post(
                    BASE + "/" + name, json={}
                )
                self.assertEqual(response.status_code, 401)

    def test_delegation_requires_resident_credential(self):
        response = self.client.post(
            BASE + "/delegate",
            json={
                "parent_grant_id": "missing",
                "target_principal": "resident:test",
                "reason": "unauthenticated rejection",
                "idempotency_key": "unauthenticated-rejection",
            },
        )
        self.assertEqual(response.status_code, 401)

    def test_no_legacy_mutation_contract(self):
        router = build_steward_authority_router(ROOT)
        paths = {route.path for route in router.routes}

        self.assertNotIn(BASE + "/approve", paths)
        self.assertNotIn(BASE + "/deny", paths)
        self.assertNotIn(BASE + "/renew", paths)

        self.assertIn(BASE + "/decide", paths)
        self.assertIn(BASE + "/request", paths)
        self.assertIn(BASE + "/revoke", paths)

    def test_authority_assets_registered(self):
        paths = {
            getattr(route, "path", None)
            for route in app.routes
        }
        self.assertIn("/web/steward-authority.js", paths)
        self.assertIn("/web/steward-authority.css", paths)

    def test_authority_ui_linked(self):
        page = (ROOT / "web/index.html").read_text()
        self.assertIn("steward-authority.js", page)
        self.assertIn("steward-authority.css", page)

    def test_expired_and_revoked_tabs_use_disjoint_termination_reasons(self):
        """Release guard: revocation precedence, not the inactive bit."""
        source = (ROOT / "web/steward-authority.js").read_text(encoding="utf-8")
        self.assertIn('record.revoked_at == null &&', source)
        self.assertIn('Number(record.expires_at) <= now', source)
        self.assertIn('rows.filter(record => record.revoked_at != null)', source)
        self.assertNotIn('Number(record.active) === 0', source)

    def test_authority_assets_exist(self):
        self.assertTrue(
            (ROOT / "web/steward-authority.js").is_file()
        )
        self.assertTrue(
            (ROOT / "web/steward-authority.css").is_file()
        )


if __name__ == "__main__":
    unittest.main()
