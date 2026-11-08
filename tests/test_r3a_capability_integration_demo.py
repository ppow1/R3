"""
R3 CONTROLLED SOURCE
File: tests/test_r3a_capability_integration_demo.py
Component: R3A-CAPABILITY-INTEGRATION-REGRESSION
File Revision: 1.0.2
Created: 2026-11-07 UTC
Created By: Codex GPT-6
Purpose: Verify canonical CME invocation, idempotent recovery, and independently gated completion.
Execution Model: Isolated fixture providers and durable-state test double.
Observability: Invocation traces, output artifacts, and verifier result assertions.
Dependencies: r3a_runtime.capability_contracts; r3a_runtime.cme.
Authority: R3 Alpha AP2 capability integration and escalation continuity.
Changed: 2026-11-07 | AP2-ESCALATED-REASONING | Codex GPT-6 | Distinguish first invocation creation from ambiguous recovery in the non-replayable path.
Changed: 2026-11-07 | R3A-MODULAR-FOUNDATION-001 | Codex GPT-6 | Exercise AP0-M1 provider process installation, activation, immutable version replacement, replay, and deactivation.
Supersedes: None.
Contracts: r3a.capability-invocation.v1; r3a.engineering-work-order.v1; r3a.verification-result.v1; module.lifecycle v2.
Tests: This test module.
History/Predecessor: Existing AP2 capability integration regression.
"""
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
from unittest.mock import AsyncMock, patch

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

from r3a_runtime.capability_contracts import (CapabilityRegistry, operation_from_manifest,
                                              validate_invocation_request)
from r3a_runtime.cme import CME
from r3a_runtime.engineering import (CapabilityOperationRef, CriterionResult, EngineeringWorkOrder,
                                    VerificationResult, validate_completion)
from r3a_runtime.db import utcnow
from r3a_runtime.provider_runtime import ProviderProcessManager, _module_environment


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
        self.modules = {}

    async def get_engineering_work_order(self, order_id):
        return {"state": self.order_state, "details": {"work_order": self.order.to_dict()}}

    async def begin_capability_invocation(self, request, digest, authorization):
        key = request["idempotency_key"]
        previous = self.invocations.get(key)
        if previous:
            if previous["request_digest"] != digest:
                raise ValueError("idempotency conflict")
            return {**copy.deepcopy(previous), "created": False}
        value = {"idempotency_key": key, "request_digest": digest, "state": "STARTED",
                 "result": None, "created": True}
        self.invocations[key] = value
        return copy.deepcopy(value)

    async def finish_capability_invocation(self, key, digest, result):
        if self.fail_finish_once and result["outcome"] == "SUCCEEDED":
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

    async def rows(self, query, params=()):
        row = self.modules.get(tuple(params))
        return ([{"artifact_digest": row["artifact_digest"], "lifecycle_state": row["lifecycle_state"]}]
                if row else [])

    async def register_module(self, manifest, lifecycle="INSTALLED", health="unknown", diagnostic=None):
        key = manifest["module_id"], manifest["module_version"]
        self.modules[key] = {"artifact_digest": manifest["artifact_digest"], "lifecycle_state": lifecycle}

    async def module_state(self, module_id, version, lifecycle, health, diagnostic=None, *, machine_version=1):
        self.modules[(module_id, version)]["lifecycle_state"] = lifecycle

    async def record_module_replacement(self, module_id, old_version, new_version, *, machine_version=1):
        pass


