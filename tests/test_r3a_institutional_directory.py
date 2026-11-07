"""Provider tests for the R3A-owned, read-only institutional directory adapter."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
import asyncio
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from unittest.mock import patch

from r3a_runtime.config import _validate_plugin_config
from r3a_runtime.capability_contracts import CapabilityRegistry, normalize_provider_result, validate_operation
from r3a_runtime.cme import CME
from r3a_plugins.institutional_directory import plugin


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "r3a_plugins/institutional_directory"


def descriptor_and_configuration():
    manifest = json.loads((PACKAGE / "manifest.json").read_text())
    config = json.loads((PACKAGE / "config.example.json").read_text())
    _validate_plugin_config(config, manifest["configuration_schema"], "directory.config")
    return manifest, validate_operation(manifest["operation"]), config


class InstitutionalDirectoryProviderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="r3a-directory-test-")
        self.root = Path(self.temp.name)
        self.database = self.root / "hr.sqlite3"
        with sqlite3.connect(self.database) as connection:
            connection.execute("CREATE TABLE hr_records (resident_id TEXT PRIMARY KEY, revision INTEGER NOT NULL, payload TEXT NOT NULL)")
            connection.executemany("INSERT INTO hr_records VALUES (?, ?, ?)", [
                ("r3:grace", 4, json.dumps({
                    "resident_id": "r3:grace", "display_name": "Grace", "office": "Director of Operations",
                    "status": "onboarding", "schema_version": 1,
                    "fields": {"role": {"value": "Director of Operations", "classification": "public"},
                               "private_note": {"value": "do not disclose", "classification": "confidential"}},
                    "extensions": {}, "history_refs": []})),
                ("r3:marie", 2, json.dumps({
                    "resident_id": "r3:marie", "display_name": "Marie", "office": "Research / Independent Review",
                    "status": "onboarding", "schema_version": 1,
                    "fields": {}, "extensions": {}, "history_refs": []})),
            ])
        os.utime(self.database, (1_700_000_000, 1_700_000_000))
        self.manifest, self.descriptor, self.config = descriptor_and_configuration()
        self.config["max_age_seconds"] = 3600
        self.provider = plugin.create_provider(self.config)
        self.env = patch.dict(os.environ, {
            "R3A_HR_DIRECTORY_DATABASE": str(self.database),
            "R3A_DIRECTORY_RESPONSIBILITY_CATALOG": "",
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_manifest_pins_provider_and_responsibility_schema(self):
        self.assertEqual(hashlib.sha256((PACKAGE / "plugin.py").read_bytes()).hexdigest(),
                         self.manifest["artifact_sha256"])
        for artifact in self.manifest["supporting_artifacts"]:
            self.assertEqual(artifact["artifact_sha256"],
                             hashlib.sha256((PACKAGE / artifact["artifact_ref"]).read_bytes()).hexdigest())
        self.assertEqual("institutional.directory.discover", self.descriptor["operation_id"])
        self.assertEqual("read", self.descriptor["effect_class"])
        registry = CapabilityRegistry()
        registered = registry.register(self.descriptor, self.config, legacy_manifest=self.manifest)
        self.assertEqual("Institutional Directory Discovery",
                         registry.discover()[0]["presentation"]["name"])
        self.assertIsInstance(registered.load_provider(), plugin.InstitutionalDirectoryProvider)

    def test_real_hr_shape_is_read_only_source_backed_and_classification_filtered(self):
        before = hashlib.sha256(self.database.read_bytes()).hexdigest()
        result = self.provider.invoke({}, context={"config_revision": "cfg-1", "capability_catalog": []})
        output, evidence = normalize_provider_result(result, self.descriptor)
        after = hashlib.sha256(self.database.read_bytes()).hexdigest()
        self.assertEqual(before, after)
        self.assertEqual("r3a.institutional-directory.v1", output["schema_id"])
        self.assertEqual(2, len(output["residents"]))
        grace = next(row for row in output["residents"] if row["resident_id"] == "r3:grace")
        self.assertEqual("Director of Operations", grace["office"])
        self.assertEqual("onboarding", grace["status"])
        self.assertEqual(4, grace["record_revision"])
        self.assertEqual("Director of Operations", grace["role_description"])
        self.assertIsNone(grace["availability"])
        self.assertEqual("unavailable", grace["availability_state"])
        self.assertEqual("unavailable", grace["responsibility_state"])
        self.assertNotIn("private_note", json.dumps(output))
        self.assertEqual("stale", output["source"]["freshness"])
        self.assertEqual(self.manifest["artifact_sha256"], self.descriptor["provider"]["artifact_sha256"])
        self.assertEqual("hr.resident-records", evidence[0]["source_id"])
        self.assertEqual([{"resident_id": "r3:grace", "record_revision": 4},
                          {"resident_id": "r3:marie", "record_revision": 2}],
                         evidence[0]["record_revisions"])

    def test_configured_responsibility_catalog_maps_only_registered_operations(self):
        catalog_path = self.root / "responsibilities.json"
        catalog_path.write_text(json.dumps({
            "schema_id": "r3a.institutional-responsibility-catalog.v1", "schema_version": 1,
            "source_id": "institutional.hr.responsibilities", "source_revision": "hr-rev-12",
            "updated_at": "2026-11-07T12:00:00Z", "offices": [{
                "office": "Director of Operations", "responsibilities": [{
                    "responsibility_id": "operations.coordinate", "description": "Fixture responsibility from test data.",
                    "capability_ids": ["test.operations.read", "test.not.registered"]}]}]}))
        catalog_digest = hashlib.sha256(catalog_path.read_bytes()).hexdigest()
        self.config["max_age_seconds"] = 604800
        self.env.stop()
        self.env = patch.dict(os.environ, {
            "R3A_HR_DIRECTORY_DATABASE": str(self.database),
            "R3A_DIRECTORY_RESPONSIBILITY_CATALOG": str(catalog_path),
        })
        self.env.start()
        catalog_descriptor = {
            "contract_id": "r3a.capability-operation.v1", "contract_version": "1.0.0",
            "operation_id": "test.operations.read", "operation_revision": "1.0.0",
            "provider": {"provider_id": "test.provider", "provider_version": "1.0.0",
                         "entrypoint": "test:create_provider", "artifact_sha256": "a" * 64},
            "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
            "output_schema": {"type": "object", "properties": {}, "additionalProperties": True},
            "effect_class": "read", "caller_constraints": {"allowed_principals": [], "allowed_residents": [], "allowed_services": []},
            "target_scope_schema": {"type": "object", "properties": {}, "additionalProperties": False},
            "required_grants": ["test.operations.read"],
            "evidence": {"schema": {"type": "array", "items": {"type": "object"}}, "verification_obligations": []},
            "recovery": {"idempotency_required": False, "idempotency_scope": "invocation", "replay_safe": True, "reconciliation_operation_id": None},
            "execution": {"timeout_seconds": 1, "retry_disposition": "safe_retry"},
            "lifecycle": {"desired_state": "enabled"},
        }
        result = self.provider.invoke({}, context={"config_revision": "cfg-1", "capability_catalog": [{
            "descriptor": catalog_descriptor, "presentation": {"name": "Operations Read", "description": "Fixture", "description_registered": True},
            "registry_observation": {"state": "registered", "health": "not_probed", "provider_availability": "not_probed"}}]})
        output, _ = normalize_provider_result(result, self.descriptor)
        grace = next(row for row in output["residents"] if row["resident_id"] == "r3:grace")
        binding = grace["responsibilities"][0]
        self.assertEqual("measured", grace["responsibility_state"])
        self.assertEqual(catalog_digest, output["responsibility_catalog"]["source_sha256"])
        self.assertEqual("hr-rev-12", output["responsibility_catalog"]["source_revision"])
        self.assertFalse(binding["capabilities"][0]["authorization_evaluated"])
        self.assertEqual("not_registered", binding["capabilities"][1]["registry_state"])
        self.assertFalse(output["capabilities"][0]["authorization_evaluated"])

    def test_missing_database_is_explicitly_unavailable_and_filter_is_bounded(self):
        self.env.stop()
        self.env = patch.dict(os.environ, {
            "R3A_HR_DIRECTORY_DATABASE": str(self.root / "missing.sqlite3"),
            "R3A_DIRECTORY_RESPONSIBILITY_CATALOG": "",
        })
        self.env.start()
        unavailable = self.provider.invoke({}, context={"capability_catalog": []})
        output, _ = normalize_provider_result(unavailable, self.descriptor)
        self.assertEqual("unavailable", output["source"]["freshness"])
        self.assertEqual([], output["residents"])
        self.assertEqual("directory_source_unavailable", output["source"]["error"])

        self.env.stop()
        self.env = patch.dict(os.environ, {
            "R3A_HR_DIRECTORY_DATABASE": str(self.database),
            "R3A_DIRECTORY_RESPONSIBILITY_CATALOG": "",
        })
        self.env.start()
        bounded = self.provider.invoke({"limit": 1}, context={"capability_catalog": []})
        output, _ = normalize_provider_result(bounded, self.descriptor)
        self.assertEqual(1, len(output["residents"]))
        self.assertEqual(2, output["source"]["total_matching_records"])
        self.assertFalse(output["source"]["complete_inventory"])

    def test_grace_tool_adapter_receives_directory_output_and_separate_source_evidence(self):
        registry = CapabilityRegistry()
        registry.register(self.descriptor, self.config, legacy_manifest=self.manifest)
        instance = CME.__new__(CME)
        instance.settings = SimpleNamespace(capability_registry=registry,
                                            module_capabilities=(self.descriptor["operation_id"],),
                                            source_digest="cfg-directory-test")
        instance._authorize_capability = AsyncMock(return_value={
            "provider_id": "capability_grants", "decision_id": "directory-decision",
            "audit_event_id": "directory-audit", "policy_revision": None,
            "config_revision": "cfg-directory-test"})
        result = asyncio.run(instance._invoke_resident_capability(
            {"activity_id": "activity-1", "attempt_id": "attempt-1", "correlation_id": "corr-1"},
            {"contract_id": "r3a.resident-capability-tool", "contract_version": "1.0.0",
             "capability_id": self.descriptor["operation_id"], "arguments": {}}))
        self.assertEqual("succeeded", result["outcome"])
        self.assertEqual("r3a.institutional-directory.v1", result["output"]["schema_id"])
        self.assertEqual(2, len(result["output"]["residents"]))
        self.assertIn("hr.resident-records", {row["source_id"] for row in result["evidence"]})
        self.assertTrue(result["authorization"]["audit_event_id"])


if __name__ == "__main__":
    unittest.main()
