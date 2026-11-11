"""
R3 CONTROLLED TEST SOURCE
File: tests/test_r3a_steward_access.py
Component: R3A-AP3-STEWARD-ACCESS
File Revision: 1.2.3
Created: 2026-11-07T21:37:42Z
Created By: Codex GPT-6
Purpose: Verify Steward assertion validation, opaque sessions, revocation, CSRF origin policy, and CME identity delegation.
Execution Model: unittest with in-process ASGI requests and isolated provider fakes.
Observability: Assertions cover HTTP decisions, CME caller attribution, and durable-event provider calls.
Dependencies: FastAPI, httpx, r3a_runtime.steward_access.
Authority: AP3-M1 Issue #49; focused verification.
Changed: 2026-11-07T21:37:42Z | AP3-M1 | Codex GPT-6 | Add auth/session lifecycle and delegation acceptance checks.
Changed: 2026-11-07T21:44:36Z | AP3-M1 | Codex GPT-6 | Verify authenticated-at and factor provenance in the signed assertion contract.
Changed: 2026-11-07T21:48:11Z | AP3-M1 | Codex GPT-6 | Verify CME grant denials and truthful unavailable health reporting.
Changed: 2026-11-07T21:53:47Z | AP3-M1 | Codex GPT-6 | Exercise the exact Bitwarden provider lease shape and freshness threshold behavior.
Changed: 2026-11-07T21:56:49Z | AP3-M1 | Codex GPT-6 | Assert strict config validation rejects invalid scalar types.
Changed: 2026-11-07T22:00:10Z | AP3-M1 | Codex GPT-6 | Verify Bitwarden remote revision and machine principal provenance persist without the secret.
Changed: 2026-11-07T22:02:18Z | AP3-M1 | Codex GPT-6 | Assert durable denial events for invalid origins and post-logout access.
Changed: 2026-11-07T22:03:19Z | AP3-M1 | Codex GPT-6 | Verify remote configuration rejects non-Secure session cookies.
Changed: 2026-11-07T23:43:25Z | AP3-M1 | Codex GPT-6 | Verify replacement identity-provider binding, published principal/session response, and shared CME path.
Changed: 2026-11-07T23:43:25Z | AP3-M1 | Codex GPT-6 | Reject malformed replacement-provider results.
Changed: 2026-11-07T23:43:25Z | AP3-M1 | Codex GPT-6 | Verify the website session read returns the trusted provider principal.
Changed: 2026-11-07T23:53:17Z | AP3-M1/AP3-M2 | Codex GPT-6 | Verify provider reason-code/provenance compatibility, lease ordering/cleanup, and Website dependency revocation.
Changed: 2026-11-07T23:57:23Z | AP3-M1/#51 | Codex GPT-6 | Verify the prototype operation returns correlated CME activity and audit evidence through the shared session.
Changed: 2026-11-08T00:01:13Z | AP3-M1/#51 | Codex GPT-6 | Verify /api/v1 cookie sharing, Origin-protected Website mutations, and generic CME registry discovery.
Changed: 2026-11-08T13:45:00Z | AP3-M1/#51 | Codex GPT-6 | Verify existing R3 portal session binding to the shared revocable AP3 session.
Changed: 2026-11-09T16:32:39Z | R3A-AUTH-INDEPENDENCE-001 | Codex GPT-6 | Use the R3A-only cookie namespace in session tests and guard published examples against R3 cookie collisions.
Changed: 2026-11-09T17:06:17Z | R3A-AUTH-INDEPENDENCE-SECURE-LAN | Codex GPT-6 | Assert the target R3A configuration requires Secure cookies for LAN authentication.
Changed: 2026-11-09T19:23:00Z | AP3-R3A-010-LAN-IP | Codex GPT-6 | Verify the native session cookie is limited to the R3A path and is not sent to R3 authentication routes.
Supersedes: None.
Contracts: r3a.identity-provider.v1; r3a.steward-principal.v1; r3a.steward-session.v1; r3a.capability-invocation.v1.
Tests: python -m unittest tests.test_r3a_steward_access.
History/Predecessor: New file; initial publication recorded in Git.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import Depends, FastAPI, Request

from r3a_runtime.steward_access import (
    AccessUnavailable, HmacIngressIdentityProvider, IdentityAssertion, R3AccountSessionIdentityProvider,
    StewardAccess, create_access_from_environment, load_access_config,
    require_steward_principal,
)


class MemorySessionStore:
    def __init__(self):
        self.sessions = {}
        self.assertions = set()
        self.events = []

    def create(self, *, token_digest, principal_id, issuer, authenticated_at, factor_refs,
               expires_at, assertion_id, correlation_id, secret_provenance):
        if assertion_id in self.assertions:
            raise PermissionError("identity_assertion_replayed")
        self.assertions.add(assertion_id)
        self.sessions[token_digest] = {"principal_id": principal_id, "issuer": issuer,
                                       "authenticated_at": authenticated_at, "factor_refs": factor_refs,
                                       "secret_provenance": secret_provenance,
                                       "issued_at": datetime.now(timezone.utc), "expires_at": expires_at,
                                       "revoked_at": None, "correlation_id": correlation_id}

    def read(self, token_digest):
        return self.sessions.get(token_digest)

    def revoke(self, token_digest, *, correlation_id):
        record = self.sessions.get(token_digest)
        if not record or record["revoked_at"]:
            return False
        record["revoked_at"] = datetime.now(timezone.utc)
        return True

    def audit(self, *, event_type, principal_id, outcome, correlation_id, details):
        self.events.append({"event_type": event_type, "principal_id": principal_id,
                            "outcome": outcome, "correlation_id": correlation_id, **details})
        return f"event-{len(self.events)}"


def config():
    return {"schema_id": "r3a.steward-access.config.v1", "schema_version": 1, "enabled": True,
            "session_dsn_env": "R3A_TEST_STEWARD_DSN",
            "identity": {"issuer": "test-ingress", "steward_principal_id": "steward:test",
                         "assertion_secret_ref": {"provider_id": "test-secrets", "provider_version": "1.1.0",
                                                  "secret_id": "test-secret"}, "assertion_max_age_seconds": 60},
            "secret_provider_manifest": "/etc/r3a/test/manifest.json",
            "secret_provider_config": "/etc/r3a/test/provider.json",
            "session": {"cookie_name": "r3a_steward_session", "lifetime_seconds": 600,
                        "connect_timeout_seconds": 3, "secure_cookie": False,
                        "allowed_origins": ["http://testserver"]},
            "cme": {"control_socket": "/tmp/r3a-cme.sock", "request_timeout_seconds": 5,
                    "health_stale_after_seconds": 30},
            "remote_transport": {"state": "unavailable", "public_exposure": False}}


class CookieNamespaceContractTests(unittest.TestCase):
    def test_published_configs_use_r3a_cookie_namespace(self):
        examples = ("steward_access.config.example.json",
                    "steward_access.r3-portal.config.example.json")
        for name in examples:
            with self.subTest(name=name):
                path = Path(__file__).parents[1] / "r3a_plugins" / name
                cookie_name = json.loads(path.read_text(encoding="utf-8"))["session"]["cookie_name"]
                self.assertTrue(cookie_name.startswith("r3a_"))
                self.assertNotIn(cookie_name, {"r3_steward_session", "rv_account_session",
                                               "rv_account_csrf"})
                self.assertNotEqual("steward:pat", json.loads(path.read_text(encoding="utf-8"))
                                     .get("identity", {}).get("steward_principal_id"))

    def test_target_steward_config_requires_secure_cookie(self):
        path = Path(__file__).parents[1] / "r3a_plugins" / "steward_access.config.example.json"
        session = json.loads(path.read_text(encoding="utf-8"))["session"]
        self.assertEqual("r3a_steward_session", session["cookie_name"])
        self.assertIs(session["secure_cookie"], True)


def assertion_headers(*, issuer="test-ingress", subject="steward:test", assertion_id=None,
                      issued_at=None, authenticated_at=None, factors="", key="test-key"):
    assertion_id = assertion_id or str(uuid.uuid4())
    issued_at = int(time.time()) if issued_at is None else issued_at
    timestamp = str(issued_at)
    authenticated_at = authenticated_at or datetime.now(timezone.utc).isoformat()
    body = "\n".join((issuer, subject, assertion_id, timestamp, authenticated_at, factors)).encode()
    signature = hmac.new(key.encode(), body, hashlib.sha256).hexdigest()
    return {"X-R3-Identity-Issuer": issuer, "X-R3-Identity-Subject": subject,
            "X-R3-Identity-ID": assertion_id, "X-R3-Identity-Time": timestamp,
            "X-R3-Identity-Authenticated-At": authenticated_at, "X-R3-Identity-Factors": factors,
            "X-R3-Identity-Signature": signature, "Origin": "http://testserver"}


class StewardAccessTests(unittest.IsolatedAsyncioTestCase):
    class Lease:
        def __init__(self, correlation_id):
            self.provider_id = "test-secrets"
            self.provider_version = "1.1.0"
            self.secret_id = "test-secret"
            self.remote_revision = "test-revision"
            self.fetched_at = datetime.now(timezone.utc).isoformat()
            self.machine_principal = type("Machine", (), {})()
            self.machine_principal.contract_id = "r3a.machine-principal.v1"
            self.machine_principal.contract_version = "1.0.0"
            self.machine_principal.principal_id = "machine:test"
            self.machine_principal.issuer = "test-secret-provider"
            self.machine_principal.authenticated_at = datetime.now(timezone.utc).isoformat()
            self.machine_principal.correlation_id = correlation_id
            self.closed = False

        def reveal(self):
            return "test-key"

        def close(self):
            self.closed = True

    class SecretProvider:
        def __init__(self):
            self.leases = []

        def resolve(self, _reference, *, correlation_id):
            lease = StewardAccessTests.Lease(correlation_id)
            self.leases.append(lease)
            return lease

    class SecretProviderErrorStub(Exception):
        def __init__(self, outcome, reason_code):
            self.outcome = outcome
            self.reason_code = reason_code
            super().__init__("synthetic redacted provider failure")

    async def asyncSetUp(self):
        self.store = MemorySessionStore()
        self.secret_provider = self.SecretProvider()
        self.identity_provider = HmacIngressIdentityProvider(
            config(), self.secret_provider, config()["identity"]["assertion_secret_ref"])
        self.access = StewardAccess(config(), self.store, self.identity_provider)
        self.app = FastAPI()
        self.app.include_router(self.access.router())
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://testserver")

    async def test_replaceable_identity_provider_uses_shared_session_and_grant_path(self):
        now = datetime.now(timezone.utc)
        class ReplacementProvider:
            contract_id = "r3a.identity-provider.v1"
            contract_version = "1.4.2"
            calls = []

            def authenticate(inner_self, request, *, correlation_id):
                inner_self.calls.append(correlation_id)
                return IdentityAssertion("portal-oidc", "steward:replacement", "oidc-jti-1",
                                         int(time.time()), now, ("webauthn",), {"adapter": "oidc-test"})

        replacement = ReplacementProvider()
        self.access = StewardAccess(config(), self.store, replacement)
        app = FastAPI()
        app.state.steward_access = self.access
        app.include_router(self.access.router())

        @app.get("/api/v1/steward/r3a/private")
        async def website_private(principal=Depends(require_steward_principal)):
            return principal

        @app.post("/api/v1/steward/notifications/private")
        async def website_mutation(principal=Depends(require_steward_principal)):
            return principal

        @app.get("/api/v1/auth/session")
        async def r3_account_route(request: Request):
            return {"r3a_cookie_received": "r3a_steward_session" in request.cookies}

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url="http://testserver") as client:
            response = await client.post("/api/v1/steward/session",
                                         headers={"Origin": "http://testserver",
                                                  "X-Correlation-ID": str(uuid.uuid4())})
            self.assertEqual(200, response.status_code)
            self.assertIn("Path=/api/v1/steward", response.headers["set-cookie"])
            payload = response.json()
            self.assertEqual("r3a.steward-session.v1", payload["contract"])
            self.assertEqual({"contract": "r3a.steward-principal.v1",
                              "principal_id": "steward:replacement", "issuer": "portal-oidc",
                              "authenticated_at": now.isoformat(), "factor_refs": ["webauthn"]},
                             payload["principal"])
            self.assertEqual(1, len(replacement.calls))
            self.assertEqual("steward:replacement",
                             next(iter(self.store.sessions.values()))["principal_id"])
            r3_session = await client.get("/api/v1/auth/session")
            self.assertEqual(200, r3_session.status_code)
            self.assertFalse(r3_session.json()["r3a_cookie_received"])
            website_identity = await client.get("/api/v1/steward/r3a/private")
            self.assertEqual(200, website_identity.status_code)
            self.assertEqual("steward:replacement", website_identity.json()["principal_id"])
            self.assertEqual(403, (await client.post("/api/v1/steward/notifications/private")).status_code)
            mutation = await client.post("/api/v1/steward/notifications/private",
                                         headers={"Origin": "http://testserver"})
            self.assertEqual(200, mutation.status_code)
            self.assertEqual("steward:replacement", mutation.json()["principal_id"])
            current = await client.get("/api/v1/steward/session")
            self.assertEqual(200, current.status_code)
            self.assertEqual("steward:replacement", current.json()["principal"]["principal_id"])
            invocation = {"contract_id": "r3a.capability-invocation.v1",
                          "operation_id": "institution.directory.discover",
                          "operation_contract_version": "1.0.0", "invocation_id": str(uuid.uuid4()),
                          "idempotency_key": str(uuid.uuid4()), "caller": {"principal_id": "browser:fake"},
                          "input": {}}

            async def fake_control(_socket, operation, payload, idempotency_key, timeout):
                self.assertEqual("capability.invoke", operation)
                self.assertEqual("steward:replacement", payload["request"]["caller"]["principal_id"])
                return {"state": "SUCCEEDED", "activity_id": "activity-prototype-1",
                        "event_ids": ["cme-event-prototype-1"],
                        "correlation_id": payload["request"]["correlation_id"],
                        "authorization": {"audit_event_id": "cme-audit-prototype-1"}}

            with patch("r3a_runtime.control.control_request", new=AsyncMock(side_effect=fake_control)):
                result = await client.post("/api/v1/steward/operations/invoke",
                                           json={"request": invocation},
                                           headers={"Origin": "http://testserver"})
            self.assertEqual(200, result.status_code)
            self.assertEqual("activity-prototype-1", result.json()["result"]["activity_id"])
            self.assertEqual(["cme-event-prototype-1"], result.json()["result"]["event_ids"])
            self.assertEqual("cme-audit-prototype-1",
                             result.json()["result"]["authorization"]["audit_event_id"])
            self.assertEqual(result.json()["correlation_id"],
                             result.json()["result"]["correlation_id"])
            self.assertEqual(result.json()["correlation_id"], self.store.events[-1]["correlation_id"])
            ended = await client.delete("/api/v1/steward/session", headers={"Origin": "http://testserver"})
            self.assertEqual({"contract": "r3a.steward-session.v1", "state": "revoked",
                              "revoked": True, "principal_id": "steward:replacement",
                              "correlation_id": ended.json()["correlation_id"]}, ended.json())
            self.assertEqual(401, (await client.get("/api/v1/steward/r3a/private")).status_code)
            self.assertEqual("steward.website.access_denied", self.store.events[-1]["event_type"])

    def test_rejects_unknown_identity_provider_contract_version(self):
        provider = type("WrongProvider", (), {"contract_id": "r3a.identity-provider.v1",
                                                "contract_version": "2.0.0"})()
        with self.assertRaisesRegex(AccessUnavailable, "identity_provider_contract_unsupported"):
            StewardAccess(config(), self.store, provider)

    def test_rejects_malformed_identity_provider_result(self):
        with self.assertRaisesRegex(AccessUnavailable, "identity_provider_contract_result_invalid"):
            StewardAccess._validate_provider_assertion({"principal_id": "browser:forged"})

    async def test_secret_provider_reason_code_is_preserved_as_durable_structured_status(self):
        class UnavailableProvider:
            def resolve(_self, _reference, *, correlation_id):
                raise StewardAccessTests.SecretProviderErrorStub(
                    "UNAVAILABLE", "credentials_unavailable")

        access = StewardAccess(config(), self.store,
                               HmacIngressIdentityProvider(config(), UnavailableProvider(),
                                                           config()["identity"]["assertion_secret_ref"]))
        app = FastAPI()
        app.include_router(access.router())
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url="http://testserver") as client:
            response = await client.post("/api/v1/steward/session", headers=assertion_headers())
        self.assertEqual(503, response.status_code)
        self.assertEqual("Steward authentication unavailable", response.json()["detail"])
        self.assertEqual("steward.authentication.unavailable", self.store.events[-1]["event_type"])
        self.assertEqual("credentials_unavailable", self.store.events[-1]["reason_code"])
        self.assertEqual("UNAVAILABLE", self.store.events[-1]["provider_outcome"])

    async def test_capability_discovery_is_generic_read_only_and_session_protected(self):
        await self.client.post("/api/v1/steward/session", headers=assertion_headers())
        registry = [{"descriptor": {"operation_id": "institution.directory.discover",
                                     "contract_version": "1.0.0"}, "health": "available"}]
        with patch("r3a_runtime.control.control_request",
                   new=AsyncMock(return_value={"operations": registry})) as call:
            response = await self.client.get("/api/v1/steward/capabilities")
        self.assertEqual(200, response.status_code)
        self.assertEqual("r3a.steward-capability-discovery.v1", response.json()["contract"])
        self.assertEqual(registry, response.json()["operations"])
        self.assertFalse(response.json()["authorization_evaluated"])
        self.assertEqual("capability.discover", call.await_args.args[1])
        self.assertEqual("steward.capability_discovery", self.store.events[-1]["event_type"])

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_invalid_subject_and_signature_are_denied_and_audited(self):
        response = await self.client.post("/api/v1/steward/session",
                                          headers=assertion_headers(subject="resident:grace"))
        self.assertEqual(401, response.status_code)
        self.assertEqual([], self.secret_provider.leases,
                         "identity subject must be rejected before resolving the signing secret")
        forged = assertion_headers()
        forged["X-R3-Identity-Signature"] = "0" * 64
        response = await self.client.post("/api/v1/steward/session", headers=forged)
        self.assertEqual(401, response.status_code)
        self.assertEqual(2, sum(event["event_type"] == "steward.authentication.denied" for event in self.store.events))

    async def test_assertion_age_is_checked(self):
        response = await self.client.post("/api/v1/steward/session",
                                          headers=assertion_headers(issued_at=int(time.time()) - 120))
        self.assertEqual(401, response.status_code)

    async def test_session_is_opaque_persisted_and_revocation_is_immediate(self):
        response = await self.client.post("/api/v1/steward/session", headers=assertion_headers())
        self.assertEqual(200, response.status_code)
        self.assertEqual("steward:test", response.json()["principal_id"])
        self.assertEqual("r3a.steward-principal.v1", response.json()["principal"]["contract"])
        self.assertEqual([], response.json()["factor_refs"])
        self.assertTrue(self.secret_provider.leases[-1].closed)
        token = self.client.cookies.get("r3a_steward_session")
        self.assertIsNotNone(token)
        digest = hashlib.sha256(token.encode()).hexdigest()
        self.assertIn(digest, self.store.sessions)
        self.assertNotIn(token, self.store.sessions)
        self.assertEqual("test-revision", self.store.sessions[digest]["secret_provenance"]["remote_revision"])
        self.assertEqual("machine:test", self.store.sessions[digest]["secret_provenance"]["machine_principal"]["principal_id"])
        provenance = self.store.sessions[digest]["secret_provenance"]
        self.assertEqual(("r3a.secrets.provider.v1", "1.1.0"),
                         (provenance["contract_id"], provenance["contract_version"]))
        self.assertEqual(("r3a.machine-principal.v1", "1.0.0"),
                         (provenance["machine_principal"]["contract_id"],
                          provenance["machine_principal"]["contract_version"]))
        self.assertEqual("test-secret", provenance["secret_id"])
        status = await self.client.get("/api/v1/steward/status")
        self.assertEqual(200, status.status_code)
        self.assertEqual("unavailable", status.json()["cme"]["health"])
        self.assertEqual("unavailable", status.json()["freshness"])
        self.assertEqual("steward.state.read", self.store.events[-1]["event_type"])
        ended = await self.client.delete("/api/v1/steward/session", headers={"Origin": "http://testserver"})
        self.assertEqual(200, ended.status_code)
        self.assertEqual(401, (await self.client.get("/api/v1/steward/status")).status_code)
        self.assertEqual("steward.state.read_denied", self.store.events[-1]["event_type"])

    async def test_expired_durable_session_is_denied_and_audited(self):
        response = await self.client.post("/api/v1/steward/session", headers=assertion_headers())
        self.assertEqual(200, response.status_code)
        token = self.client.cookies.get("r3a_steward_session")
        digest = hashlib.sha256(token.encode()).hexdigest()
        self.store.sessions[digest]["expires_at"] = datetime.now(timezone.utc) - timedelta(seconds=1)

        status = await self.client.get("/api/v1/steward/session")
        operation = await self.client.post("/api/v1/steward/operations/invoke",
                                           headers={"Origin": "http://testserver"},
                                           json={"request": {"contract_id": "r3a.capability-invocation.v1"}})

        self.assertEqual(401, status.status_code)
        self.assertEqual(401, operation.status_code)
        event_types = [event["event_type"] for event in self.store.events]
        self.assertIn("steward.session.access_denied", event_types)
        self.assertIn("steward.operation.denied", event_types)

    async def test_session_assertion_replay_is_denied(self):
        headers = assertion_headers(assertion_id="same-ingress-assertion")
        first = await self.client.post("/api/v1/steward/session", headers=headers)
        self.assertEqual(200, first.status_code)
        self.client.cookies.clear()
        second = await self.client.post("/api/v1/steward/session", headers=headers)
        self.assertEqual(401, second.status_code)

    async def test_operation_replaces_browser_principal_and_uses_cme(self):
        created = await self.client.post("/api/v1/steward/session", headers=assertion_headers())
        self.assertEqual(200, created.status_code)
        invocation = {"contract_id": "r3a.capability-invocation.v1", "operation_id": "institutional.directory.discover",
                      "operation_contract_version": "1.0.0", "invocation_id": str(uuid.uuid4()),
                      "idempotency_key": str(uuid.uuid4()), "caller": {"principal_id": "browser:forged",
                      "resident_id": "resident:grace", "service_id": "forged"}, "input": {}}

        async def fake_control(_socket, operation, payload, idempotency_key, timeout):
            self.assertEqual("capability.invoke", operation)
            self.assertEqual("steward:test", payload["request"]["caller"]["principal_id"])
            self.assertIsNone(payload["request"]["caller"]["resident_id"])
            self.assertIsNone(payload["request"]["caller"]["service_id"])
            return {"state": "SUCCEEDED", "authorization": {"provider_id": "capability_grants",
                    "decision_id": "decision-1", "audit_event_id": "audit-1"}}

        with patch("r3a_runtime.control.control_request", new=AsyncMock(side_effect=fake_control)):
            result = await self.client.post("/api/v1/steward/operations/invoke", json={"request": invocation},
                                            headers={"Origin": "http://testserver"})
        self.assertEqual(200, result.status_code)
        self.assertEqual("audit-1", result.json()["result"]["authorization"]["audit_event_id"])
        self.assertEqual("steward.operation.completed", self.store.events[-1]["event_type"])

    async def test_cme_grant_denial_remains_a_denial(self):
        await self.client.post("/api/v1/steward/session", headers=assertion_headers())

        async def deny(*_args, **_kwargs):
            raise RuntimeError("PermissionError: capability grant absent")

        with patch("r3a_runtime.control.control_request", new=AsyncMock(side_effect=deny)):
            result = await self.client.post("/api/v1/steward/operations/invoke",
                                            json={"request": {"operation_id": "ungranted.operation"}},
                                            headers={"Origin": "http://testserver"})
        self.assertEqual(403, result.status_code)
        self.assertEqual("steward.operation.denied", self.store.events[-1]["event_type"])
        self.assertEqual("denied", self.store.events[-1]["outcome"])

    async def test_old_cme_heartbeat_is_reported_stale(self):
        await self.client.post("/api/v1/steward/session", headers=assertion_headers())

        async def stale_health(*_args, **_kwargs):
            return {"health": "healthy", "state": "RUNNING", "scheduler_tick_age_seconds": 31}

        with patch("r3a_runtime.control.control_request", new=AsyncMock(side_effect=stale_health)):
            response = await self.client.get("/api/v1/steward/status")
        self.assertEqual("stale", response.json()["freshness"])
        self.assertEqual("stale", self.store.events[-1]["outcome"])

    async def test_mutation_from_unconfigured_origin_is_denied(self):
        await self.client.post("/api/v1/steward/session", headers=assertion_headers())
        response = await self.client.delete("/api/v1/steward/session", headers={"Origin": "https://attacker.invalid"})
        self.assertEqual(403, response.status_code)
        self.assertEqual("steward.request.denied", self.store.events[-1]["event_type"])

    async def test_existing_r3_account_portal_session_establishes_shared_ap3_cookie_session(self):
        import json
        cfg = config()
        cfg["identity"] = {"provider": "r3.account-session", "issuer": "r3-account-portal",
                            "session_url": "http://127.0.0.1:8767/api/v1/auth/session",
                            "required_role": "steward", "request_timeout_seconds": 2}
        cfg.pop("secret_provider_manifest")
        cfg.pop("secret_provider_config")
        self.access = StewardAccess(cfg, self.store, R3AccountSessionIdentityProvider(cfg))
        app = FastAPI()
        app.state.steward_access = self.access
        app.include_router(self.access.router())
        payload = {"authenticated": True,
                   "identity": {"email": "Steward@Example.org", "roles": ["steward"],
                                "factor_refs": ["portal-session"]}}

        class PortalResponse:
            status = 200
            def __enter__(inner): return inner
            def __exit__(inner, *_args): return None
            def read(inner, _limit=-1): return json.dumps(payload).encode()

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url="http://testserver") as client:
            with patch("r3a_runtime.steward_access.urllib.request.build_opener") as upstream:
                upstream.return_value.open.return_value = PortalResponse()
                started = await client.post("/api/v1/steward/session",
                                            headers={"Origin": "http://testserver",
                                                     "Cookie": "rv_account_session=opaque-r2-cookie"})
            self.assertEqual(200, started.status_code)
            forwarded = upstream.return_value.open.call_args.args[0]
            self.assertEqual("rv_account_session=opaque-r2-cookie", forwarded.get_header("Cookie"))
            redirect_handler = upstream.call_args.args[0]
            self.assertIsNone(redirect_handler().redirect_request(None, None, 302, "redirect", {}, "https://outside.invalid"))
            self.assertEqual("steward@example.org", started.json()["principal"]["principal_id"])
            self.assertNotIn("opaque-r2-cookie", started.headers["set-cookie"])
            self.assertTrue(started.cookies.get("r3a_steward_session"))
            self.assertIn("httponly", started.headers["set-cookie"].lower())
            self.assertIn("samesite=strict", started.headers["set-cookie"].lower())
            current = await client.get("/api/v1/steward/session")
            self.assertEqual(200, current.status_code)
            self.assertEqual("steward@example.org", current.json()["principal"]["principal_id"])
            provenance = next(iter(self.store.sessions.values()))["secret_provenance"]
            self.assertEqual("r3.account-session", provenance["identity_provider_id"])
            self.assertEqual("r3a.identity-provider.v1", provenance["identity_provider_contract_id"])
            ended = await client.delete("/api/v1/steward/session", headers={"Origin": "http://testserver"})
            self.assertEqual(200, ended.status_code)
            self.assertEqual(401, (await client.get("/api/v1/steward/session")).status_code)

    async def test_account_portal_provider_rejects_missing_cookie_and_non_steward_role(self):
        import json
        cfg = config()
        cfg["identity"] = {"provider": "r3.account-session", "issuer": "r3-account-portal",
                            "session_url": "http://127.0.0.1:8767/api/v1/auth/session",
                            "required_role": "steward", "request_timeout_seconds": 2}
        self.access = StewardAccess(cfg, self.store, R3AccountSessionIdentityProvider(cfg))
        app = FastAPI(); app.include_router(self.access.router())
        class PortalResponse:
            status = 200
            def __enter__(inner): return inner
            def __exit__(inner, *_args): return None
            def read(inner, _limit=-1):
                return json.dumps({"authenticated": True,
                                   "identity": {"email": "person@example.org", "roles": ["resident"]}}).encode()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url="http://testserver") as client:
            with patch("r3a_runtime.steward_access.urllib.request.build_opener") as upstream:
                upstream.return_value.open.return_value = PortalResponse()
                no_cookie = await client.post("/api/v1/steward/session", headers={"Origin": "http://testserver"})
                self.assertEqual(401, no_cookie.status_code)
                upstream.assert_not_called()
                denied_role = await client.post("/api/v1/steward/session",
                                                headers={"Origin": "http://testserver",
                                                         "Cookie": "rv_account_session=opaque"})
            self.assertEqual(401, denied_role.status_code)
            self.assertEqual({}, self.store.sessions)

    async def test_account_portal_outage_fails_closed_as_unavailable(self):
        cfg = config()
        cfg["identity"] = {"provider": "r3.account-session", "issuer": "r3-account-portal",
                            "session_url": "http://127.0.0.1:8767/api/v1/auth/session",
                            "required_role": "steward", "request_timeout_seconds": 2}
        self.access = StewardAccess(cfg, self.store, R3AccountSessionIdentityProvider(cfg))
        app = FastAPI(); app.include_router(self.access.router())
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url="http://testserver") as client:
            with patch("r3a_runtime.steward_access.urllib.request.build_opener") as upstream:
                upstream.return_value.open.side_effect = OSError("offline")
                response = await client.post("/api/v1/steward/session",
                                             headers={"Origin": "http://testserver",
                                                      "Cookie": "rv_account_session=opaque"})
            self.assertEqual(503, response.status_code)
            self.assertEqual({}, self.store.sessions)

    async def test_authentication_unavailable_with_audit_store_outage_returns_503(self):
        class UnavailableProvider:
            contract_id = "r3a.identity-provider.v1"
            contract_version = "1.0.0"

            def authenticate(self, request, *, correlation_id):
                raise AccessUnavailable("identity_provider_unavailable")

        def unavailable_audit(**_event):
            raise AccessUnavailable("session_store_unavailable")

        self.store.audit = unavailable_audit
        access = StewardAccess(config(), self.store, UnavailableProvider())
        app = FastAPI()
        app.include_router(access.router())
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url="http://testserver") as client:
            response = await client.post("/api/v1/steward/session",
                                         headers={"Origin": "http://testserver"})

        self.assertEqual(503, response.status_code)
        self.assertEqual("Steward audit state unavailable", response.json()["detail"])
        self.assertEqual({}, self.store.sessions)

    async def test_account_portal_config_is_loopback_only_and_does_not_require_bitwarden(self):
        import json
        import tempfile
        cfg = config()
        cfg["identity"] = {"provider": "r3.account-session", "issuer": "r3-account-portal",
                            "session_url": "http://127.0.0.1:8767/api/v1/auth/session",
                            "required_role": "steward", "request_timeout_seconds": 2}
        cfg.pop("secret_provider_manifest")
        cfg.pop("secret_provider_config")
        with patch.dict(os.environ, {"R3A_TEST_STEWARD_DSN": "postgresql://test"}):
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8") as handle:
                json.dump(cfg, handle); handle.flush()
                loaded = load_access_config(handle.name)
                with patch.dict(os.environ, {"R3A_STEWARD_ACCESS_CONFIG": handle.name,
                                             "R3A_TEST_STEWARD_DSN": "postgresql://test"}):
                    access = create_access_from_environment()
            self.assertEqual("r3.account-session", loaded["identity"]["provider"])
            self.assertIsInstance(access.identity_provider, R3AccountSessionIdentityProvider)
            cfg["identity"]["session_url"] = "https://identity.example.org/api/v1/auth/session"
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8") as handle:
                json.dump(cfg, handle); handle.flush()
                with self.assertRaisesRegex(AccessUnavailable, "steward_access_identity_configuration_invalid"):
                    load_access_config(handle.name)

    async def test_configuration_refuses_public_exposure(self):
        import json
        import tempfile
        cfg = config()
        cfg["remote_transport"]["public_exposure"] = True
        os.environ["R3A_TEST_STEWARD_DSN"] = "postgresql://not-used"
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8") as handle:
            json.dump(cfg, handle)
            handle.flush()
            with self.assertRaisesRegex(Exception, "public_exposure_requires_separate_review"):
                load_access_config(handle.name)
        os.environ.pop("R3A_TEST_STEWARD_DSN", None)

    async def test_configuration_rejects_boolean_thresholds(self):
        import json
        import tempfile
        cfg = config()
        cfg["cme"]["health_stale_after_seconds"] = True
        os.environ["R3A_TEST_STEWARD_DSN"] = "postgresql://not-used"
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8") as handle:
            json.dump(cfg, handle)
            handle.flush()
            with self.assertRaisesRegex(Exception, "steward_access_cme_configuration_invalid"):
                load_access_config(handle.name)
        os.environ.pop("R3A_TEST_STEWARD_DSN", None)

    async def test_remote_transport_requires_secure_cookie(self):
        import json
        import tempfile
        cfg = config()
        cfg["remote_transport"]["state"] = "configured"
        os.environ["R3A_TEST_STEWARD_DSN"] = "postgresql://not-used"
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8") as handle:
            json.dump(cfg, handle)
            handle.flush()
            with self.assertRaisesRegex(Exception, "secure_cookie_required_for_remote_transport"):
                load_access_config(handle.name)
        os.environ.pop("R3A_TEST_STEWARD_DSN", None)

    async def test_remote_transport_rejects_http_origin_even_with_secure_cookie(self):
        import json
        import tempfile
        cfg = config()
        cfg["remote_transport"]["state"] = "configured"
        cfg["session"]["secure_cookie"] = True
        with patch.dict(os.environ, {"R3A_TEST_STEWARD_DSN": "postgresql://not-used"}):
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8") as handle:
                json.dump(cfg, handle)
                handle.flush()
                with self.assertRaisesRegex(AccessUnavailable,
                                            "https_origin_required_for_remote_transport"):
                    load_access_config(handle.name)

    async def test_remote_transport_accepts_private_https_origin_with_secure_cookie(self):
        import json
        import tempfile
        cfg = config()
        cfg["remote_transport"]["state"] = "configured"
        cfg["session"]["secure_cookie"] = True
        cfg["session"]["allowed_origins"] = ["https://steward.lan.example:8443"]
        with patch.dict(os.environ, {"R3A_TEST_STEWARD_DSN": "postgresql://not-used"}):
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8") as handle:
                json.dump(cfg, handle)
                handle.flush()
                self.assertEqual(cfg, load_access_config(handle.name))


if __name__ == "__main__":
    unittest.main()
