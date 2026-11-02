# R3 CONTROLLED SOURCE
# File: tests/test_resident_continuity.py
# Component: R3-RESIDENT-CONTINUITY-REGRESSION
# File Revision: 1.0.1
# Created: Unknown (existing file)
# Created By: Unknown (existing file)
# Purpose: Permanent resident-neutral regression for durable activity/objective distinction.
# Execution Model: Standard-library unittest
# Observability: Assertions against SQLite inbox and review records
# Dependencies: runtime/resident_inference.py
# Authority: R3 charter revision 2
# Changed: 2026-11-02 UTC | R3-VERIFY-LEARN-006 | Verify assignment continuity through review submission.
# Supersedes: None
# Tests: This file
# History/Predecessor: Git blob eed458b2ddbfbd8d535402db593c94550f23eae2
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

    def complete(self, messages, tools):
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
