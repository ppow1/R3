"""
R3 CONTROLLED SOURCE
File: tests/test_r3a_grace_capability_autonomy.py
Component: R3A-GRACE-CAPABILITY-AUTONOMY-TESTS
File Revision: 1.0.2
Created: 2026-11-10T13:35:00Z
Created By: Codex GPT-6
Purpose: Verify dynamic authorized capability discovery, Grace's inventory answer path, and real CME read-provider execution.
Execution Model: unittest with real registered read-only knowledge provider and durable activity test double.
Observability: Assertions inspect model input, authorization decisions, invocation records, evidence, and final activity result.
Dependencies: R3A CME, Grace module, capability registry, institutional knowledge provider.
Authority: Steward directive R3A Grace Autonomy / Tool-Aware Conversation and Real Capability Execution, Issue #43.
Changed: 2026-11-10T13:35:00Z | R3A-GRACE-CAPABILITY-AUTONOMY | Codex GPT-6 | Add dynamic discovery and end-to-end tool-choice regressions.
Changed: 2026-11-10T13:50:00Z | R3A-GRACE-CAPABILITY-AUTONOMY | Codex GPT-6 | Verify an empty authorized capability inventory completes with a truthful answer.
Changed: 2026-11-10T14:05:00Z | R3A-GRACE-CAPABILITY-AUTONOMY | Codex GPT-6 | Verify canonical directory principal authorization uses the primary executor grant and preserves both identities.
Supersedes: None.
Contracts: r3a.capability-invocation.v1; r3a.resident-capability-tool@1.0.0; grace.conversation.
Tests: python -m pytest -q tests/test_r3a_grace_capability_autonomy.py
History/Predecessor: New permanent regression suite.
"""
from __future__ import annotations

import asyncio
import json
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from r3a_runtime.authorization import CapabilityGrantAuthorizationProvider
from r3a_runtime.capability_contracts import CapabilityRegistry, operation_from_manifest
from r3a_runtime.cme import CME
from r3a_runtime.grace_module import GraceResident
from r3a_runtime.provider_runtime import ProviderProcessManager


ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_MANIFEST = ROOT / "r3a_plugins/institutional_knowledge/manifest.json"


