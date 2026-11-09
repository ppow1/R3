"""
R3 CONTROLLED TEST SOURCE
File: tests/test_r3a_native_identity.py
Component: R3A-AP3-IDENTITY
File Revision: 1.0.1
Created: 2026-11-09T17:31:32Z
Created By: R3 Integration
Purpose: Verify independent identity-provider binding, shared session behavior, and LAN/browser controls.
Execution Model: unittest with isolated in-process identity/session fakes and temporary config files.
Observability: Assertions cover auth responses, session/cookie attributes, enrollment replay, revocation, and config fail-closed behavior.
Dependencies: pytest/unittest, FastAPI, httpx, R3A runtime packages.
Authority: AP3/R3A-010; Issue #49; approved R3A Authentication Independence Plan.
Tests: /tmp environment requirements-deploy.lock plus project psycopg dependency.
Changed: 2026-11-09T17:54:09Z | R3A-AUTH-COOKIE-ISOLATION | Codex GPT-6 | Verify HTTPS-only native auth and a dedicated private DNS hostname.
Supersedes: None.
Contracts: r3a.identity-provider.v1; r3a.steward-session.v1; r3a.steward-login-request.v1.
History/Predecessor: Initial test suite in Remote Access commit 16b6230d5b48bb9bd1872f687f43678faeb296d7.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import httpx
from fastapi import FastAPI

from r3a_runtime.steward_access import AccessUnavailable, StewardAccess, load_access_config
from r3a_runtime.steward_identity import (
    IDENTITY_ISSUER, PASSWORD_SCHEME, PostgresStewardIdentityRepository,
    R3aNativeIdentityProvider, normalize_login, password_verifier,
)


class MemoryStore:
    def __init__(self):
        self.rows = {}
        self.events = []

    def create(self, **row):
        self.rows[row["token_digest"]] = {**row, "revoked_at": None, "issued_at": datetime.now(timezone.utc)}

    def read(self, digest):
        return self.rows.get(digest)

    def revoke(self, digest, *, correlation_id):
        row = self.rows.get(digest)
        if not row or row["revoked_at"]:
            return False
        row["revoked_at"] = datetime.now(timezone.utc)
        return True

    def audit(self, **event):
        self.events.append(event)
        return f"event-{len(self.events)}"

    def health(self):
        return "ready"


class FakeIdentityRepository:
    def __init__(self):
        self.active = True
        self.login = "steward@example.test"
        self.password = "a-long-test-password"
        self.challenge_used = False

    def authenticate(self, login_name, password, *, now):
        if normalize_login(login_name) != self.login or password != self.password or not self.active:
            return None
        return {"principal_id": "steward:test-native", "issuer": IDENTITY_ISSUER}

    def complete_enrollment(self, challenge, login_name, password):
        if (challenge != "one-time-test-challenge-value-1234567890" or self.challenge_used
                or normalize_login(login_name) != self.login):
            raise PermissionError("enrollment_challenge_invalid")
        self.challenge_used = True
        self.password = password
        self.active = True
        return {"principal_id": "steward:test-native", "issuer": IDENTITY_ISSUER}

    def principal_active(self, principal_id):
        return self.active and principal_id == "steward:test-native"

    def health(self):
        return "ready"


def native_config():
    return {
        "schema_id": "r3a.steward-access.config.v1", "schema_version": 1, "enabled": True,
        "identity_mode": "independent",
        "session_dsn_env": "R3A_TEST_STEWARD_DSN",
        "identity": {"provider": "r3a.native", "issuer": IDENTITY_ISSUER},
        "session": {"cookie_name": "r3a_steward_session", "lifetime_seconds": 600,
                    "connect_timeout_seconds": 2, "secure_cookie": True,
                    "allowed_origins": ["https://r3a.riverview.home.arpa"]},
        "cme": {"control_socket": "/tmp/r3a-cme.sock", "request_timeout_seconds": 2,
                "health_stale_after_seconds": 30},
        "remote_transport": {"state": "unavailable", "public_exposure": False},
    }


class NativeIdentityTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.repository = FakeIdentityRepository()
        self.provider = R3aNativeIdentityProvider(native_config()["identity"], self.repository)
        self.store = MemoryStore()
        self.access = StewardAccess(native_config(), self.store, self.provider)
        self.app = FastAPI()
        self.app.include_router(self.access.router())

    async def test_login_issues_shared_opaque_cookie_and_logout_revokes_it(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app),
                                     base_url="https://r3a.riverview.home.arpa") as client:
            response = await client.post("/api/v1/steward/session", headers={"Origin": "https://r3a.riverview.home.arpa"},
                                         json={"intent": "login", "login_name": self.repository.login,
                                               "password": self.repository.password})
            self.assertEqual(200, response.status_code)
            self.assertEqual("no-store", response.headers["cache-control"])
            self.assertEqual("r3a.steward-session.v1", response.json()["contract"])
            self.assertEqual("steward:test-native", response.json()["principal"]["principal_id"])
            self.assertNotIn("token", response.json())
            cookie = response.headers["set-cookie"]
            self.assertIn("r3a_steward_session=", cookie)
            self.assertIn("httponly", cookie.lower())
            self.assertIn("samesite=strict", cookie.lower())
            self.assertIn("path=/api/v1", cookie.lower())
            self.assertIn("secure", cookie.lower())
            self.assertEqual(1, len(self.store.rows))
            status = await client.get("/api/v1/steward/session")
            self.assertEqual(200, status.status_code)
            self.assertEqual("no-store", status.headers["cache-control"])
            logout = await client.delete("/api/v1/steward/session", headers={"Origin": "https://r3a.riverview.home.arpa"})
            self.assertEqual(200, logout.status_code)
            denied = await client.get("/api/v1/steward/session")
            self.assertEqual(401, denied.status_code)

    async def test_credentials_are_origin_protected_and_failure_is_non_enumerating(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app),
                                     base_url="https://r3a.riverview.home.arpa") as client:
            no_origin = await client.post("/api/v1/steward/session",
                                          json={"login_name": self.repository.login, "password": self.repository.password})
            foreign = await client.post("/api/v1/steward/session", headers={"Origin": "https://attacker.invalid"},
                                        json={"login_name": self.repository.login, "password": self.repository.password})
            wrong_account = await client.post("/api/v1/steward/session", headers={"Origin": "https://r3a.riverview.home.arpa"},
                                               json={"login_name": "unknown@example.test", "password": "wrong"})
            wrong_password = await client.post("/api/v1/steward/session", headers={"Origin": "https://r3a.riverview.home.arpa"},
                                                json={"login_name": self.repository.login, "password": "wrong"})
        self.assertEqual(403, no_origin.status_code)
        self.assertEqual(403, foreign.status_code)
        self.assertEqual("no-store", foreign.headers.get("cache-control"))
        self.assertEqual(401, wrong_account.status_code)
        self.assertEqual("no-store", wrong_account.headers.get("cache-control"))
        self.assertEqual(wrong_account.json(), wrong_password.json())
        self.assertEqual({}, self.store.rows)

    async def test_enrollment_uses_single_use_provider_contract_and_account_state_revokes_session(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app),
                                     base_url="https://r3a.riverview.home.arpa") as client:
            enrolled = await client.post("/api/v1/steward/session", headers={"Origin": "https://r3a.riverview.home.arpa"},
                json={"intent": "enroll", "login_name": self.repository.login,
                      "password": "fresh-test-password-long-enough", "challenge": "one-time-test-challenge-value-1234567890"})
            self.assertEqual(200, enrolled.status_code)
            self.assertIn("governed-enrollment", enrolled.json()["factor_refs"])
            replay = await client.post("/api/v1/steward/session", headers={"Origin": "https://r3a.riverview.home.arpa"},
                json={"intent": "enroll", "login_name": self.repository.login,
                      "password": "another-fresh-test-password", "challenge": "one-time-test-challenge-value-1234567890"})
            self.assertEqual(401, replay.status_code)
            self.repository.active = False
            status = await client.get("/api/v1/steward/session")
            self.assertEqual(401, status.status_code)
            self.assertTrue(next(iter(self.store.rows.values()))["revoked_at"])

    async def test_independent_auth_and_session_health_is_unauthed_but_truthful(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app),
                                     base_url="https://r3a.riverview.home.arpa") as client:
            health = await client.get("/api/v1/steward/health")
        self.assertEqual(200, health.status_code)
        self.assertEqual("ready", health.json()["identity_provider"])
        self.assertEqual("ready", health.json()["session_store"])

    async def test_account_association_requires_source_eligibility_before_database_access(self):
        repo = PostgresStewardIdentityRepository("postgresql://placeholder")
        with self.assertRaisesRegex(ValueError, "identity_source_not_eligible"):
            repo.associate({"association_id": "743ed2f2-8bf7-4554-9899-53c5a2ca1380",
                "principal_id": "steward:pending", "login_name": "steward@example.test",
                "source_system": "r3", "source_subject_id": "subject-ref", "source_revision": "rev-1",
                "active": False, "verified": True, "steward_eligible": True, "approved_by": "steward",
                "approval_reference": "approval-ref", "hr_source": "hr", "hr_subject_reference": "hr-ref",
                "hr_revision": "hr-rev"})

    async def test_native_configuration_rejects_public_origin_and_legacy_provider(self):
        os.environ["R3A_TEST_STEWARD_DSN"] = "postgresql://placeholder"
        try:
            config = native_config()
            config["session"]["allowed_origins"] = ["https://public.example.org"]
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8") as handle:
                json.dump(config, handle); handle.flush()
                with self.assertRaisesRegex(AccessUnavailable, "origin_must_be_lan_only"):
                    load_access_config(handle.name)
            for origin, secure_cookie in (("https://192.168.1.155", True),
                                          ("http://r3a.riverview.home.arpa", False)):
                config = native_config()
                config["session"]["allowed_origins"] = [origin]
                config["session"]["secure_cookie"] = secure_cookie
                with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8") as handle:
                    json.dump(config, handle); handle.flush()
                    with self.assertRaises(AccessUnavailable):
                        load_access_config(handle.name)
            config = native_config()
            config["identity"] = {"provider": "r3.account-session", "issuer": "r3", "session_url":
                "http://127.0.0.1:8303/api/v1/auth/session", "required_role": "steward", "request_timeout_seconds": 2}
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8") as handle:
                json.dump(config, handle); handle.flush()
                with self.assertRaisesRegex(AccessUnavailable, "legacy_identity_provider_forbidden"):
                    load_access_config(handle.name)
        finally:
            os.environ.pop("R3A_TEST_STEWARD_DSN", None)


class CredentialPrimitiveTests(unittest.TestCase):
    def test_scrypt_verifier_is_salted_and_fixed_to_documented_scheme(self):
        first_salt, second_salt = b"a" * 16, b"b" * 16
        first = password_verifier("long-enough-test-password", first_salt)
        self.assertEqual(32, len(first))
        self.assertNotEqual(first, password_verifier("long-enough-test-password", second_salt))
        self.assertEqual("scrypt-32768-8-1", PASSWORD_SCHEME)
