"""
R3 CONTROLLED TEST SOURCE
File: tests/test_r3a_steward_access.py
Component: R3A-AP3-STEWARD-ACCESS
File Revision: 1.1.1
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
Supersedes: None.
Contracts: r3a.identity-provider.v1; r3a.steward-principal.v1; r3a.steward-session.v1; r3a.capability-invocation.v1.
Tests: python -m unittest tests.test_r3a_steward_access.
History/Predecessor: New file; initial publication recorded in Git.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import FastAPI

from r3a_runtime.steward_access import (
    AccessUnavailable, HmacIngressIdentityProvider, IdentityAssertion, StewardAccess, load_access_config,
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
                         "assertion_secret_ref": {"provider_id": "test-secrets", "provider_version": "1.0.0",
                                                  "secret_id": "test-secret"}, "assertion_max_age_seconds": 60},
            "secret_provider_manifest": "/etc/r3a/test/manifest.json",
            "secret_provider_config": "/etc/r3a/test/provider.json",
            "session": {"cookie_name": "r3_steward_session", "lifetime_seconds": 600,
                        "connect_timeout_seconds": 3, "secure_cookie": False,
                        "allowed_origins": ["http://testserver"]},
            "cme": {"control_socket": "/tmp/r3a-cme.sock", "request_timeout_seconds": 5,
                    "health_stale_after_seconds": 30},
            "remote_transport": {"state": "unavailable", "public_exposure": False}}


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
            self.provider_version = "1.0.0"
            self.remote_revision = "test-revision"
            self.fetched_at = datetime.now(timezone.utc).isoformat()
            self.machine_principal = type("Machine", (), {})()
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
        app.include_router(self.access.router())
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url="http://testserver") as client:
            response = await client.post("/api/v1/steward/session",
                                         headers={"Origin": "http://testserver",
                                                  "X-Correlation-ID": str(uuid.uuid4())})
            self.assertEqual(200, response.status_code)
            payload = response.json()
            self.assertEqual("r3a.steward-session.v1", payload["contract"])
            self.assertEqual({"contract": "r3a.steward-principal.v1",
                              "principal_id": "steward:replacement", "issuer": "portal-oidc",
                              "authenticated_at": now.isoformat(), "factor_refs": ["webauthn"]},
                             payload["principal"])
            self.assertEqual(1, len(replacement.calls))
            self.assertEqual("steward:replacement",
                             next(iter(self.store.sessions.values()))["principal_id"])
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
                return {"state": "SUCCEEDED", "authorization": {"audit_event_id": "cme-audit"}}

            with patch("r3a_runtime.control.control_request", new=AsyncMock(side_effect=fake_control)):
                result = await client.post("/api/v1/steward/operations/invoke",
                                           json={"request": invocation},
                                           headers={"Origin": "http://testserver"})
            self.assertEqual(200, result.status_code)
            ended = await client.delete("/api/v1/steward/session", headers={"Origin": "http://testserver"})
            self.assertEqual({"contract": "r3a.steward-session.v1", "state": "revoked",
                              "revoked": True, "principal_id": "steward:replacement",
                              "correlation_id": ended.json()["correlation_id"]}, ended.json())

    def test_rejects_unknown_identity_provider_contract_version(self):
        provider = type("WrongProvider", (), {"contract_id": "r3a.identity-provider.v1",
                                                "contract_version": "2.0.0"})()
        with self.assertRaisesRegex(AccessUnavailable, "identity_provider_contract_unsupported"):
            StewardAccess(config(), self.store, provider)

    def test_rejects_malformed_identity_provider_result(self):
        with self.assertRaisesRegex(AccessUnavailable, "identity_provider_contract_result_invalid"):
            StewardAccess._validate_provider_assertion({"principal_id": "browser:forged"})

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_invalid_subject_and_signature_are_denied_and_audited(self):
        response = await self.client.post("/api/v1/steward/session",
                                          headers=assertion_headers(subject="resident:grace"))
        self.assertEqual(401, response.status_code)
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
        token = self.client.cookies.get("r3_steward_session")
        self.assertIsNotNone(token)
        digest = hashlib.sha256(token.encode()).hexdigest()
        self.assertIn(digest, self.store.sessions)
        self.assertNotIn(token, self.store.sessions)
        self.assertEqual("test-revision", self.store.sessions[digest]["secret_provenance"]["remote_revision"])
        self.assertEqual("machine:test", self.store.sessions[digest]["secret_provenance"]["machine_principal"]["principal_id"])
        status = await self.client.get("/api/v1/steward/status")
        self.assertEqual(200, status.status_code)
        self.assertEqual("unavailable", status.json()["cme"]["health"])
        self.assertEqual("unavailable", status.json()["freshness"])
        self.assertEqual("steward.state.read", self.store.events[-1]["event_type"])
        ended = await self.client.delete("/api/v1/steward/session", headers={"Origin": "http://testserver"})
        self.assertEqual(200, ended.status_code)
        self.assertEqual(401, (await self.client.get("/api/v1/steward/status")).status_code)
        self.assertEqual("steward.state.read_denied", self.store.events[-1]["event_type"])

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


if __name__ == "__main__":
    unittest.main()