class CapabilityDiscoveryTests(unittest.TestCase):
    def test_inventory_uses_authorized_active_operations_and_reports_provider_failures(self):
        active = {
            "descriptor": {"operation_id": "hardware.telemetry.read", "contract_version": "1.0.0",
                           "effect_class": "read", "lifecycle": {"desired_state": "enabled"},
                           "provider": {"provider_id": "provider.telemetry", "provider_version": "2.0.0"}},
            "presentation": {"name": "Hardware telemetry", "description": "Read live sensor evidence."},
            "registry_observation": {"state": "ACTIVE", "observed_at": "2026-11-10T13:00:00Z"},
        }
        failed = {
            "descriptor": {"operation_id": "model.status.read", "contract_version": "1.0.0",
                           "effect_class": "read", "lifecycle": {"desired_state": "enabled"},
                           "provider": {"provider_id": "provider.model-status", "provider_version": "1.1.0"}},
            "presentation": {"name": "Model status", "description": "Read configured model health."},
            "registry_observation": {"state": "FAILED", "observed_at": "2026-11-10T13:00:00Z",
                                     "diagnostic": {"error_type": "ProviderTimeout", "private": "omit"}},
        }
        denied = {
            "descriptor": {"operation_id": "billing.read", "contract_version": "1.0.0",
                           "effect_class": "read", "lifecycle": {"desired_state": "enabled"},
                           "provider": {"provider_id": "provider.billing", "provider_version": "1.0.0"}},
            "presentation": {"name": "Billing", "description": "Restricted billing data."},
            "registry_observation": {"state": "ACTIVE"},
        }
        items = (active, failed, denied)
        registry = SimpleNamespace(
            discover=lambda **_kwargs: items,
            resolve=lambda operation_id, _version: SimpleNamespace(
                resident_tool_projection=lambda: {
                    "contract_id": "r3a.resident-capability-tool", "contract_version": "1.0.0",
                    "capability_id": operation_id, "name": "hardware_telemetry_read",
                    "description": "Read live sensor evidence.", "arguments_schema": {"type": "object"}}))
        cme = CME.__new__(CME)
        cme.module_id = "resident.grace"
        cme.settings = SimpleNamespace(module_capabilities=(
            "hardware.telemetry.read", "model.status.read", "billing.read"), capability_registry=registry)
        cme._authorization_decision = AsyncMock(side_effect=lambda capability_id, **_kwargs:
            (_ for _ in ()).throw(PermissionError("grant missing")) if capability_id == "billing.read"
            else SimpleNamespace(allowed=True))
        activity = {"activity_id": str(uuid.uuid4()), "attempt_id": str(uuid.uuid4()),
                    "input": {"resident_id": "resident:grace"}}

        available, limitations = asyncio.run(cme._resident_capability_view(activity, "resident.grace"))

        self.assertEqual(["hardware.telemetry.read"], [item["capability_id"] for item in available])
        self.assertEqual(["model.status.read"], [item["capability_id"] for item in limitations])
        self.assertEqual("failed", limitations[0]["availability"])
        self.assertEqual("ProviderTimeout", limitations[0]["diagnostic"]["error_type"])
        self.assertNotIn("private", json.dumps(limitations))
        self.assertNotIn("billing.read", json.dumps([available, limitations]))

    def test_directory_principal_uses_the_running_executor_module_grant(self):
        operation = {
            "descriptor": {"operation_id": "institution.knowledge.read", "contract_version": "1.0.0",
                           "effect_class": "read", "lifecycle": {"desired_state": "enabled"},
                           "provider": {"provider_id": "provider.knowledge", "provider_version": "1.0.0"}},
            "presentation": {"name": "Institutional knowledge", "description": "Search approved sources."},
            "registry_observation": {"state": "ACTIVE"},
        }
        registry = SimpleNamespace(
            discover=lambda **_kwargs: (operation,),
            resolve=lambda operation_id, _version: SimpleNamespace(
                resident_tool_projection=lambda: {
                    "contract_id": "r3a.resident-capability-tool", "contract_version": "1.0.0",
                    "capability_id": operation_id, "name": "Institutional knowledge",
                    "description": "Search approved sources.", "arguments_schema": {"type": "object"}}))

        class ExecutorGrantStore:
            def __init__(self):
                self.calls = []

            async def require_capability(self, principal, capability, _activity=None):
                self.calls.append((principal, capability))
                if (principal, capability) != ("resident.grace", "institution.knowledge.read"):
                    raise PermissionError("no grant for this subject")

            async def audit_capability_invocation(self, _resident_id, _capability_id, _result, _details):
                return "authorization-audit-test"

        cme = CME.__new__(CME)
        cme.module_id = "resident.grace"
        cme.settings = SimpleNamespace(module_capabilities=("institution.knowledge.read",),
                                       capability_registry=registry, source_digest="config-test")
        cme.store = ExecutorGrantStore()
        cme.authorization_provider = CapabilityGrantAuthorizationProvider(cme.store, "config-test")
        activity = {"activity_id": "activity-principal-binding", "attempt_id": "attempt-1",
                    "input": {"resident_id": "resident:grace"}}

        available, limitations = asyncio.run(
            cme._resident_capability_view(activity, "resident:grace"))

        self.assertEqual(["institution.knowledge.read"], [item["capability_id"] for item in available])
        self.assertEqual([], limitations)
        self.assertTrue(cme.store.calls)
        self.assertEqual({("resident.grace", "institution.knowledge.read")}, set(cme.store.calls))


