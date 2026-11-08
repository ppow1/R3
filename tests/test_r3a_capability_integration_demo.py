"""End-to-end isolated demonstration of CME dispatch and independent verification."""
# R3 CONTROLLED SOURCE
# File: tests/test_r3a_capability_integration_demo.py
# Component: R3A-AP2-ENGINEERING-INTEGRATION-TEST
# File Revision: 1.0.1
# Created: Unknown (legacy)
# Created By: Unknown (legacy)
# Purpose: Exercise canonical CME invocation, isolated Engineering file execution, recovery, and verification.
# Execution Model: Python unittest with isolated temporary workspace and durable-store protocol fixture.
# Observability: Test assertion results, invocation evidence, artifact digest, and verifier outcome.
# Dependencies: Python standard library; r3a_runtime CME, capability, and Engineering contracts.
# Authority: Steward directive — R3A Engineering Integration Live Execution, 2026-11-08.
# Changed: 2026-11-08T14:00:30Z | R3A-ENGINEERING-INTEGRATION | Codex GPT-6 | Bound the isolated async scenario and report timeouts clearly.
# Supersedes: None.
# Contracts: r3a.capability-invocation.v1; r3a.engineering-work-order.v1; r3a.verification-result.v1.
# Tests: This test module.
# History/Predecessor: Git blob c22fd56ec8638d34ac6c37019914332f0a881faa.
from __future__ import annotations

import asyncio
import copy
import hashlib
import importlib.util
import importlib.machinery
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

if importlib.util.find_spec("psycopg") is None:
    pg_module = types.ModuleType("psycopg")
    pg_module.__spec__ = importlib.machinery.ModuleSpec("psycopg", loader=None)
    pg_module.AsyncConnection = type("AsyncConnection", (), {})
    rows_module = types.ModuleType("psycopg.rows")
    rows_module.__spec__ = importlib.machinery.ModuleSpec("psycopg.rows", loader=None)
    rows_module.dict_row = object()
    pg_module.rows = rows_module
    sys.modules["psycopg"] = pg_module
    sys.modules["psycopg.rows"] = rows_module
if importlib.util.find_spec("psycopg_pool") is None:
    pool_module = types.ModuleType("psycopg_pool")
    pool_module.__spec__ = importlib.machinery.ModuleSpec("psycopg_pool", loader=None)
    pool_module.AsyncConnectionPool = type("AsyncConnectionPool", (), {
        "__init__": lambda self, *args, **kwargs: None})
    sys.modules["psycopg_pool"] = pool_module

from r3a_runtime.capability_contracts import CapabilityRegistry, validate_invocation_request
from r3a_runtime.cme import CME
from r3a_runtime.engineering import (CapabilityOperationRef, CriterionResult, EngineeringWorkOrder,
                                    VerificationResult, validate_completion)
from r3a_runtime.db import utcnow


ACTIVITY = "11111111-1111-4111-8111-111111111111"
ATTEMPT = "22222222-2222-4222-8222-222222222222"
CORRELATION = "33333333-3333-4333-8333-333333333333"
PROPOSAL = "44444444-4444-4444-8444-444444444444"
ORDER = "55555555-5555-4555-8555-555555555555"
ACTION = "66666666-6666-4666-8666-666666666666"
VERIFICATION = "77777777-7777-4777-8777-777777777777"


def descriptor() -> dict:
    provider = Path(__file__).parents[1] / "r3a_runtime/providers/isolated_workspace.py"
    return {
        "contract_id": "r3a.capability-operation.v1", "contract_version": "1.0.0",
        "operation_id": "engineering.workspace.apply_patch", "operation_revision": "demo-v1",
        "provider": {"provider_id": "r3a.isolated_workspace", "provider_version": "1.0.0",
                     "entrypoint": "r3a_runtime.providers.isolated_workspace:create_provider",
                     "artifact_sha256": hashlib.sha256(provider.read_bytes()).hexdigest()},
        "input_schema": {"type": "object", "required": ["path", "content"], "additionalProperties": False,
                         "properties": {"path": {"type": "string"}, "content": {"type": "string"}}},
        "output_schema": {"type": "object", "required": ["path", "sha256", "bytes_written", "replayed"],
                          "additionalProperties": False,
                          "properties": {"path": {"type": "string"}, "sha256": {"type": "string"},
                                         "bytes_written": {"type": "integer", "minimum": 0},
                                         "replayed": {"type": "boolean"}}},
        "effect_class": "isolated_write",
        "caller_constraints": {"allowed_principals": ["resident.grace"],
                                "allowed_residents": ["resident.grace"], "allowed_services": []},
        "target_scope_schema": {"type": "object", "required": ["workspace_id"],
                                "additionalProperties": False,
                                "properties": {"workspace_id": {"type": "string", "enum": ["candidate-1"]}}},
        "required_grants": ["engineering.workspace.apply_patch"],
        "evidence": {"schema": {"type": "object"}, "verification_obligations": ["independent_digest_check"]},
        "recovery": {"idempotency_required": True, "idempotency_scope": "work_order",
                     "replay_safe": True, "reconciliation_operation_id": None},
        "execution": {"timeout_seconds": 30, "retry_disposition": "safe_retry"},
        "lifecycle": {"desired_state": "enabled"},
        "resident_tool": {"name": "engineering_workspace_apply_patch", "description": "Apply one bounded file."}}


