"""Contract and conformance tests for the R3A Riverview directory adapter."""
from __future__ import annotations

import hashlib
import json
import os
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


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows


class ReadOnlyDirectoryFixture:
    """Synthetic PostgreSQL projection; it contains no live resident records."""
    def __init__(self):
        self.statements = []
        self.closed = False
        self.fixtures = {
            "institutional_offices": [
                {"office_id": "office:operations", "office_role": "Director of Operations", "status": "active"},
                {"office_id": "office:engineering", "office_role": "Engineering Manager", "status": "inactive"},
            ],
            "office_bindings": [
                {"office_id": "office:operations", "principal_id": "resident:grace", "binding_revision": 12},
            ],
            "capability_catalog": [
                {"capability_id": "engineering.assignment.execute", "owner_office": "office:engineering",
                 "authority_action": "Execute an approved isolated engineering assignment.",
                 "enabled": True, "availability_policy": "requires_active_engineering_office",
                 "registration_blocker": "no_active_engineering_office",
                 "input_schema": {"type": "object", "properties": {}},
                 "authorization_contract": "r3a.authorization-decision.v1", "resources": ["workspace:isolated"]},
            ],
            "capability_resources": [
                {"capability_id": "engineering.assignment.execute", "resource_id": "workspace:isolated",
                 "implementation_ref": "fixture:implementation"},
            ],
        }

    def execute(self, query, params=None):
        normalized = query.upper()
        self.statements.append((query, params))
        if normalized.startswith("BEGIN TRANSACTION"):
            return FakeCursor([])
        if normalized == "COMMIT":
            return FakeCursor([])
        if "INSTITUTIONAL_OFFICES" in normalized:
            rows = self.fixtures["institutional_offices"]
            if params and params.get("office_id"):
                rows = [row for row in rows if row["office_id"] == params["office_id"]]
            return FakeCursor(rows[:params["limit"]])
        if "OFFICE_BINDINGS" in normalized:
            rows = self.fixtures["office_bindings"]
            if params.get("resident_id"):
                rows = [row for row in rows if row["principal_id"] == params["resident_id"]]
            return FakeCursor(rows[:params["limit"]])
        if "CAPABILITY_CATALOG" in normalized:
            return FakeCursor(self.fixtures["capability_catalog"][:params["limit"]])
        if "CAPABILITY_RESOURCES" in normalized:
            return FakeCursor(self.fixtures["capability_resources"][:params["limit"]])
        raise AssertionError("provider attempted an unrecognized query")

    def close(self):
        self.closed = True


def descriptor_and_configuration():
    manifest = json.loads((PACKAGE / "manifest.json").read_text())
    config = json.loads((PACKAGE / "config.example.json").read_text())
    _validate_plugin_config(config, manifest["configuration_schema"], "directory.config")
    return manifest, validate_operation(manifest["operation"]), config


