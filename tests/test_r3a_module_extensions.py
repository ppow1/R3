"""
R3 CONTROLLED SOURCE
File: tests/test_r3a_module_extensions.py
Component: TEST-R3A-MODULE-EXTENSION-CONTRACTS
File Revision: 1.0.1
Created: 2026-11-10T01:09:23Z
Created By: Codex GPT-6
Purpose: Permanently verify generic resident and durable activity-handler module declarations.
Execution Model: Pytest fixture tests; no live identity authority, database, or process launch.
Observability: Contract errors and registry-resolution outcomes are asserted directly.
Dependencies: r3a_runtime.module_extensions and capability contract validation.
Authority: AD-024; Modular Plugins #46; fixture acceptance only.
Changed: 2026-11-10T01:09:23Z | R3A-MODULAR-PLUGINS-46 | Codex GPT-6 | Add extensible executor and handler contract tests.
Changed: 2026-11-10T01:09:23Z | R3A-MODULAR-PLUGINS-46 | Codex GPT-6 | Verify authoritative binding resolution against active role declarations and pinned artifacts.
Supersedes: None
Contracts: r3a.resident.module-binding.v1; r3a.resident.executor@1.0.0; r3a.activity-handler.v1.
Tests: python3 -m pytest -q tests/test_r3a_module_extensions.py
History/Predecessor: Prior revision at commit 67aa6c181e237b97acee975b297e44e7e14aa440, blob 01b2744f1e57284807e5ce48d756d9639f6705b3.
"""
from __future__ import annotations

import copy
import hashlib
import json

import pytest

from r3a_runtime.capability_contracts import CapabilityContractError, validate_module_manifest
from r3a_runtime.module_extensions import (
    ModuleExtensionError,
    resolve_activity_handler,
    resolve_resident_binding,
    validate_activity_handler,
    validate_executor_configuration,
    validate_resident_binding,
    validate_resident_bindings,
)


def resident_binding(resident_id: str, module_id: str, *, digest: str = "a" * 64,
                     association_id: str | None = None) -> dict:
    return {
        "contract_id": "r3a.resident.module-binding",
        "contract_version": "1.0.0",
        "resident_id": resident_id,
        "module_id": module_id,
        "module_version": "1.0.0",
        "artifact_digest": digest,
        "execution_contract_range": {"contract_id": "r3a.resident.execution", "major": 1,
                                     "min_minor": 0, "max_minor": 2},
        "binding_revision": "binding-r3",
        "configuration_ref": "executor.json",
        "configuration_revision": "b" * 64,
        "identity_association": {"authority": "hr-directory", "record_id": association_id or resident_id,
                                 "record_revision": "directory-r7"},
    }


HANDLER = {
    "contract_id": "r3a.activity-handler",
    "contract_version": "1.0.0",
    "handler_id": "example.inventory-handler",
    "handler_version": "1.0.0",
    "activity_types": ["example.inventory.reconcile"],
    "activity_contract_range": {"contract_id": "r3a.activity-intake", "major": 1,
                                 "min_minor": 0, "max_minor": 0},
    "handler_contract_range": {"contract_id": "r3a.activity-handler", "major": 1,
                                "min_minor": 0, "max_minor": 0},
    "request_schema": {"type": "object", "properties": {"scope": {"type": "string"}},
                       "required": ["scope"], "additionalProperties": False},
    "result_schema": {"type": "object", "properties": {"changed": {"type": "integer"}},
                      "required": ["changed"], "additionalProperties": False},
    "progress_schema": {"type": "object", "properties": {"phase": {"type": "string"}},
                         "required": ["phase"], "additionalProperties": False},
    "checkpoint_schema": {"type": "object", "properties": {"cursor": {"type": "integer"}},
                           "required": ["cursor"], "additionalProperties": False},
    "progress_semantics": "Monotonic phase and completed-item count; CME timestamps each observation.",
    "checkpoint_semantics": "A checkpoint is resumable from the next uncommitted item.",
    "required_capabilities": ["inventory.read"],
    "resource_constraints": {"cpu_millis": 500, "memory_bytes": 268435456, "max_concurrency": 2},
    "state_namespace": "example.inventory",
    "migration_contract": "example.inventory-migration.v1",
    "recovery": {"mode": "checkpointed", "idempotency_contract": "stable-input-key.v1",
                 "checkpoint_contract": "example.inventory-checkpoint.v1"},
}


