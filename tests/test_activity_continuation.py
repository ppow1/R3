# R3 CONTROLLED SOURCE
# File: tests/test_activity_continuation.py
# Purpose: Permanent resident-neutral durable activity continuation regressions.
from __future__ import annotations
import asyncio
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
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
        row = self.db.execute(
            "SELECT status,result FROM resident_inbox WHERE id=?", (event,)
        ).fetchone()
        self.assertEqual(row[0], "BLOCKED")
        self.assertEqual(json.loads(row[1])["objective_status"], "BLOCKED")
        self.assertIsNone(self.inbox.next("TestResident"))
        self.assertEqual(self.db.execute(
            "SELECT count(*) FROM resident_inbox"
        ).fetchone()[0], 1)

    def test_blocked_without_dependency_evidence_fails_closed(self):
        event = self.inbox.enqueue(
            "TestResident", "RESIDENT_ACTIVITY", {"objective": "Investigate"}
        )
        with self.assertRaisesRegex(RuntimeError, "dependency evidence"):
            asyncio.run(self.handler([{"state": "blocked"}])("TestResident"))
        row = self.db.execute(
            "SELECT status,result FROM resident_inbox WHERE id=?", (event,)
        ).fetchone()
        self.assertEqual(row[0], "FAILED")
        self.assertNotEqual(json.loads(row[1]).get("objective_status"), "BLOCKED")

    def test_blocked_survives_restart_without_implicit_reexecution(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "institution.sqlite3"
            connection = sqlite3.connect(path)
            inbox = Inbox(connection)
            event = inbox.enqueue(
                "ResearchResident", "RESIDENT_ACTIVITY",
                {"objective": "Investigate missing authority"},
            )
            inbox.next("ResearchResident")
            inbox.finish(event, "BLOCKED", {
                "decision": {"state": "blocked", "reason": "Grant not approved"},
                "objective_status": "BLOCKED",
            })
            connection.close()

            restarted = sqlite3.connect(path)
            try:
                inbox = Inbox(restarted)
                self.assertIsNone(inbox.next("ResearchResident"))
                row = restarted.execute(
                    "SELECT status,result FROM resident_inbox WHERE id=?", (event,)
                ).fetchone()
                self.assertEqual(row[0], "BLOCKED")
                self.assertEqual(json.loads(row[1])["objective_status"], "BLOCKED")
            finally:
                restarted.close()

    def test_blocked_cannot_submit_independent_review(self):
        event = self.inbox.enqueue(
            "TestResident", "RESIDENT_ACTIVITY", {"assignment_id": "assignment"}
        )
        self.inbox.next("TestResident")
        with self.assertRaisesRegex(ValueError, "Only completed"):
            self.inbox.finish(event, "BLOCKED", {
                "objective_status": "BLOCKED"
            }, review={
                "assignment_id": "assignment",
                "criteria": [{"id": "acceptance"}],
                "evidence": {},
            })
        self.assertEqual(
            self.db.execute(
                "SELECT count(*) FROM verification_requests"
            ).fetchone()[0], 0,
        )
        self.assertEqual(
            self.db.execute(
                "SELECT status FROM resident_inbox WHERE id=?", (event,)
            ).fetchone()[0], "PROCESSING",
        )

    def test_assignment_status_api_displays_blocked_without_acceptance(self):
        from runtime.assignment_intake import AssignmentIntake
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "institution.sqlite3"
            app = AssignmentIntake(
                path, "test-token-" * 4, {"TestResident"}, {"TestResident"}
            )
            connection = sqlite3.connect(path)
            try:
                inbox = Inbox(connection)
                event = inbox.enqueue(
                    "TestResident", "RESIDENT_ACTIVITY",
                    {"assignment_id": "work", "objective": "Check authorization"},
                )
                connection.execute(
                    "INSERT INTO assignment_intake_assignments VALUES (?,?,?,?,?)",
                    ("work", "test-request-hash", event, "TestResident", 0),
                )
                connection.commit()
                inbox.next("TestResident")
                inbox.finish(event, "BLOCKED", {
                    "decision": {"state": "blocked", "reason": "Missing grant"},
                    "objective_status": "BLOCKED",
                })
                status = app.status(event)
                self.assertEqual(status["events"][-1]["status"], "BLOCKED")
                self.assertEqual(
                    status["events"][-1]["result"]["objective_status"], "BLOCKED",
                )
                self.assertEqual(
                    status["verification"]["verification_status"], "NOT_REQUESTED",
                )
            finally:
                connection.close()


if __name__ == "__main__":
    unittest.main()
