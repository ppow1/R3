"""
R3 CONTROLLED SOURCE
File: tests/test_r3a_reasoning_provider.py
Component: R3A-AP2-REASONING-PROVIDER-TESTS
File Revision: 1.0.0
Created: 2026-11-07 UTC
Created By: Codex GPT-6
Purpose: Verify configured model inference executes through the canonical provider boundary with preserved provenance.
Execution Model: Python unittest with a bounded HTTP provider fake.
Observability: Route identity, provider usage, request/response provenance, and evidence are asserted.
Dependencies: r3a_plugins.reasoning_inference and canonical capability contracts.
Authority: R3 Alpha autonomy Task B, GitHub Issues #43 and #46.
Changed: 2026-11-07 | AP2-ESCALATED-REASONING | Codex GPT-6 | Add focused model provider contract validation.
Changed: 2026-11-07 | AP2-ESCALATED-REASONING | Codex GPT-6 | Verify reserved CME inference dispatch runs once and rejects ambiguous replays.
Supersedes: None.
Contracts: r3a.capability-operation.v1; r3a.capability-invocation.v1.
Tests: This test module; isolated live model inference separately required.
History/Predecessor: New file; initial revision recorded in Git.
"""
from __future__ import annotations

import json
import copy
import hashlib
import unittest
import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from r3a_plugins.reasoning_inference.plugin import create_provider
from r3a_runtime.capability_contracts import (CapabilityProviderResult, CapabilityRegistry,
                                              normalize_provider_result)
from r3a_runtime.cme import CME


class ReasoningInferenceProviderTests(unittest.TestCase):
    def test_provider_uses_cme_selected_configured_route_and_returns_provenance(self):
        provider = create_provider({"temperature": 0.1})
        response = {"id": "provider-response-1", "choices": [{"message": {
            "content": "Inspect the source's permitted transitions before concluding."}}],
                    "usage": {"prompt_tokens": 42, "completion_tokens": 12}}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, _limit):
                return json.dumps(response).encode()

        with patch("urllib.request.urlopen", return_value=FakeResponse()) as send:
            result = provider.invoke(
                {"messages": [{"role": "user", "content": "evaluate the evidence"}]},
                context={"invocation_id": "inv-1", "model_role_id": "resident.primary",
                         "model_route": {"route_id": "configured-primary", "provider": "openai-compatible",
                                         "endpoint": "http://model.invalid/v1/chat/completions",
                                         "model": "configured-model", "timeout_seconds": 12,
                                         "max_tokens": 64}})
        self.assertIsInstance(result, CapabilityProviderResult)
        output, evidence = normalize_provider_result(result, {
            "output_schema": {"type": "object", "required": ["content"],
                              "properties": {"content": {"type": "string"}}},
            "evidence": {"schema": {"type": "array", "items": {"type": "object"}}}})
        self.assertEqual(output["content"], response["choices"][0]["message"]["content"])
        self.assertEqual(output["model"], "configured-model")
        self.assertEqual(evidence[0]["result_ref"], "provider-response-1")
        self.assertEqual(evidence[0]["usage"]["completion_tokens"], 12)
        request = json.loads(send.call_args.args[0].data)
        self.assertEqual(request["model"], "configured-model")
        self.assertEqual(request["max_tokens"], 64)

    def test_cme_runs_new_reserved_external_call_once_and_fails_closed_on_ambiguous_replay(self):
        descriptor = json.load(open("r3a_plugins/reasoning_inference/manifest.json"))["operation"]
        registry = CapabilityRegistry()
        registry.register(descriptor, {"temperature": 0.1})

        class Store:
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

        class Provider:
            calls = 0

            def invoke(self, _arguments, *, context):
                self.calls += 1
                now = datetime.now(timezone.utc).isoformat()
                content = "Additional analysis"
                return CapabilityProviderResult(
                    {"role_id": context["model_role_id"], "route_id": "primary",
                     "provider": "configured", "model": "configured-model", "content": content,
                     "provider_result_ref": "provider-result", "usage": {"completion_tokens": 8},
                     "elapsed_ms": 12.0, "finished_at": now},
                    [{"evidence_id": "evidence-1", "request_ref": context["invocation_id"],
                      "request_sha256": "a" * 64, "result_ref": "provider-result",
                      "result_sha256": hashlib.sha256(content.encode()).hexdigest(),
                      "role_id": context["model_role_id"], "route_id": "primary",
                      "provider": "configured", "model": "configured-model",
                      "usage": {"completion_tokens": 8}, "elapsed_ms": 12.0, "observed_at": now}])

        provider = Provider()
        request = {"contract_id": "r3a.capability-invocation.v1", "contract_version": "1.0.0",
                   "invocation_id": "11111111-1111-4111-8111-111111111111",
                   "operation_id": descriptor["operation_id"],
                   "operation_contract_version": descriptor["contract_version"],
                   "caller": {"principal_id": "resident:grace", "resident_id": "resident.grace",
                              "service_id": None},
                   "target": {"role_id": "resident.primary"},
                   "input": {"messages": [{"role": "user", "content": "analyze evidence"}]},
                   "activity_id": "22222222-2222-4222-8222-222222222222",
                   "attempt_id": "33333333-3333-4333-8333-333333333333",
                   "correlation_id": "44444444-4444-4444-8444-444444444444",
                   "work_order": None, "evidence_purpose": "bounded reasoning escalation",
                   "idempotency_key": "activity:escalation:1", "deadline": None,
                   "config_revision": "cfg-test",
                   "budget_reservation": {"contract_id": "r3a.activity-budget-reservation.v1",
                       "contract_version": "1.0.0", "reservation_id": "reservation-1",
                       "activity_id": "22222222-2222-4222-8222-222222222222",
                       "resource": "completion_tokens", "units": 64, "limit": 128,
                       "policy_revision": "cfg-test"}}
        instance = CME.__new__(CME)
        instance.settings = SimpleNamespace(capability_registry=registry, source_digest="cfg-test")
        instance.store = Store()
        instance._authorize_capability = AsyncMock(return_value={
            "provider_id": "fixture-grants", "decision_id": "decision-1",
            "audit_event_id": "audit-1", "policy_revision": "cfg-test",
            "config_revision": "cfg-test"})
        provider_context = {"model_role_id": "resident.primary",
                            "model_route": {"route_id": "primary", "provider": "configured",
                                            "model": "configured-model"}}

        from r3a_plugins.reasoning_inference import plugin as inference_plugin
        with patch.object(inference_plugin, "create_provider", return_value=provider):
            result = asyncio.run(instance.invoke_capability(
                request, _approved_budget_reservation=request["budget_reservation"],
                _provider_context=provider_context))
            self.assertEqual("SUCCEEDED", result["outcome"])
            self.assertEqual(1, provider.calls)
            # Model an interruption after the durable STARTED record but before result commit.
            instance.store.invocation.update(state="STARTED", result=None)
            with self.assertRaisesRegex(RuntimeError, "not replay safe"):
                asyncio.run(instance.invoke_capability(
                    request, _approved_budget_reservation=request["budget_reservation"],
                    _provider_context=provider_context))
        self.assertEqual(1, provider.calls)


if __name__ == "__main__":
    unittest.main()
