"""Focused contract tests for the R3A-owned NVIDIA telemetry capability."""
# R3 CONTROLLED SOURCE
# File: tests/test_r3a_octominer_plugin.py
# Component: R3A-PLUG-OCTOMINER-TEST
# File Revision: 2.0.0
# Created: 2026-11-07T04:19:12Z
# Created By: Codex GPT-6
# Purpose: Verify fixed read-only SSH GPU/storage collection and structured evidence.
# Execution Model: Python unittest with mocked OpenSSH boundary.
# Observability: Verify fixed command, parsed physical identity, units, digest and failure handling.
# Dependencies: Python standard library; r3a_plugins.octominer_telemetry.plugin.
# Authority: Issue #46; tests invoke no host or legacy service.
# Changed: 2026-11-07 | R3A-PLUG-001 | Codex GPT-6 | Adapt tests to independent R3A SSH collector.
# Supersedes: Revision 1.0.0 HTTP fixture tests; legacy API transport removed.
# Contracts: r3a.capability-plugin 1.0.0; r3a.octominer-nvidia-smi-ssh.config.v1; Issue #46.
# Tests: Self.
# History/Predecessor: Git commit dee12de54618e36cce42b8002d7fb5cf1f436ec8.

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from r3a_runtime.config import ConfigurationError, _validate_plugin_config
from r3a_plugins.octominer_telemetry import plugin


SAMPLE = (
    "GPU-111, NVIDIA Tesla P100, 00000000:04:00.0, 550.144.03, 16384, 1200, 15184, 35, 46, 82.5, 50\n"
    "GPU-222, NVIDIA GeForce RTX 4090, 00000000:07:00.0, 550.144.03, 24564, 6000, 18564, 17, 41, 98.2, N/A\n"
)
DF_SAMPLE = "Filesystem  1B-blocks       Used Available Use% Mounted on\n/dev/sda4   117722342400 100777000000 12200000000  85% /\n"


class OctoMinerPluginTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.identity = self.root / "r3a_identity"
        self.known_hosts = self.root / "known_hosts"
        self.identity.write_text("test-only-placeholder")
        self.known_hosts.write_text("192.0.2.10 ssh-ed25519 TEST_ONLY_KEY")
        self.config = {"host_id": "octo1", "ssh_host": "192.0.2.10", "ssh_port": 22,
                       "ssh_user": "octo_readonly", "identity_file": str(self.identity),
                       "known_hosts_file": str(self.known_hosts), "timeout_seconds": 4,
                       "max_age_seconds": 10}

    def tearDown(self):
        self.tmp.cleanup()

    def test_manifest_is_read_only_versioned_and_digest_pinned(self):
        root = Path(__file__).resolve().parents[1]
        manifest = json.loads((root / "r3a_plugins/octominer_telemetry/manifest.json").read_text())
        artifact = root / "r3a_plugins/octominer_telemetry" / manifest["artifact_ref"]
        self.assertEqual(1, manifest["schema_version"])
        self.assertTrue(manifest["read_only"])
        self.assertEqual("1.0.0", manifest["contract_version"])
        self.assertEqual(manifest["artifact_sha256"], hashlib.sha256(artifact.read_bytes()).hexdigest())

    def test_plugin_owned_config_uses_manifest_declared_schema(self):
        root = Path(__file__).resolve().parents[1]
        package = root / "r3a_plugins/octominer_telemetry"
        manifest = json.loads((package / "manifest.json").read_text())
        config = json.loads((package / "config.example.json").read_text())
        _validate_plugin_config(config, manifest["configuration_schema"], "test.config")
        config["ssh_port"] = "22"
        with self.assertRaises(ConfigurationError):
            _validate_plugin_config(config, manifest["configuration_schema"], "test.config")

    def test_parser_preserves_gpu_identity_metrics_and_units(self):
        devices = plugin.parse_nvidia_smi_csv(SAMPLE, host_id="octo1", collected_at="2026-11-07T00:00:00Z")
        self.assertEqual(2, len(devices))
        self.assertEqual("GPU-111", devices[0]["nvidia_uuid"])
        self.assertEqual("octo1:nvidia:GPU-111", devices[0]["resource_id"])
        self.assertEqual(35.0, devices[0]["utilization_percent"])
        self.assertEqual(46.0, devices[0]["temperature_c"])
        self.assertEqual(50.0, devices[0]["fan_speed_percent"])
        self.assertIsNone(devices[1]["fan_speed_percent"])
        self.assertEqual("2026-11-07T00:00:00Z", devices[0]["observed_at"])
        self.assertEqual("MiB", plugin.FIELD_UNITS["memory_used_mib"])
        self.assertEqual("degC", plugin.FIELD_UNITS["temperature_c"])
        self.assertEqual("W", plugin.FIELD_UNITS["power_draw_w"])

    def test_storage_parser_preserves_mount_identity_and_byte_counts(self):
        rows = plugin.parse_df_posix(DF_SAMPLE, host_id="octo1", collected_at="2026-11-07T00:00:00Z")
        self.assertEqual("octo1:filesystem:/", rows[0]["resource_id"])
        self.assertEqual(117722342400, rows[0]["size_bytes"])
        self.assertEqual(12200000000, rows[0]["available_bytes"])
        self.assertEqual("/dev/sda4", rows[0]["filesystem"])

    @patch.object(plugin.shutil, "which", return_value="/usr/bin/ssh")
    @patch.object(plugin.subprocess, "run")
    def test_uses_only_pinned_read_only_ssh_query(self, run, _which):
        run.side_effect = [SimpleNamespace(returncode=0, stdout=SAMPLE, stderr=""),
                           SimpleNamespace(returncode=0, stdout=DF_SAMPLE, stderr="")]
        gpu, storage = plugin.read_telemetry(self.config)
        gpu_command, storage_command = [call.args[0] for call in run.call_args_list]
        self.assertTrue(gpu["content"]["available"])
        self.assertEqual("fresh", gpu["freshness"]["state"])
        self.assertEqual("octo1", gpu["content"]["host_id"])
        self.assertEqual("ssh://octo_readonly@192.0.2.10:22/nvidia-smi", gpu["source_path"])
        self.assertEqual("fresh", storage["freshness"]["state"])
        self.assertEqual(1, len(storage["content"]["filesystems"]))
        for command in [gpu_command, storage_command]:
            self.assertIn("StrictHostKeyChecking=yes", command)
            self.assertIn("IdentitiesOnly=yes", command)
            self.assertNotIn("riverview", " ".join(command).lower())
            self.assertEqual(4, run.call_args.kwargs["timeout"])
        self.assertEqual(plugin.REMOTE_QUERY, gpu_command[-1])
        self.assertEqual(plugin.FILESYSTEM_QUERY, storage_command[-1])

    @patch.object(plugin.shutil, "which", return_value="/usr/bin/ssh")
    @patch.object(plugin.subprocess, "run")
    def test_transport_failure_returns_unavailable_evidence_without_stderr(self, run, _which):
        run.side_effect = [SimpleNamespace(returncode=255, stdout="", stderr="private host detail"),
                           SimpleNamespace(returncode=255, stdout="", stderr="private host detail")]
        evidence = plugin.read_telemetry(self.config)[0]
        self.assertEqual("unavailable", evidence["freshness"]["state"])
        self.assertEqual({"available": False, "host_id": "octo1", "error": "ssh_exit_255"},
                         evidence["content"])
        self.assertNotIn("private host detail", json.dumps(evidence))

    def test_missing_r3a_key_or_host_key_fails_without_transport(self):
        self.identity.unlink()
        with patch.object(plugin.shutil, "which", return_value="/usr/bin/ssh"), \
                patch.object(plugin.subprocess, "run") as run:
            evidence = plugin.read_telemetry(self.config)[0]
        self.assertEqual("unavailable", evidence["freshness"]["state"])
        self.assertEqual("r3a_ssh_credential_or_host_key_file_unavailable", evidence["content"]["error"])
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
