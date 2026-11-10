# R3 CONTROLLED SOURCE
# File: tests/test_r3a_resource_monitor.py
# Component: R3A-PLUG-RESOURCE-MONITOR-TEST
# File Revision: 1.0.0
# Created: 2026-11-08T18:43:38Z
# Created By: Codex GPT-6
# Purpose: Verify manifest contracts, inventory parsing, SMART unavailability and evidence integrity.
# Execution Model: Python unittest with representative lsblk/smartctl fixtures.
# Observability: Test assertions cover exact states, provenance fields, digest pins and output schemas.
# Dependencies: Python standard library; R3A capability contract validator.
# Authority: Issue #46; fixtures are not live device measurements.
# Changed: 2026-11-08T18:43:38Z | R3A-RESOURCE-MONITOR-001 | Codex GPT-6 | Add resource-monitor conformance tests.
# Supersedes: None.
# Contracts: r3a.capability-operation.v1; r3a.physical-resource-inventory.v1; r3a.software-environment-inventory.v1.
# Tests: Self.
# History/Predecessor: New file in current modular plug-in worktree.
from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from r3a_runtime.capability_contracts import (CapabilityRegistry, operation_from_manifest,
                                               validate_json, validate_operation)
from r3a_plugins.resource_monitor import monitor


ROOT = Path(__file__).resolve().parents[1]
LSBLK = json.dumps({"blockdevices": [
    {"name": "sda", "type": "disk", "size": 1200000000000, "rota": True,
     "tran": "sas", "model": "Example SAS Disk"},
    {"name": "sda1", "type": "part", "size": 1000000000},
    {"name": "nvme0n1", "type": "disk", "size": 2000000000000, "rota": False,
     "tran": "nvme", "model": "Example NVMe"},
]})
SMART_SAS = json.dumps({"device": {"protocol": "SCSI"}, "smart_status": {"passed": True},
                       "scsi_temperature": {"current": 38}, "user_capacity": {"bytes": 1200000000000}})


class ResourceMonitorTests(unittest.TestCase):
    def setUp(self):
        self.config = {"host_id": "fixture-host", "timeout_seconds": 2, "max_age_seconds": 60}

    def test_disk_and_software_manifests_are_valid_and_digest_pinned(self):
        registry = CapabilityRegistry()
        provider_ids = set()
        for name in ("disk-health.manifest.json", "software-environments.manifest.json"):
            manifest = json.loads((ROOT / "r3a_plugins/resource_monitor" / name).read_text())
            provider_ids.add(manifest["provider"]["provider_id"])
            operation = validate_operation(manifest["operation"])
            self.assertEqual("read", operation["effect_class"])
            self.assertEqual("infrastructure.resource-inventory.read", operation["required_grants"][0])
            source = ROOT / "r3a_plugins/resource_monitor" / manifest["artifact_ref"]
            self.assertEqual(manifest["artifact_sha256"], hashlib.sha256(source.read_bytes()).hexdigest())
            config = json.loads((ROOT / "r3a_plugins/resource_monitor/config.example.json").read_text())
            from r3a_runtime.config import _validate_plugin_config
            _validate_plugin_config(config, manifest["configuration_schema"], name)
            registry.register(operation_from_manifest(manifest), config, legacy_manifest=manifest)
        discovered = {row["descriptor"]["operation_id"] for row in registry.discover()}
        self.assertEqual({"r3a.disk-health-monitor", "r3a.software-environment-inventory"}, provider_ids)
        self.assertEqual({"infrastructure.resources.disk-health.read",
                          "infrastructure.software-environments.discover"}, discovered)

    def test_lsblk_inventory_includes_physical_disks_not_partitions(self):
        rows = monitor.parse_lsblk(LSBLK, host_id="fixture-host", observed_at="2026-11-08T12:00:00Z")
        self.assertEqual(["sda", "nvme0n1"], [row["name"] for row in rows])
        self.assertEqual("sas", rows[0]["transport"])
        self.assertEqual(1200000000000, rows[0]["capacity_bytes"])
        self.assertNotIn("serial", rows[0])

    def test_smartctl_sas_fixture_preserves_reported_health_and_temperature(self):
        result = monitor.parse_smartctl(SMART_SAS)
        self.assertEqual("measured", result["health_state"])
        self.assertTrue(result["smart_passed"])
        self.assertEqual(38, result["temperature_c"])
        self.assertEqual("SCSI", result["device_protocol"])

    def test_absent_smartctl_does_not_fabricate_health(self):
        with patch.object(monitor.shutil, "which", side_effect=lambda name: "/usr/bin/lsblk" if name == "lsblk" else None):
            record = monitor.collect_disk_inventory(self.config, run=lambda *_: LSBLK)
        self.assertEqual("fresh", record["freshness"]["state"])
        self.assertEqual("unavailable", record["content"]["disks"][0]["health"]["health_state"])
        self.assertEqual("smartctl_unavailable", record["content"]["disks"][0]["health"]["reason"])

    def test_sas_smartctl_nonzero_health_bit_still_preserves_json_measurement(self):
        with patch.object(monitor.shutil, "which", return_value="/usr/sbin/smartctl"):
            with patch.object(monitor.subprocess, "run", side_effect=[
                SimpleNamespace(stdout=LSBLK, returncode=0),
                SimpleNamespace(stdout=SMART_SAS, returncode=2),
                SimpleNamespace(stdout=SMART_SAS, returncode=0),
            ]):
                record = monitor.collect_disk_inventory(self.config)
        disk = record["content"]["disks"][0]
        self.assertEqual("measured", disk["health"]["health_state"])
        self.assertEqual(38, disk["health"]["temperature_c"])
        self.assertEqual(2, disk["health"]["smartctl_exit_status"])

    def test_output_obeys_registered_typed_schema_and_evidence(self):
        with patch.object(monitor.shutil, "which", return_value=None):
            record = monitor.collect_disk_inventory(self.config)
        schema = json.loads((ROOT / "r3a_plugins/resource_monitor/disk-health.manifest.json").read_text())["operation"]["output_schema"]
        validate_json(record, schema)
        self.assertEqual(64, len(record["sha256"]))
        self.assertIn(record["freshness"]["state"], {"fresh", "stale", "unavailable"})

    def test_software_inventory_is_separate_and_matches_its_output_contract(self):
        config = {**self.config, "executables": ["lsblk", "smartctl", "nvidia-smi"]}
        record = monitor.collect_software_inventory(config)
        manifest = json.loads((ROOT / "r3a_plugins/resource_monitor/software-environments.manifest.json").read_text())
        validate_json(record, manifest["operation"]["output_schema"])
        self.assertEqual("r3a.software-environment-inventory.v1", record["content"]["schema_id"])
        self.assertNotIn("disks", record["content"])

    def test_provider_rejects_target_outside_its_configured_host(self):
        provider = monitor.DiskHealthProvider(self.config)
        with self.assertRaisesRegex(ValueError, "target scope exceeds"):
            provider.invoke({}, context={"target": {"host_ids": ["other-host"]}})


if __name__ == "__main__":
    unittest.main()
