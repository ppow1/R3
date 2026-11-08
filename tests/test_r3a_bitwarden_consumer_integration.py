"""Exercise the Bitwarden reference boundary through a CME-authorized service consumer."""
# R3 CONTROLLED SOURCE
# File: tests/test_r3a_bitwarden_consumer_integration.py
# Component: R3A-AP3-M2-CONSUMER-TESTS
# File Revision: 1.0.0
# Created: 2026-11-07T21:59:02Z
# Created By: Codex GPT-6
# Purpose: Verify authorized inference uses a secret reference only as a transport credential and always closes leases.
# Execution Model: Standard-library unittest with synthetic secret provider and HTTP transport.
# Observability: CME invocation outcome, outbound headers/body, redacted durable result, and lease state.
# Dependencies: R3A CME capability registry; reasoning inference provider; secret-provider v1.
# Authority: AP3-M2 Issue #50; no live credential or network access.
# Changed: 2026-11-07T21:59:02Z | R3A-AP3-M2-CONSUMER | Codex GPT-6 | Add authorized service-consumer integration coverage.
# Supersedes: None.
# Contracts: r3a.secrets.provider.v1; r3a.capability-operation.v1; r3a.capability-invocation.v1.
# Tests: python3 -m unittest tests.test_r3a_bitwarden_consumer_integration.
# History/Predecessor: New file; initial publication recorded in Git.

from __future__ import annotations

import asyncio
import copy
import io
import importlib.util
import json
import sys
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError
from unittest.mock import AsyncMock, patch

from r3a_runtime.capability_contracts import CapabilityRegistry
from r3a_runtime.secrets import MachinePrincipalAssertion, SecretLease, SecretProviderError
from r3a_plugins.reasoning_inference.plugin import create_provider

# This integration test replaces CME's store with MemoryStore and never constructs a
# PostgreSQL pool. Keep the test runnable in checkout environments missing that optional
# runtime dependency while still exercising the real CME dispatcher implementation.
if importlib.util.find_spec("psycopg_pool") is None:
    pool_stub = types.ModuleType("psycopg_pool")
    pool_stub.AsyncConnectionPool = type("AsyncConnectionPool", (), {})
    sys.modules["psycopg_pool"] = pool_stub

from r3a_runtime.cme import CME


TOKEN = "synthetic-inference-credential-for-regression"
SECRET_ID = "synthetic-bitwarden-secret-reference"
REFERENCE_CONFIG = {
    "provider_id": "r3a.bitwarden-secrets",
    "provider_version": "1.1.2",
    "secret_id": SECRET_ID,
    "manifest_path": "/external/r3a/bitwarden/manifest.json",
    "configuration_path": "/external/r3a/bitwarden/provider.json",
    "access_token_env": "R3A_BITWARDEN_ACCESS_TOKEN",
}


class FakeSecretProvider:
    def __init__(self, *, failure: str | None = None, reason_code: str | None = None):
        self.failure = failure
        self.reason_code = reason_code
        self.access_token_env = "R3A_BITWARDEN_ACCESS_TOKEN"
        self.configuration = {"access_token_env": self.access_token_env}
        self.lease: SecretLease | None = None
        self.reference = None
        self.correlation_id = None

    def resolve(self, reference, *, correlation_id):
        self.reference = reference
        self.correlation_id = correlation_id
        if self.failure:
            raise SecretProviderError(self.failure, f"synthetic {self.failure.lower()} provider condition",
                                      reason_code=self.reason_code)
        self.lease = SecretLease(
            secret_id=reference.secret_id, provider_id=reference.provider_id,
            provider_version=reference.provider_version, remote_revision="synthetic-revision-1",
            fetched_at=datetime.now(timezone.utc).isoformat(),
            machine_principal=MachinePrincipalAssertion(
                principal_id="configured-machine-account", issuer="bitwarden-secrets-manager",
                authenticated_at=datetime.now(timezone.utc).isoformat(),
                correlation_id=correlation_id),
            _value=bytearray(TOKEN.encode()))
        return self.lease

    def assert_available(self):
        return None


class MemoryStore:
    def __init__(self):
        self.invocation = None

    async def begin_capability_invocation(self, request, digest, _authorization):
        if self.invocation is None:
            self.invocation = {"state": "STARTED", "request_digest": digest,
                               "result": None, "created": True}
        else:
            self.invocation["created"] = False
        return copy.deepcopy(self.invocation)

    async def finish_capability_invocation(self, _key, _digest, result):
        self.invocation.update(state=result["outcome"], result=copy.deepcopy(result))


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _limit):
        return json.dumps(self.payload).encode()


