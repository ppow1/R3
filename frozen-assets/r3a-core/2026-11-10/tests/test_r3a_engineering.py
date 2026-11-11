"""
R3 CONTROLLED SOURCE
File: tests/test_r3a_engineering.py
Component: R3A-AP2-ENGINEERING-CONTRACT-TESTS
File Revision: 1.0.2
Created: 2026-11-07T05:28:24Z
Created By: Codex GPT-6
Purpose: Verify AP2 work-order lineage, effect references, criterion coverage, and fail-closed completion.
Execution Model: Python unittest with in-memory contract fixtures.
Observability: Deterministic contract validation results.
Dependencies: Python standard library; r3a_runtime engineering, authorization and persistence contracts.
Authority: AP2 R3A-011/R3A-012, Issue #43; isolated R3A only.
Changed: 2026-11-07T05:28:24Z | AP2-IMPLEMENTATION | Codex GPT-6 | Add focused AP2 contract and acceptance tests.
Changed: 2026-11-07T05:45:10Z | AP2-IMPLEMENTATION | Codex GPT-6 | Cover verifier requests, durable issuance, recovery lineage, and gated completion.
Changed: 2026-11-07T05:47:16Z | AP2-IMPLEMENTATION | Codex GPT-6 | Assert exact approved unified capability contract identities.
Changed: 2026-11-07T05:52:05Z | AP2-IMPLEMENTATION | Codex GPT-6 | Verify durable proposal revision round-trip and idempotent checkpoint persistence.
Changed: 2026-11-07T05:59:32Z | AP2-IMPLEMENTATION | Codex GPT-6 | Cover canonical request mapping and distinct authorization decision/audit provenance.
Supersedes: None.
Contracts: r3a.engineering-proposal.v1; r3a.engineering-work-order.v1; r3a.engineering-action.v1; r3a.verification-result.v1.
Tests: This test module.
History/Predecessor: Prior revision at AP2 commit 600020fd81b4b1e5ed4d938f95592560963a616d, blob 92607b908bdcc00e60ad796c2a62a1cb80f026ff.
"""
from __future__ import annotations

import json
import unittest
import asyncio
import copy
from contextlib import asynccontextmanager
from dataclasses import replace
from unittest.mock import AsyncMock
from pathlib import Path
from types import SimpleNamespace

from r3a_runtime.engineering import (
    CapabilityOperationRef,
    CriterionResult,
    EngineeringAction,
    EngineeringContractError,
    EngineeringProposal,
    EngineeringWorkOrder,
    VerificationRequest,
    VerificationResult,
    proposal_digest,
    validate_completion,
)
from r3a_runtime.authorization import AuthorizationDecision, AUTHORIZATION_CONTRACT_ID
from r3a_runtime.db import Store


ACTIVITY = "11111111-1111-4111-8111-111111111111"
ATTEMPT = "22222222-2222-4222-8222-222222222222"
CORRELATION = "33333333-3333-4333-8333-333333333333"
PROPOSAL = "44444444-4444-4444-8444-444444444444"
ORDER = "55555555-5555-4555-8555-555555555555"
ACTION = "66666666-6666-4666-8666-666666666666"
VERIFICATION = "77777777-7777-4777-8777-777777777777"
RECOVERY_ATTEMPT = "88888888-8888-4888-8888-888888888888"
CRITERIA = ({"criterion_id": "artifact_matches_scope", "description": "Artifact is in authorized scope."},
            {"criterion_id": "focused_checks_pass", "description": "Declared checks pass."})


def operation(effect: str = "isolated_write") -> CapabilityOperationRef:
    return CapabilityOperationRef("engineering.workspace.apply_patch", "1.0.0", effect,
                                  {"repository": "ppow1/R3", "workspace_id": "candidate-1"},
                                  {"patch_ref": "patch:sha256:abc"})


