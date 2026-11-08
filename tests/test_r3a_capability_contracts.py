"""Canonical operation/invocation schema, registry and provider conformance tests."""
from __future__ import annotations

import json
import hashlib
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from r3a_runtime.capability_contracts import (
    CapabilityContractError, CapabilityProviderResult, CapabilityRegistry, validate_invocation_request,
    validate_invocation_result, validate_operation, operation_from_manifest, validate_json,
    normalize_provider_result,
)
from r3a_runtime.config import ConfigurationError, _satisfies_version_range, load_settings


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/capabilities"


def fixture(name: str):
    return json.loads((FIXTURES / name).read_text())


class CapabilityContractTests(unittest.TestCase):
    def setUp(self):
        manifest = json.loads((ROOT / "r3a_plugins/octominer_telemetry/manifest.json").read_text())
        self.manifest = manifest
        self.descriptor = validate_operation(fixture("octominer.operation.v1.json"))
        self.assertEqual(self.descriptor, manifest["operation"])
        self.registry = CapabilityRegistry()
        self.registered = self.registry.register(self.descriptor, {"host_id": "fixture"},
                                                 legacy_manifest=manifest)

    def test_canonical_operation_and_invocation_fixture_pair(self):
        request = validate_invocation_request(fixture("octominer.invocation.request.v1.json"),
                                              self.descriptor)
        result = validate_invocation_result(fixture("octominer.invocation.result.v1.json"),
                                            self.descriptor)
        self.assertEqual(self.descriptor["operation_id"], request["operation_id"])
        self.assertEqual("SUCCEEDED", result["outcome"])

    def test_registry_discovers_without_grant_and_resolves_provider_interface(self):
        discovered = self.registry.discover()
        self.assertEqual(1, len(discovered))
        self.assertEqual("registered", discovered[0]["registry_observation"]["state"])
        self.assertNotIn("authorized", discovered[0]["registry_observation"])
        self.assertEqual("OctoMiner GPU Telemetry", discovered[0]["presentation"]["name"])
        self.assertTrue(discovered[0]["presentation"]["description_registered"])
        self.assertEqual("not_probed", discovered[0]["registry_observation"]["provider_availability"])
        discovered_descriptor = discovered[0]["descriptor"]
        self.assertEqual(self.descriptor["input_schema"], discovered_descriptor["input_schema"])
        self.assertEqual(self.descriptor["output_schema"], discovered_descriptor["output_schema"])
        self.assertEqual("read", discovered_descriptor["effect_class"])
        self.assertEqual(self.descriptor["required_grants"], discovered_descriptor["required_grants"])
        self.assertEqual(self.descriptor["target_scope_schema"], discovered_descriptor["target_scope_schema"])
        self.assertEqual(self.descriptor["operation_id"], discovered_descriptor["operation_id"])
        self.assertEqual("not_probed", discovered[0]["registry_observation"]["provider_availability"])
        provider = self.registered.load_provider()
        self.assertTrue(callable(provider.invoke))
        self.assertEqual(self.descriptor["operation_id"], self.registered.descriptor["operation_id"])
        self.assertEqual("OctoMiner GPU Telemetry",
                         self.registered.resident_tool_projection()["name"])

    def test_octominer_resolves_and_runs_through_common_provider_and_result_contract(self):
        provider = self.registered.load_provider()
        source_output = [{"source_id": "gpu.telemetry.fixture",
                          "content": {"available": False, "error": "fixture_only"},
                          "sha256": "a" * 64}]
        with patch("r3a_plugins.octominer_telemetry.plugin.read_telemetry",
                   return_value=source_output):
            output = provider.invoke({}, context={"invocation_id": "fixture-01"})
        validate_json(output, self.descriptor["output_schema"], path="$.output")
        validate_json(output, self.descriptor["evidence"]["schema"], path="$.evidence")
        result = fixture("octominer.invocation.result.v1.json")
        result["output"] = output
        result["evidence"] = output
        self.assertEqual("SUCCEEDED", validate_invocation_result(result, self.descriptor)["outcome"])

    def test_provider_resolution_rejects_artifact_digest_mismatch(self):
        invalid = json.loads(json.dumps(self.descriptor))
        invalid["provider"]["artifact_sha256"] = "0" * 64
        registry = CapabilityRegistry()
        registered = registry.register(invalid, {"host_id": "fixture"})
        with self.assertRaisesRegex(CapabilityContractError, "source does not match"):
            registered.load_provider()

    def test_provider_can_return_distinct_typed_output_and_evidence(self):
        descriptor = json.loads(json.dumps(self.descriptor))
        descriptor["output_schema"] = {"type": "object", "required": ["count"],
                                        "properties": {"count": {"type": "integer"}},
                                        "additionalProperties": False}
        descriptor["evidence"]["schema"] = {"type": "object", "required": ["source_id", "sha256"],
                                              "properties": {"source_id": {"type": "string"},
                                                             "sha256": {"type": "string"}},
                                              "additionalProperties": False}
        result = normalize_provider_result(
            CapabilityProviderResult({"count": 3}, {"source_id": "fixture", "sha256": "a" * 64}),
            descriptor)
        self.assertEqual({"count": 3}, result[0])
        self.assertEqual({"source_id": "fixture", "sha256": "a" * 64}, result[1])
        with self.assertRaisesRegex(CapabilityContractError, r"\$\.evidence"):
            normalize_provider_result({"count": 3}, descriptor)

    def test_contract_validation_rejects_unknown_fields_wrong_version_and_scope(self):
        request = fixture("octominer.invocation.request.v1.json")
        request["authorization_decision"] = "caller-must-not-assert-this"
        with self.assertRaises(CapabilityContractError):
            validate_invocation_request(request, self.descriptor)
        request = fixture("octominer.invocation.request.v1.json")
        request["caller"]["resident_id"] = "resident.other"
        with self.assertRaises(CapabilityContractError):
            validate_invocation_request(request, self.descriptor)
        request = fixture("octominer.invocation.request.v1.json")
        request["operation_contract_version"] = "2.0.0"
        with self.assertRaises(CapabilityContractError):
            validate_invocation_request(request, self.descriptor)
        request = fixture("octominer.invocation.request.v1.json")
        request["target"] = {"unlisted_target": "source"}
        with self.assertRaises(CapabilityContractError):
            validate_invocation_request(request, self.descriptor)

    def test_duplicate_registration_and_unsupported_effect_fail_closed(self):
        with self.assertRaises(CapabilityContractError):
            self.registry.register(self.descriptor, {})
        invalid = dict(self.descriptor)
        invalid["effect_class"] = "read_write"
        with self.assertRaises(CapabilityContractError):
            validate_operation(invalid)

    def test_one_registry_accepts_all_effect_classes_with_write_recovery_requirements(self):
        registry = CapabilityRegistry()
        for effect in ("read", "isolated_write", "external_write"):
            descriptor = json.loads(json.dumps(self.descriptor))
            descriptor["operation_id"] = f"fixture.operation.{effect}"
            descriptor["effect_class"] = effect
            if effect != "read":
                descriptor["recovery"]["idempotency_required"] = True
            registry.register(descriptor, {})
        self.assertEqual({"read", "isolated_write", "external_write"},
                         {item["descriptor"]["effect_class"] for item in registry.discover()})
        write = registry.resolve("fixture.operation.isolated_write").descriptor
        request = fixture("octominer.invocation.request.v1.json")
        request["operation_id"] = write["operation_id"]
        request["idempotency_key"] = None
        with self.assertRaisesRegex(CapabilityContractError, "idempotency"):
            validate_invocation_request(request, write)

    def test_result_requires_cme_authorization_evidence(self):
        result = fixture("octominer.invocation.result.v1.json")
        result["authorization"] = None
        with self.assertRaises(CapabilityContractError):
            validate_invocation_result(result, self.descriptor)

    def test_result_evidence_schema_and_error_outcomes_are_conformance_checked(self):
        descriptor = json.loads(json.dumps(self.descriptor))
        descriptor["evidence"]["schema"] = {
            "type": "array", "items": {"type": "object", "required": ["source_id", "sha256"],
                                           "properties": {"source_id": {"type": "string"},
                                                          "sha256": {"type": "string"}},
                                           "additionalProperties": True}}
        result = fixture("octominer.invocation.result.v1.json")
        self.assertEqual("SUCCEEDED", validate_invocation_result(result, descriptor)["outcome"])
        malformed = json.loads(json.dumps(result))
        malformed["evidence"][0].pop("sha256")
        with self.assertRaisesRegex(CapabilityContractError, "missing required fields"):
            validate_invocation_result(malformed, descriptor)

        failed = json.loads(json.dumps(result))
        failed.update({"outcome": "FAILED", "effect_disposition": "NOT_STARTED",
                       "output": None, "error": {"type": "TimeoutError", "message": "fixture timeout"},
                       "retryable": True})
        self.assertEqual("FAILED", validate_invocation_result(failed, descriptor)["outcome"])
        failed["output"] = []
        with self.assertRaisesRegex(CapabilityContractError, "forbids output"):
            validate_invocation_result(failed, descriptor)

        wrong_provider = json.loads(json.dumps(result))
        wrong_provider["provider"]["artifact_sha256"] = "0" * 64
        with self.assertRaisesRegex(CapabilityContractError, "provider provenance"):
            validate_invocation_result(wrong_provider, descriptor)

    def test_canonical_manifest_needs_no_read_only_family_fields(self):
        canonical = {"schema_version": 1, "plugin_id": self.manifest["plugin_id"],
                    "plugin_version": self.manifest["plugin_version"],
                    "operation": self.descriptor, "provider": self.descriptor["provider"]}
        parsed = operation_from_manifest(canonical)
        self.assertEqual("read", parsed["effect_class"])
        write_op = json.loads(json.dumps(parsed))
        write_op["effect_class"] = "isolated_write"
        write_op["recovery"]["idempotency_required"] = True
        canonical["operation"] = write_op
        canonical["provider"] = write_op["provider"]
        self.assertEqual("isolated_write", operation_from_manifest(canonical)["effect_class"])

    def test_versioned_module_manifest_matches_provider_artifact_and_capability(self):
        manifest_path = ROOT / "r3a_runtime/providers/isolated_workspace.manifest.json"
        manifest = json.loads(manifest_path.read_text())
        operation = operation_from_manifest(manifest)
        module = manifest["module_manifest"]
        self.assertEqual(operation["provider"]["provider_id"], module["module_id"])
        invalid = json.loads(json.dumps(manifest))
        invalid["module_manifest"]["capability_refs"] = ["unregistered.operation"]
        with self.assertRaisesRegex(CapabilityContractError, "does not reference its operation"):
            operation_from_manifest(invalid)

    def test_module_dependency_semver_ranges_fail_closed(self):
        self.assertTrue(_satisfies_version_range("1.4.0", "^1.0.0"))
        self.assertFalse(_satisfies_version_range("2.0.0", "^1.0.0"))
        self.assertTrue(_satisfies_version_range("1.2.9", "~1.2.3"))
        self.assertFalse(_satisfies_version_range("1.3.0", "~1.2.3"))
        self.assertTrue(_satisfies_version_range("1.5.0", ">=1.2.0,<2.0.0"))
        with self.assertRaisesRegex(ValueError, "unsupported module dependency"):
            _satisfies_version_range("1.0.0", "latest")

    def test_legacy_manifest_adapter_rejects_missing_or_false_read_only(self):
        legacy = {"contract_id": "r3a.resident-capability-tool", "contract_version": "1.0.0",
                  "capability_id": self.descriptor["operation_id"], "plugin_id": "legacy.telemetry",
                  "plugin_version": "1.0.0", "read_only": True,
                  "entrypoint": "r3a_plugins.octominer_telemetry.plugin:read_telemetry",
                  "artifact_sha256": self.descriptor["provider"]["artifact_sha256"],
                  "tool": {"name": "octominer_telemetry_read", "description": "Telemetry",
                           "arguments_schema": {"type": "object", "properties": {}, "additionalProperties": False}}}
        self.assertEqual("read", operation_from_manifest(legacy)["effect_class"])
        legacy["read_only"] = False
        with self.assertRaises(CapabilityContractError):
            operation_from_manifest(legacy)
        legacy.pop("read_only")
        with self.assertRaises(CapabilityContractError):
            operation_from_manifest(legacy)

    def test_config_loader_builds_registry_from_canonical_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_dir = root / "data"
            data_dir.mkdir()
            plugin_config_path = root / "telemetry-config.json"
            plugin_config_path.write_text((ROOT / "r3a_plugins/octominer_telemetry/config.example.json").read_text())
            manifest = dict(self.manifest)
            manifest.pop("operation", None)
            manifest["operation"] = self.descriptor
            for legacy_key in ("contract_id", "contract_version", "capability_id", "tool", "entrypoint", "read_only"):
                manifest.pop(legacy_key, None)
            plugin_copy = root / "octominer"
            plugin_copy.mkdir()
            for artifact_ref in [manifest["artifact_ref"]] + [x["artifact_ref"] for x in manifest["supporting_artifacts"]]:
                shutil.copy2(ROOT / "r3a_plugins/octominer_telemetry" / artifact_ref, plugin_copy / artifact_ref)
            manifest_path = plugin_copy / "canonical-manifest.json"
            manifest_path.write_text(json.dumps(manifest))
            source_path = ROOT / "r3a_runtime/observer_module.py"
            operation_id = self.descriptor["operation_id"]
            config = {
                "schema_version": 1, "instance_id": "r3a_fixture",
                "paths": {"data_dir": str(data_dir), "postgres_socket_dir": str(data_dir / "pg"),
                          "control_socket": str(data_dir / "control.sock"),
                          "diagnostics_socket": str(data_dir / "diagnostics.sock"),
                          "module_socket": str(data_dir / "module.sock"),
                          "machine_catalog_dir": str(root / "catalog")},
                "postgres": {"database": "r3a_fixture", "user": "r3a_runtime",
                             "socket_dir": str(data_dir / "pg"), "port": 55432},
                "module": {"module_id": "foundation.observer", "version": "1.0.0",
                           "contract_id": "r3a.resident-module", "protocol_major": 1,
                           "protocol_minor": 0, "capabilities": [operation_id], "owner": "R3A",
                           "entrypoint": "r3a_runtime.observer_module", "source": str(source_path),
                           "sha256": hashlib.sha256(source_path.read_bytes()).hexdigest()},
                "timing": {"observer_interval_seconds": 1, "scheduler_interval_seconds": 1,
                           "lease_seconds": 30, "heartbeat_interval_seconds": 5,
                           "heartbeat_stale_after_seconds": 15, "diagnostic_stale_after_seconds": 30,
                           "restart_initial_seconds": 1, "restart_max_seconds": 5,
                           "worker_concurrency": 1},
                "capability_operations": [{"manifest": str(manifest_path),
                                           "configuration": str(plugin_config_path)}],
            }
            bootstrap = root / "bootstrap.json"
            bootstrap.write_text(json.dumps(config))
            settings = load_settings(bootstrap)
            self.assertEqual((operation_id,), tuple(item["descriptor"]["operation_id"]
                                                     for item in settings.capability_registry.discover()))
            self.assertEqual("read", settings.capability_registry.resolve(operation_id).descriptor["effect_class"])
            manifest["module_manifest"] = {
                "contract_id": "r3a.module-manifest.v1", "contract_version": "1.0.0",
                "module_id": manifest["provider"]["provider_id"],
                "module_version": manifest["provider"]["provider_version"],
                "owner": "fixture", "binding": {"contract_id": "r3a.capability-provider.v1",
                    "protocol_major": 1, "protocol_min_minor": 0, "protocol_max_minor": 0,
                    "entrypoint": manifest["provider"]["entrypoint"]},
                "dependencies": [{"module_id": "r3a.missing.acceptance-dependency",
                                  "version_range": "^1.0.0"}],
                "configuration": {"schema_ref": manifest["configuration_schema"]["schema_id"],
                                   "configuration_ref": "configuration.json"},
                "capability_refs": [operation_id], "resource_refs": [],
                "state_namespace": manifest["provider"]["provider_id"],
                "migration_contract": "none.v1", "recovery_policy": "idempotent.v1",
                "artifact": {"artifact_ref": manifest["artifact_ref"],
                             "artifact_sha256": manifest["artifact_sha256"]}}
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ConfigurationError, "has no configured module provider"):
                load_settings(bootstrap)


if __name__ == "__main__":
    unittest.main()
