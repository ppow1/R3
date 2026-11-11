"""
R3 CONTROLLED SOURCE
File: tests/test_r3a_module_extensions.py
Component: TEST-R3A-MODULE-EXTENSION-CONTRACTS
File Revision: 1.0.5
Created: 2026-11-10T01:09:23Z
Created By: Codex GPT-6
Purpose: Permanently verify generic resident and durable activity-handler module declarations.
Execution Model: Pytest fixture tests; no live identity authority, database, or process launch.
Observability: Contract errors and registry-resolution outcomes are asserted directly.
Dependencies: r3a_runtime.module_extensions and capability contract validation.
Authority: AD-024; Modular Plugins #46; fixture acceptance only.
Changed: 2026-11-10T01:09:23Z | R3A-MODULAR-PLUGINS-46 | Codex GPT-6 | Add extensible executor and handler contract tests.
Changed: 2026-11-10T01:09:23Z | R3A-MODULAR-PLUGINS-46 | Codex GPT-6 | Verify authoritative binding resolution against active role declarations and pinned artifacts.
Changed: 2026-11-10T01:26:34Z | R3A-MODULAR-PLUGINS-46 | Codex GPT-6 | Verify bootstrap binding registration and fail-closed role/digest matching.
Changed: 2026-11-10T02:02:46Z | R3A-MODULAR-PLUGINS-46 | Codex GPT-6 | Test v1.0/v1.1 manifest schema selection and fail-closed unsupported versions.
Changed: 2026-11-10T15:24:00Z | R3A-MODULAR-EXECUTOR-ROLE | Codex GPT-6 | Verify primary-module role registration, pinned bindings, dual residents, and legacy manifest promotion.
Supersedes: None
Contracts: r3a.resident.module-binding.v1; r3a.resident.executor@1.0.0; r3a.activity-handler.v1.
Tests: python3 -m pytest -q tests/test_r3a_module_extensions.py
History/Predecessor: Prior revision at commit 76a9ad352e892f22cb0ee5a684a6cc358e5155b3, blob aa03f95ca2828d714538dabb65067bd691a8af31; immediate predecessor blob 4a49d5cf1fd7be2660306f8fac719998c2c1c57a at base c62bb28d026e1c1cad99c90583f0debae067f2a1.
"""
from __future__ import annotations

import copy
import hashlib
import json
import shutil
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from r3a_runtime.capability_contracts import CapabilityContractError, validate_module_manifest
from r3a_runtime.config import ConfigurationError, load_settings, sanitized_config
from r3a_runtime.module_extensions import (
    ModuleExtensionError,
    resolve_activity_handler,
    resolve_resident_binding,
    validate_activity_handler,
    validate_activity_handler_payload,
    validate_executor_configuration,
    validate_resident_binding,
    validate_resident_bindings,
)


