"""
R3 CONTROLLED SOURCE
File: tests/test_r3a_website.py
Component: R3A-WEBSITE-API-TESTS
File Revision: 1.0.8
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
Changed: 2026-11-09T18:10:00Z | AP3/R3A-010 | Verify native R3A login page, HTTPS-only submission, and no R3 portal discovery in native mode.
Changed: 2026-11-09T19:57:00Z | AP3/R3A-010-LIVE-LOGIN | Verify native-mode base routing, no R3 portal UI, and workspace return after login.
Changed: 2026-11-09T21:20:00Z | R3A-LOGIN-REDIRECT-LOOP | Verify only canonical session 401 redirects and operation 401s trigger a session recheck.
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
from fastapi import HTTPException

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
            source_digest="test-config-revision",
        )

    def tearDown(self):
        app.state.steward_access = self.previous_access

    def test_versioned_workspace_browser_client_is_served(self):
        response = self.client.get("/web/steward-workspace-api.mjs")
        self.assertEqual(response.status_code, 200)
        self.assertIn("r3a.steward-workspace-web.v1", response.text)

    def test_native_login_is_same_origin_nostore_and_never_discovers_r3_portal_in_native_mode(self):
        page = self.client.get("/login")
        self.assertEqual(page.status_code, 200)
        self.assertEqual(page.headers["Cache-Control"], "no-store")
        self.assertEqual(page.headers["Referrer-Policy"], "no-referrer")
        self.assertIn("R3A Steward sign in", page.text)
        self.assertIn('id="challenge"', page.text)
        script = self.client.get("/web/steward-login.js")
        self.assertEqual(script.status_code, 200)
        self.assertIn("/api/v1/steward/session", script.text)
        self.assertIn("window.location.replace('/steward')", script.text)
        self.assertIn("window.location.protocol !== 'https:'", script.text)
        self.assertIn("resumeExistingSession();", script.text)
        self.assertNotIn("localStorage", script.text)
        with patch.dict(os.environ, {"R3_WEBSITE_AUTH_MODE": "r3a-native",
                                    "R3_STEWARD_PORTAL_LOGIN_URL": "http://testserver:8303/login"}):
            identity = self.client.get("/api/v1/website/identity")
        self.assertNotIn("account_portal_login_url", identity.json())

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
        workspace = self.client.get("/web/steward-workspace-api.mjs")
        self.assertIn("r3:steward-session-established", workspace.text)
        self.assertIn("r3:steward-session-revoked", workspace.text)
        self.assertIn("new CustomEvent('r3:steward-session-established'", page.text)
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

    def test_native_mode_base_url_routes_to_independent_login_and_workspace_has_no_r3_login(self):
        with patch.dict(os.environ, {"R3_WEBSITE_AUTH_MODE": "r3a-native",
                                    "R3_STEWARD_PORTAL_LOGIN_URL": "http://testserver:8303/login"}):
            response = self.client.get("/", follow_redirects=False)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.headers["location"], "/login")
            self.assertEqual(response.headers["cache-control"], "no-store")
            login = self.client.get(response.headers["location"])
            self.assertEqual(login.status_code, 200)
            self.assertIn("R3A Steward sign in", login.text)
            workspace = self.client.get("/steward")
        self.assertEqual(workspace.status_code, 200)
        self.assertIn('id="chat-message-list"', workspace.text)
        self.assertIn('id="nav-chat"', workspace.text)
        self.assertIn('id="nav-engineering"', workspace.text)
        self.assertIn('id="profile-settings"', workspace.text)
        self.assertIn('id="website-signout"', workspace.text)
        self.assertIn("Verifying R3A Website session", workspace.text)
        self.assertIn("/api/v1/steward/session", workspace.text)
        self.assertNotIn('id="steward-connect"', workspace.text)
        self.assertNotIn('id="steward-disconnect"', workspace.text)
        self.assertNotIn("Open Steward sign-in", workspace.text)
        self.assertNotIn("chat-sign-in", workspace.text)
        for legacy_copy in ("Sign in through the existing R3 account portal",
                            "Open existing R3 account sign-in",
                            "R3 portal session not authenticated"):
            self.assertNotIn(legacy_copy, workspace.text)
        self.assertIn("window.r3aCheckWebsiteSession", workspace.text)
        self.assertIn("if (response.status === 401) { window.r3aRequireWebsiteLogin(); return null; }", workspace.text)

    def test_workspace_operation_401_rechecks_session_without_forcing_login_redirect(self):
        response = self.client.get("/web/steward-workspace-api.mjs")
        self.assertEqual(response.status_code, 200)
        self.assertIn("r3aCheckWebsiteSession?.()", response.text)
        self.assertNotIn("r3aRequireWebsiteLogin?.()", response.text)

    def test_login_page_stays_available_when_session_verification_returns_401(self):
        login = self.client.get("/login")
        script = self.client.get("/web/steward-login.js")
        self.assertEqual(login.status_code, 200)
        self.assertIn('value="enroll"', login.text)
        self.assertEqual(script.status_code, 200)
        self.assertIn("resumeExistingSession", script.text)
        self.assertIn("body.state === 'authenticated'", script.text)
        self.assertNotIn("r3aRequireWebsiteLogin", script.text)

    def test_nonpublic_website_apis_require_the_same_authenticated_session(self):
        self.access.authenticated_principal.side_effect = HTTPException(401, "Steward session unavailable")
        for path in ("/api/v1/engineering/branches", "/api/v1/engineering/worktrees", "/api/v1/snapshot"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.headers.get("Cache-Control"), "no-store")
        response = self.client.post("/api/v1/snapshot", json={})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers.get("Cache-Control"), "no-store")

    def test_estate_home_contains_keyboard_and_touch_identity_control(self):
        with patch.dict(os.environ, {"R3_WEBSITE_AUTH_MODE": "legacy"}):
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

    def test_shared_ap3_configuration_supplies_cme_socket_without_secondary_runtime_config(self):
        socket_path = os.path.abspath("r3a-control.sock")
        self.access.config = {"cme": {"control_socket": socket_path}}
        with patch.dict(os.environ, {}, clear=True), \
                patch("r3a_runtime.control.control_request", new_callable=AsyncMock,
                      return_value={"observed_at": "2026-11-09T12:00:00Z"}) as control:
            response = self.client.get("/api/v1/steward/r3a/status")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(control.await_args.args[:2], (socket_path, "diagnostics.status"))

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

    def test_authenticated_about_view_uses_dynamic_managed_module_diagnostics(self):
        runtime = {"observed_at": "2026-11-09T12:00:00Z", "source_freshness": "fresh",
                   "implementation_revision": "release-sha", "processes": [
                       {"component_id": "ring0", "state": "RUNNING", "health": "healthy", "freshness": "fresh"},
                       {"component_id": "cme", "state": "RUNNING", "health": "healthy", "freshness": "fresh"}],
                   "modules": [{"module_id": "resident.grace", "module_version": "1.2.12",
                                "lifecycle_state": "ACTIVE", "health": "healthy"},
                               {"module_id": "r3a.knowledge", "module_version": "1.1.0",
                                "lifecycle_state": "ACTIVE", "health": "healthy"}]}
        with patch.dict(os.environ, {"R3A_CONFIG": "/tmp/r3a.json"}), \
                patch("r3a_runtime.config.load_settings", return_value=self.settings), \
                patch("r3a_runtime.control.control_request", new_callable=AsyncMock,
                      return_value=runtime):
            response = self.client.get("/api/v1/steward/about")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["contract"], "r3a.website-about.v1")
        self.assertEqual(body["deployed_runtime_revision"], "release-sha")
        self.assertEqual(body["grace"]["version"], "1.2.12")
        self.assertEqual([row["module_id"] for row in body["modules"]],
                         ["resident.grace", "r3a.knowledge"])

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

    def test_resident_discovery_forwards_only_the_authenticated_principal_to_cme(self):
        result = {"contract": "r3a.resident-directory-view.v1", "residents": [],
                  "freshness": "current"}
        with patch.dict(os.environ, {"R3A_CONFIG": "/tmp/r3a.json"}), \
                patch("r3a_runtime.config.load_settings", return_value=self.settings), \
                patch("r3a_runtime.control.control_request", new_callable=AsyncMock,
                      return_value=result) as control:
            response = self.client.get("/api/v1/steward/residents")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(control.await_args.args[1], "steward.residents.discover")
        self.assertEqual(control.await_args.args[2]["principal_id"], "steward:test")

    def test_conversation_routes_use_durable_cme_contract_and_idempotency(self):
        conversation_id = "a1a1b9f9-fbd3-4cb9-9e77-25bfe8e2800e"
        client_conversation_id = "bd295347-7a57-4d63-98ae-cd06ce34f446"
        message_id = "c06f41fd-75bc-4f21-af89-8116f15e4a0e"
        with patch.dict(os.environ, {"R3A_CONFIG": "/tmp/r3a.json"}), \
                patch("r3a_runtime.config.load_settings", return_value=self.settings), \
                patch("r3a_runtime.control.control_request", new_callable=AsyncMock,
                      side_effect=[{"contract": "r3a.steward-conversation.v1",
                                    "conversation": {"conversation_id": conversation_id}},
                                   {"contract": "r3a.steward-conversation.v1",
                                    "message": {"message_id": message_id, "delivery_state": "processing"}}]) as control:
            created = self.client.post("/api/v1/steward/conversations", json={
                "resident_id": "resident.grace", "client_conversation_id": client_conversation_id},
                headers={"Origin": "http://testserver"})
            sent = self.client.post(f"/api/v1/steward/conversations/{conversation_id}/messages", json={
                "client_message_id": message_id, "text": "Please introduce yourself."},
                headers={"Origin": "http://testserver"})
        self.assertEqual(created.status_code, 201)
        self.assertEqual(sent.status_code, 202)
        self.assertEqual(control.await_args_list[0].args[1], "steward.conversation.create")
        self.assertEqual(control.await_args_list[1].args[1], "steward.conversation.send")
        self.assertEqual(control.await_args_list[1].kwargs["idempotency_key"],
                         f"website-message:{conversation_id}:{message_id}")

    def test_conversation_api_denies_missing_authenticated_session(self):
        self.access.authenticated_principal.side_effect = HTTPException(401, "session required")
        response = self.client.get("/api/v1/steward/residents")
        self.assertEqual(response.status_code, 401)

    def test_notification_inbox_uses_ap3_principal_and_registered_cme_capability(self):
        inbox = {"contract": "r3a.notification-inbox.v1", "contract_version": "1.0.0",
                 "freshness": "current", "deliveries": [], "next_cursor": None,
                 "presentation_timezone": "UTC"}
        result = {"outcome": "SUCCEEDED", "authorization": {"allowed": True}, "output": inbox}
        with patch.dict(os.environ, {"R3A_CONFIG": "/tmp/r3a.json"}), \
                patch("r3a_runtime.config.load_settings", return_value=self.settings), \
                patch("r3a_runtime.control.control_request", new_callable=AsyncMock,
                      return_value=result) as control:
            response = self.client.get("/api/v1/notifications?cursor=page-2")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), inbox)
        self.assertEqual(control.await_args.args[1], "capability.invoke")
        invocation = control.await_args.args[2]["request"]
        self.assertEqual(invocation["operation_id"], "notification.delivery.read")
        self.assertEqual(invocation["operation_contract_version"], "1.0.0")
        self.assertEqual(invocation["caller"]["principal_id"], "steward:test")
        self.assertEqual(invocation["input"], {"cursor": "page-2", "limit": 50})

    def test_notification_lifecycle_uses_cme_grants_and_replay_key(self):
        delivery_id = "9d4e4325-27b3-43aa-9197-08d6bab5a1c0"
        ack = {"contract_id": "r3a.notification-delivery", "status": "acknowledged"}
        resolution = {"contract_id": "r3a.notification-delivery", "status": "resolved"}
        results = [{"outcome": "SUCCEEDED", "authorization": {"allowed": True}, "output": ack},
                   {"outcome": "SUCCEEDED", "authorization": {"allowed": True}, "output": resolution}]
        with patch.dict(os.environ, {"R3A_CONFIG": "/tmp/r3a.json"}), \
                patch("r3a_runtime.config.load_settings", return_value=self.settings), \
                patch("r3a_runtime.control.control_request", new_callable=AsyncMock,
                      side_effect=results) as control:
            acknowledged = self.client.post(
                f"/api/v1/notifications/{delivery_id}/acknowledgment",
                json={"idempotency_key": "website-ack-0001", "note": "Seen"},
                headers={"Origin": "http://testserver"})
            resolved = self.client.post(
                f"/api/v1/notifications/{delivery_id}/resolution",
                json={"idempotency_key": "website-resolve-01", "disposition": "Handled",
                      "evidence_refs": ["notification:e1"]}, headers={"Origin": "http://testserver"})
        self.assertEqual(acknowledged.status_code, 200)
        self.assertEqual(resolved.status_code, 200)
        ack_invocation, resolve_invocation = [call.args[2]["request"] for call in control.await_args_list]
        self.assertEqual(ack_invocation["operation_id"], "notification.delivery.acknowledge")
        self.assertEqual(ack_invocation["caller"]["principal_id"], "steward:test")
        self.assertEqual(ack_invocation["idempotency_key"], "website-ack-0001")
        self.assertEqual(resolve_invocation["operation_id"], "notification.delivery.resolve")
        self.assertEqual(resolve_invocation["input"]["evidence_refs"], ["notification:e1"])

    def test_notification_inbox_requires_ap3_session_before_cme_dispatch(self):
        self.access.authenticated_principal.side_effect = HTTPException(401, "session required")
        with patch("r3a_runtime.control.control_request", new_callable=AsyncMock) as control:
            response = self.client.get("/api/v1/notifications")
        self.assertEqual(response.status_code, 401)
        control.assert_not_awaited()

    def test_notification_cme_denial_is_not_converted_to_success(self):
        result = {"outcome": "DENIED", "authorization": {"allowed": False}, "output": None}
        with patch.dict(os.environ, {"R3A_CONFIG": "/tmp/r3a.json"}), \
                patch("r3a_runtime.config.load_settings", return_value=self.settings), \
                patch("r3a_runtime.control.control_request", new_callable=AsyncMock,
                      return_value=result):
            response = self.client.get("/api/v1/notifications")
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
