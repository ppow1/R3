# R3 CONTROLLED SOURCE
# File: tests/test_resident_continuity.py
# Purpose: Permanent resident-neutral regression for durable activity/objective distinction.
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

    def test_verified_completion_requires_explicit_flag_and_evidence(self):
        endpoint = FakeEndpoint([{"state": "complete", "objective_verified": True,
                                  "evidence": "Observed required acceptance result"}])
        event_id = self.inbox.enqueue("Grace", "RESIDENT_ACTIVITY", {"objective": "Check health"})
        worker = ResidentInference(self.inbox, endpoint, system_prompt="Resident",
                                   continuation_event_types=("RESIDENT_ACTIVITY",))
        asyncio.run(worker("Grace"))
        self.assertEqual(self.result(event_id)[1]["objective_status"], "VERIFIED")


if __name__ == "__main__":
    unittest.main()