def resident_binding(resident_id: str, module_id: str, *, version: str = "1.0.0", digest: str = "a" * 64,
                     association_id: str | None = None) -> dict:
    return {
        "contract_id": "r3a.resident.module-binding",
        "contract_version": "1.0.0",
        "resident_id": resident_id,
        "module_id": module_id,
        "module_version": version,
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


def bootstrap_config(tmp_path: Path, *, include_binding: bool = True) -> Path:
    root = Path(__file__).resolve().parents[1]
    plugin_source = root / "r3a_plugins/octominer_telemetry"
    plugin_root = tmp_path / "octominer"
    shutil.copytree(plugin_source, plugin_root)
    manifest_path = plugin_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    operation = manifest["operation"]
    manifest["module_manifest"] = {
        "contract_id": "r3a.module-manifest.v1", "contract_version": "1.1.0",
        "module_id": operation["provider"]["provider_id"],
        "module_version": operation["provider"]["provider_version"], "owner": "fixture-owner",
        "binding": {"contract_id": "r3a.capability-provider.v1", "protocol_major": 1,
                    "protocol_min_minor": 0, "protocol_max_minor": 0,
                    "entrypoint": operation["provider"]["entrypoint"]},
        "dependencies": [],
        "configuration": {"schema_ref": manifest["configuration_schema"]["schema_id"],
                           "configuration_ref": "capability_operations[].configuration"},
        "capability_refs": [operation["operation_id"]], "resource_refs": [],
        "state_namespace": "r3a.octominer-telemetry",
        "migration_contract": "r3a.stateless-provider.v1",
        "recovery_policy": "operation-contract.v1",
        "artifact": {"artifact_ref": manifest["artifact_ref"],
                     "artifact_sha256": manifest["artifact_sha256"]},
        "resident_executor": {"contract_id": "r3a.resident.executor",
                              "contract_version": "1.0.0",
                              "execution_contract_range": {
                                  "contract_id": "r3a.resident.execution", "major": 1,
                                  "min_minor": 0, "max_minor": 2}},
    }
    if include_binding:
        manifest["module_manifest"]["activity_handler"] = copy.deepcopy(HANDLER)
        manifest["module_manifest"]["capability_refs"].append("inventory.read")
    manifest_path.write_text(json.dumps(manifest))
    config_file = plugin_root / "config.example.json"
    source = root / "r3a_runtime/observer_module.py"
    data = tmp_path / "state"
    value = {
        "schema_version": 1, "instance_id": "r3a_extension_fixture",
        "paths": {"data_dir": str(data), "postgres_socket_dir": str(data / "pg"),
                  "control_socket": str(data / "control.sock"),
                  "diagnostics_socket": str(data / "diagnostics.sock"),
                  "module_socket": str(data / "module.sock"),
                  "machine_catalog_dir": str(root / "r3a_runtime/state_machines")},
        "postgres": {"database": "r3a_extension_fixture", "user": "r3a_runtime",
                     "socket_dir": str(data / "pg"), "port": 55432},
        "module": {"module_id": "foundation.observer", "version": "1.0.0",
                   "contract_id": "r3a.resident-module", "protocol_major": 1,
                   "protocol_minor": 0,
                   "capabilities": [operation["operation_id"], "inventory.read"],
                   "owner": "R3A", "entrypoint": "r3a_runtime.observer_module",
                   "source": str(source), "sha256": hashlib.sha256(source.read_bytes()).hexdigest()},
        "timing": {"observer_interval_seconds": 1, "scheduler_interval_seconds": 1,
                   "lease_seconds": 30, "heartbeat_interval_seconds": 5,
                   "heartbeat_stale_after_seconds": 15, "diagnostic_stale_after_seconds": 30,
                   "restart_initial_seconds": 1, "restart_max_seconds": 5,
                   "worker_concurrency": 2},
        "capability_operations": [{"manifest": str(manifest_path), "configuration": str(config_file)}],
    }
    if include_binding:
        value["resident_module_bindings"] = [resident_binding(
            "resident:alpha", "r3a.octominer-telemetry", version="2.0.0",
            digest=manifest["artifact_sha256"])]
    bootstrap = tmp_path / "bootstrap.json"
    bootstrap.write_text(json.dumps(value))
    return bootstrap


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
        "contract_id": "r3a.module-manifest.v1", "contract_version": "1.1.0",
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
    def test_settings_load_validates_binding_against_discovered_executor_and_handler(self, tmp_path):
        settings = load_settings(bootstrap_config(tmp_path))
        assert settings.resident_module_bindings[0]["resident_id"] == "resident:alpha"
        assert sanitized_config(settings)["resident_module_bindings"] == list(settings.resident_module_bindings)
        operation = settings.capability_registry.resolve("infrastructure.octominer.telemetry.read")
        assert operation.legacy_manifest["module_manifest"]["activity_handler"]["handler_id"] == "example.inventory-handler"

    def test_settings_loader_rejects_binding_to_missing_module_or_wrong_digest(self, tmp_path):
        path = bootstrap_config(tmp_path)
        value = json.loads(path.read_text())
        value["resident_module_bindings"][0]["module_id"] = "executor.not-registered"
        path.write_text(json.dumps(value))
        with pytest.raises(ConfigurationError, match="unregistered module"):
            load_settings(path)
        value["resident_module_bindings"][0]["module_id"] = "r3a.octominer-telemetry"
        value["resident_module_bindings"][0]["artifact_digest"] = "f" * 64
        path.write_text(json.dumps(value))
        with pytest.raises(ConfigurationError, match="does not match"):
            load_settings(path)

    def test_settings_loader_rejects_binding_without_declared_executor_role(self, tmp_path):
        path = bootstrap_config(tmp_path, include_binding=False)
        value = json.loads(path.read_text())
        manifest_path = Path(value["capability_operations"][0]["manifest"])
        manifest = json.loads(manifest_path.read_text())
        manifest["module_manifest"].pop("resident_executor")
        manifest_path.write_text(json.dumps(manifest))
        value["resident_module_bindings"] = [resident_binding(
            "resident:alpha", "r3a.octominer-telemetry", version="2.0.0",
            digest=manifest["artifact_sha256"])]
        path.write_text(json.dumps(value))
        with pytest.raises(ConfigurationError, match="unregistered module"):
            load_settings(path)

    def test_top_level_module_registers_generic_executor_role_for_two_bound_residents(self, tmp_path):
        path = bootstrap_config(tmp_path, include_binding=False)
        value = json.loads(path.read_text())
        role = {"contract_id": "r3a.resident.executor", "contract_version": "1.0.0",
                "execution_contract_range": {"contract_id": "r3a.resident.execution",
                                              "major": 1, "min_minor": 0, "max_minor": 2}}
        value["module"]["resident_executor"] = role
        value["resident_module_bindings"] = [
            resident_binding("resident:alpha", value["module"]["module_id"],
                             digest=value["module"]["sha256"]),
            resident_binding("resident:beta", value["module"]["module_id"],
                             digest=value["module"]["sha256"]),
        ]
        path.write_text(json.dumps(value))

        settings = load_settings(path)
        assert settings.module_resident_executor == role
        assert sanitized_config(settings)["module"]["resident_executor"] == role
        assert [item["resident_id"] for item in settings.resident_module_bindings] == [
            "resident:alpha", "resident:beta"]

        from r3a_runtime.cme import CME
        cme = object.__new__(CME)
        cme.settings = settings
        module_manifest = cme.manifest()
        assert module_manifest["manifest_contract"] == "r3a.module-manifest.v1@1.1.0"
        assert module_manifest["resident_executor"] == role
        assert module_manifest["artifact_digest"] == settings.module_digest
        registry = [{"module_id": settings.module_id, "module_version": settings.module_version,
                     "lifecycle_state": "ACTIVE", "manifest": module_manifest}]
        for binding in settings.resident_module_bindings:
            resolved = resolve_resident_binding(
                settings.resident_module_bindings, binding["resident_id"],
                binding["identity_association"], registry)
            assert resolved["module_id"] == settings.module_id
            assert resolved["artifact_digest"] == settings.module_digest
            assert "authorized" not in resolved

    @pytest.mark.parametrize("mutate", [
        lambda module: module["resident_executor"].update(contract_version="2.0.0"),
        lambda module: module["resident_executor"].update(unreviewed=True),
    ])
    def test_top_level_module_rejects_invalid_executor_contract(self, tmp_path, mutate):
        path = bootstrap_config(tmp_path, include_binding=False)
        value = json.loads(path.read_text())
        value["module"]["resident_executor"] = {
            "contract_id": "r3a.resident.executor", "contract_version": "1.0.0",
            "execution_contract_range": {"contract_id": "r3a.resident.execution",
                                          "major": 1, "min_minor": 0, "max_minor": 2}}
        mutate(value["module"])
        path.write_text(json.dumps(value))
        with pytest.raises(ConfigurationError, match="module.resident_executor is invalid"):
            load_settings(path)

    def test_top_level_module_binding_rejects_wrong_artifact_digest(self, tmp_path):
        path = bootstrap_config(tmp_path, include_binding=False)
        value = json.loads(path.read_text())
        value["module"]["resident_executor"] = {
            "contract_id": "r3a.resident.executor", "contract_version": "1.0.0",
            "execution_contract_range": {"contract_id": "r3a.resident.execution",
                                          "major": 1, "min_minor": 0, "max_minor": 2}}
        value["resident_module_bindings"] = [resident_binding(
            "resident:alpha", "foundation.observer", digest="f" * 64)]
        path.write_text(json.dumps(value))
        with pytest.raises(ConfigurationError, match="does not match"):
            load_settings(path)

    def test_legacy_top_level_module_projection_does_not_gain_executor_metadata(self, tmp_path):
        path = bootstrap_config(tmp_path, include_binding=False)
        settings = load_settings(path)
        assert settings.module_resident_executor is None
        from r3a_runtime.cme import CME
        cme = object.__new__(CME)
        cme.settings = settings
        manifest = cme.manifest()
        assert "manifest_contract" not in manifest
        assert "resident_executor" not in manifest

    def test_cme_promotes_only_a_compatible_legacy_primary_manifest(self, tmp_path):
        path = bootstrap_config(tmp_path, include_binding=False)
        value = json.loads(path.read_text())
        value["module"]["resident_executor"] = {
            "contract_id": "r3a.resident.executor", "contract_version": "1.0.0",
            "execution_contract_range": {"contract_id": "r3a.resident.execution",
                                          "major": 1, "min_minor": 0, "max_minor": 2}}
        path.write_text(json.dumps(value))
        settings = load_settings(path)
        from r3a_runtime.cme import CME
        cme = object.__new__(CME)
        cme.settings = settings
        cme.module_version = settings.module_version
        from types import SimpleNamespace
        cme.store = SimpleNamespace(
            rows=AsyncMock(), register_module=AsyncMock(), module_state=AsyncMock())
        prior = cme.manifest()
        prior.pop("manifest_contract")
        prior.pop("resident_executor")
        cme.store.rows.return_value = [{"manifest": prior, "lifecycle_state": "ACTIVE",
                                        "health": "healthy", "diagnostic": {"source": "existing"}}]
        asyncio.run(cme._ensure_registered_module())
        cme.store.register_module.assert_awaited_once_with(
            cme.manifest(), "ACTIVE", "healthy", {"source": "existing"})
        cme.store.module_state.assert_not_awaited()

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

    def test_module_manifest_v10_remains_valid_but_rejects_v11_role_fields(self):
        declaration = module_manifest()
        declaration["contract_version"] = "1.0.0"
        declaration.pop("resident_executor")
        operation = provider_operation()
        old_contract = validate_module_manifest(
            declaration, operation,
            {"artifact_sha256": "a" * 64,
             "configuration_schema": {"schema_id": "fixture.config.v1"}})
        assert old_contract["contract_version"] == "1.0.0"
        assert "resident_executor" not in old_contract

        declaration["resident_executor"] = module_manifest()["resident_executor"]
        with pytest.raises(CapabilityContractError, match="unknown fields"):
            validate_module_manifest(
                declaration, operation,
                {"artifact_sha256": "a" * 64,
                 "configuration_schema": {"schema_id": "fixture.config.v1"}})

    @pytest.mark.parametrize("contract_version", ["1.0.1", "1.3.0", "2.0.0", "not-semver"])
    def test_module_manifest_unknown_patch_minor_or_major_fails_closed(self, contract_version):
        declaration = module_manifest()
        declaration["contract_version"] = contract_version
        with pytest.raises(CapabilityContractError, match="contract version is unsupported"):
            validate_module_manifest(
                declaration, provider_operation(),
                {"artifact_sha256": "a" * 64,
                 "configuration_schema": {"schema_id": "fixture.config.v1"}})

    def test_module_manifest_v11_requires_exact_pinned_digest_and_role_contracts(self):
        declaration = module_manifest()
        operation = provider_operation()
        with pytest.raises(CapabilityContractError, match="artifact digest"):
            validate_module_manifest(declaration, operation,
                                     {"artifact_sha256": "b" * 64,
                                      "configuration_schema": {"schema_id": "fixture.config.v1"}})
        declaration["resident_executor"]["contract_version"] = "2.0.0"
        with pytest.raises(CapabilityContractError, match="contract_version"):
            validate_module_manifest(declaration, operation,
                                     {"artifact_sha256": "a" * 64,
                                      "configuration_schema": {"schema_id": "fixture.config.v1"}})

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
        assert stored["manifest_contract"] == "r3a.module-manifest.v1@1.1.0"
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

    def test_request_result_progress_and_checkpoint_are_checked_by_declared_schemas(self):
        assert validate_activity_handler_payload(HANDLER, "request", {"scope": "unit"}) == {"scope": "unit"}
        assert validate_activity_handler_payload(HANDLER, "result", {"changed": 2}) == {"changed": 2}
        assert validate_activity_handler_payload(HANDLER, "progress", {"phase": "scan"}) == {"phase": "scan"}
        assert validate_activity_handler_payload(HANDLER, "checkpoint", {"cursor": 3}) == {"cursor": 3}
        for kind, invalid in (("request", {}), ("result", {"changed": "two"}),
                              ("progress", {"phase": 3}), ("checkpoint", {"cursor": True})):
            with pytest.raises(ModuleExtensionError, match="payload is invalid"):
                validate_activity_handler_payload(HANDLER, kind, invalid)

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
