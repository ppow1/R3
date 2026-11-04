# R3 CONTROLLED SOURCE
# File: tests/test_activity_continuation.py
# Purpose: Permanent resident-neutral durable activity continuation regressions.
# Changed: 2026-11-04 UTC | R3-GRACE-FEEDBACK-LOOP-002 | ChatGPT GPT-6 | Test repeated lineage and evidence progression.
from __future__ import annotations
import asyncio
import json
import sqlite3
import unittest
from unittest.mock import Mock
from runtime.resident_inference import Inbox, ResidentInference


class ActivityContinuationTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.inbox = Inbox(self.db)

    def tearDown(self):
        self.db.close()

    def handler(self, answers, enabled=("RESIDENT_ACTIVITY",)):
        endpoint = Mock()
        endpoint.complete.side_effect = [
            {"choices": [{"message": {"role": "assistant", "content": json.dumps(a)}}], "model": "test"}
            for a in answers
        ]
        return ResidentInference(self.inbox, endpoint, system_prompt="Test resident",
                                 continuation_event_types=enabled)

    def test_continuation_is_durable_and_resumes_next_activation(self):
        first = self.inbox.enqueue("TestResident", "RESIDENT_ACTIVITY", {"objective": "Investigate"})
        handler = self.handler([
            {"state": "continue", "next_step": "Review evidence", "evidence": "Initial observation"},
            {"state": "complete", "evidence": "Reviewed"},
        ])
        asyncio.run(handler("TestResident"))
        first_result = self.db.execute("SELECT status,result FROM resident_inbox WHERE id=?", (first,)).fetchone()
        self.assertEqual(first_result[0], "COMPLETED")
        second = json.loads(first_result[1])["continuation_event_id"]
        payload, status = self.db.execute("SELECT payload,status FROM resident_inbox WHERE id=?", (second,)).fetchone()
        self.assertEqual(status, "PENDING")
        self.assertEqual(json.loads(payload)["objective"], "Investigate")
        asyncio.run(handler("TestResident"))
        self.assertEqual(self.db.execute("SELECT status FROM resident_inbox WHERE id=?", (second,)).fetchone()[0], "COMPLETED")
        self.assertEqual(self.db.execute("SELECT count(*) FROM resident_inbox").fetchone()[0], 2)

    def test_repeated_ineffective_continuation_requests_recovery(self):
        event = self.inbox.enqueue("TestResident", "RESIDENT_ACTIVITY", {"objective": "Resolve incident"})
        handler = self.handler([
            {"state": "continue", "next_step": "Inspect status", "evidence": "No change"},
            {"state": "continue", "next_step": " inspect STATUS ", "evidence": "No change"},
            {"state": "continue", "next_step": "Use alternate authorized interface", "evidence": "New route"},
        ])
        asyncio.run(handler("TestResident"))
        asyncio.run(handler("TestResident"))
        second = self.db.execute("SELECT payload FROM resident_inbox WHERE id=?", (event + 2,)).fetchone()
        self.assertIsNotNone(second)
        self.assertTrue(json.loads(second[0])["recovery_required"])
        asyncio.run(handler("TestResident"))
        third = self.db.execute("SELECT payload FROM resident_inbox WHERE id=?", (event + 3,)).fetchone()
        self.assertIsNotNone(third)
        self.assertFalse(json.loads(third[0])["recovery_required"])
        sent = handler.endpoint.complete.call_args_list[2].args[0]
        self.assertIn("Recovery required", sent[0]["content"])

    def test_alternating_ineffective_steps_eventually_block_durably(self):
        event = self.inbox.enqueue("TestResident", "RESIDENT_ACTIVITY",
                                   {"objective": "Resolve incident"})
        handler = self.handler([
            {"state": "continue", "next_step": "Inspect A", "evidence": "unchanged"},
            {"state": "continue", "next_step": "Inspect B", "evidence": "unchanged"},
            {"state": "continue", "next_step": "Inspect A", "evidence": "unchanged"},
            {"state": "continue", "next_step": "Inspect B", "evidence": "unchanged"},
        ])
        for _ in range(3):
            asyncio.run(handler("TestResident"))
        rows = self.db.execute(
            "SELECT status,result FROM resident_inbox ORDER BY id"
        ).fetchall()
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[-1][0], "FAILED")
        result = json.loads(rows[-1][1])
        self.assertEqual(result["decision"]["state"], "blocked")
        self.assertEqual(result["objective_status"], "UNVERIFIED")
        self.assertEqual(self.db.execute(
            "SELECT count(*) FROM resident_inbox WHERE status='PENDING'"
        ).fetchone()[0], 0)

    def test_changed_evidence_allows_revisiting_step(self):
        self.inbox.enqueue("TestResident", "RESIDENT_ACTIVITY",
                           {"objective": "Investigate"})
        handler = self.handler([
            {"state": "continue", "next_step": "Inspect A", "evidence": "before"},
            {"state": "continue", "next_step": "Inspect A", "evidence": "after"},
        ])
        asyncio.run(handler("TestResident"))
        asyncio.run(handler("TestResident"))
        self.assertEqual(self.db.execute(
            "SELECT count(*) FROM resident_inbox WHERE status='PENDING'"
        ).fetchone()[0], 1)

    def test_repeated_status_with_changing_uptime_requests_recovery(self):
        self.inbox.enqueue("TestResident", "RESIDENT_ACTIVITY",
                           {"objective": "Determine actual readiness"})
        handler = self.handler([
            {"state": "continue", "next_step": "Check readiness", "evidence": "first"},
            {"state": "continue", "next_step": "Check readiness again", "evidence": "second"},
        ])
        def record_tools():
            event = self.db.execute(
                "SELECT id FROM resident_inbox WHERE status='PENDING' ORDER BY id LIMIT 1"
            ).fetchone()[0]
            self.inbox.record(event, "TOOL_INTENT", {"tool_call_id": "status", "tool": "r3.status"})
            self.inbox.record(event, "TOOL_RESULT", {"tool_call_id": "status", "content": '{"ready":false}'})
            self.inbox.record(event, "TOOL_INTENT", {"tool_call_id": "uptime", "tool": "r3.host.uptime"})
            self.inbox.record(event, "TOOL_RESULT", {"tool_call_id": "uptime", "content": '{"seconds":123}'})
        record_tools()
        asyncio.run(handler("TestResident"))
        record_tools()
        asyncio.run(handler("TestResident"))
        payload = json.loads(self.db.execute(
            "SELECT payload FROM resident_inbox WHERE status='PENDING'"
        ).fetchone()[0])
        self.assertTrue(payload["recovery_required"])
        self.assertIn("r3.status", payload["repeated_tool_observations"])

    def test_regular_event_keeps_ordinary_response(self):
        event = self.inbox.enqueue("TestResident", "CONVERSATION", {"text": "hello"})
        handler = self.handler([{"state": "continue", "next_step": "not activated"}])
        asyncio.run(handler("TestResident"))
        self.assertEqual(self.db.execute("SELECT status FROM resident_inbox WHERE id=?", (event,)).fetchone()[0], "COMPLETED")
        self.assertEqual(self.db.execute("SELECT count(*) FROM resident_inbox").fetchone()[0], 1)

    def test_invalid_decision_fails_without_new_event(self):
        event = self.inbox.enqueue("TestResident", "RESIDENT_ACTIVITY", {"objective": "Check"})
        handler = self.handler([{"state": "continue"}])
        with self.assertRaisesRegex(RuntimeError, "next_step"):
            asyncio.run(handler("TestResident"))
        self.assertEqual(self.db.execute("SELECT status FROM resident_inbox WHERE id=?", (event,)).fetchone()[0], "FAILED")
        self.assertEqual(self.db.execute("SELECT count(*) FROM resident_inbox").fetchone()[0], 1)

    def test_blocked_is_not_reported_as_completed(self):
        event = self.inbox.enqueue("TestResident", "RESIDENT_ACTIVITY", {"objective": "Check"})
        handler = self.handler([{"state": "blocked", "evidence": "Need access"}])
        asyncio.run(handler("TestResident"))
        self.assertEqual(self.db.execute("SELECT status FROM resident_inbox WHERE id=?", (event,)).fetchone()[0], "FAILED")


if __name__ == "__main__":
    unittest.main()
