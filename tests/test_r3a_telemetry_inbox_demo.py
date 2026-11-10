"""Isolated simulated autonomous-inbox demonstration; no DB/model/runtime is started."""
from __future__ import annotations

import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

if importlib.util.find_spec("psycopg_pool") is None:
    pool_module = types.ModuleType("psycopg_pool")
    pool_module.AsyncConnectionPool = type("AsyncConnectionPool", (), {})
    sys.modules["psycopg_pool"] = pool_module

from r3a_runtime import cme as cme_module
from r3a_runtime.cme import CME
from r3a_runtime.grace_module import GraceResident, resident_action_schema
from r3a_runtime.capability_contracts import CapabilityRegistry


class FakeStore:
    def __init__(self):
        self.progress = []
        self.result = None
        self.blocked = None

    async def record_progress(self, activity, progress, checkpoint):
        self.progress.append(progress)

    async def finish_activity(self, activity, result):
        self.result = result

    async def block_activity(self, activity, reason, details):
        self.blocked = (reason, details)


class TelemetryInboxDemo(unittest.IsolatedAsyncioTestCase):
    async def test_grace_discovers_authorized_plugin_and_invokes_from_queued_objective(self):
        root = Path(__file__).resolve().parents[1]
        manifest = json.loads((root / "r3a_plugins/octominer_telemetry/manifest.json").read_text())
        capability_id = manifest["operation"]["operation_id"]
        plugin_config = {"host_id": "fixture-host"}
        registry = CapabilityRegistry()
        registry.register(manifest["operation"], plugin_config, legacy_manifest=manifest)
        registry.set_provider_state(manifest["provider"]["provider_id"],
                                    manifest["provider"]["provider_version"], "ACTIVE")
        cme = CME.__new__(CME)
        cme.settings = SimpleNamespace(
            module_capabilities=(capability_id,),
            capability_registry=registry, lease_seconds=30, source_digest="fixture-config",
            restart_initial_seconds=1, restart_max_seconds=4)
        cme.module_id = "resident.grace"
        cme.store = FakeStore()
        cme.module_process = SimpleNamespace(returncode=None)
        cme.active_activities = {}
        tools = [tool for tool in cme._resident_tools()
                 if tool["capability_id"] == capability_id]
        self.assertEqual(1, len(tools))
        self.assertIn(capability_id,
                      resident_action_schema(tools)["properties"]["capability_id"]["enum"])
        tool = tools[0]
        capability_id = tool["capability_id"]
        evidence = {"source_id": "fixture.telemetry", "source_path": "fixture://source",
                    "content": {"measured": 1}, "sha256": "f" * 64}
        descriptor = registry.resolve(capability_id).descriptor
        cme.invoke_capability = AsyncMock(return_value={
            "contract_id": "r3a.capability-invocation.v1", "contract_version": "1.0.0",
            "invocation_id": "fixture-invocation", "operation_id": capability_id,
            "operation_contract_version": descriptor["contract_version"],
            "provider": descriptor["provider"], "outcome": "SUCCEEDED",
            "started_at": "2026-11-08T01:00:00Z", "finished_at": "2026-11-08T01:00:01Z",
            "output": [evidence], "evidence": [evidence],
            "authorization": {"provider_id": "capability_grants", "allowed": True,
                               "decision_id": "fixture-decision", "audit_event_id": "fixture-grant",
                               "policy_revision": None, "config_revision": "fixture-config"}})
        action_count = 0
        route = SimpleNamespace(route_id="fixture-route", provider="fixture", model="fixture-model",
                                endpoint="http://127.0.0.1/unused", timeout_seconds=1, max_tokens=64)
        grace = GraceResident.__new__(GraceResident)
        grace.module_id = "Grace"
        grace.state = "ACTIVE"
        grace.settings = SimpleNamespace(model_route=lambda _route_id: route)
        grace.last_activity = None

        async def fixture_model_request(_endpoint, _timeout, request):
            nonlocal action_count
            action_count += 1
            choices = request["response_format"]["schema"]["properties"]["capability_id"].get("enum", [])
            if action_count == 1:
                self.assertIn(capability_id, choices)
                request = {"action": "invoke_capability", "contract_id": tool["contract_id"],
                           "contract_version": tool["contract_version"], "capability_id": capability_id,
                           "arguments": {}, "rationale": "Read the independently configured telemetry."}
            else:
                decision = {"assessment": "Telemetry evidence was read from the configured provider.",
                            "status": "healthy", "evidence_refs": ["fixture.telemetry"],
                            "recommended_action": "none"}
                request = {"action": "final", "decision": decision}
            return {"id": f"fixture-response-{action_count}",
                    "choices": [{"message": {"content": json.dumps(request)}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5}}

        grace._model_request = fixture_model_request

        async def model_action(operation, context, timeout):
            self.assertEqual("execute", operation)
            self.assertTrue(any(t["capability_id"] == capability_id for t in context["available_tools"]))
            return {"result": await grace.handle("execute", context)}

        context = {"activity_type": "grace.objective", "activity_id": "queued-activity",
                   "attempt_id": "attempt-1",
                   "objective": "Read telemetry", "route_id": "fixture-route",
                   "model_route": {"route_id": "fixture-route",
                   "provider": "fixture", "model": "fixture-model", "timeout_seconds": 1},
                   "conversation": [], "reasoning_state": {}, "evidence": [],
                   "required_evidence_refs": [], "acceptance_rejections": [], "evidence_format": 1,
                   "config_revision": "fixture-config", "route_decision": None, "pending_final": None,
                   "available_tools": list(cme._resident_tools())}
        async def objective_context(_activity):
            return dict(context)

        def fixture_adapter(_config):
            return [evidence]

        cme._objective_context = objective_context
        cme._module_call = model_action
        cme._final_evidence_issues = lambda *_args: []
        activity = {"activity_id": "queued-activity", "attempt_id": "attempt-1",
                    "attempt_count": 1, "activity_type": "grace.objective",
                    "input": {"objective": "Read telemetry"}}
        with patch.object(cme_module, "_knowledge_answer_issues", return_value=[]), \
                patch("r3a_plugins.octominer_telemetry.plugin.read_telemetry", fixture_adapter):
            await cme._run_activity(activity)

        self.assertEqual(2, action_count)
        cme.invoke_capability.assert_awaited_once()
        self.assertEqual("r3a.capability-invocation.v1",
                         cme.invoke_capability.await_args.args[0]["contract_id"])
        self.assertIsNotNone(cme.store.result)
        self.assertIsNone(cme.store.blocked)
        trace = cme.store.result["reasoning_trace"]
        self.assertEqual(capability_id, trace["capability_invocations"][0]["capability_request"]["capability_id"])
        self.assertEqual("fixture.telemetry", trace["evidence"][0]["source_id"])


if __name__ == "__main__":
    unittest.main()
