# R3 CONTROLLED SOURCE
# File: tests/test_resident_continuity.py
# Component: R3-RESIDENT-CONTINUITY-REGRESSION
# File Revision: 1.0.3
# Created: Unknown (existing file)
# Created By: Unknown (existing file)
# Purpose: Permanent resident-neutral regression for durable activity/objective distinction.
# Execution Model: Standard-library unittest
# Observability: Assertions against SQLite inbox and review records
# Dependencies: runtime/resident_inference.py
# Authority: R3 charter revision 2
# Changed: 2026-11-02 UTC | R3-VERIFY-LEARN-006 | Verify assignment continuity through review submission.
# Changed: 2026-11-03T02:24:59.876Z | R3-VERIFY-FEEDBACK-LOOP-001 | Codex | Verify review feedback resumes the assignment and queues a new review.
# Changed: 2026-11-05 UTC | R3-GRACE-RECOVERY-006 | Make inference fixtures asynchronous and deterministic across event-loop shutdown.
# Supersedes: None
# Tests: This file
# History/Predecessor: Git blob 944dce6ff5075fdc75f80d048bb461dced0cf2af
# Contracts: hints/engineering-test-policy.md
from __future__ import annotations

import asyncio
import json
import sqlite3
import unittest

from runtime.resident_inference import Inbox, ResidentInference


class FakeEndpoint:
    def __init__(self, decisions):
        self.decisions = iter(decisions)
        self.messages = []

    async def complete(self, messages, tools):
        self.messages.append(messages)
        return {"model": "fixture", "choices": [{"message": {
            "role": "assistant", "content": json.dumps(next(self.decisions))
        }}]}


class ResidentContinuityTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.inbox = Inbox(self.db)

    def result(self, event_id):
        row = self.db.execute(
            "SELECT status,result FROM resident_inbox WHERE id=?", (event_id,)
        ).fetchone()
        return row[0], json.loads(row[1])

    def test_unverified_activity_completion_is_not_objective_acceptance(self):
        endpoint = FakeEndpoint([{"state": "complete", "evidence": "Host is online"}])
        event_id = self.inbox.enqueue("Grace", "RESIDENT_ACTIVITY", {"objective": "Repair service"})
        worker = ResidentInference(self.inbox, endpoint, system_prompt="Resident",
                                   continuation_event_types=("RESIDENT_ACTIVITY",))
        asyncio.run(worker("Grace"))
        status, result = self.result(event_id)
        self.assertEqual(status, "COMPLETED")
        self.assertEqual(result["objective_status"], "UNVERIFIED")
        self.assertIn("objective_verified=true", endpoint.messages[0][0]["content"])

    def test_continuation_retains_objective_and_lineage(self):
        endpoint = FakeEndpoint([{"state": "continue", "next_step": "Inspect error log",
                                  "evidence": "Service is unhealthy"}])
        event_id = self.inbox.enqueue("Grace", "RESIDENT_ACTIVITY",
                                      {"objective": "Restore service"})
        worker = ResidentInference(self.inbox, endpoint, system_prompt="Resident",
                                   continuation_event_types=("RESIDENT_ACTIVITY",))
        asyncio.run(worker("Grace"))
        _, result = self.result(event_id)
        next_id = result["continuation_event_id"]
        row = self.db.execute("SELECT status,payload FROM resident_inbox WHERE id=?",
                              (next_id,)).fetchone()
        self.assertEqual(row[0], "PENDING")
        payload = json.loads(row[1])
        self.assertEqual(payload["objective"], "Restore service")
        self.assertEqual(payload["previous_event_id"], event_id)
        self.assertEqual(payload["next_step"], "Inspect error log")

    def test_multiturn_assignment_retains_criteria_and_requests_review(self):
        criteria = [{"id": "availability", "description": "Service available"}]
        endpoint = FakeEndpoint([
            {"state": "continue", "next_step": "Inspect service"},
            {"state": "complete", "evidence": {"service": "available"}},
        ])
        first = self.inbox.enqueue("Grace", "RESIDENT_ACTIVITY", {
            "objective": "Restore service",
            "assignment_id": "work-1",
            "acceptance_criteria": criteria,
            "context": {"origin": "steward"},
        })
        worker = ResidentInference(self.inbox, endpoint, system_prompt="Resident",
                                   continuation_event_types=("RESIDENT_ACTIVITY",))
        asyncio.run(worker("Grace"))
        second = self.result(first)[1]["continuation_event_id"]
        payload = json.loads(self.db.execute(
            "SELECT payload FROM resident_inbox WHERE id=?", (second,)).fetchone()[0])
        self.assertEqual(payload["assignment_id"], "work-1")
        self.assertEqual(payload["acceptance_criteria"], criteria)
        self.assertEqual(payload["context"], {"origin": "steward"})
        asyncio.run(worker("Grace"))
        self.assertEqual(self.result(second)[1]["objective_status"], "UNVERIFIED")
        row = self.db.execute(
            "SELECT assignment_id,criteria,status FROM verification_requests WHERE source_event_id=?",
            (second,)).fetchone()
        self.assertEqual(row[0], "work-1")
        self.assertEqual(json.loads(row[1]), criteria)
        self.assertEqual(row[2], "PENDING")
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM verification_requests").fetchone()[0], 1)

    def test_review_feedback_continues_correction_and_requests_new_review(self):
        criteria = [{"id": "availability", "description": "Service is available"}]
        feedback = {
            "assignment_id": "work-review-1",
            "objective": "Restore the service and verify availability",
            "source_event_id": 14,
            "source_event_type": "RESIDENT_ACTIVITY",
            "source_payload": {"objective": "Restore the service and verify availability"},
            "prior_result": {"decision": {"state": "complete", "evidence": {}}},
            "review_request_id": 1,
            "review_outcome": "NEEDS_WORK",
            "acceptance_criteria": criteria,
            "findings": [{"criterion_id": "availability", "result": "FAIL",
                          "reason": "No independent availability evidence",
                          "evidence": {"independent_observation": False}}],
        }
        endpoint = FakeEndpoint([
            {"state": "continue", "next_step": "Run the authorized availability probe",
             "evidence": {"review": "availability criterion failed"}},
            {"state": "complete", "objective_verified": True,
             "evidence": {"availability": "observed healthy"}},
        ])
        first = self.inbox.enqueue("Grace", "REVIEW_FEEDBACK", feedback)
        worker = ResidentInference(
            self.inbox, endpoint, system_prompt="Resident",
            continuation_event_types=("RESIDENT_ACTIVITY", "REVIEW_FEEDBACK"),
        )
        asyncio.run(worker("Grace"))
        first_status, first_result = self.result(first)
        self.assertEqual(first_status, "COMPLETED")
        second = first_result["continuation_event_id"]
        payload = json.loads(self.db.execute(
            "SELECT payload FROM resident_inbox WHERE id=?", (second,)
        ).fetchone()[0])
        self.assertEqual(payload["objective"], feedback["objective"])
        self.assertEqual(payload["acceptance_criteria"], criteria)
        self.assertEqual(payload["findings"], feedback["findings"])
        self.assertEqual(payload["review_request_id"], 1)
        asyncio.run(worker("Grace"))
        self.assertEqual(self.result(second)[1]["objective_status"], "REPORTED_VERIFIED")
        row = self.db.execute(
            "SELECT assignment_id,criteria,status FROM verification_requests WHERE source_event_id=?",
            (second,),
        ).fetchone()
        self.assertEqual(row[0], "work-review-1")
        self.assertEqual(json.loads(row[1]), criteria)
        self.assertEqual(row[2], "PENDING")

    def test_verified_completion_requires_explicit_flag_and_evidence(self):
        endpoint = FakeEndpoint([{"state": "complete", "objective_verified": True,
                                  "evidence": "Observed required acceptance result"}])
        event_id = self.inbox.enqueue("Grace", "RESIDENT_ACTIVITY", {"objective": "Check health"})
        worker = ResidentInference(self.inbox, endpoint, system_prompt="Resident",
                                   continuation_event_types=("RESIDENT_ACTIVITY",))
        asyncio.run(worker("Grace"))
        self.assertEqual(self.result(event_id)[1]["objective_status"], "REPORTED_VERIFIED")


if __name__ == "__main__":
    unittest.main()