def work_order() -> EngineeringWorkOrder:
    return EngineeringWorkOrder(
        work_order_id=ORDER, work_order_version=1, activity_id=ACTIVITY,
        attempt_id=ATTEMPT, correlation_id=CORRELATION, proposal_id=PROPOSAL,
        proposal_revision=1, proposal_digest="sha256:" + "a" * 64,
        resident_id="resident.grace", config_revision="cfg-17", repository="ppow1/R3",
        baseline_ref="9925c7a408707162e6f070a4121dcc83f5fe0e0a", workspace_id="candidate-1",
        allowed_paths=("r3a_runtime/**", "tests/**"), command_profiles=("python-unittest-focused",),
        operation_refs=(operation(),), authorization_decision_id="decision-123",
        authorization_audit_event_id="audit-456",
        authorization_provider_id="capability_grants", policy_revision=None,
        authorization_expires_at="2026-11-07T06:00:00Z",
        criteria=CRITERIA, issued_at="2026-11-07T05:30:00Z")


def proposal() -> EngineeringProposal:
    return EngineeringProposal(
        proposal_id=PROPOSAL, proposal_revision=1, activity_id=ACTIVITY,
        attempt_id=ATTEMPT, correlation_id=CORRELATION, resident_id="resident.grace",
        config_revision="cfg-17", created_at="2026-11-07T05:30:00Z",
        objective="Investigate the observed observer-activity rate.", criteria=CRITERIA,
        repository="ppow1/R3", baseline_ref="9925c7a408707162e6f070a4121dcc83f5fe0e0a",
        scope={"workspace": "isolated"}, proposed_operations=(operation("read"),),
        verification_plan={"profiles": ["python-unittest-focused"]},
        reasoning_provenance={"model_request_ref": "req-1", "model_result_ref": "res-1"})


def verification(*, outcome: str = "PASS", activity_id: str = ACTIVITY,
                 order_id: str = ORDER, order_version: int = 1,
                 criterion_results: tuple[CriterionResult, ...] | None = None) -> VerificationResult:
    results = criterion_results or (
        CriterionResult("artifact_matches_scope", "PASS", ("evidence:artifact",), "Digest and path match."),
        CriterionResult("focused_checks_pass", "PASS", ("evidence:test-run",), "Focused checks passed."),
    )
    return VerificationResult(
        verification_id=VERIFICATION, activity_id=activity_id, work_order_id=order_id,
        work_order_version=order_version, verifier_id="verifier.clean-workspace",
        verifier_version="1.0.0", policy_revision="verify-policy-2",
        artifact_digests=("sha256:" + "b" * 64,), results=results,
        verified_at="2026-11-07T05:45:00Z", outcome=outcome)


def authorization(*, allowed: bool = True) -> AuthorizationDecision:
    return AuthorizationDecision(
        contract_id=AUTHORIZATION_CONTRACT_ID, contract_version="1.0.0",
        provider_id="capability_grants", allowed=allowed, reason="recorded grant decision",
        retryable=False, policy_revision=None, config_revision="cfg-17",
        observed_at="2026-11-07T05:30:00Z", correlation_id=CORRELATION,
        activity_id=ACTIVITY, attempt_id=ATTEMPT, audit_event_id="audit-456",
        decision_id="decision-123")


def store_for_order(state: str, details: dict) -> Store:
    store = Store.__new__(Store)
    cursor = SimpleNamespace(fetchone=AsyncMock(return_value={"state": state, "details": copy.deepcopy(details)}))
    connection = SimpleNamespace(execute=AsyncMock(return_value=cursor))

    @asynccontextmanager
    async def transaction():
        yield

    @asynccontextmanager
    async def connection_scope():
        yield connection

    connection.transaction = transaction
    store.pool = SimpleNamespace(connection=lambda: connection_scope())
    store._transition_on_conn = AsyncMock(return_value=True)
    return store


