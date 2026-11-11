"""Permanent regressions for the OctoMiner telemetry v2.1 target contract."""
# R3 CONTROLLED SOURCE
# File: tests/test_r3a_telemetry_target_scope.py
# Component: TEST-R3A-TELEMETRY-TARGET-SCOPE
# File Revision: 1.0.1
# Created: 2026-11-11T18:04:26Z
# Created By: Codex GPT-6
# Purpose: Verify fail-closed host/source scope, selective reads, and immutable v2.0 compatibility.
# Execution Model: Python unittest with fixture configuration and mocked provider boundaries.
# Observability: Exact requested source IDs, transport paths, denied targets, and artifact digests.
# Dependencies: r3a_plugins.octominer_telemetry.scope_provider; capability manifest/config contracts.
# Authority: AD-024; Roadmap Baseline 1.0 AP0-007/008/009; Modular Plugins #46 Planned Step 51.
# Changed: 2026-11-11T18:38:47Z | R3A-MODULAR-PLUGINS-STEP-70 | Codex GPT-6 | Cover absent and empty CME targets with zero collector calls.
# Changed: 2026-11-11T18:04:26Z | R3A-MODULAR-PLUGINS-STEP-51 | Codex GPT-6 | Test host/source scope enforcement and v2 provider compatibility.
# Supersedes: None.
# Contracts: r3a.capability-operation.v1; r3a.octominer-independent-telemetry.config.v3.
# Tests: Self; python -m pytest -q tests/test_r3a_telemetry_target_scope.py.
# History/Predecessor: New file; implementation contract at approved source a224a6b30f1e96b95a65fde6a50d81775f5e5039.

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from r3a_plugins.octominer_telemetry import (plugin, scope_provider_v2_1_1 as scope_provider,
                                             scoped_http_providers)
from r3a_runtime.capability_contracts import validate_json, validate_operation
from r3a_runtime.config import _validate_plugin_config


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "r3a_plugins/octominer_telemetry"
SAMPLE_GPU = (
    "GPU-111, NVIDIA Tesla P100, 00000000:04:00.0, 550.144.03, 16384, 1200, 15184, 35, 46, 82.5, 50\n"
)


def _config() -> dict:
    return {
        "host_id": "host-octo",
        "request_host_id": "host-database",
        "ssh_host": "192.0.2.10", "ssh_port": 22, "ssh_user": "readonly",
        "identity_file": "/tmp/fixture-key", "known_hosts_file": "/tmp/fixture-hosts",
        "timeout_seconds": 4, "max_age_seconds": 30,
        "model_servers": {"reasoner": {"host_id": "host-model", "base_url_env": "SCOPE_MODEL_URL",
                                          "timeout_seconds": 2, "max_age_seconds": 20}},
        "comfyui": {"host_id": "host-comfy", "base_url_env": "SCOPE_COMFY_URL",
                    "timeout_seconds": 2, "max_age_seconds": 20},
    }


