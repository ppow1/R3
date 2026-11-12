"""Generic manifest registration, resource discovery and disable conformance."""
from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from r3a_runtime.config import load_settings
from r3a_runtime.capability_contracts import CapabilityContractError
from r3a_runtime.diagnostics import DiagnosticProjection
from r3a_runtime.grace_module import resident_action_schema


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "r3a_plugins/engineering_workspace/manifest.json"
PROVIDER = ROOT / "r3a_plugins/engineering_workspace/provider.py"
CONFIG_EXAMPLE = ROOT / "r3a_plugins/engineering_workspace/config.example.json"
OPERATION_ID = "engineering.workspace.apply_patch"


def _write_bootstrap(root: Path, manifest: Path, provider_config: Path) -> Path:
    data = root / "data"
    data.mkdir(exist_ok=True)
    source = ROOT / "r3a_runtime/observer_module.py"
    value = {
        "schema_version": 1, "instance_id": "r3a_manifest_test",
        "paths": {"data_dir": str(data), "postgres_socket_dir": str(data / "pg"),
                  "control_socket": str(data / "control.sock"),
                  "diagnostics_socket": str(data / "diagnostics.sock"),
                  "module_socket": str(data / "module.sock"),
                  "machine_catalog_dir": str(root / "machines")},
        "postgres": {"database": "r3a_manifest_test", "user": "r3a_runtime",
                     "socket_dir": str(data / "pg"), "port": 55432},
        "module": {"module_id": "foundation.observer", "version": "1.0.0",
                   "contract_id": "r3a.module.v1", "protocol_major": 1,
                   "protocol_minor": 0, "capabilities": [OPERATION_ID],
                   "owner": "R3A-test", "entrypoint": "r3a_runtime.observer_module",
                   "source": str(source), "sha256": hashlib.sha256(source.read_bytes()).hexdigest()},
        "timing": {"observer_interval_seconds": 1, "scheduler_interval_seconds": 1,
                   "lease_seconds": 30, "heartbeat_interval_seconds": 5,
                   "heartbeat_stale_after_seconds": 15, "diagnostic_stale_after_seconds": 30,
                   "restart_initial_seconds": 1, "restart_max_seconds": 5,
                   "worker_concurrency": 1},
        "capability_operations": [{"manifest": str(manifest),
                                   "configuration": str(provider_config)}],
    }
    path = root / "bootstrap.json"
    path.write_text(json.dumps(value))
    return path


class ResourceSnapshotStore:
    def __init__(self, resource):
        self.resource = resource

    async def snapshot(self, *, include_events=True):
        return {"configuration": {"revision_id": "config-fixture"},
                "processes": [], "modules": [], "resources": [self.resource],
                "activities": [], "events": [], "state_machines": []}

    async def rows(self, query, params=()):
        if "latest_event_id" in query:
            return []
        return []


class ModularRegistrationConformanceTests(unittest.TestCase):
    def test_engineering_manifest_registers_existing_provider_and_discovers_target_resource(self):
        with tempfile.TemporaryDirectory(prefix="r3a-engineering-registration-") as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            workspace.mkdir()
            config_path = root / "engineering-config.json"
            config_path.write_text(json.dumps({"workspace_root": str(workspace)}))
            bootstrap = _write_bootstrap(root, MANIFEST, config_path)
            settings = load_settings(bootstrap)
            registry = settings.capability_registry
            discovered = registry.discover()
            self.assertEqual([OPERATION_ID], [item["descriptor"]["operation_id"] for item in discovered])
            self.assertEqual("Engineering Workspace Apply Patch", discovered[0]["presentation"]["name"])
            # Grace consumes the registry's discovered descriptor and presents its ID as a
            # constrained proposal option; there is no hardcoded operation ID in its selector.
            schema = resident_action_schema([], [item["descriptor"] for item in discovered])
            self.assertEqual([discovered[0]["descriptor"]["operation_id"]],
                             schema["properties"]["proposal"]["properties"]["operation_id"]["enum"])
            operation = registry.resolve(OPERATION_ID)
            self.assertEqual("isolated_write", operation.descriptor["effect_class"])
            self.assertEqual("work_order", operation.descriptor["recovery"]["idempotency_scope"])
            self.assertEqual(["engineering.workspace.apply_patch"],
                             operation.descriptor["required_grants"])
            self.assertEqual({"workspace_id": {"type": "string", "minLength": 1}},
                             operation.descriptor["target_scope_schema"]["properties"])
            provider = operation.load_provider()
            self.assertEqual(workspace.resolve(), provider.root)
            self.assertTrue(callable(provider.invoke))
            write_result = provider.invoke(
                {"path": "deliverables/registered.txt", "content": "manifest-backed provider"},
                context={"effect_class": "isolated_write",
                         "target": {"workspace_id": "engineering-test"},
                         "work_order": {"workspace_id": "engineering-test",
                                        "allowed_paths": ["deliverables/**"]},
                         "invocation_id": "manifest-registration-test"})
            self.assertEqual(24, write_result["bytes_written"])
            self.assertEqual("manifest-backed provider",
                             (workspace / "deliverables/registered.txt").read_text())

            resource = {"resource_id": "workspace:engineering-test", "contract_version": "1.0.0",
                        "owner": "R3A-test", "capacity": 1, "allocated": 0,
                        "health": "available", "observed_at": datetime.now(timezone.utc),
                        "metadata": {"kind": "isolated_workspace", "workspace_id": "engineering-test"}}
            status = asyncio.run(DiagnosticProjection(settings, ResourceSnapshotStore(resource)).handle(
                "status", {}, "resource-discovery-test"))
            discovered_resource = next(item for item in status["resources"]
                                       if item["resource_id"] == resource["resource_id"])
            self.assertEqual("available", discovered_resource["health"])
            self.assertEqual("engineering-test", discovered_resource["metadata"]["workspace_id"])

    def test_disabled_manifest_is_hidden_and_unresolvable_through_generic_registry(self):
        with tempfile.TemporaryDirectory(prefix="r3a-engineering-disabled-") as temporary:
            root = Path(temporary)
            provider_dir = root / "provider"
            provider_dir.mkdir()
            shutil.copy2(PROVIDER, provider_dir / PROVIDER.name)
            manifest = json.loads(MANIFEST.read_text())
            manifest["operation"]["lifecycle"]["desired_state"] = "disabled"
            digest = hashlib.sha256((provider_dir / PROVIDER.name).read_bytes()).hexdigest()
            manifest["artifact_sha256"] = digest
            manifest["provider"]["artifact_sha256"] = digest
            manifest["operation"]["provider"]["artifact_sha256"] = digest
            disabled_manifest = provider_dir / "disabled.manifest.json"
            disabled_manifest.write_text(json.dumps(manifest))
            provider_config = root / "engineering-config.json"
            provider_config.write_text(json.dumps({"workspace_root": str(root)}))
            settings = load_settings(_write_bootstrap(root, disabled_manifest, provider_config))
            registry = settings.capability_registry
            self.assertEqual((), registry.discover())
            retained = registry.discover(include_disabled=True)
            self.assertEqual([OPERATION_ID], [item["descriptor"]["operation_id"] for item in retained])
            self.assertEqual("disabled", retained[0]["descriptor"]["lifecycle"]["desired_state"])
            with self.assertRaisesRegex(CapabilityContractError, "disabled"):
                registry.resolve(OPERATION_ID)


if __name__ == "__main__":
    unittest.main()