def work_order() -> EngineeringWorkOrder:
    operation = CapabilityOperationRef("engineering.workspace.apply_patch", "1.0.0", "isolated_write",
                                       {"workspace_id": "candidate-1"},
                                       {"path": "artifacts/result.txt", "content": "R3A isolated demo\n"})
    return EngineeringWorkOrder(
        work_order_id=ORDER, work_order_version=1, activity_id=ACTIVITY, attempt_id=ATTEMPT,
        correlation_id=CORRELATION, proposal_id=PROPOSAL, proposal_revision=1,
        proposal_digest="sha256:" + "a" * 64, resident_id="resident.grace", config_revision="cfg-demo",
        repository="ppow1/R3", baseline_ref="9925c7a408707162e6f070a4121dcc83f5fe0e0a",
        workspace_id="candidate-1", allowed_paths=("artifacts/**",), command_profiles=("file-write-demo",),
        operation_refs=(operation,), authorization_decision_id="decision-order",
        authorization_audit_event_id="audit-order", authorization_provider_id="fixture-grants",
        policy_revision="policy-demo", authorization_expires_at=None,
        criteria=({"criterion_id": "artifact_matches_scope", "description": "artifact digest and path match"},
                  {"criterion_id": "focused_checks_pass", "description": "independent checks pass"}),
        issued_at="2026-11-07T06:00:00Z")


class DurableFixtureStore:
    """Isolated durable-state stand-in with the same idempotency state transitions as Store."""
    def __init__(self, order: EngineeringWorkOrder):
        self.order = order
        self.order_state = "EXECUTING"
        self.invocations = {}
        self.fail_finish_once = True
        self.order_transitions = []

    async def get_engineering_work_order(self, order_id):
        return {"state": self.order_state, "details": {"work_order": self.order.to_dict()}}

    async def begin_capability_invocation(self, request, digest, authorization):
        key = request["idempotency_key"]
        previous = self.invocations.get(key)
        if previous:
            if previous["request_digest"] != digest:
                raise ValueError("idempotency conflict")
            return copy.deepcopy(previous)
        value = {"idempotency_key": key, "request_digest": digest, "state": "STARTED", "result": None}
        self.invocations[key] = value
        return copy.deepcopy(value)

    async def finish_capability_invocation(self, key, digest, result):
        if self.fail_finish_once:
            self.fail_finish_once = False
            raise RuntimeError("simulated process interruption after provider commit")
        value = self.invocations[key]
        if value["request_digest"] != digest:
            raise ValueError("request digest mismatch")
        value.update(state=result["outcome"], result=copy.deepcopy(result))

    async def transition_engineering_work_order(self, order_id, state, activity, attempt, correlation,
                                                reason, details, *, work_order=None, verification=None):
        if state == "COMPLETED":
            validate_completion(work_order, verification)
        self.order_state = state
        self.order_transitions.append((state, details, verification))
        return True


