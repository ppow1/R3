# R3 CONTROLLED SOURCE
# File: tests/test_verification.py
# Component: R3-VERIFICATION-LEARNING-REGRESSION
# File Revision: 1.2.0
# Created: 2026-11-02 UTC (exact time unverified)
# Created By: ChatGPT GPT-6
# Purpose: Permanent regression for criterion identity and non-automatic learning changes.
# Execution Model: Standard-library unittest, isolated in-memory SQLite.
# Observability: Test assertions.
# Dependencies: runtime/verification.py
# Authority: hints/engineering-test-policy.md
# Changed: 2026-11-02 UTC | R3-VERIFY-LEARN-003 | Initial general-purpose contract tests.
# Changed: 2026-11-02 UTC | R3-VERIFY-LEARN-005 | Cover idempotent review submission and completion integration.
# Changed: 2026-11-02 UTC | R3-VERIFY-LEARN-007 | Test independent criterion review decisions and incomplete evidence.
# Supersedes: None
# Contracts: hints/verification-and-learning.md
# Tests: This file.
# History/Predecessor: Git blob 6321d08d6a041326ab3b7b346c6db1157b3f9500
import sqlite3
import unittest

from runtime.verification import VerificationLedger


class VerificationLedgerTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.ledger = VerificationLedger(self.db)

    def finding(self, review, criterion, result, reason, revision):
        return self.ledger.record_finding(
            assignment_id="assignment", review_id=review, criterion_id=criterion,
            criterion_version="v1", implementation_revision=revision,
            result=result, reason=reason, evidence={"observation": reason},
            reviewer="independent-reviewer")

    def test_criteria_remain_distinct_across_corrections(self):
        self.finding("r1", "A", "FAIL", "missing behavior", "i1")
        self.finding("r2", "A", "PASS", "behavior observed", "i2")
        self.finding("r2", "B", "FAIL", "regression", "i2")
        self.assertEqual([x["result"] for x in self.ledger.history("assignment", "A")],
                         ["FAIL", "PASS"])
        self.assertEqual([x["result"] for x in self.ledger.history("assignment", "B")],
                         ["FAIL"])

    def test_repeated_criterion_preserves_different_reasons(self):
        self.finding("r1", "A", "FAIL", "incorrect output", "i1")
        self.finding("r2", "A", "FAIL", "missing evidence", "i2")
        self.assertEqual([x["reason"] for x in self.ledger.history("assignment", "A")],
                         ["incorrect output", "missing evidence"])

    def test_improvement_is_candidate_not_automatic_policy(self):
        finding = self.finding("r1", "A", "FAIL", "ambiguous tolerance", "i1")
        candidate = self.ledger.propose_improvement(
            source_finding_id=finding, summary="Clarify tolerances",
            hypothesis="Work orders omitted required tolerance",
            evidence={"finding": finding}, expected_benefit="Fewer ambiguous reviews",
            risks="Over-specific requirements")
        self.assertEqual(self.ledger.candidate(candidate)["status"], "CANDIDATE")
        self.ledger.evaluate_candidate(candidate, disposition="DEFERRED",
                                       reason="Gather more evidence", actor="reviewer")
        self.assertEqual(self.ledger.candidate(candidate)["status"], "DEFERRED")
        with self.assertRaises(ValueError):
            self.ledger.evaluate_candidate(candidate, disposition="IMPLEMENTED",
                                           reason="Apply change", actor="reviewer")

    def test_review_request_is_pending_and_idempotent(self):
        criteria = [{"id": "A", "description": "Required outcome"}]
        first = self.ledger.submit_review(17, "assignment", criteria, {"proof": "observed"})
        second = self.ledger.submit_review(17, "assignment", criteria, {"proof": "observed"})
        self.assertEqual(first, second)
        self.assertEqual(self.db.execute(
            "SELECT status FROM verification_requests WHERE id=?", (first,)).fetchone()[0],
            "PENDING")

    def test_completion_queues_review_without_acceptance(self):
        from runtime.resident_inference import Inbox
        inbox = Inbox(self.db)
        event_id = inbox.enqueue("resident", "assignment", {"assignment_id": "work"})
        inbox.next("resident")
        inbox.finish(event_id, "COMPLETED", {"objective_status": "UNVERIFIED"},
                     review={"assignment_id": "work",
                             "criteria": [{"id": "A", "description": "Outcome"}],
                             "evidence": {"observation": "result"}})
        self.assertEqual(self.db.execute(
            "SELECT status FROM verification_requests WHERE source_event_id=?",
            (event_id,)).fetchone()[0], "PENDING")
        self.assertEqual(self.db.execute(
            "SELECT result FROM resident_inbox WHERE id=?", (event_id,)).fetchone()[0],
            '{"objective_status": "UNVERIFIED"}')

    def test_review_requires_all_criteria_and_independent_judgment(self):
        request = self.ledger.submit_review(20, "work", [
            {"id": "A", "version": "v1"}, {"id": "B", "version": "v1"}
        ], {"executor_claim": "complete"})
        self.assertEqual(len(self.ledger.pending_reviews()), 1)
        with self.assertRaises(ValueError):
            self.ledger.decide_review(request, reviewer="auditor",
                                      implementation_revision="commit1",
                                      findings=[{"criterion_id": "A", "result": "PASS",
                                                 "reason": "observed", "evidence": "log"}])
        self.assertEqual(len(self.ledger.pending_reviews()), 1)
        self.assertEqual(len(self.ledger.history("work")), 0)
        result = self.ledger.decide_review(
            request, reviewer="auditor", implementation_revision="commit1",
            findings=[
                {"criterion_id": "A", "result": "PASS", "reason": "observed",
                 "evidence": {"log": "verified"}},
                {"criterion_id": "B", "result": "FAIL", "reason": "missing behavior",
                 "evidence": {"test": "failed"}},
            ])
        self.assertEqual(result, "NEEDS_WORK")
        self.assertEqual(len(self.ledger.history("work")), 2)
        with self.assertRaises(ValueError):
            self.ledger.decide_review(request, reviewer="auditor",
                                      implementation_revision="commit2", findings=[])

    def test_inconclusive_is_not_rejection_or_acceptance(self):
        request = self.ledger.submit_review(
            21, "work2", [{"id": "A"}], {"executor_claim": "complete"})
        outcome = self.ledger.decide_review(
            request, reviewer="auditor", implementation_revision="commit1",
            findings=[{"criterion_id": "A", "result": "INSUFFICIENT_EVIDENCE",
                       "reason": "No independent observation", "evidence": {}}])
        self.assertEqual(outcome, "INCONCLUSIVE")
        self.assertEqual(self.ledger.pending_reviews(), [])

    def test_finding_is_not_self_certified_acceptance(self):
        self.finding("r1", "A", "INSUFFICIENT_EVIDENCE", "executor assertion only", "i1")
        self.assertEqual(self.ledger.history("assignment")[0]["result"],
                         "INSUFFICIENT_EVIDENCE")


if __name__ == "__main__":
    unittest.main()
