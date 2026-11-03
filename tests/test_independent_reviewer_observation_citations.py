# R3 CONTROLLED SOURCE
# File: tests/test_independent_reviewer_observation_citations.py
# Component: R3-INDEPENDENT-REVIEWER-EVIDENCE-CITATIONS
# File Revision: 1.0.0
# Created: 2026-11-03 UTC
# Created By: ChatGPT GPT-6 via GitHub API
# Purpose: Permanent contract for citing independent journal observations in criterion findings.
# Execution Model: Standard-library unittest with a temporary SQLite journal and deterministic model adapter.
# Observability: Verifies the exact journal observation is retained as independent finding evidence.
# Dependencies: runtime.independent_reviewer; runtime.resident_inference; reviewer configuration prompt.
# Authority: hints/engineering-test-policy.md; verification must fail closed without cited observations.
# Contracts: runtime/independent_reviewer.py; config/residents/prompts/reviewer.md
# Tests: python3 -m unittest discover -s tests
# History/Predecessor: New file.
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from runtime.independent_reviewer import IndependentReviewer
from runtime.resident_inference import Inbox


class _Endpoint:
    timeout = 5

    def complete(self, messages, definitions):
        request = json.loads(messages[1]["content"])
        journal_id = request["journal_observation_id"]
        assessment = {
            "findings": [{
                "criterion_id": request["acceptance_criteria"][0]["id"],
                "result": "PASS",
                "reason": "The independent journal row contains the intake channel.",
                "observation_ids": [journal_id],
            }]
        }
        return {"choices": [{"message": {
            "content": json.dumps(assessment),
            "tool_calls": [],
        }}]}


class _ReadOnlyTools:
    def discover(self):
        return [{
            "tool": "r3.status",
            "read_only": True,
            "definition": {
                "type": "function",
                "function": {
                    "name": "r3.status",
                    "description": "Return status",
                    "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
                },
            },
        }]


class IndependentReviewerObservationCitationTests(unittest.TestCase):
    def test_cited_journal_observation_is_preserved_as_independent_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "institution.db"
            db = sqlite3.connect(db_path)
            inbox = Inbox(db)
            criteria = [{
                "id": "durable-intake",
                "version": "1",
                "description": "Intake metadata is durably recorded.",
            }]
            event_id = inbox.enqueue("Grace", "RESIDENT_ACTIVITY", {
                "assignment_id": "assignment-citation-contract",
                "objective": "Observe the durable intake record.",
                "acceptance_criteria": criteria,
                "intake": {
                    "channel": "r3-assignment-intake",
                    "request_sha256": "a" * 64,
                },
            })
            db.commit()
            db.close()

            reviewer = IndependentReviewer(
                _Endpoint(), _ReadOnlyTools(), "review", journal_path=db_path)
            result = reviewer({
                "source_event_id": event_id,
                "assignment_id": "assignment-citation-contract",
                "criteria": criteria,
            })

            finding = result["findings"][0]
            self.assertEqual(finding["result"], "PASS")
            self.assertTrue(finding["evidence"]["independent_observation"])
            self.assertEqual(
                finding["evidence"]["observations"][0]["source"],
                "read-only-r3-journal",
            )
            self.assertEqual(
                finding["evidence"]["observations"][0]["result"]["event"]["payload"]["intake"]["channel"],
                "r3-assignment-intake",
            )

    def test_reviewer_prompt_requires_journal_citations_for_lineage_findings(self):
        prompt = (
            Path(__file__).resolve().parents[1]
            / "config" / "residents" / "prompts" / "reviewer.md"
        ).read_text(encoding="utf-8")
        self.assertIn("journal_observation_id", prompt)
        self.assertIn("do not omit it when the journal directly supports the finding", prompt)


if (c=u.structuredContent||{}).commit_sha===undefined) throw new Error("bad");
