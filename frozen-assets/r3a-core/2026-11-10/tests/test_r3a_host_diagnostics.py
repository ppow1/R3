# R3 CONTROLLED SOURCE
# File: tests/test_r3a_host_diagnostics.py
# Component: R3A-PLUG-HOST-DIAGNOSTICS-TEST
# File Revision: 1.0.0
# Created: 2026-11-08T19:26:31Z
# Created By: Codex GPT-6
# Purpose: Verify typed host diagnostic output, source states and target constraints.
# Execution Model: Python unittest using procfs fixture files and mocked optional sensors.
# Observability: Schema validation, source digest and measured/unavailable field assertions.
# Dependencies: Python standard library; canonical R3A capability contract validator.
# Authority: Issue #46; fixtures are not Camrui hardware evidence.
# Changed: 2026-11-08T19:26:31Z | R3A-HOST-DIAGNOSTICS-001 | Codex GPT-6 | Add host diagnostics conformance tests.
# Supersedes: None.
# Contracts: r3a.capability-operation.v1; r3a.host-diagnostics.v1.
# Tests: Self.
# History/Predecessor: New file.
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from r3a_runtime.capability_contracts import (CapabilityRegistry, operation_from_manifest,
                                               validate_json, validate_operation)
from r3a_plugins.resource_monitor import host_diagnostics


ROOT = Path(__file__).resolve().parents[1]


class HostDiagnosticsTests(unittest.TestCase):
    def test_manifest_is_digest_pinned_and_operation_is_registered_shape(self):
        manifest = json.loads((ROOT / "r3a_plugins/resource_monitor/host-diagnostics.manifest.json").read_text())
        validate_operation(manifest["operation"])
        self.assertEqual("infrastructure.host-diagnostics.read", manifest["operation"]["operation_id"])
        source = ROOT / "r3a_plugins/resource_monitor" / manifest["artifact_ref"]
        self.assertEqual(manifest["artifact_sha256"], hashlib.sha256(source.read_bytes()).hexdigest())
        config = json.loads((ROOT / "r3a_plugins/resource_monitor/host-diagnostics.config.example.json").read_text())
        from r3a_runtime.config import _validate_plugin_config
        _validate_plugin_config(config, manifest["configuration_schema"], "host-diagnostics.config")
        registry = CapabilityRegistry()
        registry.register(operation_from_manifest(manifest), config, legacy_manifest=manifest)
        self.assertEqual(manifest["operation"]["operation_id"],
                         registry.discover()[0]["descriptor"]["operation_id"])

    def test_collects_measured_host_values_and_explicitly_unavailable_sensors(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            meminfo = root / "meminfo"
            uptime = root / "uptime"
            meminfo.write_text("MemTotal: 2048 kB\nMemAvailable: 1024 kB\n")
            uptime.write_text("12345.50 456.0\n")
            config = {"host_id": "fixture-host", "timeout_seconds": 2, "max_age_seconds": 60,
                      "filesystem_paths": ["/"], "meminfo_path": str(meminfo),
                      "uptime_path": str(uptime)}
            with patch.object(host_diagnostics.shutil, "which", return_value=None):
                result = host_diagnostics.collect_host_diagnostics(config)
        manifest = json.loads((ROOT / "r3a_plugins/resource_monitor/host-diagnostics.manifest.json").read_text())
        validate_json(result, manifest["operation"]["output_schema"])
        self.assertEqual(2097152, result["content"]["memory"]["total_bytes"])
        self.assertEqual(50.0, result["content"]["memory"]["used_percent"])
        self.assertEqual(12345.5, result["content"]["uptime"]["seconds"])
        self.assertEqual("unavailable", result["content"]["sensors"]["state"])
        self.assertEqual(64, len(result["sha256"]))

    def test_sensor_temperature_and_fan_units_are_reported_from_names(self):
        rows = host_diagnostics._sensor_values({"chip": {"temp1_input": 41.5, "fan1_input": 880}})
        self.assertEqual(["degC", "rpm"], [row["unit"] for row in rows])

    def test_provider_rejects_other_host_targets(self):
        provider = host_diagnostics.HostDiagnosticsProvider({"host_id": "host-a"})
        with self.assertRaisesRegex(ValueError, "target scope exceeds"):
            provider.invoke({}, context={"target": {"host_ids": ["host-b"]}})


if __name__ == "__main__":
    unittest.main()