class InstitutionalDirectoryProviderTests(unittest.TestCase):
    def setUp(self):
        self.manifest, self.descriptor, self.config = descriptor_and_configuration()
        self.fixture = ReadOnlyDirectoryFixture()
        self.provider = plugin.InstitutionalDirectoryProvider(
            self.config, connect=lambda dsn: self.fixture)

    def test_manifest_pins_provider_and_dynamic_operation(self):
        self.assertEqual(hashlib.sha256((PACKAGE / "plugin.py").read_bytes()).hexdigest(),
                         self.manifest["artifact_sha256"])
        self.assertEqual(self.manifest["artifact_sha256"], self.descriptor["provider"]["artifact_sha256"])
        self.assertEqual("institutional.directory.discover", self.descriptor["operation_id"])
        self.assertEqual(["institutional.directory.discover"], self.descriptor["required_grants"])
        self.assertEqual("read", self.descriptor["effect_class"])
        registry = CapabilityRegistry()
        registered = registry.register(self.descriptor, self.config, legacy_manifest=self.manifest)
        self.assertEqual("Institutional Directory Discover", registry.discover()[0]["presentation"]["name"])
        self.assertIsInstance(registered.load_provider(), plugin.InstitutionalDirectoryProvider)

    def test_authoritative_snapshot_is_bounded_hashed_and_read_only(self):
        env = patch.dict(os.environ, {"R3A_DIRECTORY_POSTGRES_DSN": "fixture-dsn-not-output"})
        with env:
            result = self.provider.invoke({}, context={})
        output, evidence = normalize_provider_result(result, self.descriptor)
        self.assertEqual("r3a.institutional-directory.v1", output["schema_id"])
        self.assertEqual("riverview_authority.directory", output["source"]["source_id"])
        self.assertEqual("fresh", output["source"]["freshness"])
        self.assertEqual("measured", output["source"]["availability"])
        self.assertFalse(output["source"]["potentially_truncated"])
        self.assertEqual(64, len(output["source"]["snapshot_sha256"]))
        self.assertEqual(2, len(output["offices"]))
        self.assertEqual("resident:grace", output["residents"][0]["resident_id"])
        self.assertIsNone(output["residents"][0]["display_name"])
        self.assertEqual("unavailable", output["residents"][0]["availability_state"])
        self.assertEqual("no_active_engineering_office",
                         output["capabilities"][0]["registration_blocker"])
        self.assertEqual("unavailable", output["capabilities"][0]["availability_state"])
        self.assertEqual("fixture:implementation",
                         output["capabilities"][0]["resources"][0]["implementation_ref"])
        self.assertEqual(1, output["source"]["row_counts"]["resources"])
        self.assertEqual("read_only_repeatable_read", output["source"]["transaction_isolation"])
        self.assertIn("engineering.assignment.execute", json.dumps(output))
        self.assertNotIn("fixture-dsn-not-output", json.dumps(output))
        sql = " ".join(statement.upper() for statement, _ in self.fixture.statements)
        self.assertIn("READ ONLY", sql)
        self.assertTrue(sql.strip().endswith("COMMIT"))
        self.assertNotRegex(sql, r"\b(INSERT|UPDATE|DELETE|ALTER|DROP|TRUNCATE)\b")
        self.assertTrue(self.fixture.closed)
        self.assertEqual("riverview_authority.directory", evidence[0]["source_id"])

    def test_missing_dsn_returns_explicit_unavailable_without_connection(self):
        called = []
        provider = plugin.InstitutionalDirectoryProvider(self.config,
                                                         connect=lambda dsn: called.append(dsn))
        env = patch.dict(os.environ, {"R3A_DIRECTORY_POSTGRES_DSN": ""})
        with env:
            result = provider.invoke({}, context={})
        output, evidence = normalize_provider_result(result, self.descriptor)
        self.assertEqual("unavailable", output["source"]["freshness"])
        self.assertEqual("directory_source_not_configured", output["source"]["error"])
        self.assertEqual([], called)
        self.assertIsNone(evidence[0]["snapshot_sha256"])

    def test_connection_failure_returns_unavailable_and_redacts_driver_detail(self):
        provider = plugin.InstitutionalDirectoryProvider(
            self.config, connect=lambda dsn: (_ for _ in ()).throw(RuntimeError(f"secret={dsn}")))
        env = patch.dict(os.environ, {"R3A_DIRECTORY_POSTGRES_DSN": "password-value"})
        with env:
            output, _ = normalize_provider_result(provider.invoke({}, context={}), self.descriptor)
        self.assertEqual("unavailable", output["source"]["availability"])
        self.assertEqual("directory_source_unavailable:RuntimeError", output["source"]["error"])
        self.assertNotIn("password-value", json.dumps(output))

    def test_filter_and_limit_are_applied_as_parameters(self):
        env = patch.dict(os.environ, {"R3A_DIRECTORY_POSTGRES_DSN": "fixture"})
        with env:
            result = self.provider.invoke({"office_id": "office:operations", "resident_id": "resident:grace", "limit": 1}, context={})
        output, _ = normalize_provider_result(result, self.descriptor)
        self.assertEqual(["office:operations"], [row["office_id"] for row in output["offices"]])
        query, parameters = next((query, params) for query, params in self.fixture.statements
                                 if "office_bindings" in query)
        self.assertIn("%(resident_id)s", query)
        self.assertIn("%(resident_id)s::text IS NULL", query)
        self.assertEqual("resident:grace", parameters["resident_id"])
        self.assertEqual(1, parameters["limit"])

    def test_dynamic_grace_tool_receives_directory_output_and_distinct_evidence(self):
        registry = CapabilityRegistry()
        registry.register(self.descriptor, self.config, legacy_manifest=self.manifest)
        registry.set_provider_state(self.descriptor["provider"]["provider_id"],
                                    self.descriptor["provider"]["provider_version"], "ACTIVE")
        instance = CME.__new__(CME)
        instance.settings = SimpleNamespace(capability_registry=registry,
                                            module_capabilities=(self.descriptor["operation_id"],),
                                            source_digest="cfg-directory-test")
        instance.module_id = "resident.grace"
        env = patch.dict(os.environ, {"R3A_DIRECTORY_POSTGRES_DSN": "fixture"})
        with env:
            raw = self.provider.invoke({}, context={})
            output, evidence = normalize_provider_result(raw, self.descriptor)
            instance.invoke_capability = AsyncMock(return_value={
                "contract_id": "r3a.capability-invocation.v1", "contract_version": "1.0.0",
                "invocation_id": "directory-invocation", "operation_id": self.descriptor["operation_id"],
                "operation_contract_version": self.descriptor["contract_version"],
                "provider": self.descriptor["provider"], "outcome": "SUCCEEDED",
                "started_at": "2026-11-08T01:00:00Z", "finished_at": "2026-11-08T01:00:01Z",
                "output": output, "evidence": evidence,
                "authorization": {"provider_id": "capability_grants", "allowed": True,
                                   "decision_id": "directory-decision", "audit_event_id": "directory-audit",
                                   "policy_revision": None, "config_revision": "cfg-directory-test"}})
            result = __import__("asyncio").run(instance._invoke_resident_capability(
                {"activity_id": "activity-1", "attempt_id": "attempt-1", "correlation_id": "corr-1"},
                {"contract_id": "r3a.resident-capability-tool", "contract_version": "1.0.0",
                 "capability_id": self.descriptor["operation_id"], "arguments": {}}))
        self.assertEqual("succeeded", result["outcome"])
        self.assertEqual("r3a.institutional-directory.v1", result["output"]["schema_id"])
        self.assertIn("engineering.assignment.execute",
                      {row["capability_id"] for row in result["output"]["capabilities"]})
        self.assertEqual("riverview_authority.directory", result["evidence"][0]["source_id"])
        self.assertTrue(result["evidence"][0]["source_path"].startswith("capability."))
        self.assertEqual(hashlib.sha256(result["evidence"][0]["content"].encode()).hexdigest(),
                         result["evidence"][0]["sha256"])
        self.assertEqual(64, len(result["evidence"][0]["source_sha256"]))
        self.assertTrue(result["authorization"]["audit_event_id"])
        instance.invoke_capability.assert_awaited_once()
        self.assertEqual("r3a.capability-invocation.v1",
                         instance.invoke_capability.await_args.args[0]["contract_id"])


if __name__ == "__main__":
    unittest.main()