class IsolatedCapabilityIntegrationTests(unittest.TestCase):
    def test_cme_dispatch_recovery_artifact_verification_and_gated_completion(self):
        async def scenario(root: Path):
            order = work_order()
            registry = CapabilityRegistry()
            descriptor_value = descriptor()
            registry.register(descriptor_value, {"workspace_root": str(root)})
            registered = registry.resolve("engineering.workspace.apply_patch")
            self.assertEqual("isolated_write", registered.descriptor["effect_class"])
            self.assertEqual(1, len(registry.discover()))
            request = {
                "contract_id": "r3a.capability-invocation.v1", "contract_version": "1.0.0",
                "invocation_id": ACTION, "operation_id": "engineering.workspace.apply_patch",
                "operation_contract_version": "1.0.0",
                "caller": {"principal_id": "resident.grace", "resident_id": "resident.grace", "service_id": None},
                "target": {"workspace_id": "candidate-1"},
                "input": {"path": "artifacts/result.txt", "content": "R3A isolated demo\n"},
                "activity_id": ACTIVITY, "attempt_id": ATTEMPT, "correlation_id": CORRELATION,
                "work_order": {"work_order_id": ORDER, "version": 1},
                "evidence_purpose": "Create bounded isolated artifact for verification.",
                "idempotency_key": f"{ORDER}:1:1", "deadline": None, "config_revision": "cfg-demo"}
            validate_invocation_request(request, descriptor_value)
            instance = CME.__new__(CME)
            instance.settings = SimpleNamespace(capability_registry=registry)
            instance.store = DurableFixtureStore(order)
            artifact = root / "artifacts/result.txt"
            authorization_observed = []
            async def authorize(*args, **kwargs):
                if not authorization_observed:
                    self.assertFalse(artifact.exists(), "authorization must precede provider execution")
                authorization_observed.append(kwargs["context"])
                return {"provider_id": "fixture-grants", "decision_id": "decision-invocation",
                        "audit_event_id": "audit-invocation", "policy_revision": "policy-demo",
                        "config_revision": "cfg-demo"}
            instance._authorize_capability = AsyncMock(side_effect=authorize)
            with self.assertRaisesRegex(RuntimeError, "simulated process interruption"):
                await instance.invoke_capability(request, work_order=order)
            self.assertTrue(artifact.is_file())
            expected_digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
            self.assertEqual("STARTED", instance.store.invocations[request["idempotency_key"]]["state"])
            recovered = await instance.invoke_capability(request, work_order=order)
            self.assertEqual("SUCCEEDED", recovered["outcome"])
            self.assertTrue(recovered["output"]["replayed"])
            cached = await instance.invoke_capability(request, work_order=order)
            self.assertEqual(recovered, cached)
            self.assertEqual(3, instance._authorize_capability.await_count)
            self.assertEqual("CME", authorization_observed[0]["dispatcher"])
            self.assertEqual({"workspace_id": "candidate-1"}, authorization_observed[0]["target"])
            self.assertEqual("COMMITTED", recovered["effect_disposition"])

            # Independent verifier reads the artifact directly, outside the provider result path.
            observed_digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
            self.assertEqual(expected_digest, observed_digest)
            verifier = VerificationResult(
                verification_id=VERIFICATION, activity_id=ACTIVITY, work_order_id=ORDER,
                work_order_version=1, verifier_id="verifier.clean-workspace", verifier_version="1.0.0",
                policy_revision="verify-policy-demo", artifact_digests=(f"sha256:{observed_digest}",),
                results=(CriterionResult("artifact_matches_scope", "PASS", ("file:artifacts/result.txt",),
                                         "Independent path and digest check passed."),
                         CriterionResult("focused_checks_pass", "PASS", ("check:workspace-fixture",),
                                         "Fixture contract and output checks passed.")),
                verified_at=utcnow().isoformat(), outcome="PASS")
            await instance.store.transition_engineering_work_order(
                ORDER, "VERIFYING", ACTIVITY, ATTEMPT, CORRELATION,
                "Independent verifier inspected artifact", {"artifact_sha256": expected_digest})
            await instance.complete_engineering_work_order(order, verifier)
            self.assertEqual(["VERIFYING", "COMPLETED"], [x[0] for x in instance.store.order_transitions])
            self.assertEqual("PASS", instance.store.order_transitions[-1][2].outcome)

        with tempfile.TemporaryDirectory(prefix="r3a-capability-demo-") as temporary:
            try:
                asyncio.run(asyncio.wait_for(scenario(Path(temporary)), timeout=15.0))
            except asyncio.TimeoutError as exc:
                self.fail("CME Engineering integration scenario exceeded 15 seconds; "
                          "provider invocation, recovery, verification, or completion stalled")


if __name__ == "__main__":
    unittest.main()