class ProviderLifecycleFixtureStore:
    """Lifecycle state/event stand-in for the durable Store module contract."""
    def __init__(self):
        self.modules = {}
        self.transitions = []
        self.replacements = []

    async def rows(self, query, params=()):
        row = self.modules.get(tuple(params))
        if row is None:
            return []
        if "artifact_digest" in query:
            return [{"artifact_digest": row["artifact_digest"], "lifecycle_state": row["lifecycle_state"]}]
        return [{"lifecycle_state": row["lifecycle_state"]}]

    async def register_module(self, manifest, lifecycle="INSTALLED", health="unknown", diagnostic=None):
        key = manifest["module_id"], manifest["module_version"]
        prior = self.modules.get(key)
        if prior and prior["artifact_digest"] != manifest["artifact_digest"]:
            raise RuntimeError("module version is immutable")
        self.modules[key] = {"artifact_digest": manifest["artifact_digest"],
                             "lifecycle_state": prior["lifecycle_state"] if prior else lifecycle}

    async def module_state(self, module_id, version, lifecycle, health, diagnostic=None, *, machine_version=1):
        key = module_id, version
        row = self.modules[key]
        previous = row["lifecycle_state"]
        allowed = {"INSTALLED": {"INSTALLED", "ACTIVATING", "STOPPED", "INCOMPATIBLE"},
                   "ACTIVATING": {"ACTIVE", "FAILED", "INCOMPATIBLE", "STOPPING"},
                   "ACTIVE": {"STOPPING", "FAILED", "REPLACING"},
                   "STOPPING": {"STOPPED", "FAILED"},
                   "STOPPED": {"ACTIVATING", "REPLACING", "INCOMPATIBLE"},
                   "FAILED": {"ACTIVATING", "STOPPED", "REPLACING"},
                   "INCOMPATIBLE": {"ACTIVATING", "STOPPED"},
                   "REPLACING": {"ACTIVE", "STOPPING", "FAILED", "INCOMPATIBLE"}}
        if lifecycle != previous and lifecycle not in allowed[previous]:
            raise ValueError(f"invalid lifecycle transition: {previous} -> {lifecycle}")
        row["lifecycle_state"] = lifecycle
        self.transitions.append((key, previous, lifecycle, health, diagnostic or {}))

    async def record_module_replacement(self, module_id, old_version, new_version, *, machine_version=1):
        self.replacements.append((module_id, old_version, new_version))


