"""Release contract and isolated artifact checks for the Engineering workspace provider."""
# R3 CONTROLLED SOURCE
# File: tests/test_r3a_engineering_provider.py
# Component: R3A-ENGINEERING-WORKSPACE-TEST
# File Revision: 1.0.0
# Created: 2026-11-08 UTC
# Created By: Codex GPT-6
# Purpose: Validate the manifest-pinned workspace operation, configured write bound, and independent artifact verification.
# Execution Model: Isolated temporary workspace; no CME service or managed data access.
# Observability: Manifest/provider digests, actual artifact bytes, verifier criterion evidence.
# Dependencies: R3A canonical capability and Engineering contracts.
# Authority: Steward standing backlog, Issue #43 comment 6725061460.
# Changed: Initial release-readiness checks for isolated Engineering provider.
# Supersedes: None.
# Contracts: r3a.capability-operation.v1; r3a.engineering-work-order.v1; r3a.verification-result.v1.
# Tests: Self.
# History/Predecessor: New test module.

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from r3a_runtime.capability_contracts import CapabilityRegistry, operation_from_manifest, validate_operation
from r3a_runtime.config import _validate_plugin_config
from r3a_runtime.engineering import CapabilityOperationRef, EngineeringWorkOrder
from r3a_runtime.engineering_verifier import verify_workspace_artifact


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "r3a_plugins/engineering_workspace"


class EngineeringWorkspaceProviderTests(unittest.TestCase):
    def test_release_manifest_pins_adapter_and_provider_and_config_is_external(self):
        manifest = json.loads((PACKAGE / "manifest.json").read_text())
        adapter = PACKAGE / manifest["artifact_ref"]
        operation = manifest["operation"]
        provider_path = ROOT / "r3a_runtime/providers/isolated_workspace.py"
        self.assertEqual(manifest["artifact_sha256"], hashlib.sha256(adapter.read_bytes()).hexdigest())
        self.assertEqual(operation["provider"]["artifact_sha256"],
                         hashlib.sha256(provider_path.read_bytes()).hexdigest())
        self.assertEqual("isolated_write", operation["effect_class"])
        self.assertEqual([operation["operation_id"]], operation["required_grants"])
        self.assertEqual("work_order", operation["recovery"]["idempotency_scope"])
        self.assertTrue(operation["recovery"]["replay_safe"])
        config = json.loads((PACKAGE / "config.example.json").read_text())
        _validate_plugin_config(config, manifest["configuration_schema"], "engineering_workspace.config")

    def test_registered_provider_creates_bounded_artifact_and_verifier_reads_it_independently(self):
        with tempfile.TemporaryDirectory(prefix="r3a-engineering-provider-") as temporary:
            root = Path(temporary)
            manifest = json.loads((PACKAGE / "manifest.json").read_text())
            operation = validate_operation(operation_from_manifest(manifest))
            configuration = {"workspace_root": str(root), "maximum_file_bytes": 512}
            _validate_plugin_config(configuration, manifest["configuration_schema"], "test.config")
            registered = CapabilityRegistry().register(operation, configuration, legacy_manifest=manifest)
            provider = registered.load_provider()
            workspace_id = "isolated-test-workspace"
            content = json.dumps({"workspace_id": workspace_id, "change": "bounded test artifact"})
            context = {"effect_class": "isolated_write", "target": {"workspace_id": workspace_id},
                       "work_order": {"workspace_id": workspace_id, "allowed_paths": ["deliverables/**"]},
                       "invocation_id": "first"}
            arguments = {"path": "deliverables/result.json", "content": content}
            first = provider.invoke(arguments, context=context)
            self.assertEqual(hashlib.sha256(content.encode()).hexdigest(), first["sha256"])
            self.assertEqual(content.encode(), (root / arguments["path"]).read_bytes())
            replay = provider.invoke(arguments, context={**context, "invocation_id": "recovery"})
            self.assertTrue(replay["replayed"])
            with self.assertRaisesRegex(FileExistsError, "different bytes"):
                provider.invoke({**arguments, "content": "different"}, context=context)

            operation_ref = CapabilityOperationRef(
                operation["operation_id"], operation["contract_version"], "isolated_write",
                {"workspace_id": workspace_id}, arguments)
            order = EngineeringWorkOrder(
                work_order_id="55555555-5555-4555-8555-555555555555", work_order_version=1,
                activity_id="11111111-1111-4111-8111-111111111111",
                attempt_id="22222222-2222-4222-8222-222222222222",
                correlation_id="33333333-3333-4333-8333-333333333333",
                proposal_id="44444444-4444-4444-8444-444444444444", proposal_revision=1,
                proposal_digest="sha256:" + "a" * 64, resident_id="resident.fixture",
                config_revision="config-fixture", repository="isolated/example", baseline_ref="fixture",
                workspace_id=workspace_id, allowed_paths=("deliverables/**",), command_profiles=("file-write",),
                operation_refs=(operation_ref,), authorization_decision_id="decision-fixture",
                authorization_audit_event_id="audit-fixture", authorization_provider_id="fixture",
                policy_revision="policy-fixture", authorization_expires_at=None,
                criteria=({"criterion_id": "workspace-binding", "type": "json_fields_equal",
                           "artifact_path": "deliverables/result.json", "bindings": [
                               {"artifact_pointer": "/workspace_id", "source": "work_order",
                                "source_pointer": "/workspace_id"}]},),
                issued_at="2026-11-08T00:00:00Z")
            verification = verify_workspace_artifact(
                order, operation, root, verifier_id="verifier.json-bindings",
                verifier_version="1.0.0", policy_revision="fixture-policy")
            self.assertEqual("PASS", verification.outcome)
            self.assertEqual("PASS", verification.results[0].status)
            self.assertIn("sha256:" + first["sha256"], verification.artifact_digests)

    def test_invalid_scope_and_oversized_file_have_no_write_effect(self):
        with tempfile.TemporaryDirectory(prefix="r3a-engineering-bound-") as temporary:
            root = Path(temporary)
            manifest = json.loads((PACKAGE / "manifest.json").read_text())
            registry = CapabilityRegistry()
            registered = registry.register(validate_operation(operation_from_manifest(manifest)),
                                           {"workspace_root": str(root), "maximum_file_bytes": 4},
                                           legacy_manifest=manifest)
            provider = registered.load_provider()
            context = {"effect_class": "isolated_write", "target": {"workspace_id": "w1"},
                       "work_order": {"workspace_id": "w1", "allowed_paths": ["deliverables/**"]},
                       "invocation_id": "bounded"}
            with self.assertRaisesRegex(ValueError, "configured maximum_file_bytes"):
                provider.invoke({"path": "deliverables/large.txt", "content": "12345"}, context=context)
            with self.assertRaisesRegex(PermissionError, "outside the authorized isolated workspace"):
                provider.invoke({"path": "deliverables/scope.txt", "content": "x"},
                                context={**context, "target": {"workspace_id": "other"}})
            self.assertFalse((root / "deliverables/large.txt").exists())
            self.assertFalse((root / "deliverables/scope.txt").exists())


if __name__ == "__main__":
    unittest.main()