def registered_module(module_id: str, *, version: str = "1.0.0", digest: str = "c" * 64,
                      lifecycle: str = "ACTIVE", handler: dict | None = None,
                      executor: dict | None = None) -> dict:
    manifest = {"module_id": module_id, "module_version": version, "artifact_digest": digest}
    if handler is not None:
        manifest["activity_handler"] = handler
    if executor is not None:
        manifest["resident_executor"] = executor
    return {"module_id": module_id, "module_version": version,
            "lifecycle_state": lifecycle, "manifest": manifest}


def provider_operation(module_id="executor.orbit", version="1.0.0", digest="a" * 64):
    return {"operation_id": "executor.invoke", "provider": {
        "provider_id": module_id, "provider_version": version,
        "entrypoint": "fixture.executor:create", "artifact_sha256": digest}}


def module_manifest(*, module_id="executor.orbit", version="1.0.0", digest="a" * 64):
    return {
        "contract_id": "r3a.module-manifest.v1", "contract_version": "1.0.0",
        "module_id": module_id, "module_version": version, "owner": "fixture-owner",
        "binding": {"contract_id": "r3a.capability-provider.v1", "protocol_major": 1,
                    "protocol_min_minor": 0, "protocol_max_minor": 0,
                    "entrypoint": "fixture.executor:create"},
        "dependencies": [],
        "configuration": {"schema_ref": "fixture.config.v1", "configuration_ref": "executor.json"},
        "capability_refs": ["executor.invoke"], "resource_refs": [],
        "state_namespace": "executor.orbit", "migration_contract": "fixture.state.v1",
        "recovery_policy": "replay-per-operation-contract",
        "artifact": {"artifact_ref": "executor.py", "artifact_sha256": digest},
        "resident_executor": {"contract_id": "r3a.resident.executor", "contract_version": "1.0.0",
                              "execution_contract_range": {"contract_id": "r3a.resident.execution",
                                                           "major": 1, "min_minor": 0,
                                                           "max_minor": 2}},
    }


class TestResidentBinding:
    def test_two_independent_unlisted_residents_bind_generic_executor_metadata(self):
        declaration = module_manifest()
        operation = provider_operation()
        approved = validate_module_manifest(
            declaration, operation,
            {"artifact_sha256": "a" * 64,
             "configuration_schema": {"schema_id": "fixture.config.v1"}})
        assert approved["resident_executor"]["contract_id"] == "r3a.resident.executor"
        bindings = validate_resident_bindings([
            resident_binding("resident:alpha", "executor.orbit"),
            resident_binding("resident:beta", "executor.orbit", digest="d" * 64),
        ])
        assert [item["resident_id"] for item in bindings] == ["resident:alpha", "resident:beta"]
        assert all("grant" not in item and "authorized" not in item for item in bindings)

    def test_provider_registry_manifest_retains_generic_executor_and_handler_roles(self):
        from types import SimpleNamespace
        from r3a_runtime.provider_runtime import ProviderProcessManager

        declaration = module_manifest()
        declaration["capability_refs"].append("inventory.read")
        declaration["activity_handler"] = copy.deepcopy(HANDLER)
        declared = validate_module_manifest(
            declaration, provider_operation(),
            {"artifact_sha256": "a" * 64,
             "configuration_schema": {"schema_id": "fixture.config.v1"}})
        operation = SimpleNamespace(
            descriptor={"provider": {"provider_id": "executor.orbit",
                                      "provider_version": "1.0.0",
                                      "entrypoint": "fixture.executor:create",
                                      "artifact_sha256": "a" * 64}},
            legacy_manifest={"module_manifest": declared,
                             "configuration_schema": {"schema_id": "fixture.config.v1"}})
        runtime = object.__new__(ProviderProcessManager)
        stored = runtime._manifest(operation)
        assert stored["resident_executor"] == declared["resident_executor"]
        assert stored["activity_handler"] == declared["activity_handler"]

    @pytest.mark.parametrize("mutate", [
        lambda item: item["identity_association"].update(record_id="resident:other"),
        lambda item: item.update(artifact_digest="not-a-digest"),
        lambda item: item["execution_contract_range"].update(major=2),
        lambda item: item.update(configuration_revision="x" * 64),
    ])
    def test_invalid_authority_reference_digest_contract_and_configuration_revision_rejected(self, mutate):
        value = resident_binding("resident:alpha", "executor.orbit")
        mutate(value)
        with pytest.raises(ModuleExtensionError):
            validate_resident_binding(value)

    def test_duplicate_effective_binding_rejected(self):
        value = resident_binding("resident:alpha", "executor.orbit")
        with pytest.raises(ModuleExtensionError, match="duplicate"):
            validate_resident_bindings([value, copy.deepcopy(value)])

    def test_binding_resolution_requires_authoritative_association_active_module_and_pinned_role(self):
        binding = resident_binding("resident:alpha", "executor.orbit")
        executor = module_manifest()["resident_executor"]
        active = registered_module("executor.orbit", digest="a" * 64, executor=executor)
        resolved = resolve_resident_binding([binding], "resident:alpha",
                                            binding["identity_association"], [active])
        assert resolved["artifact_digest"] == "a" * 64
        assert "authorized" not in resolved
        for association, modules in (
                ({**binding["identity_association"], "record_revision": "old"}, [active]),
                (binding["identity_association"], [{**active, "lifecycle_state": "STOPPED"}]),
                (binding["identity_association"], [registered_module(
                    "executor.orbit", digest="c" * 64, executor=executor)]),
                (binding["identity_association"], [registered_module(
                    "executor.orbit", digest="a" * 64)])):
            with pytest.raises(ModuleExtensionError):
                resolve_resident_binding([binding], "resident:alpha", association, modules)

    def test_configuration_digest_and_schema_are_enforced(self, tmp_path):
        config = {"feature": "independent-executor"}
        raw = json.dumps(config, sort_keys=True).encode()
        (tmp_path / "executor.json").write_bytes(raw)
        binding = resident_binding("resident:alpha", "executor.orbit")
        binding["configuration_revision"] = hashlib.sha256(raw).hexdigest()
        assert validate_executor_configuration(
            binding, configuration_root=tmp_path,
            schema={"type": "object", "properties": {"feature": {"type": "string"}},
                    "required": ["feature"], "additionalProperties": False}) == config
        with pytest.raises(ModuleExtensionError, match="digest"):
            validate_executor_configuration(
                resident_binding("resident:alpha", "executor.orbit"), configuration_root=tmp_path,
                schema={"type": "object"})
        binding = resident_binding("resident:alpha", "executor.orbit")
        binding["configuration_revision"] = hashlib.sha256(raw).hexdigest()
        with pytest.raises(ModuleExtensionError, match="executor configuration is invalid"):
            validate_executor_configuration(
                binding, configuration_root=tmp_path,
                schema={"type": "object", "properties": {"feature": {"type": "integer"}},
                        "required": ["feature"], "additionalProperties": False})