class EngineeringContractTests(unittest.TestCase):
    def test_grace_proposal_retains_objective_criteria_plan_and_reasoning_provenance(self):
        proposal_value = proposal()
        data = proposal_value.to_dict()
        self.assertEqual(data["contract_id"], "r3a.engineering-proposal")
        self.assertEqual(data["reasoning_provenance"]["model_result_ref"], "res-1")
        self.assertEqual(data["criteria"], list(CRITERIA))
        self.assertEqual(EngineeringProposal.from_dict(data), proposal_value)
        self.assertEqual(len(proposal_digest(proposal_value)), len("sha256:") + 64)

    def test_proposal_is_durably_checkpointed_on_activity_with_idempotent_revision(self):
        store = Store.__new__(Store)
        store.record_progress = AsyncMock()
        activity = {"activity_id": ACTIVITY, "attempt_id": ATTEMPT, "checkpoint": {},
                    "input": {"objective": proposal().objective, "correlation_id": CORRELATION}}
        first = asyncio.run(store.record_engineering_proposal(activity, proposal()))
        self.assertTrue(first["recorded"])
        checkpoint = store.record_progress.await_args.args[2]
        self.assertEqual(checkpoint["engineering_proposal"]["proposal_id"], PROPOSAL)
        self.assertEqual(checkpoint["engineering_proposal_digest"], proposal_digest(proposal()))

        activity["checkpoint"] = checkpoint
        same = asyncio.run(store.record_engineering_proposal(activity, proposal()))
        self.assertFalse(same["recorded"])
        self.assertEqual(store.record_progress.await_count, 1)

        changed = replace(proposal(), reasoning_provenance={"model_request_ref": "req-2"})
        with self.assertRaisesRegex(ValueError, "immutable once durably recorded"):
            asyncio.run(store.record_engineering_proposal(activity, changed))

    def test_work_order_binds_unified_operation_and_serializes_lineage(self):
        order = work_order()
        data = order.to_dict()
        json.dumps(data)
        self.assertEqual(data["operation_refs"][0]["contract_id"], "r3a.capability-operation.v1")
        self.assertEqual(data["operation_refs"][0]["effect_class"], "isolated_write")
        self.assertEqual(data["activity_id"], ACTIVITY)
        self.assertEqual(data["authorization_decision_id"], "decision-123")

    def test_work_order_preserves_provider_defined_authorization_expiry_without_inventing_one(self):
        self.assertIsNone(replace(work_order(), authorization_expires_at=None).authorization_expires_at)
        with self.assertRaisesRegex(EngineeringContractError, "must follow issued_at"):
            replace(work_order(), authorization_expires_at="2026-11-07T05:00:00Z")

    def test_isolated_write_target_cannot_escape_work_order_workspace(self):
        with self.assertRaisesRegex(EngineeringContractError, "must match the authorized workspace"):
            replace(work_order(), operation_refs=(CapabilityOperationRef(
                "engineering.workspace.apply_patch", "1.0.0", "isolated_write",
                {"workspace_id": "other-workspace", "repository": "ppow1/R3"},
                {"patch_ref": "patch:sha256:abc"}),))
        with self.assertRaisesRegex(EngineeringContractError, "workspace-relative"):
            replace(work_order(), allowed_paths=("../outside",))

    def test_durable_order_creation_requires_and_persists_provider_decision(self):
        store = Store.__new__(Store)
        store.get_engineering_work_order = AsyncMock(return_value=None)
        store.transition = AsyncMock(return_value=True)
        accepted = asyncio.run(store.create_engineering_work_order(work_order().to_dict(), authorization()))
        self.assertTrue(accepted)
        args = store.transition.await_args
        self.assertEqual(args.args[:5], ("engineering_work_order", ORDER, "engineering.work-order", 1,
                                         "AUTHORIZED"))
        self.assertEqual(str(args.kwargs["correlation_id"]), CORRELATION)
        self.assertEqual(str(args.kwargs["causation_id"]), ATTEMPT)
        self.assertEqual(args.args[6]["authorization"]["authorization_decision_id"], "decision-123")
        self.assertEqual(args.args[6]["authorization"]["authorization_audit_event_id"], "audit-456")

    def test_durable_order_creation_is_idempotent_and_rejects_changed_content(self):
        order = work_order().to_dict()
        auth_record = {"authorization_decision_id": "decision-123", "authorization_audit_event_id": "audit-456",
                       "provider_id": "capability_grants",
                       "allowed": True, "reason": "recorded grant decision", "retryable": False,
                       "policy_revision": None, "config_revision": "cfg-17",
                       "observed_at": "2026-11-07T05:30:00Z", "correlation_id": CORRELATION,
                       "activity_id": ACTIVITY, "attempt_id": ATTEMPT}
        store = Store.__new__(Store)
        store.get_engineering_work_order = AsyncMock(return_value={
            "state": "EXECUTING", "details": {"work_order": copy.deepcopy(order),
                                                  "authorization": copy.deepcopy(auth_record),
                                                  "activity_id": ACTIVITY, "correlation_id": CORRELATION}})
        store.transition = AsyncMock()
        self.assertTrue(asyncio.run(store.create_engineering_work_order(order, authorization())))
        store.transition.assert_not_awaited()
        order["baseline_ref"] = "changed"
        with self.assertRaisesRegex(ValueError, "already exists"):
            asyncio.run(store.create_engineering_work_order(order, authorization()))

    def test_completion_transition_requires_exact_durable_order_and_verifier_pass(self):
        order_object = work_order()
        order = order_object.to_dict()
        store = store_for_order("VERIFYING", {
            "contract_id": "r3a.engineering-work-order", "contract_version": "1.0.0",
            "work_order": order, "authorization": {"authorization_decision_id": "decision-123"},
            "activity_id": ACTIVITY, "attempt_id": ATTEMPT, "correlation_id": CORRELATION})
        accepted = asyncio.run(store.transition_engineering_work_order(
            ORDER, "COMPLETED", ACTIVITY, RECOVERY_ATTEMPT, CORRELATION,
            "independent verifier passed all criteria", {}, work_order=order_object,
            verification=verification()))
        self.assertTrue(accepted)
        args = store._transition_on_conn.await_args
        self.assertEqual(str(args.kwargs["causation_id"]), RECOVERY_ATTEMPT)
        self.assertEqual(args.args[7]["attempt_id"], ATTEMPT)
        self.assertEqual(args.args[7]["transition_attempt_id"], RECOVERY_ATTEMPT)
        self.assertEqual(args.args[7]["verification_result"]["outcome"], "PASS")

    def test_completion_transition_fails_closed_for_nonpassing_result(self):
        order_object = work_order()
        store = store_for_order("VERIFYING", {"work_order": order_object.to_dict(),
                                                "activity_id": ACTIVITY, "attempt_id": ATTEMPT,
                                                "correlation_id": CORRELATION})
        failed = verification(outcome="FAIL", criterion_results=(
            CriterionResult("artifact_matches_scope", "FAIL", ("evidence:artifact",), "Scope exceeded."),
            CriterionResult("focused_checks_pass", "PASS", ("evidence:test",), "Tests passed.")))
        with self.assertRaisesRegex(EngineeringContractError, "requires independent verification PASS"):
            asyncio.run(store.transition_engineering_work_order(
                ORDER, "COMPLETED", ACTIVITY, ATTEMPT, CORRELATION,
                "must reject failed verifier", {}, work_order=order_object, verification=failed))
        store._transition_on_conn.assert_not_awaited()

    def test_generic_transition_cannot_bypass_work_order_completion_gate(self):
        store = Store.__new__(Store)
        with self.assertRaisesRegex(PermissionError, "independent verification gate"):
            asyncio.run(store.transition("engineering_work_order", ORDER,
                                         "engineering.work-order", 1, "COMPLETED",
                                         "unsafe direct completion"))

    def test_operation_effects_are_metadata_not_separate_families(self):
        for effect in ("read", "isolated_write", "external_write"):
            self.assertEqual(operation(effect).effect_class, effect)
        with self.assertRaises(EngineeringContractError):
            operation("unknown_write")

    def test_completion_requires_exact_order_version_and_all_criteria(self):
        order = work_order()
        validate_completion(order, verification())
        with self.assertRaisesRegex(EngineeringContractError, "different work-order version"):
            validate_completion(order, verification(order_version=2))
        partial = verification(criterion_results=(
            CriterionResult("artifact_matches_scope", "PASS", ("evidence:artifact",), "Digest and path match."),))
        with self.assertRaisesRegex(EngineeringContractError, "exactly the work-order criteria"):
            validate_completion(order, partial)

    def test_completion_rejects_failed_or_inconclusive_verification(self):
        order = work_order()
        failed = verification(outcome="FAIL", criterion_results=(
            CriterionResult("artifact_matches_scope", "FAIL", (), "Artifact exceeded scope."),
            CriterionResult("focused_checks_pass", "PASS", ("evidence:test-run",), "Checks passed."),))
        inconclusive = verification(outcome="INCONCLUSIVE", criterion_results=(
            CriterionResult("artifact_matches_scope", "PASS", ("evidence:artifact",), "Digest matches."),
            CriterionResult("focused_checks_pass", "INCONCLUSIVE", (), "Verifier could not run profile."),))
        for result in (failed, inconclusive):
            with self.assertRaisesRegex(EngineeringContractError, "requires independent verification PASS"):
                validate_completion(order, result)

    def test_state_machine_requires_authorization_and_verification_before_completion(self):
        path = Path(__file__).parents[1] / "r3a_runtime/state_machines/engineering_work_order.json"
        machine = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(machine["machine_id"], "engineering.work-order")
        transitions = machine["transitions"]
        self.assertNotIn("PROPOSED", transitions)
        self.assertNotIn("COMPLETED", transitions["AUTHORIZED"])
        self.assertIn("VERIFYING", transitions["EXECUTING"])
        self.assertIn("COMPLETED", transitions["VERIFYING"])
        self.assertIn("EXECUTING", transitions["REWORK_REQUIRED"])
        self.assertEqual(machine["terminal"], ["COMPLETED", "CANCELLED"])
        self.assertIn("RECOVERING", transitions["BLOCKED"])

    def test_action_uses_canonical_invocation_envelope_and_stable_identity(self):
        action = EngineeringAction(
            action_id=ACTION, idempotency_key=f"{ORDER}:1:1", work_order_id=ORDER,
            work_order_version=1, activity_id=ACTIVITY, attempt_id=ATTEMPT,
            correlation_id=CORRELATION, operation=operation(), caller_id="resident.grace",
            requested_at="2026-11-07T05:30:00Z", config_revision="cfg-17",
            evidence_purpose="Apply the authorized isolated patch.")
        data = action.to_dict()
        request = data["invocation_request"]
        self.assertEqual(request["contract_id"], "r3a.capability-invocation.v1")
        self.assertEqual(request["contract_version"], "1.0.0")
        self.assertEqual(request["operation_contract_version"], "1.0.0")
        self.assertEqual(request["idempotency_key"], f"{ORDER}:1:1")
        self.assertEqual(request["input"], operation().inputs)
        self.assertEqual(request["target"], operation().target)
        self.assertEqual(request["work_order"], {"work_order_id": ORDER, "version": 1})
        self.assertNotIn("authorization", request)
        self.assertNotIn("authorization_decision_id", request)
        self.assertEqual(set(request), {"contract_id", "contract_version", "invocation_id", "operation_id",
                                        "operation_contract_version", "caller", "target", "input", "activity_id",
                                        "attempt_id", "correlation_id", "work_order", "evidence_purpose",
                                        "idempotency_key", "deadline", "config_revision"})

    def test_verification_request_is_bound_to_candidate_and_criteria(self):
        request = VerificationRequest(
            verification_id=VERIFICATION, activity_id=ACTIVITY, work_order_id=ORDER,
            work_order_version=1, verifier_id="verifier.clean-workspace",
            verifier_version="1.0.0", config_revision="cfg-17",
            criterion_ids=("artifact_matches_scope", "focused_checks_pass"),
            artifact_digests=("sha256:" + "b" * 64,),
            evidence_refs=("evidence:execution", "evidence:artifact"),
            requested_at="2026-11-07T05:40:00Z")
        data = request.to_dict()
        self.assertEqual(data["contract_id"], "r3a.verification-request")
        self.assertEqual(data["work_order_id"], ORDER)
        self.assertEqual(len(data["criterion_ids"]), 2)

if __name__ == "__main__":
    unittest.main()