class GraceCapabilityConversationTests(unittest.TestCase):
    def _resident(self, content):
        resident = GraceResident.__new__(GraceResident)
        resident.module_id = "resident.grace"
        resident.module_version = "test"
        resident.state = "ACTIVE"
        resident.last_activity = None
        route = SimpleNamespace(route_id="route.test", provider="fixture", model="fixture-model",
                                endpoint="http://127.0.0.1:1/chat", timeout_seconds=1, max_tokens=256)
        resident.settings = SimpleNamespace(model_route=lambda _route_id=None: route)
        resident._model_request = AsyncMock(return_value={
            "id": "fixture-response", "usage": {"prompt_tokens": 10, "completion_tokens": 20},
            "choices": [{"finish_reason": "stop", "message": {"content": content}}]})
        return resident

    def test_tool_inventory_question_can_complete_from_dynamic_tools_and_limitations(self):
        tools = [{"contract_id": "r3a.resident-capability-tool", "contract_version": "1.0.0",
                  "capability_id": "hardware.telemetry.read", "name": "Hardware telemetry",
                  "description": "Read live hardware sensor evidence.",
                  "arguments_schema": {"type": "object", "properties": {}, "additionalProperties": False}}]
        limitations = [{"capability_id": "model.status.read", "name": "Model status",
                        "description": "Read configured model health.", "availability": "failed",
                        "provider_id": "provider.model-status", "provider_version": "1.1.0",
                        "observed_at": "2026-11-10T13:00:00Z",
                        "diagnostic": {"error_type": "ProviderTimeout"}}]
        decision = {"action": "final", "decision": {
            "assessment": "I can read hardware telemetry. Model status is currently unavailable because its provider timed out.",
            "status": "healthy", "evidence_refs": [], "recommended_action": "none"}}
        resident = self._resident(json.dumps(decision))
        payload = {"activity_id": "activity-tool-question", "attempt_id": "attempt-1",
                   "request_ref": "request-1", "config_revision": "config-1",
                   "activity_type": "grace.objective", "event_kind": "conversation",
                   "objective": "Can you please tell me what tools you have available?",
                   "evidence": [], "available_tools": tools, "capability_limitations": limitations,
                   "conversation": [], "route_id": "route.test"}

        result = asyncio.run(resident.handle("execute", payload))

        self.assertEqual("final", result["action"])
        self.assertEqual("healthy", result["decision"]["status"])
        self.assertIn("hardware telemetry", result["decision"]["assessment"].lower())
        request = resident._model_request.await_args.args[2]
        context = json.loads(request["messages"][-1]["content"])
        self.assertEqual(tools, context["available_tools"])
        self.assertEqual(limitations, context["capability_limitations"])
        self.assertIn("When asked what tools or capabilities are available", request["messages"][0]["content"])
        self.assertIn("Do not choose blocked solely", request["messages"][0]["content"])

    def test_empty_authorized_inventory_can_complete_with_an_accurate_no_tools_answer(self):
        decision = {"action": "final", "decision": {
            "assessment": "No tools are currently authorized for me to use.",
            "status": "healthy", "evidence_refs": [], "recommended_action": "none"}}
        resident = self._resident(json.dumps(decision))
        payload = {"activity_id": "activity-empty-tool-question", "attempt_id": "attempt-1",
                   "request_ref": "request-1", "config_revision": "config-1",
                   "activity_type": "grace.objective", "event_kind": "conversation",
                   "objective": "What tools are available?", "evidence": [],
                   "available_tools": [], "capability_limitations": [],
                   "conversation": [], "route_id": "route.test"}

        result = asyncio.run(resident.handle("execute", payload))

        self.assertEqual("final", result["action"])
        self.assertEqual("healthy", result["decision"]["status"])
        self.assertIn("no tools are currently authorized", result["decision"]["assessment"].lower())
        request = resident._model_request.await_args.args[2]
        context = json.loads(request["messages"][-1]["content"])
        self.assertEqual([], context["available_tools"])
        self.assertEqual([], context["capability_limitations"])