class TestActivityHandler:
    def test_non_grace_handler_declaration_and_registry_discovery(self):
        checked = validate_activity_handler(HANDLER)
        resolved = resolve_activity_handler(
            [registered_module("example.inventory", handler=checked)],
            "example.inventory.reconcile")
        assert resolved["handler"]["handler_id"] == "example.inventory-handler"
        assert resolved["artifact_digest"] == "c" * 64
        assert "authorization" not in resolved

    def test_missing_ambiguous_inactive_and_incompatible_handler_fail_closed(self):
        active = registered_module("example.inventory", handler=HANDLER)
        with pytest.raises(ModuleExtensionError, match="missing, ambiguous"):
            resolve_activity_handler([], "example.inventory.reconcile")
        with pytest.raises(ModuleExtensionError, match="missing, ambiguous"):
            resolve_activity_handler([active, active], "example.inventory.reconcile")
        with pytest.raises(ModuleExtensionError, match="missing, ambiguous"):
            resolve_activity_handler([{**active, "lifecycle_state": "STOPPED"}],
                                     "example.inventory.reconcile")
        with pytest.raises(ModuleExtensionError, match="missing, ambiguous"):
            resolve_activity_handler([active], "example.inventory.reconcile", activity_contract_minor=2)

    def test_invalid_resource_schema_and_recovery_contracts_rejected(self):
        for field, value in (("resource_constraints", {"cpu_millis": 0, "memory_bytes": 5,
                                                         "max_concurrency": 1}),
                             ("request_schema", {"type": "unsupported"}),
                             ("recovery", {"mode": "checkpointed", "idempotency_contract": "x",
                                           "checkpoint_contract": ""})):
            bad = copy.deepcopy(HANDLER)
            bad[field] = value
            with pytest.raises(ModuleExtensionError):
                validate_activity_handler(bad)

    def test_handler_schema_rejects_unsupported_schema_features(self):
        bad = copy.deepcopy(HANDLER)
        bad["result_schema"]["format"] = "date-time"
        with pytest.raises(ModuleExtensionError, match="unsupported keywords"):
            validate_activity_handler(bad)

    def test_required_capabilities_must_be_module_declared(self):
        declaration = module_manifest()
        declaration["activity_handler"] = copy.deepcopy(HANDLER)
        with pytest.raises(CapabilityContractError, match="requires a capability"):
            validate_module_manifest(
                declaration, provider_operation(),
                {"artifact_sha256": "a" * 64,
                 "configuration_schema": {"schema_id": "fixture.config.v1"}})
