"""
R3 CONTROLLED SOURCE
File: tests/test_r3a_capability_integration_demo.py
Component: R3A-CAPABILITY-INTEGRATION-REGRESSION
File Revision: 1.0.7
Created: 2026-11-07 UTC
Created By: Codex GPT-6
Purpose: Verify canonical CME invocation, idempotent recovery, and independently gated completion.
Execution Model: Isolated fixture providers and durable-state test double.
Observability: Invocation traces, output artifacts, and verifier result assertions.
Dependencies: r3a_runtime.capability_contracts; r3a_runtime.cme.
Authority: R3 Alpha AP2 capability integration and escalation continuity.
Changed: 2026-11-07 | AP2-ESCALATED-REASONING | Codex GPT-6 | Distinguish first invocation creation from ambiguous recovery in the non-replayable path.
Changed: 2026-11-07 | R3A-MODULAR-FOUNDATION-001 | Codex GPT-6 | Exercise AP0-M1 provider process installation, activation, immutable version replacement, replay, and deactivation.
Changed: 2026-11-10T01:35:58Z | R3A-MODULAR-PLUGINS-46 | Codex GPT-6 | Verify generic executor and activity-handler declarations survive registration, replacement, activation, and deactivation.
Changed: 2026-11-10T01:38:38Z | R3A-MODULAR-PLUGINS-46 | Codex GPT-6 | Exercise an actual provider worker startup failure during replacement and assert the old process remains effective.
Changed: 2026-11-10T01:38:38Z | R3A-MODULAR-PLUGINS-46 | Codex GPT-6 | Verify process loss after activation is durably diagnosed and blocks further discovery/invocation.
Changed: 2026-11-10T01:38:38Z | R3A-MODULAR-PLUGINS-46 | Codex GPT-6 | Verify handler discovery selects only the replacement module version after lifecycle transition.
Changed: 2026-11-10T02:02:46Z | R3A-MODULAR-PLUGINS-46 | Codex GPT-6 | Use manifest v1.1.0 when lifecycle fixtures declare resident and handler roles.
Supersedes: None.
Contracts: r3a.capability-invocation.v1; r3a.engineering-work-order.v1; r3a.verification-result.v1; module.lifecycle v2.
Tests: This test module.
History/Predecessor: Existing AP2 capability integration regression; prior tracked blob 10dc99eb14a2d7365d71a8db84af131ed605c4e2; immediate predecessor recorded in Git.
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

import pytest

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
                                              CapabilityProviderResult, validate_invocation_request)
from r3a_runtime.cme import CME
from r3a_runtime.config import _validate_plugin_config, load_settings
from r3a_runtime.engineering import (CapabilityOperationRef, CriterionResult, EngineeringWorkOrder,
                                    VerificationResult, validate_completion)
from r3a_runtime.db import utcnow
from r3a_runtime.provider_runtime import ProviderProcessManager, _module_environment
from r3a_runtime.module_extensions import resolve_activity_handler
from r3a_runtime.capability_worker import CapabilityWorker
from tests.test_r3a_modular_autonomy import make_config


ACTIVITY = "11111111-1111-4111-8111-111111111111"
ATTEMPT = "22222222-2222-4222-8222-222222222222"
CORRELATION = "33333333-3333-4333-8333-333333333333"
PROPOSAL = "44444444-4444-4444-8444-444444444444"
ORDER = "55555555-5555-4555-8555-555555555555"
ACTION = "66666666-6666-4666-8666-666666666666"
VERIFICATION = "77777777-7777-4777-8777-777777777777"


def descriptor() -> dict:
    return operation_from_manifest(engineering_manifest())


def engineering_manifest() -> dict:
    path = Path(__file__).parents[1] / "r3a_plugins/engineering_workspace/manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_engineering_operation_is_defined_by_external_versioned_manifest():
    manifest = engineering_manifest()
    operation = operation_from_manifest(manifest)
    assert operation["operation_id"] == "engineering.workspace.apply_patch"
    assert operation["provider"]["provider_version"] == manifest["plugin_version"]
    assert manifest["module_manifest"]["module_id"] == operation["provider"]["provider_id"]
    assert manifest["module_manifest"]["configuration"]["schema_ref"] == \
        manifest["configuration_schema"]["schema_id"]
    _validate_plugin_config({"workspace_root": "/tmp/r3a-engineering-workspace"},
                            manifest["configuration_schema"], "engineering configuration")
    with pytest.raises(ValueError, match="configuration"):
        _validate_plugin_config({"workspace_root": "/tmp/workspace", "secret": "forbidden"},
                                manifest["configuration_schema"], "engineering configuration")
    incompatible = copy.deepcopy(manifest)
    incompatible["module_manifest"]["binding"]["protocol_min_minor"] = 1
    with pytest.raises(ValueError, match="protocol range"):
        operation_from_manifest(incompatible)


def test_provider_environment_forwards_only_manifest_authorized_database_references():
    package = Path(__file__).resolve().parents[1] / "r3a_plugins/institutional_directory"
    manifest = json.loads((package / "manifest.json").read_text())
    operation = operation_from_manifest(manifest)
    registry = CapabilityRegistry()
    registered = registry.register(operation, json.loads((package / "config.example.json").read_text()),
                                   legacy_manifest=manifest)
    with patch.dict("os.environ", {"R3A_DIRECTORY_POSTGRES_DSN": "directory-secret-reference",
                                    "R3A_TELEMETRY_DATABASE_DSN": "unrelated-database-secret"}):
        environment = _module_environment(registered)
    assert environment["R3A_DIRECTORY_POSTGRES_DSN"] == "directory-secret-reference"
    assert "R3A_TELEMETRY_DATABASE_DSN" not in environment


def test_provider_lifecycle_restores_only_durably_active_modules():
    async def scenario():
        operation = SimpleNamespace(descriptor={
            "operation_id": "institutional.directory.discover",
            "lifecycle": {"desired_state": "enabled"},
            "provider": {"provider_id": "r3a.institutional-directory", "provider_version": "1.1.1"},
        }, legacy_manifest={})
        class Registry:
            def __init__(self):
                self.states = []
            def discover(self, **_kwargs):
                return [{"descriptor": operation.descriptor}]
            def resolve_provider(self, *_args):
                return operation
            def set_provider_state(self, *args):
                self.states.append(args)
        class Store:
            def __init__(self, resume):
                self.resume = resume
            async def register_module(self, *_args, **_kwargs):
                return None
            async def rows(self, *_args, **_kwargs):
                return [{"lifecycle_state": "STOPPED",
                         "diagnostic": {"resume_on_start": self.resume}}]
            async def module_state(self, *_args, **_kwargs):
                return None
        manifest = {"module_id": "r3a.institutional-directory", "module_version": "1.1.1",
                    "protocol_major": 1, "protocol_min_minor": 0, "protocol_max_minor": 0,
                    "artifact_digest": "a" * 64}
        for resume, expected in ((True, 1), (False, 0)):
            registry, store = Registry(), Store(resume)
            runtime = ProviderProcessManager(SimpleNamespace(), store, registry)
            runtime._manifest = lambda _operation: manifest
            runtime.activate = AsyncMock(return_value={"state": "ACTIVE"})
            await runtime.install_all()
            assert runtime.activate.await_count == expected

    asyncio.run(scenario())


def test_generic_provider_worker_round_trips_typed_output_and_evidence():
    async def scenario():
        output = {"schema_id": "knowledge.results.v1", "results": [{"source_id": "knowledge.policy"}]}
        evidence = [{"evidence_id": "knowledge.policy", "document_sha256": "a" * 64}]
        worker = CapabilityWorker("r3a.knowledge", "1.1.0", "fixture:create_provider",
                                  Path("/unused"), "a" * 64)
        worker.state = "ACTIVE"
        worker.provider = SimpleNamespace(invoke=lambda _arguments, *, context:
                                           CapabilityProviderResult(output, evidence))
        wire = await worker.handle("execute", {"arguments": {"query": "policy"}, "context": {}})
        assert {"contract_id": "r3a.capability-provider-result.v1",
                "contract_version": "1.0.0", "output": output, "evidence": evidence} == \
            wire["provider_result"]
        json.dumps(wire)

        manager = ProviderProcessManager.__new__(ProviderProcessManager)
        manager._lock = asyncio.Lock()
        manager.processes = {}
        binding = SimpleNamespace(module_id="r3a.knowledge", version="1.1.0",
                                  socket=Path("/unused"), admission_open=True,
                                  inflight=0, drained=asyncio.Event())
        binding.drained.set()
        manager.processes[(binding.module_id, binding.version)] = binding
        manager._ensure_active = AsyncMock(return_value=binding)
        operation = SimpleNamespace(descriptor={"execution": {"timeout_seconds": 2}})
        with patch("r3a_runtime.provider_runtime.request",
                   new=AsyncMock(return_value={"result": wire})):
            restored = await manager.invoke(operation, {"query": "policy"}, context={})
        assert isinstance(restored, CapabilityProviderResult)
        assert output == restored.output
        assert evidence == restored.evidence

    asyncio.run(scenario())


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
        if "health" in query:
            return [{"lifecycle_state": row["lifecycle_state"], "health": row["health"],
                     "observed_at": row["observed_at"], "diagnostic": copy.deepcopy(row["diagnostic"])}]
        return [{"lifecycle_state": row["lifecycle_state"]}]

    async def register_module(self, manifest, lifecycle="INSTALLED", health="unknown", diagnostic=None):
        key = manifest["module_id"], manifest["module_version"]
        prior = self.modules.get(key)
        if prior and prior["artifact_digest"] != manifest["artifact_digest"]:
            raise RuntimeError("module version is immutable")
        self.modules[key] = {"artifact_digest": manifest["artifact_digest"],
                             "lifecycle_state": prior["lifecycle_state"] if prior else lifecycle,
                             "health": prior["health"] if prior else health,
                             "observed_at": None,
                             "diagnostic": prior["diagnostic"] if prior else copy.deepcopy(diagnostic or {}),
                             "manifest": copy.deepcopy(manifest)}

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
        row["health"] = health
        row["observed_at"] = "fixture-observation"
        row["diagnostic"] = copy.deepcopy(diagnostic or {})
        self.transitions.append((key, previous, lifecycle, health, diagnostic or {}))

    async def record_module_replacement(self, module_id, old_version, new_version, *, machine_version=1):
        self.replacements.append((module_id, old_version, new_version))


class IsolatedCapabilityIntegrationTests(unittest.TestCase):
    def test_registered_engineering_provider_process_can_be_replaced_and_stopped(self):
        async def scenario(root: Path):
            bootstrap = make_config(root)
            config = json.loads(bootstrap.read_text(encoding="utf-8"))
            engineering_root = Path(__file__).parents[1] / "r3a_plugins/engineering_workspace"
            module_declaration = {}
            module_declaration["resident_executor"] = {
                "contract_id": "r3a.resident.executor", "contract_version": "1.0.0",
                "execution_contract_range": {"contract_id": "r3a.resident.execution", "major": 1,
                                             "min_minor": 0, "max_minor": 2}}
            module_declaration["activity_handler"] = {
                "contract_id": "r3a.activity-handler", "contract_version": "1.0.0",
                "handler_id": "fixture.engineering-handler", "handler_version": "1.0.0",
                "activity_types": ["fixture.engineering.reconcile"],
                "activity_contract_range": {"contract_id": "r3a.activity-intake", "major": 1,
                                             "min_minor": 0, "max_minor": 0},
                "handler_contract_range": {"contract_id": "r3a.activity-handler", "major": 1,
                                            "min_minor": 0, "max_minor": 0},
                "request_schema": {"type": "object", "properties": {}, "additionalProperties": False},
                "result_schema": {"type": "object", "properties": {}, "additionalProperties": False},
                "progress_schema": {"type": "object", "properties": {}, "additionalProperties": False},
                "checkpoint_schema": {"type": "object", "properties": {}, "additionalProperties": False},
                "progress_semantics": "Progress observations are monotonic.",
                "checkpoint_semantics": "Checkpoint resumes after the last committed item.",
                "required_capabilities": [],
                "resource_constraints": {"cpu_millis": 250, "memory_bytes": 134217728,
                                         "max_concurrency": 1},
                "state_namespace": "fixture.engineering", "migration_contract": "fixture.engineering-migration.v1",
                "recovery": {"mode": "checkpointed", "idempotency_contract": "fixture.engineering-idempotency.v1",
                             "checkpoint_contract": "fixture.engineering-checkpoint.v1"}}
            engineering_config = root / "engineering-workspace.json"
            engineering_config.write_text(json.dumps({"workspace_root": str(root)}), encoding="utf-8")
            telemetry_root = Path(__file__).parents[1] / "r3a_plugins/octominer_telemetry"
            config["module"]["capabilities"].extend([
                "engineering.workspace.apply_patch", "infrastructure.octominer.telemetry.read"])
            config["capability_operations"] = [
                {"manifest": str(engineering_root / "manifest.json"),
                 "configuration": str(engineering_config)},
                {"manifest": str(telemetry_root / "manifest.json"),
                 "configuration": str(telemetry_root / "config.example.json")},
            ]
            bootstrap.write_text(json.dumps(config), encoding="utf-8")
            settings = load_settings(bootstrap)
            registry = settings.capability_registry
            first_registered = registry.resolve_provider("engineering.workspace.apply_patch", "1.0.0")
            first_registered.legacy_manifest["module_manifest"]["contract_version"] = "1.1.0"
            first_registered.legacy_manifest["module_manifest"].update(copy.deepcopy(module_declaration))
            registry._operations[("engineering.workspace.apply_patch", "r3a.isolated_workspace", "1.0.0")] = \
                first_registered
            first = first_registered.descriptor
            first_manifest = copy.deepcopy(first_registered.legacy_manifest)
            second = copy.deepcopy(first)
            second["provider"]["provider_version"] = "1.0.1"
            replacement_artifact = (Path(__file__).parents[1] /
                                    "r3a_plugins/engineering_workspace/replacement_test_fixture.py")
            second["provider"]["entrypoint"] = (
                "r3a_plugins.engineering_workspace.replacement_test_fixture:create_provider")
            second["provider"]["artifact_sha256"] = hashlib.sha256(
                replacement_artifact.read_bytes()).hexdigest()
            second_manifest = copy.deepcopy(first_manifest)
            second_manifest["plugin_version"] = "1.0.1"
            second_manifest["artifact_ref"] = "replacement_test_fixture.py"
            second_manifest["artifact_sha256"] = second["provider"]["artifact_sha256"]
            second_manifest["supporting_artifacts"] = [{
                "artifact_ref": "provider.py",
                "artifact_sha256": first["provider"]["artifact_sha256"]
            }]
            second_manifest["provider"].update(second["provider"])
            second_manifest["operation"]["operation_revision"] = "1.0.1"
            second_manifest["operation"]["provider"].update(second["provider"])
            second_manifest["module_manifest"]["module_version"] = "1.0.1"
            second_manifest["module_manifest"]["binding"]["entrypoint"] = second["provider"]["entrypoint"]
            second_manifest["module_manifest"]["artifact"] = {
                "artifact_ref": "replacement_test_fixture.py",
                "artifact_sha256": second["provider"]["artifact_sha256"]}
            second = operation_from_manifest(second_manifest)
            second_manifest["_provider_artifact_path"] = str(replacement_artifact)
            second_manifest["_pinned_artifact_paths"] = {
                str(replacement_artifact): second["provider"]["artifact_sha256"],
                **first_manifest["_pinned_artifact_paths"]}
            registry.register(second, {"workspace_root": str(root)}, legacy_manifest=second_manifest)
            failed_manifest = copy.deepcopy(first_manifest)
            failed_manifest["plugin_version"] = "1.0.2"
            failed_manifest["provider"]["provider_version"] = "1.0.2"
            failed_manifest["provider"]["entrypoint"] = (
                "r3a_plugins.engineering_workspace.provider:missing_factory")
            failed_manifest["operation"]["provider"].update(failed_manifest["provider"])
            failed_manifest["module_manifest"]["module_version"] = "1.0.2"
            failed_manifest["module_manifest"]["binding"]["entrypoint"] = (
                "r3a_plugins.engineering_workspace.provider:missing_factory")
            failed = operation_from_manifest(failed_manifest)
            registry.register(failed, {"workspace_root": str(root)}, legacy_manifest=failed_manifest)
            with patch.dict("os.environ", {"R3A_TELEMETRY_DATABASE_DSN": "must-not-cross-module-boundary",
                                            "R3A_OCTOMINER_SSH_HOST": "telemetry-host"}):
                telemetry = registry.resolve("infrastructure.octominer.telemetry.read")
                module_env = _module_environment(telemetry)
            self.assertNotIn("R3A_TELEMETRY_DATABASE_DSN", module_env)
            self.assertEqual("telemetry-host", module_env["R3A_OCTOMINER_SSH_HOST"])
            self.assertTrue(telemetry.legacy_manifest["_pinned_artifact_paths"])
            self.assertTrue(all(len(digest) == 64 and Path(path).is_file()
                                for path, digest in telemetry.legacy_manifest["_pinned_artifact_paths"].items()))
            store = ProviderLifecycleFixtureStore()
            runtime = ProviderProcessManager(settings, store, registry)
            cme = CME.__new__(CME)
            cme.settings = settings
            cme.store = store
            cme.provider_runtime = runtime
            telemetry_discovery = await cme._control_request(
                "capability.discover", {"operation_id": "infrastructure.octominer.telemetry.read"},
                "discover-telemetry-manifest")
            self.assertFalse(telemetry_discovery["authorization_evaluated"])
            self.assertEqual("infrastructure.octominer.telemetry.read",
                             telemetry_discovery["operations"][0]["descriptor"]["operation_id"])
            telemetry_install = await cme._control_request(
                "capability.module.install",
                {"operation_id": "infrastructure.octominer.telemetry.read"},
                "install-telemetry-manifest")
            self.assertTrue(telemetry_install["installed"])
            install = await cme._control_request(
                "capability.module.install",
                {"operation_id": "engineering.workspace.apply_patch", "provider_version": "1.0.0"},
                "install-engineering-v1")
            self.assertTrue(install["installed"])
            install_new = await cme._control_request(
                "capability.module.install",
                {"operation_id": "engineering.workspace.apply_patch", "provider_version": "1.0.1"},
                "install-engineering-v1.0.1")
            self.assertTrue(install_new["installed"])
            expected_executor = module_declaration["resident_executor"]
            expected_handler = module_declaration["activity_handler"]
            installed_roles = store.modules[("r3a.isolated_workspace", "1.0.0")]["manifest"]
            self.assertEqual(expected_executor, installed_roles["resident_executor"])
            self.assertEqual(expected_handler, installed_roles["activity_handler"])
            replacement_roles = store.modules[("r3a.isolated_workspace", "1.0.1")]["manifest"]
            self.assertEqual(expected_executor, replacement_roles["resident_executor"])
            self.assertEqual(expected_handler, replacement_roles["activity_handler"])
            installed = await store.rows("lifecycle_state", ("r3a.isolated_workspace", "1.0.0"))
            self.assertEqual("INSTALLED", installed[0]["lifecycle_state"])

            old = registry.resolve_provider("engineering.workspace.apply_patch", "1.0.0")
            await cme._control_request(
                "capability.module.activate",
                {"operation_id": "engineering.workspace.apply_patch", "provider_version": "1.0.0"},
                "activate-engineering-v1")
            context = {"invocation_id": "lifecycle-fixture", "effect_class": "isolated_write",
                       "target": {"workspace_id": "candidate-1"},
                       "work_order": {"workspace_id": "candidate-1", "allowed_paths": ["artifacts/**"]}}
            result = await runtime.invoke(old, {"path": "artifacts/result.txt", "content": "R3A module lifecycle\n"}, context)
            self.assertFalse(result["replayed"])

            with self.assertRaisesRegex(RuntimeError, "provider|factory|attribute"):
                await cme._control_request(
                    "capability.module.replace",
                    {"operation_id": "engineering.workspace.apply_patch",
                     "old_module_id": "r3a.isolated_workspace", "old_version": "1.0.0",
                     "new_provider_version": "1.0.2"},
                    "replace-engineering-provider-with-failing-candidate")
            selected_after_failure = registry.resolve("engineering.workspace.apply_patch")
            self.assertEqual("1.0.0", selected_after_failure.descriptor["provider"]["provider_version"])
            failed_candidate = await store.rows(
                "lifecycle_state", ("r3a.isolated_workspace", "1.0.2"))
            self.assertEqual("FAILED", failed_candidate[0]["lifecycle_state"])
            prior_after_failure = await store.rows(
                "lifecycle_state", ("r3a.isolated_workspace", "1.0.0"))
            self.assertEqual("ACTIVE", prior_after_failure[0]["lifecycle_state"])
            self.assertEqual([], store.replacements)

            replacement = await cme._control_request(
                "capability.module.replace",
                {"operation_id": "engineering.workspace.apply_patch",
                 "old_module_id": "r3a.isolated_workspace", "old_version": "1.0.0",
                 "new_provider_version": "1.0.1"},
                "replace-engineering-provider")
            self.assertTrue(replacement["replaced"])
            active = registry.resolve("engineering.workspace.apply_patch")
            self.assertEqual("1.0.1", active.descriptor["provider"]["provider_version"])
            self.assertNotEqual(first["provider"]["artifact_sha256"],
                                active.descriptor["provider"]["artifact_sha256"])
            self.assertEqual("infrastructure.octominer.telemetry.read",
                             registry.resolve("infrastructure.octominer.telemetry.read").descriptor["operation_id"])
            handler_rows = [
                {"module_id": module_id, "module_version": version,
                 "lifecycle_state": row["lifecycle_state"], "manifest": row["manifest"]}
                for (module_id, version), row in store.modules.items()]
            discovered_handler = resolve_activity_handler(
                handler_rows, "fixture.engineering.reconcile")
            self.assertEqual("r3a.isolated_workspace", discovered_handler["module_id"])
            self.assertEqual("1.0.1", discovered_handler["module_version"])
            self.assertEqual(active.descriptor["provider"]["artifact_sha256"],
                             discovered_handler["artifact_digest"])
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
            status = await cme._control_request(
                "capability.module.status",
                {"operation_id": "engineering.workspace.apply_patch", "provider_version": "1.0.1"},
                "status-engineering-v1.0.1")
            self.assertEqual("1.0.1", status["provider_version"])
            self.assertEqual("ACTIVE", status["module"]["lifecycle_state"])
            self.assertEqual("healthy", status["module"]["health"])
            self.assertEqual("fixture-observation", status["module"]["observed_at"])
            self.assertEqual("r3a.capability-provider.v1",
                             status["module"]["diagnostic"]["observed_contract"]["contract_id"])
            await cme._control_request(
                "capability.module.deactivate",
                {"operation_id": "engineering.workspace.apply_patch", "provider_version": "1.0.1"},
                "deactivate-engineering-v1.0.1")
            stopped_new = await store.rows("lifecycle_state", ("r3a.isolated_workspace", "1.0.1"))
            self.assertEqual("STOPPED", stopped_new[0]["lifecycle_state"])
            self.assertEqual(expected_executor,
                             store.modules[("r3a.isolated_workspace", "1.0.1")]["manifest"]["resident_executor"])
            self.assertEqual(expected_handler,
                             store.modules[("r3a.isolated_workspace", "1.0.1")]["manifest"]["activity_handler"])
            replacement_states = [state for key, _previous, state, _health, _diagnostic in store.transitions
                                  if key[0] == "r3a.isolated_workspace"]
            self.assertIn("REPLACING", replacement_states)
            self.assertEqual("STOPPED", replacement_states[-1])
            with self.assertRaisesRegex(ValueError, "provider is stopped"):
                registry.resolve("engineering.workspace.apply_patch")
            await cme._control_request(
                "capability.module.activate",
                {"operation_id": "engineering.workspace.apply_patch", "provider_version": "1.0.1"},
                "reactivate-engineering-v1.0.1-for-health-failure")
            active_binding = runtime.processes[("r3a.isolated_workspace", "1.0.1")]
            active_binding.process.terminate()
            await active_binding.process.wait()
            await runtime.check_health()
            failed_after_start = store.modules[("r3a.isolated_workspace", "1.0.1")]
            self.assertEqual("FAILED", failed_after_start["lifecycle_state"])
            self.assertEqual("unavailable", failed_after_start["health"])
            self.assertEqual("provider process exited", failed_after_start["diagnostic"]["reason"])
            with self.assertRaisesRegex(ValueError, "provider is failed"):
                registry.resolve("engineering.workspace.apply_patch")
            self.assertEqual("infrastructure.octominer.telemetry.read",
                             registry.resolve("infrastructure.octominer.telemetry.read").descriptor["operation_id"])

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
            from r3a_plugins.engineering_workspace import provider as engineering_provider
            with patch.object(engineering_provider, "create_provider", return_value=Reader()):
                result = await instance._control_request(
                    "capability.invoke", {"request": request}, "control-idempotency")
            self.assertEqual("SUCCEEDED", result["outcome"])
            self.assertEqual("NOT_STARTED", result["effect_disposition"])
            self.assertIsNone(instance._authorize_capability.await_args.kwargs["context"]["work_order_id"])
            self.assertEqual(f"invocation:{ACTION}", next(iter(instance.store.invocations)))

        with tempfile.TemporaryDirectory(prefix="r3a-canonical-read-") as temporary:
            asyncio.run(scenario(Path(temporary)))

    def test_handler_work_item_uses_canonical_authorized_isolated_write_dispatch(self):
        async def scenario(root: Path):
            order = work_order()
            registry = CapabilityRegistry()
            registry.register(descriptor(), {"workspace_root": str(root)})
            instance = CME.__new__(CME)
            instance.settings = SimpleNamespace(capability_registry=registry, source_digest="cfg-demo")
            instance.store = DurableFixtureStore(order)
            instance.store.fail_finish_once = False
            instance._authorize_capability = AsyncMock(return_value={
                "provider_id": "fixture-grants", "decision_id": "decision-handler-action",
                "audit_event_id": "audit-handler-action", "policy_revision": "policy-demo",
                "config_revision": "cfg-demo"})
            action_id = "handler-action-001"
            target = {"workspace_id": "candidate-1"}
            arguments = {"path": "artifacts/handler-result.txt", "content": "handler action"}
            request = {
                "contract_id": "r3a.capability-invocation.v1", "contract_version": "1.1.0",
                "invocation_id": "88888888-8888-4888-8888-888888888888",
                "operation_id": "engineering.workspace.apply_patch",
                "operation_contract_version": "1.0.0",
                "caller": {"principal_id": "resident.grace", "resident_id": "resident.grace",
                           "service_id": None},
                "target": target, "input": arguments, "activity_id": ACTIVITY, "attempt_id": ATTEMPT,
                "correlation_id": CORRELATION, "work_order": {"work_order_id": action_id, "version": 1},
                "evidence_purpose": "Write one handler-authorized isolated artifact.",
                "idempotency_key": "handler-action:activity:handler-action-001", "deadline": None,
                "config_revision": "cfg-demo"}
            digest = hashlib.sha256(b"canonical-handler-action").hexdigest()
            item = {"contract_id": "r3a.activity-handler.work-item", "contract_version": "1.0.0",
                    "work_id": action_id, "record": {"workspace_id": "candidate-1",
                                                          "allowed_paths": ["artifacts/**"]},
                    "activity_id": ACTIVITY, "attempt_id": ATTEMPT,
                    "handler": {"module_id": "example.handler", "module_version": "1.0.0",
                                "artifact_digest": "a" * 64},
                    "action_id": action_id, "action_sha256": digest,
                    "operation_id": "engineering.workspace.apply_patch",
                    "operation_contract_version": "1.0.0", "target": target, "input": arguments}

            result = await instance.invoke_capability(request, _handler_work_item=item,
                                                      _handler_action=True)
            artifact = root / "artifacts/handler-result.txt"
            self.assertEqual("SUCCEEDED", result["outcome"])
            self.assertEqual("COMMITTED", result["effect_disposition"])
            self.assertEqual("handler action", artifact.read_text(encoding="utf-8"))
            context = instance._authorize_capability.await_args.kwargs["context"]
            self.assertEqual(action_id, context["work_order_id"])
            self.assertEqual(target, context["target"])

        with tempfile.TemporaryDirectory(prefix="r3a-handler-work-item-") as temporary:
            asyncio.run(scenario(Path(temporary)))



if __name__ == "__main__":
    unittest.main()