class TelemetryTargetScopeTests(unittest.TestCase):
    def test_mismatched_host_denies_before_any_transport(self):
        provider = scope_provider.create_provider(_config())
        with patch.object(scope_provider, "_run_ssh_query") as ssh, \
                patch.object(scoped_http_providers, "_get_json") as http:
            with self.assertRaisesRegex(PermissionError, "host without configured provider sources"):
                provider.invoke({}, context={"target": {
                    "host_ids": ["host-unconfigured"], "source_ids": ["gpu.telemetry.host-octo"]}})
        ssh.assert_not_called()
        http.assert_not_called()

    def test_source_outside_requested_host_denies_before_any_transport(self):
        provider = scope_provider.create_provider(_config())
        with patch.object(scope_provider, "_run_ssh_query") as ssh, \
                patch.object(scoped_http_providers, "_get_json") as http:
            with self.assertRaisesRegex(PermissionError, "outside the requested host scope"):
                provider.invoke({}, context={"target": {
                    "host_ids": ["host-octo"],
                    "source_ids": ["model-server.reasoner.readiness"],
                }})
        ssh.assert_not_called()
        http.assert_not_called()

    def test_selected_gpu_source_runs_only_its_fixed_ssh_query(self):
        config = _config()
        provider = scope_provider.create_provider(config)
        with patch.object(plugin, "_run_ssh_query", return_value=SAMPLE_GPU) as ssh, \
                patch.object(scoped_http_providers, "_get_json") as http, \
                patch.dict(os.environ, {}, clear=True):
            result = provider.invoke({}, context={"target": {
                "host_ids": ["host-octo"],
                "source_ids": ["gpu.telemetry.host-octo"],
            }})
        ssh.assert_called_once_with(config, scope_provider.REMOTE_QUERY)
        http.assert_not_called()
        self.assertEqual(["gpu.telemetry.host-octo"], [item["source_id"] for item in result])
        self.assertEqual("host-octo", result[0]["content"]["host_id"])

    def test_selected_model_readiness_queries_health_but_not_slots(self):
        provider = scope_provider.create_provider(_config())
        with patch.object(scoped_http_providers, "_get_json",
                          return_value=({}, "2026-11-11T18:00:00Z", None)) as http, \
                patch.object(scope_provider, "_run_ssh_query") as ssh:
            result = provider.invoke({}, context={"target": {
                "host_ids": ["host-model"],
                "source_ids": ["model-server.reasoner.readiness"],
            }})
        self.assertEqual(1, http.call_count)
        self.assertEqual("/health", http.call_args.args[1])
        ssh.assert_not_called()
        self.assertEqual(["model-server.reasoner.readiness"], [item["source_id"] for item in result])

    def test_unconfigured_source_and_malformed_target_fail_closed(self):
        provider = scope_provider.create_provider(_config())
        for target in (
            {"host_ids": ["host-octo"], "source_ids": ["gpu.telemetry.other"]},
            {"host_ids": ["host-octo"], "source_ids": []},
            {"host_ids": ["host-octo"], "source_ids": None},
            {"host_ids": [], "source_ids": ["gpu.telemetry.host-octo"]},
            {"host_ids": None, "source_ids": ["gpu.telemetry.host-octo"]},
            {"host_ids": ["host-octo", " host-octo "]},
            {"host_ids": ["host-octo"], "source_ids": ["gpu.telemetry.host-octo"], "unexpected": True},
        ):
            with self.subTest(target=target):
                with patch.object(scope_provider, "_run_ssh_query") as ssh:
                    with self.assertRaises((ValueError, PermissionError)):
                        provider.invoke({}, context={"target": target})
                    ssh.assert_not_called()

    def test_missing_or_empty_cme_target_fails_before_any_collector(self):
        provider = scope_provider.create_provider(_config())
        contexts = ({}, {"target": {}}, {"target": None})
        for context in contexts:
            with self.subTest(context=context), \
                    patch.object(scope_provider, "_run_ssh_query") as ssh, \
                    patch.object(scope_provider, "read_compute_apps") as processes, \
                    patch.object(scoped_http_providers, "_get_json") as http:
                with self.assertRaises(ValueError):
                    provider.invoke({}, context=context)
                ssh.assert_not_called()
                processes.assert_not_called()
                http.assert_not_called()

    def test_direct_collector_call_without_target_fails_closed(self):
        with patch.object(scope_provider, "_run_ssh_query") as ssh, \
                patch.object(scope_provider, "read_compute_apps") as processes, \
                patch.object(scoped_http_providers, "_get_json") as http:
            with self.assertRaisesRegex(ValueError, "target scope is required"):
                scope_provider.read_scoped_telemetry(_config())
        ssh.assert_not_called()
        processes.assert_not_called()
        http.assert_not_called()

    def test_history_only_host_scope_reads_only_that_hosts_persisted_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = Path(directory) / "history.sqlite3"
            with sqlite3.connect(journal) as conn:
                conn.execute("CREATE TABLE telemetry_samples (sample_id INTEGER PRIMARY KEY, source_id TEXT, "
                             "state TEXT, observed_at TEXT, attempted_at TEXT, content_json TEXT, sha256 TEXT)")
                conn.executemany("INSERT INTO telemetry_samples VALUES(?,?,?,?,?,?,?)", [
                    (1, "gpu.telemetry.host-octo", "fresh", "t1", "t1", '{"host_id":"host-octo"}', "a" * 64),
                    (2, "model-server.reasoner.readiness", "fresh", "t2", "t2", '{"service_id":"reasoner"}', "b" * 64),
                ])
            config = _config()
            config["history_path_env"] = "R3A_SCOPE_FIXTURE_HISTORY"
            with patch.dict(os.environ, {"R3A_SCOPE_FIXTURE_HISTORY": str(journal)}), \
                    patch.object(scope_provider, "_run_ssh_query") as ssh, \
                    patch.object(scoped_http_providers, "_get_json") as http:
                result = scope_provider.read_scoped_telemetry(config, {
                    "host_ids": ["host-octo"], "source_ids": [scope_provider.HISTORY_SOURCE_ID]})
            ssh.assert_not_called()
            http.assert_not_called()
            self.assertEqual([scope_provider.HISTORY_SOURCE_ID], [item["source_id"] for item in result])
            self.assertEqual(["gpu.telemetry.host-octo"],
                             [item["source_id"] for item in result[0]["content"]["samples"]])

    def test_v211_manifest_pins_scope_provider_and_requires_existing_grant(self):
        manifest = json.loads((PACKAGE / "manifest.v2.1.1.json").read_text())
        operation = validate_operation(manifest["operation"])
        self.assertEqual("2.1.1", manifest["plugin_version"])
        self.assertEqual("2.1.1", manifest["operation"]["operation_revision"])
        self.assertEqual("r3a.octominer-independent-telemetry.config.v3",
                         manifest["configuration_schema"]["schema_id"])
        self.assertEqual([], manifest["operation"]["caller_constraints"]["allowed_residents"])
        self.assertEqual(["infrastructure.octominer.telemetry.read"],
                         manifest["operation"]["required_grants"])
        with self.assertRaises(ValueError):
            validate_json({}, operation["target_scope_schema"])
        with self.assertRaises(ValueError):
            validate_json({"host_ids": ["host-octo"], "source_ids": []},
                          operation["target_scope_schema"])
        for item in [{"artifact_ref": manifest["artifact_ref"],
                      "artifact_sha256": manifest["artifact_sha256"]},
                     *manifest["supporting_artifacts"]]:
            artifact = PACKAGE / item["artifact_ref"]
            self.assertEqual(item["artifact_sha256"], hashlib.sha256(artifact.read_bytes()).hexdigest())

        config = json.loads((PACKAGE / "config.v3.example.json").read_text())
        _validate_plugin_config(config, manifest["configuration_schema"], "fixture.config")
        provider = scope_provider.create_provider(config)
        self.assertEqual("replace-with-verified-model-server-host-id",
                         provider.configuration["model_servers"]["grace-reasoning-80b"]["host_id"])

    def test_legacy_v20_manifest_keeps_its_original_digest_pins(self):
        manifest = json.loads((PACKAGE / "manifest.json").read_text())
        self.assertEqual("2.0.0", manifest["plugin_version"])
        self.assertEqual(manifest["artifact_sha256"],
                         hashlib.sha256((PACKAGE / "plugin.py").read_bytes()).hexdigest())
        for supporting in manifest["supporting_artifacts"]:
            self.assertEqual(supporting["artifact_sha256"],
                             hashlib.sha256((PACKAGE / supporting["artifact_ref"]).read_bytes()).hexdigest())

    def test_failed_v21_candidate_is_preserved_and_v211_has_separate_artifact(self):
        manifest_210 = json.loads((PACKAGE / "manifest.v2.1.0.json").read_text())
        self.assertEqual("2.1.0", manifest_210["plugin_version"])
        self.assertEqual(manifest_210["artifact_sha256"],
                         hashlib.sha256((PACKAGE / manifest_210["artifact_ref"]).read_bytes()).hexdigest())
        manifest_211 = json.loads((PACKAGE / "manifest.v2.1.1.json").read_text())
        self.assertEqual("2.1.1", manifest_211["plugin_version"])
        self.assertNotEqual(manifest_210["artifact_sha256"], manifest_211["artifact_sha256"])
        self.assertNotEqual(manifest_210["artifact_ref"], manifest_211["artifact_ref"])

    def test_v21_activation_requires_host_mapping_for_each_configured_endpoint(self):
        config = _config()
        del config["model_servers"]["reasoner"]["host_id"]
        with self.assertRaisesRegex(ValueError, "host_id"):
            scope_provider.create_provider(config)


if __name__ == "__main__":
    unittest.main()
