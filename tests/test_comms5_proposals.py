# R3 CONTROLLED TEST
# File: tests/test_comms5_proposals.py
# Component: R3-COMMS5-PROPOSAL-ADAPTER-TESTS
# File Revision: 1.1.0
# Created: 2026-11-06T01:39:36Z
# Created By: Codex GPT-6, acting on Steward instruction
# Purpose: Verify the narrow proposal-draft Comms5 contract, safe status reporting, and idempotency.
# Execution Model: Isolated fake Comms5 operation adapter; no live service calls.
# Observability: Operation names and sanitized lifecycle metadata asserted in memory.
# Dependencies: runtime.comms5_proposals; Python standard library.
# Authority: Grace Autonomy P1; tests must not create institutional or production records.
# Changed: 2026-11-06T01:39:36Z | GRACE-PROPOSAL-P1 | Codex GPT-6 | Add permanent adapter contract tests.
# Changed: 2026-11-06T01:48:39Z | GRACE-PROPOSAL-P1 | Codex GPT-6 | Assert proposal progress and lifecycle truthfulness remain in Grace's loaded prompt.
# Changed: 2026-11-06T01:48:39Z | GRACE-PROPOSAL-P1 | Codex GPT-6 | Verify a readback's lifecycle controls approval claims.
# Changed: 2026-11-06T02:15:00Z | GRACE-AUTONOMY-P2 | Codex GPT-6 | Verify bounded read-only proposal/objective lifecycle projections.
# Supersedes: None
# Contracts: riverview-comms-contract:5.0; hints/engineering-test-policy.md
# Tests: `python -m unittest tests.test_comms5_proposals -v`
# History/Predecessor: New file; no predecessor.
import tempfile
import unittest
from pathlib import Path

from runtime.comms5_proposals import (
    Comms5DraftClient,
    ProposalSubmissionError,
    objective_status_capability,
    proposal_status_capability,
    read_bearer_token,
)
from runtime.configuration import load_configuration


