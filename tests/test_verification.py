# R3 CONTROLLED SOURCE
# File: tests/test_verification.py
# Component: R3-VERIFICATION-LEARNING-REGRESSION
# File Revision: 1.3.6
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
# Changed: 2026-11-02 UTC | R3-VERIFY-LEARN-008 | Verify independent worker, self-review exclusion, and failure recovery.
# Changed: 2026-11-02 UTC | R3-VERIFY-LEARN-010 | Require separately sourced reviewer observations for acceptance.
# Changed: 2026-11-02 UTC | R3-VERIFY-LEARN-011 | Regression for caller-owned transaction rollback.
# Changed: 2026-11-02 UTC | R3-VERIFY-LEARN-012 | Ensure transaction marker table exists before rollback assertion.
# Changed: 2026-11-02 UTC | R3-VERIFY-LEARN-013 | Permanent regression for authoritative assignment review status.
# Changed: 2026-11-02 UTC | R3-VERIFY-LEARN-015 | Test manager feedback dispatch after failed review.
# Changed: 2026-11-03T02:24:59.876Z | R3-VERIFY-FEEDBACK-LOOP-001 | Codex | Test source context and recovery of undelivered review feedback.
# Supersedes: None
# Contracts: hints/verification-and-learning.md
# Tests: This file.
# History/Predecessor: Git blob 37315a802a29d04f6961a7c8590b919633715399
import sqlite3
import threading
import unittest

