"""
R3 CONTROLLED SOURCE
File: tests/test_r3a_website.py
Component: R3A-WEBSITE-API-TESTS
File Revision: 1.0.5
Created: 2026-11-07T21:59:13Z
Created By: Codex GPT-6
Purpose: Verify shared-session gating, versioned objective forwarding, and website client assets.
Execution Model: unittest with FastAPI TestClient and mocked Unix socket responses.
Observability: HTTP status/body assertions and CME control request assertions.
Dependencies: FastAPI, httpx, r3_app, unittest.mock.
Authority: R3A Class I website development authorized by Issue #51.
Changed: 2026-11-07T21:59:13Z | R3A-007/R3A-010/R3A-013/R3A-019 | Codex GPT-6 | Add API tests for effective config, authentication, diagnostics, and objective submission.
Changed: 2026-11-07T22:04:07Z | R3A-007/R3A-010 | Codex GPT-6 | Verify request correlation header and preservation of CME correlation IDs.
Changed: 2026-11-07T23:40:00Z | R3A-007/R3A-010 | Codex GPT-6 | Verify the versioned workspace client asset route.
Changed: 2026-11-07T23:55:00Z | R3A-010 | Codex GPT-6 | Verify shared AP3 session gating and no browser bearer-token auth.
Changed: 2026-11-08T13:30:00Z | R3A-WEB-IDENTITY | Verify running identity metadata and accessible rail identity markup.
Changed: 2026-11-08T14:30:00Z | R3A-010/#49/#51 | Verify same-host configured R3 portal login discovery and reject cross-host links.
Supersedes: None.
Contracts: r3a.steward-session.v1; r3a.grace-objective-submission.v1; R3A AP0 diagnostic socket.
Tests: python -m unittest tests.test_r3a_website.
History/Predecessor: New file; initial publication recorded in Git.
"""
from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from r3_app import app


class StewardWebsiteApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.previous_access = app.state.steward_access
        self.access = SimpleNamespace(authenticated_principal=AsyncMock(return_value={"principal_id": "steward:test"}))
        app.state.steward_access = self.access
        self.settings = SimpleNamespace(
            diagnostics_socket="/run/r3a/diagnostics.sock",
            control_socket="/run/r3a/control.sock",
        )

    def tearDown(self):
        app.state.steward_access = self.previous_access

    def test_versioned_workspace_browser_client_is_served(self):
        response = self.client.get("/web/steward-workspace-api.mjs")
        self.assertEqual(response.status_code, 200)
        self.assertIn("r3a.steward-workspace-web.v1", response.text)

    def test_roadmap_module_is_served_and_panel_has_live_provenance_labels(self):
        module = self.client.get("/web/roadmap-status.mjs")
        self.assertEqual(module.status_code, 200)
        self.assertIn("fetchRoadmapIssues", module.text)
        page = self.client.get("/")
        self.assertIn('id="nav-roadmap"', page.text)
        self.assertIn("roadmap:{rect:normalizedRect(roadmapPanel)", page.text)
        self.assertIn("if(p.roadmap)", page.text)
        self.assertIn('id="notifications-opacity"', page.text)
        self.assertIn('id="roadmap-opacity"', page.text)
        self.assertIn("issue reports are not proof of CME execution", module.text)

    def test_website_identity_reports_running_build_version_environment_and_port(self):
        client = TestClient(app, base_url="http://testserver:8311")
        with patch.dict(os.environ, {"R3_WEBSITE_ENVIRONMENT": "Development / Alpha"}):
            response = client.get("/api/v1/website/identity")
        self.assertEqual(response.status_code, 200)
        identity = response.json()
        self.assertEqual(identity["contract"], "r3a.website-identification.v1")
        self.assertEqual(identity["application"], "Riverview R3 Alpha")
        self.assertEqual(identity["website_version"], app.version)
        self.assertEqual(identity["environment"], "Development / Alpha")
        self.assertEqual(identity["service_port"], 8311)
        self.assertTrue(identity["build_commit"] == "unknown" or
                        (7 <= len(identity["build_commit"]) <= 40 and
                         all(char in "0123456789abcdef" for char in identity["build_commit"])))

    def test_identity_exposes_only_configured_same_host_portal_login_url(self):
        client = TestClient(app, base_url="http://testserver:8311")
        with patch.dict(os.environ, {"R3_STEWARD_PORTAL_LOGIN_URL": "http://testserver:8303/login"}):
            response = client.get("/api/v1/website/identity")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["account_portal_login_url"], "http://testserver:8303/login")
        with patch.dict(os.environ, {"R3_STEWARD_PORTAL_LOGIN_URL": "https://attacker.invalid/login"}):
            response = client.get("/api/v1/website/identity")
        self.assertNotIn("account_portal_login_url", response.json())

    def test_identity_exposes_only_valid_external_roadmap_configuration(self):
        client = TestClient(app, base_url="http://testserver:8311")
        valid = {"R3_WEBSITE_ROADMAP_REPOSITORY": "ppow1/R3",
                 "R3_WEBSITE_GITHUB_API_BASE": "https://api.github.com"}
        with patch.dict(os.environ, valid):
            response = client.get("/api/v1/website/identity")
        self.assertEqual(response.json()["roadmap_repository"], "ppow1/R3")
        self.assertEqual(response.json()["roadmap_api_base"], "https://api.github.com")
        invalid = {"R3_WEBSITE_ROADMAP_REPOSITORY": "https://attacker.invalid/x",
                   "R3_WEBSITE_GITHUB_API_BASE": "http://attacker.invalid"}
        with patch.dict(os.environ, invalid):
            response = client.get("/api/v1/website/identity")
        self.assertNotIn("roadmap_repository", response.json())
        self.assertNotIn("roadmap_api_base", response.json())

    def test_steward_login_ui_uses_existing_portal_without_collecting_credentials(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn('id="steward-portal-login"', response.text)
        self.assertIn("R3 portal in the new tab", response.text)
        self.assertNotIn('type="password"', response.text)

    def test_estate_home_contains_keyboard_and_touch_identity_control(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn('id="rail-brand" type="button"', response.text)
        self.assertIn('aria-describedby="website-identity-tooltip"', response.text)
        self.assertIn('id="website-identity-tooltip" role="tooltip" hidden', response.text)
        self.assertIn("pointerenter", response.text)
        self.assertIn("pointerdown", response.text)
        favicon = self.client.get("/favicon.svg")
        self.assertEqual(favicon.status_code, 200)
        self.assertEqual(favicon.headers["content-type"], "image/svg+xml")

    def test_missing_external_auth_configuration_is_explicitly_unavailable(self):
        with patch.dict(os.environ, {}, clear=True):
            response = self.client.get("/api/v1/steward/r3a/status")
        self.assertEqual(response.status_code, 503)

    def test_temporary_bearer_does_not_replace_shared_session(self):
        app.state.steward_access = None
        with patch.dict(os.environ, {"R3A_CONFIG": "/tmp/r3a.json"}), \
                patch("r3a_runtime.control.control_request", new_callable=AsyncMock) as request:
            response = self.client.get("/api/v1/steward/r3a/status",
                                       headers={"Authorization": "Bearer configured"})
        self.assertEqual(response.status_code, 503)
        request.assert_not_awaited()

    def test_configuration_view_uses_current_revision_and_bounded_activation_events(self):
        status = {"observed_at": "2026-11-07T21:00:00Z", "source": "postgresql", "configuration": {
            "revision_id": "rev-2", "schema_version": 1, "source_digest": "abc",
            "activated_at": "2026-11-07T20:00:00Z", "actor": "uid:1000",
            "config": {"module": {"module_id": "resident.grace"}},
        }}
        events = {"events": [
            {"event_type": "config.activated", "event_id": "evt-2", "occurred_at": "2026-11-07T20:00:00Z",
             "actor": "uid:1000", "config_revision": "rev-2", "reason": "configuration activated"},
            {"event_type": "activity.completed", "event_id": "evt-1"},
        ]}
        with patch.dict(os.environ, {"R3A_CONFIG": "/tmp/r3a.json"}), \
                patch("r3a_runtime.config.load_settings", return_value=self.settings), \
                patch("r3a_runtime.control.control_request", new_callable=AsyncMock,
                      side_effect=[status, events]):
            response = self.client.get("/api/v1/steward/r3a/configuration")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["revision"]["revision_id"], "rev-2")
        self.assertEqual(body["effective_values"]["module"]["module_id"], "resident.grace")
        self.assertEqual([row["event_id"] for row in body["activation_history"]], ["evt-2"])
        self.assertFalse(body["history_complete"])
        self.assertFalse(body["write_available"])

    def test_objective_is_forwarded_to_cme_with_idempotency(self):
        result = {"activity_id": "activity-1", "state": "QUEUED", "correlation_id": "cme-correlation-1"}
        with patch.dict(os.environ, {"R3A_CONFIG": "/tmp/r3a.json"}), \
                patch("r3a_runtime.config.load_settings", return_value=self.settings), \
                patch("r3a_runtime.control.control_request", new_callable=AsyncMock,
                      return_value=result) as request:
            response = self.client.post("/api/v1/steward/r3a/objectives", json={
                    "contract": "r3a.grace-objective-submission.v1", "contract_version": "1.0.0",
                    "objective": "Check runtime", "acceptance_criteria": [{
                        "criterion_id": "path", "type": "transition_path",
                        "from_state": "RUNNING", "to_state": "STOPPING"}],
                    "idempotency_key": "website-request-1"})
        self.assertEqual(response.status_code, 202)
        self.assertTrue(response.headers["X-Request-ID"])
        self.assertEqual(response.json()["contract"], "r3a.grace-objective-submission.v1")
        self.assertEqual(response.json()["contract_version"], "1.0.0")
        self.assertEqual(response.json()["activity_id"], "activity-1")
        self.assertEqual(response.json()["correlation_id"], "cme-correlation-1")
        self.assertEqual(request.await_args.args[1], "grace.objective.submit")
        self.assertEqual(request.await_args.kwargs["idempotency_key"], "website-request-1")


if __name__ == "__main__":
    unittest.main()