def invocation_request(descriptor):
    return {
        "contract_id": "r3a.capability-invocation.v1", "contract_version": "1.0.0",
        "invocation_id": "11111111-1111-4111-8111-111111111111",
        "operation_id": descriptor["operation_id"],
        "operation_contract_version": descriptor["contract_version"],
        "caller": {"principal_id": "resident.grace", "resident_id": "resident.grace",
                   "service_id": None},
        "target": {"role_id": "resident.primary"},
        "input": {"messages": [{"role": "user", "content": "analyze the configured evidence"}]},
        "activity_id": "22222222-2222-4222-8222-222222222222",
        "attempt_id": "33333333-3333-4333-8333-333333333333",
        "correlation_id": "44444444-4444-4444-8444-444444444444",
        "work_order": None, "evidence_purpose": "configured model reasoning",
        "idempotency_key": "activity:secret-consumer:1", "deadline": None,
        "config_revision": "cfg-test",
        "budget_reservation": {"contract_id": "r3a.activity-budget-reservation.v1",
            "contract_version": "1.0.0", "reservation_id": "reservation-1",
            "activity_id": "22222222-2222-4222-8222-222222222222",
            "resource": "completion_tokens", "units": 64, "limit": 128,
            "policy_revision": "cfg-test"},
    }