class IsolatedCapabilityIntegrationTests(unittest.TestCase):
    def test_registered_engineering_provider_process_can_be_replaced_and_stopped(self):
        async def scenario(root: Path):
            first = descriptor()
            second = copy.deepcopy(first)
            second["provider"]["provider_version"] = "1.0.1"
            replacement_artifact = (Path(__file__).parents[1] /
                                    "r3a_runtime/providers/isolated_workspace_replacement_fixture.py")
            second["provider"]["entrypoint"] = (
                "r3a_runtime.providers.isolated_workspace_replacement_fixture:create_provider")
            second["provider"]["artifact_sha256"] = hashlib.sha256(
                replacement_artifact.read_bytes()).hexdigest()
            registry = CapabilityRegistry()
            registry.register(first, {"workspace_root": str(root)})
            registry.register(second, {"workspace_root": str(root)})
            telemetry_root = Path(__file__).parents[1] / "r3a_plugins/octominer_telemetry"
            telemetry_manifest = json.loads((telemetry_root / "manifest.json").read_text())
            telemetry_config = json.loads((telemetry_root / "config.example.json").read_text())
            artifact_paths = {telemetry_manifest["artifact_sha256"]: str(telemetry_root / telemetry_manifest["artifact_ref"])}
            for supporting in telemetry_manifest["supporting_artifacts"]:
                artifact_paths[supporting["artifact_sha256"]] = str(telemetry_root / supporting["artifact_ref"])
            telemetry_operation = operation_from_manifest(telemetry_manifest)
            telemetry_manifest["_provider_artifact_path"] = artifact_paths[
                telemetry_operation["provider"]["artifact_sha256"]]
            telemetry_manifest["_pinned_artifact_paths"] = artifact_paths
            registry.register(telemetry_operation, telemetry_config, legacy_manifest=telemetry_manifest)
            with patch.dict("os.environ", {"R3A_TELEMETRY_DATABASE_DSN": "must-not-cross-module-boundary",
                                            "R3A_OCTOMINER_SSH_HOST": "telemetry-host"}):
                module_env = _module_environment(registry.resolve(
                    "infrastructure.octominer.telemetry.read"))
            self.assertNotIn("R3A_TELEMETRY_DATABASE_DSN", module_env)
            self.assertEqual("telemetry-host", module_env["R3A_OCTOMINER_SSH_HOST"])
            store = ProviderLifecycleFixtureStore()
            settings = SimpleNamespace(data_dir=root / "data")
            runtime = ProviderProcessManager(settings, store, registry)
            await runtime.install_all()
            installed = await store.rows("lifecycle_state", ("r3a.isolated_workspace", "1.0.0"))
            self.assertEqual("INSTALLED", installed[0]["lifecycle_state"])

            old = registry.resolve_provider("engineering.workspace.apply_patch", "1.0.0")
            await runtime.activate(old)
            context = {"invocation_id": "lifecycle-fixture", "effect_class": "isolated_write",
                       "target": {"workspace_id": "candidate-1"},
                       "work_order": {"workspace_id": "candidate-1", "allowed_paths": ["artifacts/**"]}}
            result = await runtime.invoke(old, {"path": "artifacts/result.txt", "content": "R3A module lifecycle\n"}, context)
            self.assertFalse(result["replayed"])

            new = registry.resolve_provider("engineering.workspace.apply_patch", "1.0.1")
            await runtime.begin_replacement("r3a.isolated_workspace", "1.0.0")
            await runtime.activate(new)
            registry.activate_provider("engineering.workspace.apply_patch", "1.0.1")
            await runtime.stop("r3a.isolated_workspace", "1.0.0")
            await store.record_module_replacement("r3a.isolated_workspace", "1.0.0", "1.0.1")
            active = registry.resolve("engineering.workspace.apply_patch")
            self.assertEqual("1.0.1", active.descriptor["provider"]["provider_version"])
            self.assertNotEqual(first["provider"]["artifact_sha256"],
                                active.descriptor["provider"]["artifact_sha256"])
            self.assertEqual("infrastructure.octominer.telemetry.read",
                             registry.resolve("infrastructure.octominer.telemetry.read").descriptor["operation_id"])
            replacement_context = {**context, "invocation_id": "replacement-implementation"}
            replacement_result = await runtime.invoke(
                active, {"path": "artifacts/replacement.txt", "content": "new implementation\n"},
                replacement_context)
            replacement_bytes = b"replacement-provider: new implementation\n"
            self.assertEqual(hashlib.sha256(replacement_bytes).hexdigest(), replacement_result["sha256"])
            self.assertEqual(replacement_bytes, (root / "artifacts/replacement.txt").read_bytes())
            replay = await runtime.invoke(
                active, {"path": "artifacts/replacement.txt", "content": "new implementation\n"},
                replacement_context)
            self.assertTrue(replay["replayed"])
            stopped = await store.rows("lifecycle_state", ("r3a.isolated_workspace", "1.0.0"))
            self.assertEqual("STOPPED", stopped[0]["lifecycle_state"])
            self.assertEqual([("r3a.isolated_workspace", "1.0.0", "1.0.1")], store.replacements)
            await runtime.stop("r3a.isolated_workspace", "1.0.1")

        with tempfile.TemporaryDirectory(prefix="r3a-provider-lifecycle-") as temporary:
            asyncio.run(scenario(Path(temporary)))

    def test_cme_discovery_exposes_registered_operations_without_authorizing(self):
        async def scenario():
            registered_descriptor = descriptor()
            registry = CapabilityRegistry()
            registry.register(registered_descriptor, {"workspace_root": "/tmp"})
            instance = CME.__new__(CME)
            instance.settings = SimpleNamespace(capability_registry=registry, source_digest="cfg-demo")
            result = await instance._control_request("capability.discover", {}, "discover-all")
            self.assertFalse(result["authorization_evaluated"])
            self.assertEqual("none; discovery does not authorize invocation", result["effect"])
            self.assertEqual(registered_descriptor["operation_id"],
                             result["operations"][0]["descriptor"]["operation_id"])
            selected = await instance._control_request(
                "capability.discover",
                {"operation_id": registered_descriptor["operation_id"],
                 "contract_version": registered_descriptor["contract_version"]},
                "discover-one")
            self.assertEqual(registered_descriptor,
                             selected["operations"][0]["descriptor"])
            self.assertEqual("Engineering Workspace Apply Patch",
                             selected["operations"][0]["presentation"]["name"])

        asyncio.run(scenario())

    def test_canonical_read_uses_cme_without_engineering_work_order(self):
        async def scenario(root: Path):
            order = work_order()
            read_descriptor = descriptor()
            read_descriptor["effect_class"] = "read"
            read_descriptor["recovery"]["idempotency_required"] = False
            registry = CapabilityRegistry()
            registry.register(read_descriptor, {"workspace_root": str(root)})
            instance = CME.__new__(CME)
            instance.settings = SimpleNamespace(capability_registry=registry, source_digest="cfg-demo")
            instance.store = DurableFixtureStore(order)
            instance.store.fail_finish_once = False
            instance._authorize_capability = AsyncMock(return_value={
                "provider_id": "fixture-grants", "decision_id": "decision-read",
                "audit_event_id": "audit-read", "policy_revision": "policy-demo",
                "config_revision": "cfg-demo"})

            class Reader:
                def invoke(self, arguments, *, context):
                    return {"path": arguments["path"], "sha256": "a" * 64,
                            "bytes_written": 0, "replayed": False}

            request = {
                "contract_id": "r3a.capability-invocation.v1", "contract_version": "1.0.0",
                "invocation_id": ACTION, "operation_id": "engineering.workspace.apply_patch",
                "operation_contract_version": "1.0.0",
                "caller": {"principal_id": "resident.grace", "resident_id": "resident.grace", "service_id": None},
                "target": {"workspace_id": "candidate-1"},
                "input": {"path": "artifacts/result.txt", "content": "observed"},
                "activity_id": ACTIVITY, "attempt_id": ATTEMPT, "correlation_id": CORRELATION,
                "work_order": None, "evidence_purpose": "Read one registered capability fixture.",
                "idempotency_key": None, "deadline": None, "config_revision": "cfg-demo"}
            from r3a_runtime.providers import isolated_workspace
            with patch.object(isolated_workspace, "create_provider", return_value=Reader()):
                result = await instance._control_request(
                    "capability.invoke", {"request": request}, "control-idempotency")
            self.assertEqual("SUCCEEDED", result["outcome"])
            self.assertEqual("NOT_STARTED", result["effect_disposition"])
            self.assertIsNone(instance._authorize_capability.await_args.kwargs["context"]["work_order_id"])
            self.assertEqual(f"invocation:{ACTION}", next(iter(instance.store.invocations)))

        with tempfile.TemporaryDirectory(prefix="r3a-canonical-read-") as temporary:
            asyncio.run(scenario(Path(temporary)))

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
            instance.settings = SimpleNamespace(capability_registry=registry, source_digest="cfg-demo")
            instance.store = DurableFixtureStore(order)
            instance.settings.data_dir = root / "r3a-data"
            instance.provider_runtime = ProviderProcessManager(instance.settings, instance.store, registry)
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
            with self.assertRaisesRegex(PermissionError, "requires its validated Engineering work order"):
                await instance.invoke_capability(request, work_order=None)
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
            await instance.provider_runtime.close()

        with tempfile.TemporaryDirectory(prefix="r3a-capability-demo-") as temporary:
            asyncio.run(scenario(Path(temporary)))


if __name__ == "__main__":
    unittest.main()
