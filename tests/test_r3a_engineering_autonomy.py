"""Focused AP2 tests for model-action bounds and independent artifact verification."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from r3a_runtime.engineering import (CapabilityOperationRef, EngineeringWorkOrder,
                                    validate_engineering_assignment)
from r3a_runtime.engineering_verifier import verify_workspace_artifact
from r3a_runtime.grace_module import resident_action_schema


ASSIGNMENT = {
    "contract_id": "r3a.engineering-assignment", "contract_version": "1.0.0",
    "repository": "isolated/example", "baseline_ref": "integration-baseline",
    "workspace_id": "temporary-workspace", "allowed_paths": ["deliverables/**"],
    "command_profiles": ["bounded-file-write"], "verifier_id": "verifier.json-bindings",
    "verifier_version": "1.0.0", "policy_revision": "policy-v1",
    "criteria": [{"criterion_id": "operation-and-scope-match", "type": "json_fields_equal",
                   "artifact_path": "deliverables/review.json", "bindings": [
                       {"artifact_pointer": "/operation_id", "source": "operation", "source_pointer": "/operation_id"},
                       {"artifact_pointer": "/effect_class", "source": "operation", "source_pointer": "/effect_class"},
                       {"artifact_pointer": "/target/workspace_id", "source": "work_order", "source_pointer": "/workspace_id"}]}]}


def make_order(assignment):
    operation = CapabilityOperationRef("engineering.example.write", "1.0.0", "isolated_write",
                                       {"workspace_id": assignment["workspace_id"]},
                                       {"path": "deliverables/review.json", "content": "{}"})
    return EngineeringWorkOrder(
        work_order_id="55555555-5555-4555-8555-555555555555", work_order_version=1,
        activity_id="11111111-1111-4111-8111-111111111111",
        attempt_id="22222222-2222-4222-8222-222222222222",
        correlation_id="33333333-3333-4333-8333-333333333333",
        proposal_id="44444444-4444-4444-8444-444444444444", proposal_revision=1,
        proposal_digest="sha256:" + "a" * 64, resident_id="resident.grace", config_revision="cfg-v1",
        repository=assignment["repository"], baseline_ref=assignment["baseline_ref"],
        workspace_id=assignment["workspace_id"], allowed_paths=tuple(assignment["allowed_paths"]),
        command_profiles=tuple(assignment["command_profiles"]), operation_refs=(operation,),
        authorization_decision_id="decision-1", authorization_audit_event_id="audit-1",
        authorization_provider_id="fixture-grants", policy_revision="policy-v1",
        authorization_expires_at=None, criteria=tuple(assignment["criteria"]),
        issued_at="2026-11-07T15:00:00Z")


class EngineeringAutonomyBoundaryTests(unittest.TestCase):
    def test_assignment_criteria_are_scoped_and_typed(self):
        checked = validate_engineering_assignment(ASSIGNMENT)
        self.assertEqual("temporary-workspace", checked["workspace_id"])
        invalid = json.loads(json.dumps(ASSIGNMENT))
        invalid["criteria"][0]["artifact_path"] = "../escape.json"
        with self.assertRaises(ValueError):
            validate_engineering_assignment(invalid)

    def test_resident_schema_constrains_proposal_to_discovered_operations(self):
        schema = resident_action_schema([], [{"operation_id": "engineering.example.write"}])
        self.assertEqual(["engineering.example.write"],
                         schema["properties"]["proposal"]["properties"]["operation_id"]["enum"])

    def test_verifier_reads_artifact_and_compares_declared_operation_and_scope_bindings(self):
        assignment = validate_engineering_assignment(ASSIGNMENT)
        order = make_order(assignment)
        descriptor = {"operation_id": "engineering.example.write", "contract_version": "1.0.0",
                      "effect_class": "isolated_write", "required_grants": ["engineering.example.write"],
                      "recovery": {"replay_safe": True},
                      "configuration": {"workspace_root": "/"}}
        with tempfile.TemporaryDirectory(prefix="r3a-engineering-verifier-") as directory:
            descriptor["configuration"]["workspace_root"] = directory
            root = Path(directory)
            artifact = root / "deliverables/review.json"
            artifact.parent.mkdir()
            artifact.write_text(json.dumps({"operation_id": descriptor["operation_id"],
                                            "effect_class": descriptor["effect_class"],
                                            "target": {"workspace_id": order.workspace_id}}))
            result = verify_workspace_artifact(
                order, descriptor, directory, verifier_id="verifier.json-bindings",
                verifier_version="1.0.0", policy_revision="policy-v1")
            self.assertEqual("PASS", result.outcome)
            artifact.write_text('{"operation_id":"wrong","effect_class":"isolated_write",'
                                '"target":{"workspace_id":"temporary-workspace"}}')
            failed = verify_workspace_artifact(
                order, descriptor, directory, verifier_id="verifier.json-bindings",
                verifier_version="1.0.0", policy_revision="policy-v1")
            self.assertEqual("FAIL", failed.outcome)

    def test_work_order_round_trip_preserves_operation_and_acceptance(self):
        order = make_order(validate_engineering_assignment(ASSIGNMENT))
        self.assertEqual(order, EngineeringWorkOrder.from_dict(order.to_dict()))


if __name__ == "__main__":
    unittest.main()