class BitwardenConsumerIntegrationTests(unittest.TestCase):
    def test_consumer_rejects_missing_invalid_and_ambiguous_references(self):
        context = {"invocation_id": "invalid-reference-test"}
        with self.assertRaisesRegex(ValueError, "secret reference is invalid"):
            create_provider({"temperature": 0.1, "secret_reference": {"secret_id": SECRET_ID}}).invoke(
                {}, context=context)
        with self.assertRaisesRegex(ValueError, "identity or version is unsupported"):
            create_provider({"temperature": 0.1, "secret_reference": {
                **REFERENCE_CONFIG, "provider_version": "9.0.0"}}).invoke({}, context=context)
        with self.assertRaisesRegex(ValueError, "either api_key_env or secret_reference"):
            create_provider({"temperature": 0.1, "api_key_env": "FIXTURE_TOKEN",
                             "secret_reference": REFERENCE_CONFIG}).invoke({}, context=context)

    def setUp(self):
        manifest = json.loads((Path(__file__).resolve().parents[1]
                               / "r3a_plugins/reasoning_inference/manifest.json").read_text())
        self.descriptor = manifest["operation"]
        self.registry = CapabilityRegistry()
        self.secret_provider = FakeSecretProvider()
        self.operation = self.registry.register(
            self.descriptor,
            {"temperature": 0.1, "secret_reference": REFERENCE_CONFIG})
        self.cme = CME.__new__(CME)
        self.cme.settings = SimpleNamespace(capability_registry=self.registry, source_digest="cfg-test")
        self.cme.store = MemoryStore()
        self.cme._authorize_capability = AsyncMock(return_value={
            "provider_id": "fixture-grants", "decision_id": "decision-1",
            "audit_event_id": "audit-1", "policy_revision": "cfg-test",
            "config_revision": "cfg-test"})
        self.request = invocation_request(self.descriptor)
        self.context = {"model_role_id": "resident.primary", "model_route": {
            "route_id": "configured-primary", "provider": "fixture-model",
            "endpoint": "http://model.invalid/v1/chat/completions", "model": "fixture-model",
            "timeout_seconds": 5, "max_tokens": 64}}

    def invoke(self):
        return asyncio.run(self.cme.invoke_capability(
            self.request, _approved_budget_reservation=self.request["budget_reservation"],
            _provider_context=self.context))

    def test_cme_authorized_consumer_resolves_reference_sends_header_and_redacts_echo(self):
        payload = {"id": f"response-{TOKEN}", "choices": [{"message": {"content": f"answer {TOKEN}"}}],
                   "usage": {"prompt_tokens": 12, "note": f"usage {TOKEN}"}}
        with patch("r3a_plugins.reasoning_inference.plugin.load_configured_provider",
                   return_value=self.secret_provider) as load_provider, \
             patch("urllib.request.urlopen", return_value=FakeResponse(payload)) as send:
            result = self.invoke()

        self.cme._authorize_capability.assert_awaited_once()
        load_provider.assert_called_once_with(REFERENCE_CONFIG["manifest_path"],
                                              REFERENCE_CONFIG["configuration_path"])
        self.assertEqual("SUCCEEDED", result["outcome"])
        self.assertEqual(SECRET_ID, self.secret_provider.reference.secret_id)
        self.assertEqual(self.request["correlation_id"], self.secret_provider.correlation_id)
        request = send.call_args.args[0]
        self.assertEqual(f"Bearer {TOKEN}", request.get_header("Authorization"))
        self.assertNotIn(TOKEN, request.data.decode())
        self.assertTrue(self.secret_provider.lease.closed)
        serialized_result = json.dumps(result, sort_keys=True)
        serialized_durable = json.dumps(self.cme.store.invocation["result"], sort_keys=True)
        self.assertNotIn(TOKEN, serialized_result)
        self.assertNotIn(TOKEN, serialized_durable)
        self.assertIn("[REDACTED]", serialized_result)
        credential = result["evidence"][0]["credential_source"]
        self.assertEqual("configured-machine-account", credential["machine_principal"]["principal_id"])
        self.assertEqual("synthetic-revision-1", credential["remote_revision"])

    def test_provider_failure_is_durable_and_does_not_call_model_service(self):
        self.secret_provider = FakeSecretProvider(failure="DENIED")
        with patch("r3a_plugins.reasoning_inference.plugin.load_configured_provider",
                   return_value=self.secret_provider), \
             patch("urllib.request.urlopen") as send:
            with self.assertRaisesRegex(RuntimeError, r"secret provider outcome: DENIED \(access_denied\)"):
                self.invoke()
        send.assert_not_called()
        self.assertEqual("FAILED", self.cme.store.invocation["result"]["outcome"])
        self.assertNotIn(TOKEN, json.dumps(self.cme.store.invocation["result"]))

    def test_consumer_preserves_provider_reason_codes_without_secret_material(self):
        failures = [
            ("UNAVAILABLE", "credentials_unavailable"),
            ("UNAVAILABLE", "cli_unavailable"),
            ("DENIED", "access_denied"),
            ("NOT_FOUND", "reference_not_found"),
            ("FAILED", "provider_failure"),
        ]
        for outcome, reason_code in failures:
            with self.subTest(reason_code=reason_code):
                self.cme.store = MemoryStore()
                self.secret_provider = FakeSecretProvider(failure=outcome, reason_code=reason_code)
                with patch("r3a_plugins.reasoning_inference.plugin.load_configured_provider",
                           return_value=self.secret_provider), \
                     patch("urllib.request.urlopen") as send:
                    with self.assertRaisesRegex(RuntimeError,
                                                rf"provider outcome: {outcome} \({reason_code}\)"):
                        self.invoke()
                send.assert_not_called()
                self.assertNotIn(TOKEN, json.dumps(self.cme.store.invocation["result"]))
                self.assertIn(reason_code, json.dumps(self.cme.store.invocation["result"]))

    def test_cme_authorization_denial_prevents_secret_resolution_and_transport(self):
        self.cme._authorize_capability = AsyncMock(side_effect=PermissionError("grant denied"))
        with patch("r3a_plugins.reasoning_inference.plugin.load_configured_provider",
                   return_value=self.secret_provider) as load_provider, \
             patch("urllib.request.urlopen") as send:
            with self.assertRaisesRegex(PermissionError, "grant denied"):
                self.invoke()
        self.cme._authorize_capability.assert_awaited_once()
        load_provider.assert_not_called()
        self.assertIsNone(self.secret_provider.reference)
        self.assertIsNone(self.secret_provider.lease)
        send.assert_not_called()
        self.assertIsNone(self.cme.store.invocation)

    def test_invalid_external_provider_configuration_fails_closed_without_model_request(self):
        with patch("r3a_plugins.reasoning_inference.plugin.load_configured_provider",
                   side_effect=ValueError("synthetic loader detail")), \
             patch("urllib.request.urlopen") as send:
            with self.assertRaisesRegex(RuntimeError, "provider_configuration_invalid") as caught:
                self.invoke()
        self.assertNotIn("synthetic loader detail", str(caught.exception))
        send.assert_not_called()
        durable = json.dumps(self.cme.store.invocation["result"])
        self.assertEqual("FAILED", self.cme.store.invocation["result"]["outcome"])
        self.assertNotIn(TOKEN, durable)

    def test_http_failure_body_is_not_persisted_and_lease_closes(self):
        http_error = HTTPError(
            self.context["model_route"]["endpoint"], 401, "Unauthorized", {}, io.BytesIO(TOKEN.encode()))
        with patch("r3a_plugins.reasoning_inference.plugin.load_configured_provider",
                   return_value=self.secret_provider), \
             patch("urllib.request.urlopen", side_effect=http_error):
            with self.assertRaisesRegex(RuntimeError, "HTTP 401") as caught:
                self.invoke()
        self.assertNotIn(TOKEN, str(caught.exception))
        self.assertTrue(self.secret_provider.lease.closed)
        durable = json.dumps(self.cme.store.invocation["result"])
        self.assertEqual("FAILED", self.cme.store.invocation["result"]["outcome"])
        self.assertNotIn(TOKEN, durable)


if __name__ == "__main__":
    unittest.main()
