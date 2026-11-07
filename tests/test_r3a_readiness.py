"""
R3 CONTROLLED SOURCE
File: tests/test_r3a_readiness.py
Component: R3A-AP1-READINESS-PROVIDER-REGRESSION
File Revision: 1.0.0
Created: 2026-11-07 UTC (exact time not captured)
Created By: Codex GPT-6
Purpose: Verify configured provider-backed readiness, evidence identity, timeout behavior, freshness and durable deferral release.
Execution Model: Python unittest using mocked provider transports and Store persistence adapters; no model inference or host requests.
Observability: Asserted provider evidence, configuration revision, readiness state, retries and requeue outcomes.
Dependencies: Python 3.12 standard library; r3a_runtime.readiness/contracts/config/CME.
Authority: R3A AP0/AP1 Modular Autonomy Implementation Slice 2; isolated development branch only.
Changed: 2026-11-07T00:20:59Z | R3A-AP1-SLICE-2 | Codex GPT-6 | Verify provider response identity, evidence, retries, versioning, freshness and durable requeue with fakes.
Supersedes: None.
Contracts: R3A-019; r3a.model-readiness-provider.v1; r3a.model-readiness.v1; r3a.model-route-decision.v1.
Tests: This test module.
History/Predecessor: New file; initial publication recorded in Git.
"""
from __future__ import annotations

import asyncio
import json
import unittest
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from r3a_runtime.config import load_settings
from r3a_runtime.contracts import resolve_role
from r3a_runtime.cme import CME
from r3a_runtime.readiness import (OPENAI_MODELS_PROVIDER_ID, READINESS_PROVIDER_CONTRACT_ID,
                                   READINESS_PROVIDER_CONTRACT_VERSION,
                                   OpenAICompatibleModelsReadinessProvider, ReadinessCheckRequest,
                                   create_readiness_provider, register_readiness_provider)
from tests.test_r3a_modular_autonomy import make_config


def readiness_request(directory: Path) -> tuple[object, object, object, ReadinessCheckRequest]:
    settings = load_settings(make_config(directory))
    role = next(item for item in settings.model_roles if item.role_id == "resident.primary")
    route = settings.model_route(role.route_id)
    request = ReadinessCheckRequest(READINESS_PROVIDER_CONTRACT_ID, role.readiness.contract_version,
                                    settings.module_id, role, route, role.readiness,
                                    settings.source_digest, str(uuid4()))
    return settings, role, route, request


