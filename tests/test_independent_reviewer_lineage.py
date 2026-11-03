# R3 CONTROLLED SOURCE
# File: tests/test_independent_reviewer_lineage.py
# Component: R3-INDEPENDENT-REVIEWER-LINEAGE-REGRESSION
# File Revision: 1.0.0
# Created: 2026-11-03 UTC
# Created By: Codex
# Purpose: Permanent contract for independent review across durable assignment event lineage.
# Execution Model: Standard-library unittest with a temporary SQLite journal.
# Observability: Reviewer read-only observation includes linked source, feedback, and continuation rows.
# Dependencies: runtime/independent_reviewer.py; runtime/resident_inference.py
# Authority: hints/engineering-test-policy.md
# Tests: This file.
# Contracts: runtime/verification.py; runtime/resident_inference.py
# History/Predecessor: New file.
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from runtime.independent_reviewer import IndependentReviewer
from runtime.resident_inference import Inbox


class IndependentReviewerLineageTests(unittest.TestCase):
    def test_compact_continuation_keeps_durable_actions_and_drops_duplicate_envelope(self):
        item = {
            "event": {
                "id": 8, "resident": "Grace", "event_type": "REVIEW_FEEDBACK",
                "payload": {
                    "assignment_id": "work-1",
                    "objective": "Original objective",
                    "acceptance_criteria": [{"id": "a"}],
                    "review_request_id": 3,
                    "previous_event_id": 7,
                    "previous_result": {"decision": {"state": "continue", "evidence": ["copied"]}},
                    "next_step": "Repeat the read-only observation",
                },
                "status": "COMPLETED",
                "result": {
                    "continuation_event_id": 9,
                    "decision": {"state": "continue", "next_step": "Repeat the read-only observation",
                                 "evidence": ["already represented by TOOL_RESULT"]},
                },
            },
            "turns": [
                {"sequence": 0, "kind": "ASSISTANT",
                 "content": {"tool_calls": [{"function": {"name": "r3.status"}}]}},
                {"sequence": 1, "kind": "TOOL_INTENT",
                 "content": {"tool": "r3.status", "params": {}}},
                {"sequence": 2, "kind": "TOOL_RESULT",
                 "content": {"role": "tool", "content": '{"healthy": true}'}},
                {"sequence": 3, "kind": "ASSISTANT",
                 "content": {"content": "continue"}},
            ],
        }

        compact = IndependentReviewer._compact_lineage_event(item, source_event_id=99)

        self.assertNotIn("previous_result", compact["event"]["payload"])
        self.assertNotIn("objective", compact["event"]["payload"])
        self.assertEqual(compact["event"]["payload"]["review_request_id"], 3)
        self.assertEqual(compact["event"]["result"]["decision"],
                         {"state": "continue", "next_step": "Repeat the read-only observation"})
        self.assertEqual([turn["kind"] for turn in compact["turns"]],
                         ["TOOL_INTENT", "TOOL_RESULT"])

    def test_large_repeated_tool_lineage_is_compact_and_auditable(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "institution.db"
            db = sqlite3.connect(db_path)
            inbox = Inbox(db)
            criteria = [{"id": "observed", "version": "1",
                         "description": "All read-only observations remain attributable"}]
            base = {
                "assignment_id": "long-assignment",
                "objective": "Collect repeat observations and retain a concise audit summary",
                "acceptance_criteria": criteria,
            }
            first = inbox.enqueue("Grace", "RESIDENT_ACTIVITY", base)
            current = first
            observations = 200
            for index in range(observations):
                inbox.next("Grace")
                call_id = f"call-{index}"
                inbox.record(current, "TOOL_INTENT", {
                    "tool_call_id": call_id, "tool": "r3.status", "params": {},
                })
                inbox.record(current, "TOOL_RESULT", {
                    "role": "tool", "tool_call_id": call_id,
                    "content": json.dumps({"healthy": True, "observation": index}),
                })
                if index + 1 < observations:
                    payload = {
                        **base,
                        "source_event_id": first,
                        "previous_event_id": current,
                    }
                    current = inbox.continue_activity(
                        current, "Grace", "REVIEW_FEEDBACK", payload,
                        {"decision": {"state": "continue", "next_step": "Continue observation"}},
                    )
                else:
                    inbox.finish(current, "COMPLETED", {
                        "decision": {
                            "state": "complete",
                            "objective_verified": True,
                            "evidence": {"observations": observations},
                        },
                    })
            db.close()

            reviewer = IndependentReviewer(
                endpoint=type("Endpoint", (), {"timeout": 5})(),
                tools=None,
                system_prompt="review",
                journal_path=db_path,
            )
            observed = reviewer._observe_journal({
                "source_event_id": current,
                "assignment_id": base["assignment_id"],
                "criteria": criteria,
            })

            summary = observed["lineage_summary"]
            self.assertEqual(summary["event_count"], observations)
            self.assertEqual(len(summary["event_ids"]), observations)
            self.assertEqual(summary["tool_actions"]["r3.status"]["call_count"], observations)
            self.assertEqual(summary["tool_actions"]["r3.status"]["result_count"], observations)
            self.assertEqual(
                summary["tool_actions"]["r3.status"]["distinct_result_count"], observations)
            self.assertEqual(
                json.loads(summary["tool_actions"]["r3.status"]["first_result"]["content"])["observation"],
                0)
            self.assertEqual(
                json.loads(summary["tool_actions"]["r3.status"]["last_result"]["content"])["observation"],
                observations - 1)
            self.assertEqual(summary["terminal_events"][-1]["event_id"], current)
            self.assertLess(len(json.dumps(observed).encode("utf-8")), 25000)

    def test_observation_includes_evidence_across_feedback_lineage(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "institution.db"
            db = sqlite3.connect(db_path)
            inbox = Inbox(db)
            criteria = [
                {"id": "status", "version": "1", "description": "Status call is journaled"},
                {"id": "uptime", "version": "1", "description": "Uptime call is journaled"},
            ]
            base = {
                "assignment_id": "assignment-lineage",
                "objective": "Observe status and uptime",
                "acceptance_criteria": criteria,
            }
            first = inbox.enqueue("Grace", "RESIDENT_ACTIVITY", base)
            inbox.next("Grace")
            inbox.record(first, "TOOL_INTENT", {
                "tool_call_id": "status-call", "tool": "r3.status", "params": {},
            })
            inbox.record(first, "TOOL_RESULT", {
                "role": "tool", "tool_call_id": "status-call",
                "content": json.dumps({"service": "r3-tools", "healthy": True}),
            })
            inbox.finish(first, "COMPLETED", {"decision": {"state": "complete"}})

            feedback_payload = {
                **base,
                "source_event_id": first,
                "source_event_type": "RESIDENT_ACTIVITY",
                "review_outcome": "NEEDS_WORK",
                "previous_result": {"decision": {"state": "complete"}},
            }
            feedback = inbox.enqueue("Grace", "REVIEW_FEEDBACK", feedback_payload)
            inbox.next("Grace")
            correction = inbox.continue_activity(
                feedback, "Grace", "REVIEW_FEEDBACK",
                {**feedback_payload, "previous_event_id": feedback,
                 "next_step": "Capture host uptime"},
                {"decision": {"state": "continue", "next_step": "Capture host uptime"}},
            )
            inbox.next("Grace")
            inbox.record(correction, "TOOL_INTENT", {
                "tool_call_id": "uptime-call", "tool": "r3.host.uptime", "params": {},
            })
            inbox.record(correction, "TOOL_RESULT", {
                "role": "tool", "tool_call_id": "uptime-call",
                "content": json.dumps({"returncode": 0, "stdout": "up 1 day", "stderr": ""}),
            })
            inbox.finish(correction, "COMPLETED", {"decision": {"state": "complete"}})
            db.close()

            reviewer = IndependentReviewer(
                endpoint=type("Endpoint", (), {"timeout": 5})(),
                tools=None,
                system_prompt="review",
                journal_path=db_path,
            )
            observed = reviewer._observe_journal({
                "source_event_id": correction,
                "assignment_id": base["assignment_id"],
                "criteria": criteria,
            })

            self.assertEqual(observed["lineage_event_ids"], [first, feedback, correction])
            self.assertEqual(observed["event"]["id"], correction)
            actions = observed["lineage_summary"]["tool_actions"]
            self.assertEqual(set(actions), {"r3.status", "r3.host.uptime"})
            self.assertEqual(actions["r3.status"]["call_count"], 1)
            self.assertEqual(actions["r3.host.uptime"]["call_count"], 1)
            self.assertEqual(actions["r3.status"]["last_result"]["content"],
                             json.dumps({"service": "r3-tools", "healthy": True}))
            self.assertEqual(actions["r3.host.uptime"]["last_result"]["content"],
                             json.dumps({"returncode": 0, "stdout": "up 1 day", "stderr": ""}))


if __name__ == "__main__":
    unittest.main()
