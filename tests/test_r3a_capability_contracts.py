"""Canonical operation/invocation schema, registry and provider conformance tests."""
from __future__ import annotations

import json
import hashlib
import shutil
import tempfile
import unittest
from pathlib import Path

from r3a_runtime.capability_contracts import (
    CapabilityContractError, CapabilityRegistry, validate_invocation_request,
    validate_invocation_result, validate_operation, operation_from_manifest,
)
from r3a_runtime.config import load_settings


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
        provider = self.registered.load_provider()
        self.assertTrue(callable(provider.invoke))
        self.assertEqual("octominer_telemetry_read",
                         self.registered.resident_tool_projection()["name"])

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


if __name__ == "__main__":
    unittest.main()