from runtime.admission import AdmissionGate
from runtime.verification import VerificationLedger, IndependentReviewWorker


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

    def test_assignment_status_is_derived_from_review_decisions(self):
        initial = self.ledger.assignment_review_status("work")
        self.assertEqual(initial["verification_status"], "NOT_REQUESTED")
        self.assertEqual(initial["review_count"], 0)
        request = self.ledger.submit_review(100, "work", [{"id": "A"}], {"claim": "done"})
        pending = self.ledger.assignment_review_status("work")
        self.assertEqual(pending["verification_status"], "PENDING")
        self.assertEqual(pending["pending_review_count"], 1)
        self.ledger.decide_review(
            request, reviewer="auditor", implementation_revision="rev1",
            findings=[{"criterion_id": "A", "result": "FAIL",
                       "reason": "Result did not meet criterion",
                       "evidence": {"observation": "not satisfied"}}])
        rejected = self.ledger.assignment_review_status("work")
        self.assertEqual(rejected["verification_status"], "NEEDS_WORK")
        self.assertEqual(rejected["pending_review_count"], 0)
        second = self.ledger.submit_review(101, "work", [{"id": "A"}], {"claim": "corrected"})
        self.assertEqual(self.ledger.assignment_review_status("work")["verification_status"], "PENDING")
        self.ledger.decide_review(
            second, reviewer="auditor", implementation_revision="rev2",
            findings=[{"criterion_id": "A", "result": "PASS",
                       "reason": "Observed corrected result",
                       "evidence": {"independent_observation": {"result": "satisfied"}}}])
        accepted = self.ledger.assignment_review_status("work")
        self.assertEqual(accepted["verification_status"], "ACCEPTED")
        self.assertEqual(accepted["review_count"], 2)
        self.assertEqual(accepted["latest_source_event_id"], 101)

    def test_review_request_is_pending_and_idempotent(self):
        criteria = [{"id": "A", "description": "Required outcome"}]
        first = self.ledger.submit_review(17, "assignment", criteria, {"proof": "observed"})
        second = self.ledger.submit_review(17, "assignment", criteria, {"proof": "observed"})
        self.assertEqual(first, second)
        self.assertEqual(self.db.execute(
            "SELECT status FROM verification_requests WHERE id=?", (first,)).fetchone()[0],
            "PENDING")

    def test_review_submission_respects_caller_transaction_rollback(self):
        self.db.execute("CREATE TABLE IF NOT EXISTS transaction_marker (id INTEGER)")
        self.db.commit()
        self.db.execute("BEGIN")
        self.db.execute("INSERT INTO transaction_marker VALUES (1)")
        self.ledger.submit_review(101, "assignment", [{"id": "A"}], {})
        self.assertTrue(self.db.in_transaction)
        self.db.rollback()
        self.assertEqual(self.db.execute(
            "SELECT count(*) FROM verification_requests WHERE source_event_id=101"
        ).fetchone()[0], 0)
        self.assertEqual(self.db.execute(
            "SELECT count(*) FROM transaction_marker"
        ).fetchone()[0], 0)

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

    def test_worker_marks_review_processing_until_assessment_is_recorded(self):
        request_id = self.ledger.submit_review(401, "assignment", [{"id": "A"}], {})

        def evaluate(request):
            self.assertEqual(request["id"], request_id)
            status, started_at = self.db.execute(
                "SELECT status,processing_started_at FROM verification_requests WHERE id=?",
                (request_id,),
            ).fetchone()
            self.assertEqual(status, "PROCESSING")
            self.assertIsNotNone(started_at)
            return {"implementation_revision": "rev1", "findings": [
                {"criterion_id": "A", "result": "PASS",
                 "reason": "independently observed",
                 "evidence": {"independent_observation": {"tool": "status"}}},
            ]}

        worker = IndependentReviewWorker(self.ledger, "auditor", evaluate)
        self.assertEqual(worker.process_pending(),
                         [{"request_id": request_id, "outcome": "ACCEPTED"}])
        self.assertEqual(self.ledger.processing_review_count(), 0)

    def test_interrupted_review_is_retryable_after_worker_restart(self):
        request_id = self.ledger.submit_review(402, "assignment", [{"id": "A"}], {})
        self.db.execute(
            "UPDATE verification_requests SET status='PROCESSING' WHERE id=?", (request_id,)
        )
        self.db.commit()

        worker = IndependentReviewWorker(
            self.ledger, "auditor",
            lambda request: {"implementation_revision": "rev1", "findings": [
                {"criterion_id": "A", "result": "INSUFFICIENT_EVIDENCE",
                 "reason": "No independent observation", "evidence": {}},
            ]},
        )

        self.assertEqual(self.ledger.processing_review_count(), 0)
        self.assertEqual(
            self.db.execute("SELECT last_error FROM verification_requests WHERE id=?",
                            (request_id,)).fetchone()[0],
            "InterruptedByRestart",
        )
        self.assertEqual([item["id"] for item in self.ledger.pending_reviews()], [request_id])
        self.assertEqual(worker.process_pending()[0]["outcome"], "INCONCLUSIVE")

    def test_shutdown_closes_future_review_claims_but_preserves_active_result(self):
        db = sqlite3.connect(":memory:", check_same_thread=False)
        ledger = VerificationLedger(db)
        first = ledger.submit_review(51, "assignment-first", [{"id": "A"}], {})
        second = ledger.submit_review(52, "assignment-second", [{"id": "A"}], {})
        evaluating = threading.Event()
        release = threading.Event()
        release_timed_out = threading.Event()
        evaluations = []

        def evaluator(request):
            evaluations.append(request["id"])
            if request["id"] == first:
                evaluating.set()
                if not release.wait(timeout=2):
                    release_timed_out.set()
            return {
                "implementation_revision": "rev1",
                "findings": [{
                    "criterion_id": "A", "result": "PASS",
                    "reason": "independently observed",
                    "evidence": {"independent_observation": {"tool": "status", "result": "healthy"}},
                }],
            }

        gate = AdmissionGate()
        worker = IndependentReviewWorker(ledger, "auditor", evaluator)
        outcomes = []
        runner = threading.Thread(
            target=lambda: outcomes.extend(worker.process_pending(admission_gate=gate))
        )
        try:
            runner.start()
            self.assertTrue(evaluating.wait(timeout=2))
            gate.close()
            release.set()
            runner.join(timeout=2)
            self.assertFalse(runner.is_alive())
            self.assertFalse(release_timed_out.is_set())
            self.assertEqual([first], evaluations)
            self.assertEqual([{"request_id": first, "outcome": "ACCEPTED"}], outcomes)
            statuses = {
                row[0]: row[1] for row in db.execute(
                    "SELECT id,status FROM verification_requests"
                )
            }
            self.assertEqual("ACCEPTED", statuses[first])
            self.assertEqual("PENDING", statuses[second])
        finally:
            release.set()
            if runner.is_alive():
                runner.join(timeout=2)
            db.close()

    def test_worker_records_independent_review(self):
        request = self.ledger.submit_review(41, "assignment",
                                            [{"id": "A"}], {"reported": "done"})
        worker = IndependentReviewWorker(
            self.ledger, "auditor",
            lambda item: {"implementation_revision": "rev1",
                          "findings": [{"criterion_id": "A", "result": "PASS",
                                        "reason": "independently observed",
                                        "evidence": {"independent_observation": {"tool": "status", "result": "healthy"}}}]})
        self.assertEqual(worker.process_pending(),
                         [{"request_id": request, "outcome": "ACCEPTED"}])
        self.assertEqual(self.ledger.pending_reviews(), [])
        self.assertEqual(self.ledger.history("assignment")[0]["reviewer"], "auditor")

    def test_worker_rejects_executor_claim_as_only_pass_evidence(self):
        self.ledger.submit_review(43, "assignment", [{"id": "A"}],
                                  {"executor_claim": "done"})
        worker = IndependentReviewWorker(
            self.ledger, "auditor",
            lambda request: {"implementation_revision": "rev1",
                             "findings": [{"criterion_id": "A", "result": "PASS",
                                           "reason": "executor says done",
                                           "evidence": {"executor_claim": "done"}}]})
        with self.assertRaises(ValueError):
            worker.process_pending()
        self.assertEqual(len(self.ledger.pending_reviews()), 1)

    def test_failed_review_dispatches_manager_feedback(self):
        from runtime.resident_inference import Inbox
        inbox = Inbox(self.db)
        criteria = [{"id": "A", "description": "Observed outcome"}]
        source = inbox.enqueue("worker", "RESIDENT_ACTIVITY", {
            "objective": "Restore the service",
            "assignment_id": "assignment",
            "acceptance_criteria": criteria,
        })
        inbox.next("worker")
        inbox.finish(source, "COMPLETED", {"decision": {"state": "complete"}})
        request = self.ledger.submit_review(source, "assignment", criteria, {})
        worker = IndependentReviewWorker(
            self.ledger, "auditor",
            lambda _: {"implementation_revision": "rev1",
                       "findings": [{"criterion_id": "A", "result": "FAIL",
                                     "reason": "Not satisfied", "evidence": {"observed": False}}]},
            manager="Grace")
        outcomes = worker.process_pending()
        self.assertEqual(outcomes[0]["request_id"], request)
        self.assertEqual(outcomes[0]["outcome"], "NEEDS_WORK")
        event = inbox.next("Grace")
        self.assertEqual(event[0], outcomes[0]["feedback_event_id"])
        self.assertEqual(event[1], "REVIEW_FEEDBACK")
        self.assertEqual(event[2]["assignment_id"], "assignment")
        self.assertEqual(event[2]["objective"], "Restore the service")
        self.assertEqual(event[2]["source_payload"]["acceptance_criteria"], criteria)
        self.assertEqual(event[2]["prior_result"], {"decision": {"state": "complete"}})
        self.assertEqual(event[2]["findings"][0]["criterion_id"], "A")
        self.assertEqual(worker.process_pending(), [])

    def test_worker_recovers_durable_review_with_missing_feedback_delivery(self):
        from runtime.resident_inference import Inbox
        inbox = Inbox(self.db)
        criteria = [{"id": "A", "description": "Observed outcome"}]
        source = inbox.enqueue("worker", "RESIDENT_ACTIVITY", {
            "objective": "Restore the service",
            "assignment_id": "assignment",
            "acceptance_criteria": criteria,
        })
        request = self.ledger.submit_review(source, "assignment", criteria, {})
        self.ledger.decide_review(
            request, reviewer="auditor", implementation_revision="rev1",
            findings=[{"criterion_id": "A", "result": "FAIL",
                       "reason": "Observed outcome is missing",
                       "evidence": {"observed": False}}])
        worker = IndependentReviewWorker(
            self.ledger, "auditor", lambda _: self.fail("No pending review should be evaluated"),
            manager="Grace")
        self.assertEqual(worker.process_pending(), [])
        feedback = inbox.next("Grace")
        self.assertIsNotNone(feedback)
        self.assertEqual(feedback[1], "REVIEW_FEEDBACK")
        self.assertEqual(feedback[2]["objective"], "Restore the service")
        self.assertEqual(feedback[2]["review_request_id"], request)
        self.assertEqual(self.ledger.undelivered_review_feedback(), [])

    def test_worker_failure_does_not_lose_pending_request(self):
        self.ledger.submit_review(42, "assignment", [{"id": "A"}], {})
        def fail(_request):
            raise RuntimeError("Reviewer unavailable")
        with self.assertRaises(RuntimeError):
            IndependentReviewWorker(self.ledger, "auditor", fail).process_pending()
        self.assertEqual(len(self.ledger.pending_reviews()), 1)
        self.assertEqual(self.ledger.processing_review_count(), 0)
        self.assertEqual(
            self.db.execute("SELECT last_error FROM verification_requests").fetchone()[0],
            "RuntimeError",
        )
        self.assertEqual(self.ledger.history("assignment"), [])

    def test_executor_cannot_review_own_activity(self):
        from runtime.resident_inference import Inbox
        inbox = Inbox(self.db)
        event = inbox.enqueue("Grace", "RESIDENT_ACTIVITY", {"objective": "work"})
        self.ledger.submit_review(event, "assignment", [{"id": "A"}], {})
        with self.assertRaises(ValueError):
            IndependentReviewWorker(
                self.ledger, "Grace", lambda request: {}).process_pending()
        self.assertEqual(len(self.ledger.pending_reviews()), 1)

    def test_finding_is_not_self_certified_acceptance(self):
        self.finding("r1", "A", "INSUFFICIENT_EVIDENCE", "executor assertion only", "i1")
        self.assertEqual(self.ledger.history("assignment")[0]["result"],
                         "INSUFFICIENT_EVIDENCE")


if __name__ == "__main__":
    unittest.main()