class CMERegisteredCapabilityConversationTests(unittest.TestCase):
    class Store:
        def __init__(self):
            self.invocations = {}
            self.requests = {}
            self.progress = []
            self.completed = None
            self.blocked = None

        async def require_capability(self, resident_id, capability_id, activity_id=None):
            allowed = {("resident.grace", "institution.knowledge.read", "activity-real-tool"),
                       ("resident:grace", "resident.objective.execute", "activity-real-tool")}
            if (resident_id, capability_id, activity_id) not in allowed:
                raise PermissionError("No active grant")

        async def audit_capability_invocation(self, _resident_id, _capability_id, _result, _details):
            return str(uuid.uuid4())

        async def rows(self, _query, _parameters=()):
            return []

        async def register_module(self, _manifest, _state, _health):
            return None

        async def module_state(self, *_args, **_kwargs):
            return None

        async def begin_capability_invocation(self, request, _digest, _authorization):
            self.requests[request["idempotency_key"]] = request
            return {"state": "STARTED", "created": True}

        async def finish_capability_invocation(self, persistence_key, _digest, result):
            self.invocations[persistence_key] = result

        async def record_progress(self, _activity, progress, checkpoint=None):
            self.progress.append((dict(progress), checkpoint))

        async def renew_activity_lease(self, _activity):
            return None

        async def finish_activity(self, _activity, result):
            self.completed = result

        async def block_activity(self, _activity, reason, details):
            self.blocked = (reason, details)

        async def fail_activity(self, _activity, error, _retry):
            raise AssertionError(f"unexpected activity failure: {error}")

    def test_grace_selects_registered_read_tool_through_cme_and_completes_conversation(self):
        async def exercise():
            import tempfile
            with tempfile.TemporaryDirectory() as directory:
                source = Path(directory) / "operations.json"
                source.write_text('{"retention":{"days":30}}', encoding="utf-8")
                manifest = json.loads(KNOWLEDGE_MANIFEST.read_text(encoding="utf-8"))
                configuration = {"sources": [{"source_id": "knowledge.test.policy", "path": str(source),
                                               "freshness_max_age_seconds": 86400}],
                                 "max_results": 5, "max_document_bytes": 1024 * 1024}
                registry = CapabilityRegistry()
                registered = registry.register(operation_from_manifest(manifest), configuration,
                                               legacy_manifest=manifest)
                registry.set_provider_state(registered.descriptor["provider"]["provider_id"],
                                            registered.descriptor["provider"]["provider_version"],
                                            "ACTIVE")
                store = self.Store()
                cme = CME.__new__(CME)
                cme.module_id = "resident.grace"
                cme.module_version = "test"
                cme.module_process = SimpleNamespace(returncode=None)
                cme.settings = SimpleNamespace(
                    module_id="resident.grace", module_capabilities=("institution.knowledge.read",),
                    capability_registry=registry, source_digest="config-revision-test", lease_seconds=30,
                    scheduler_interval_seconds=1, restart_initial_seconds=1, restart_max_seconds=3,
                    data_dir=Path(directory) / "runtime")
                cme.store = store
                cme.authorization_provider = CapabilityGrantAuthorizationProvider(store, "config-revision-test")
                cme.provider_runtime = ProviderProcessManager(cme.settings, store, registry)
                cme.active_activities = {}
                cme._objective_context = AsyncMock(return_value={
                    "activity_type": "grace.objective", "activity_id": "activity-real-tool",
                    "attempt_id": "attempt-1", "objective": "What is the policy retention period?",
                    "resident_profile": {"resident_id": "resident:grace", "office_id": "office:grace",
                                          "office_role": "Director of Operations",
                                          "model_route_id": "route.test", "config_revision": "config-revision-test",
                                          "directory_evidence": {"snapshot_sha256": "a" * 64}},
                    "event_kind": "conversation", "route_id": "route.test",
                    "model_route": {"route_id": "route.test", "provider": "fixture", "model": "fixture",
                                    "endpoint": "http://127.0.0.1:1/chat", "timeout_seconds": 1,
                                    "max_tokens": 128},
                    "evidence_format": "r3a.knowledge-evidence.v1", "required_evidence_refs": [],
                    "evidence": [], "available_tools": [registered.resident_tool_projection()],
                    "capability_limitations": [], "conversation": [], "reasoning_state": {},
                    "pending_final": None, "config_revision": "config-revision-test"})
                tool_request = {"action": "invoke_capability", "contract_id": "r3a.resident-capability-tool",
                                "contract_version": "1.0.0", "capability_id": "institution.knowledge.read",
                                "arguments": {"query": "What is the retention period?"},
                                "rationale": "The answer requires a policy source."}
                final_decision = {"assessment": "The configured policy states retention is 30 days.",
                                  "status": "healthy", "evidence_refs": ["knowledge.test.policy"],
                                  "recommended_action": "none"}
                responses = [
                    {"result": {"action": "invoke_capability", "capability_request": tool_request,
                                 "model_content": json.dumps(tool_request),
                                 "model": {"request_ref": "model-tool", "result_ref": "result-tool"}}},
                    {"result": {"action": "final", "decision": final_decision,
                                 "model_content": json.dumps({"action": "final", "decision": final_decision}),
                                 "model": {"request_ref": "model-final", "result_ref": "result-final"}}},
                ]
                observed_payloads = []

                async def module_call(_operation, payload, **_kwargs):
                    observed_payloads.append(json.loads(json.dumps(payload)))
                    return responses.pop(0)

                cme._module_call = module_call
                cme._resolve_resident_executor = AsyncMock(return_value=None)
                activity = {"activity_type": "grace.objective", "activity_id": "activity-real-tool",
                            "attempt_id": "attempt-1", "attempt_count": 0,
                            "input": {"resident_id": "resident:grace",
                                      "objective": "What is the policy retention period?",
                                      "event_kind": "conversation"}, "checkpoint": {}}

                try:
                    await cme._run_activity(activity)
                finally:
                    await cme.provider_runtime.close()

                self.assertIsNone(store.blocked)
                self.assertEqual(final_decision, store.completed["decision"])
                self.assertEqual(1, len(store.invocations), {"completed": store.completed, "progress": store.progress})
                invocation = next(iter(store.invocations.values()))
                self.assertEqual("SUCCEEDED", invocation["outcome"])
                request_caller = next(iter(store.requests.values()))["caller"]
                self.assertEqual("resident:grace", request_caller["principal_id"])
                self.assertEqual("resident.grace", request_caller["resident_id"])
                self.assertEqual("activity-real-tool", invocation["activity_id"])
                self.assertEqual("retention.days: 30", invocation["output"]["results"][0]["content"])
                self.assertIn("knowledge.test.policy", [item["source_id"] for item in invocation["evidence"]])
                checkpoint = next(checkpoint for progress, checkpoint in store.progress
                                  if progress["phase"] == "resident.capability.completed")
                self.assertIn("knowledge.test.policy", [item["source_id"]
                                                        for item in checkpoint["evidence"]])
                self.assertEqual(2, len(observed_payloads))

        asyncio.run(exercise())

    def test_tool_provider_failure_is_returned_to_grace_as_a_clear_limitation(self):
        async def exercise():
            store = self.Store()
            cme = CME.__new__(CME)
            cme.module_id = "resident.grace"
            cme.module_version = "test"
            cme.module_process = SimpleNamespace(returncode=None)
            cme.settings = SimpleNamespace(module_id="resident.grace", module_capabilities=(),
                                           source_digest="config-revision-test", lease_seconds=30,
                                           scheduler_interval_seconds=1, restart_initial_seconds=1,
                                           restart_max_seconds=3)
            cme.store = store
            cme.active_activities = {}
            cme._objective_context = AsyncMock(return_value={
                "activity_type": "grace.objective", "activity_id": "activity-failing-tool",
                "attempt_id": "attempt-1", "objective": "Read current model status.",
                "event_kind": "conversation", "route_id": "route.test",
                "model_route": {"route_id": "route.test", "provider": "fixture", "model": "fixture",
                                "endpoint": "http://127.0.0.1:1/chat", "timeout_seconds": 1,
                                "max_tokens": 128},
                "evidence_format": "r3a.knowledge-evidence.v1", "required_evidence_refs": [],
                "evidence": [], "available_tools": [], "capability_limitations": [],
                "conversation": [], "reasoning_state": {}, "pending_final": None,
                "config_revision": "config-revision-test"})
            cme._invoke_resident_capability = AsyncMock(side_effect=RuntimeError("provider timed out"))
            tool_request = {"action": "invoke_capability", "contract_id": "r3a.resident-capability-tool",
                            "contract_version": "1.0.0", "capability_id": "model.status.read",
                            "arguments": {}, "rationale": "The Steward asked for current status."}
            final_decision = {"assessment": "The model status provider is unavailable because its request timed out.",
                              "status": "degraded", "evidence_refs": [], "recommended_action": "Retry later."}
            responses = [
                {"result": {"action": "invoke_capability", "capability_request": tool_request,
                             "model_content": json.dumps(tool_request), "model": {"request_ref": "model-tool"}}},
                {"result": {"action": "final", "decision": final_decision,
                             "model_content": json.dumps({"action": "final", "decision": final_decision}),
                             "model": {"request_ref": "model-final"}}},
            ]

            async def module_call(_operation, _payload, **_kwargs):
                return responses.pop(0)

            cme._module_call = module_call
            activity = {"activity_type": "grace.objective", "activity_id": "activity-failing-tool",
                        "attempt_id": "attempt-1", "attempt_count": 0,
                        "input": {"objective": "Read current model status.", "event_kind": "conversation"},
                        "checkpoint": {}}

            await cme._run_activity(activity)

            cme._invoke_resident_capability.assert_awaited_once()
            self.assertEqual(final_decision, store.completed["decision"])
            checkpoint = next(checkpoint for progress, checkpoint in store.progress
                              if progress["phase"] == "resident.capability.unavailable")
            receipt = next(json.loads(message["content"])
                           for message in checkpoint["reasoning_state"]["conversation"]
                           if message["role"] == "user" and "capability_result" in message["content"])
            self.assertEqual("unavailable", receipt["capability_result"]["outcome"])
            self.assertEqual("RuntimeError", receipt["capability_result"]["limitation"]["type"])
            self.assertEqual("provider timed out", receipt["capability_result"]["limitation"]["message"])

        asyncio.run(exercise())


if __name__ == "__main__":
    unittest.main()