class Comms5DraftClientTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.readback = {
            "status": "available",
            "executed": True,
            "seed_id": "seed:test-1",
            "proposal_id": "proposal:test-1",
            "revision": 1,
            "lifecycle_status": "DRAFT",
            "content_sha256": "0" * 64,
            "revision_record": {
                "title": "Clock proposal",
                "objective": "Add a date and time clock",
            },
        }

        def call_tool(operation, arguments):
            self.calls.append((operation, arguments))
            if operation == "submit_steward_seed":
                return {
                    "status": "submitted",
                    "executed": True,
                    "seed_id": "seed:test-1",
                    "proposal_id": "proposal:test-1",
                    "revision": 1,
                    "lifecycle_status": "DRAFT",
                }
            if operation == "seed_status":
                return self.readback
            if operation == "objective_status":
                return {
                    "status": "available", "executed": True,
                    "objective": {"objective_id": "objective:test-1", "state": "WORK_ORDER_CREATED",
                                  "revision": 3, "evidence": {"must_not_escape": "private"}},
                    "assignment": {"state": "rework_required", "description": "must not escape"},
                    "verification": {"decision": "INCONCLUSIVE", "summary": "must not escape"},
                    "execution_intents": [{"status": "succeeded", "command": "must not escape"}],
                    "event_lineage": [{"event_type": "work", "details": "must not escape"}],
                }
            raise AssertionError("Unexpected Comms5 operation")

        self.client = Comms5DraftClient(
            "https://comms.example/mcp", "test-bearer",
            call_tool=call_tool,
        )

    def test_submission_uses_only_draft_write_then_authorized_status_read(self):
        result = self.client.submit(
            "Title: Clock\nObjective: Show local date and time.",
            principal="resident:Grace",
            correlation_id="call-clock-1",
        )
        self.assertEqual([name for name, _ in self.calls], [
            "submit_steward_seed", "seed_status",
        ])
        submitted = self.calls[0][1]
        self.assertEqual(submitted["authenticated_principal"], "resident:Grace")
        self.assertEqual(submitted["seed_text"], "Title: Clock\nObjective: Show local date and time.")
        self.assertTrue(submitted["idempotency_key"].startswith("r3-proposal-"))
        self.assertEqual(self.calls[1][1], {"seed_id": "seed:test-1"})
        self.assertEqual(result, {
            "status": "persisted",
            "proposal_id": "proposal:test-1",
            "seed_id": "seed:test-1",
            "revision": 1,
            "lifecycle_status": "DRAFT",
            "persisted": True,
            "steward_decision_required": True,
            "approval_granted": False,
        })
        self.assertNotIn("revision_record", result)

    def test_idempotency_key_is_stable_for_same_principal_and_call(self):
        first = self.client._idempotency_key("resident:Grace", "call-clock-1")
        retry = self.client._idempotency_key("resident:Grace", "call-clock-1")
        next_call = self.client._idempotency_key("resident:Grace", "call-clock-2")
        self.assertEqual(first, retry)
        self.assertNotEqual(first, next_call)

    def test_body_reader_mismatch_returns_unverified_without_approval_claim(self):
        self.readback["proposal_id"] = "proposal:other"
        result = self.client.submit(
            "Clock proposal", principal="resident:Grace", correlation_id="call-2",
        )
        self.assertEqual(result["status"], "submission_readback_unverified")
        self.assertEqual(result["proposal_id"], "proposal:test-1")
        self.assertFalse(result["persisted"])
        self.assertFalse(result["approval_granted"])
        self.assertTrue(result["reconcile_before_retry"])

    def test_existing_approved_status_is_reported_from_authoritative_readback(self):
        self.readback["lifecycle_status"] = "APPROVED"
        result = self.client.submit(
            "Clock proposal", principal="resident:Grace", correlation_id="call-approved",
        )
        self.assertEqual(result["lifecycle_status"], "APPROVED")
        self.assertTrue(result["approval_granted"])
        self.assertFalse(result["steward_decision_required"])

    def test_proposal_status_is_read_only_and_omits_protected_content(self):
        result = self.client.proposal_status("seed:test-1")
        self.assertEqual(self.calls, [("seed_status", {"seed_id": "seed:test-1"})])
        self.assertEqual(result["seed_id"], "seed:test-1")
        self.assertEqual(result["lifecycle_status"], "DRAFT")
        self.assertNotIn("revision_record", result)

    def test_objective_status_returns_bounded_execution_and_review_state(self):
        result = self.client.objective_status("objective:test-1")
        self.assertEqual(self.calls, [("objective_status", {"objective_id": "objective:test-1"})])
        self.assertEqual(result["lifecycle_status"], "WORK_ORDER_CREATED")
        self.assertEqual(result["assignment_status"], "rework_required")
        self.assertEqual(result["verification_status"], "INCONCLUSIVE")
        self.assertEqual(result["execution_status"], "succeeded")
        self.assertNotIn("evidence", result)
        self.assertNotIn("event_lineage", result)

    def test_lifecycle_capabilities_are_fixed_read_only_operations(self):
        proposal = proposal_status_capability(self.client)
        objective = objective_status_capability(self.client)
        self.assertTrue(proposal.read_only)
        self.assertTrue(objective.read_only)
        self.assertEqual(proposal.action, "proposal.status.read")
        self.assertEqual(objective.action, "objective.status.read")
        self.assertEqual(proposal.scope_ref, "institution:proposal-drafts")
        self.assertEqual(objective.scope_ref, "institution:objective-status")

    def test_oversized_or_invalid_drafts_never_call_comms5(self):
        with self.assertRaises(ProposalSubmissionError):
            self.client.submit("é" * 4001, principal="resident:Grace", correlation_id="call-3")
        with self.assertRaises(ProposalSubmissionError):
            self.client.submit("draft", principal="resident:Grace", correlation_id="bad correlation")
        self.assertEqual(self.calls, [])

    def test_unavailable_transport_does_not_claim_persistence(self):
        def fail(operation, arguments):
            raise OSError("private transport detail")

        client = Comms5DraftClient("https://comms.example/mcp", "test-bearer", call_tool=fail)
        with self.assertRaisesRegex(ProposalSubmissionError, "reconciled") as caught:
            client.submit("draft", principal="resident:Grace", correlation_id="call-4")
        self.assertNotIn("private transport detail", str(caught.exception))

    def test_credential_file_must_be_private(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "token"
            path.write_text("test-token\n", encoding="utf-8")
            path.chmod(0o600)
            self.assertEqual(read_bearer_token(path), "test-token")
            path.chmod(0o644)
            with self.assertRaises(ProposalSubmissionError):
                read_bearer_token(path)

    def test_grace_prompt_requires_drafting_and_truthful_lifecycle_states(self):
        root = Path(__file__).resolve().parents[1]
        configuration = load_configuration(root / "config")
        grace = next(x for x in configuration["residents"]
                     if x["settings"]["name"] == "Grace")
        prompt = grace["system_prompt"]
        self.assertIn("make substantive progress on the draft", prompt)
        self.assertIn("drafted, durably persisted, submitted for Steward decision", prompt)
        self.assertIn("Claim each state only when the corresponding authoritative operation returns evidence", prompt)
        self.assertIn("use the corresponding read-only Comms5 status tool", prompt)
        self.assertIn("a queued work order is not execution", prompt)


if __name__ == "__main__":
    unittest.main()