class ProviderObservationTests(unittest.TestCase):
    def test_ready_requires_exact_provider_model_identity_and_records_evidence(self):
        with TemporaryDirectory() as temp:
            settings, role, route, request = readiness_request(Path(temp))
            body = json.dumps({"data": [{"id": route.model}]}).encode()
            provider = OpenAICompatibleModelsReadinessProvider(
                transport=lambda endpoint, timeout, api_key: (200, body))
            observed = asyncio.run(provider.observe(request))
            self.assertEqual((observed.status, observed.model_id, observed.provider_id),
                             ("ready", route.model, OPENAI_MODELS_PROVIDER_ID))
            self.assertEqual(observed.config_revision, settings.source_digest)
            self.assertEqual(observed.evidence["http_status"], 200)
            self.assertTrue(observed.evidence["configured_model_present"])
            self.assertTrue(observed.evidence_ref.startswith("sha256:"))
            self.assertEqual(observed.contract_version, "2.0.0")
            self.assertEqual(type(observed).from_dict(observed.to_dict()), observed)
            with self.assertRaises(ValueError):
                type(observed).from_dict({**observed.to_dict(), "contract_version": "1.0.0"})

    def test_model_absent_from_provider_catalog_is_unavailable(self):
        with TemporaryDirectory() as temp:
            _, _, _, request = readiness_request(Path(temp))
            provider = OpenAICompatibleModelsReadinessProvider(
                transport=lambda *_args: (200, b'{"data":[{"id":"some-other-model"}]}'))
            observed = asyncio.run(provider.observe(request))
            self.assertEqual(observed.status, "unavailable")
            self.assertEqual(observed.reason, "configured_model_absent_from_provider_catalog")
            decision = resolve_role((request.role,), request.role.role_id, {"plan"},
                                    {request.role.role_id: observed.to_dict()},
                                    config_revision=request.config_revision)
            self.assertEqual((decision.action, decision.selected_role_id), ("defer", None))

    def test_rate_limit_uses_configured_retry_before_reporting_ready(self):
        with TemporaryDirectory() as temp:
            _, _, route, request = readiness_request(Path(temp))
            body = json.dumps({"data": [{"id": route.model}]}).encode()
            responses = iter([(429, b"{}"), (200, body)])
            delays = []

            async def record_delay(delay):
                delays.append(delay)

            provider = OpenAICompatibleModelsReadinessProvider(
                transport=lambda *_args: next(responses), sleep=record_delay)
            observed = asyncio.run(provider.observe(request))
            self.assertEqual(observed.status, "ready")
            self.assertEqual(observed.evidence["attempts"], 2)
            self.assertEqual(delays, [request.policy.retry_delay_seconds])

    def test_timeout_retries_are_configured_and_unavailable_never_ready(self):
        with TemporaryDirectory() as temp:
            _, _, _, request = readiness_request(Path(temp))
            calls = []
            delays = []

            def timeout(*_args):
                calls.append(1)
                raise TimeoutError("provider timed out")

            async def record_delay(delay):
                delays.append(delay)

            provider = OpenAICompatibleModelsReadinessProvider(transport=timeout, sleep=record_delay)
            observed = asyncio.run(provider.observe(request))
            self.assertEqual(observed.status, "unavailable")
            self.assertEqual(observed.evidence["attempts"], request.policy.max_attempts)
            self.assertEqual(len(calls), request.policy.max_attempts)
            self.assertEqual(len(delays), request.policy.max_attempts - 1)
            self.assertEqual(observed.evidence["error_code"], "timeout")

    def test_unreachable_provider_is_unavailable_with_bounded_retry_evidence(self):
        with TemporaryDirectory() as temp:
            _, _, _, request = readiness_request(Path(temp))
            calls = []

            def unreachable(*_args):
                calls.append(1)
                raise urllib.error.URLError("connection refused")

            async def no_wait(_delay):
                return None

            observed = asyncio.run(OpenAICompatibleModelsReadinessProvider(
                transport=unreachable, sleep=no_wait).observe(request))
            self.assertEqual(observed.status, "unavailable")
            self.assertEqual(len(calls), request.policy.max_attempts)
            self.assertEqual(observed.evidence["error_code"], "URLError")

    def test_provider_registry_accepts_independent_v1_implementations(self):
        provider_id = "test.readiness.provider"

        class Provider:
            contract_id = READINESS_PROVIDER_CONTRACT_ID
            contract_version = READINESS_PROVIDER_CONTRACT_VERSION

            def __init__(self):
                self.provider_id = provider_id

            async def observe(self, _request):
                raise AssertionError("registry test does not call provider inference or network")

        register_readiness_provider(provider_id, Provider)
        self.assertEqual(create_readiness_provider(provider_id).provider_id, provider_id)

    def test_invalid_provider_response_is_unknown_and_has_no_route(self):
        with TemporaryDirectory() as temp:
            settings, role, _, request = readiness_request(Path(temp))
            provider = OpenAICompatibleModelsReadinessProvider(
                transport=lambda *_args: (200, b'{"unexpected":true}'))
            observed = asyncio.run(provider.observe(request))
            self.assertEqual(observed.status, "unknown")
            decision = resolve_role((role,), role.role_id, {"plan"},
                                    {role.role_id: observed.to_dict()},
                                    config_revision=settings.source_digest)
            self.assertNotEqual(decision.action, "route")

    def test_stale_and_wrong_revision_readiness_cannot_route(self):
        with TemporaryDirectory() as temp:
            settings, role, _, request = readiness_request(Path(temp))
            body = json.dumps({"data": [{"id": request.route.model}]}).encode()
            observed = asyncio.run(OpenAICompatibleModelsReadinessProvider(
                transport=lambda *_args: (200, body)).observe(request))
            old = (datetime.now(timezone.utc) - timedelta(seconds=role.readiness_max_age_seconds + 5))
            stale = {**observed.to_dict(), "observed_at": old.isoformat()}
            self.assertEqual(resolve_role((role,), role.role_id, {"plan"}, {role.role_id: stale},
                                          config_revision=settings.source_digest).action, "defer")
            wrong_revision = {**observed.to_dict(), "config_revision": "older-config"}
            decision = resolve_role((role,), role.role_id, {"plan"}, {role.role_id: wrong_revision},
                                    config_revision=settings.source_digest)
            self.assertEqual(decision.action, "defer")
            self.assertIn("stale", decision.reason)


class DurableReadinessContinuationTests(unittest.IsolatedAsyncioTestCase):
    async def test_provider_ready_observation_releases_existing_waiting_activity(self):
        with TemporaryDirectory() as temp:
            settings, role, route, request = readiness_request(Path(temp))
            body = json.dumps({"data": [{"id": route.model}]}).encode()
            provider = OpenAICompatibleModelsReadinessProvider(
                transport=lambda *_args: (200, body))

            class StoreFake:
                def __init__(self):
                    self.observation = None
                    self.requeued = []
                    self.waiting = [{"activity_id": uuid4(), "input": {
                        "role_id": role.role_id, "role_config_revision": settings.source_digest,
                        "required_capabilities": ["plan"], "required_modalities": []}}]

                async def observe_model_role(self, observation):
                    self.observation = observation

                async def model_role_observations(self, role_ids):
                    if self.observation is None:
                        return {}
                    return {self.observation.role_id: self.observation.to_dict()}

                async def waiting_model_activities(self):
                    return self.waiting

                async def requeue_model_activity(self, activity_id, requested_role, selected_role, causation):
                    self.requeued.append((activity_id, requested_role, selected_role, causation))
                    return True

                async def block_waiting_model_activity(self, *_args):
                    raise AssertionError("fresh matching model should not block a deferred activity")

            cme = CME(settings, readiness_providers={OPENAI_MODELS_PROVIDER_ID: provider})
            store = StoreFake()
            cme.store = store
            observation, count = await cme._observe_model_role(role)
            self.assertEqual(observation.status, "ready")
            self.assertEqual(store.observation.config_revision, settings.source_digest)
            self.assertEqual(count, 1)
            self.assertEqual(store.requeued[0][1:3], (role.role_id, role.role_id))
            self.assertEqual(store.requeued[0][3], observation.observation_id)


if __name__ == "__main__":
    unittest.main()
