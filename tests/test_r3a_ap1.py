"""
R3 CONTROLLED SOURCE
File: tests/test_r3a_ap1.py
Component: R3A-AP1-TARGETED-TESTS
File Revision: 1.0.10
Created: 2026-11-06 UTC (exact time not independently captured)
Created By: Codex GPT-6
Purpose: Verify AP1 model-route resolution and source-aware knowledge retrieval contracts.
Execution Model: Python unittest, isolated temporary fixtures.
Observability: Deterministic assertions and unittest results.
Dependencies: Python standard library; r3a_runtime.config and r3a_runtime.knowledge.
Authority: AP1 / R3A-019 targeted verification authorized by Steward.
Changed: 2026-11-06T18:05:53Z | R3A-019 | Codex GPT-6 | Add focused route and knowledge retrieval checks.
Changed: 2026-11-06T18:07:21Z | R3A-019 | Codex GPT-6 | Verify source-state transition retrieval returns all four permitted successors.
Changed: 2026-11-06T18:07:40Z | R3A-019 | Codex GPT-6 | Extend the fixture to include all four RUNNING successors.
Changed: 2026-11-06T18:26:37Z | R3A-019 | Codex GPT-6 | Handle preceding article phrases and preserve source-state precision.
Changed: 2026-11-06T18:27:15Z | R3A-019 | Codex GPT-6 | Retain the knowledge source ID in the query fixture.
Changed: 2026-11-06T18:54:42Z | R3A-019 | Codex GPT-6 | Assert transition successors arrive together for model grounding.
Changed: 2026-11-06T19:01:13Z | R3A-019 | Codex GPT-6 | Cover the after-state wording used by notification events.
Changed: 2026-11-06T19:05:07Z | R3A-019 | Codex GPT-6 | Test evidence selection for knowledge-only and runtime objectives.
Changed: 2026-11-06T19:14:04Z | R3A-019 | Codex GPT-6 | Check exhaustive transition answer completeness and truthful blockers.
Changed: 2026-11-06T19:16:11Z | R3A-019 | Codex GPT-6 | Cover explicit transitions.STATE knowledge references.
Supersedes: None.
Contracts: R3A-019 configured model routing and knowledge grounding/retrieval.
Tests: This test module.
History/Predecessor: Git blob a1c2e1c4e3898fa967e6677429ec606a6dcfa4bb at commit 362510b7d32edd1eabdcb07c9677f1b6a47f2adf.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from r3a_runtime.cme import _knowledge_answer_issues, _requires_runtime_evidence
from r3a_runtime.config import ConfigurationError, ModelRoute, resolve_model_route
from r3a_runtime.knowledge import retrieve


class ModelRouteTests(unittest.TestCase):
    def setUp(self):
        self.local = ModelRoute("local", "openai-compatible", "http://127.0.0.1:18796/v1/chat/completions",
                                "qwen-local", 540.0, 160)
        self.escalated = ModelRoute("escalated", "openai-compatible", "https://model.example/v1/chat/completions",
                                    "reasoner", 90.0, 256)

    def test_default_and_requested_routes_resolve_only_configured_ids(self):
        routes = (self.local, self.escalated)
        self.assertEqual(resolve_model_route(routes, "local").route_id, "local")
        self.assertEqual(resolve_model_route(routes, "local", "escalated").model, "reasoner")
        with self.assertRaises(ConfigurationError):
            resolve_model_route(routes, "local", "unconfigured")


class KnowledgeRetrievalTests(unittest.TestCase):
    def test_runtime_evidence_is_selected_only_for_runtime_questions(self):
        self.assertFalse(_requires_runtime_evidence(
            "List every state permitted immediately after RUNNING in process.lifecycle"))
        self.assertTrue(_requires_runtime_evidence(
            "Are Ring0, CME, PostgreSQL, and Grace healthy now?"))

    def test_exhaustive_transition_answers_require_every_destination(self):
        evidence = [{"source_id": "knowledge.1", "source_path": "transitions.RUNNING",
                     "content": "Transitions from RUNNING: DEGRADED, STOPPING, FAILED, RESTARTING"}]
        objective = "List every state permitted after RUNNING"
        partial = {"status": "healthy", "assessment": "DEGRADED and STOPPING"}
        self.assertEqual(_knowledge_answer_issues(objective, evidence, partial), ["FAILED", "RESTARTING"])
        complete = {"status": "healthy",
                    "assessment": "DEGRADED, STOPPING, FAILED, and RESTARTING"}
        self.assertEqual(_knowledge_answer_issues(objective, evidence, complete), [])
        blocked = {"status": "blocked", "assessment": "blocked"}
        self.assertEqual(_knowledge_answer_issues(objective, evidence, blocked),
                         ["model returned blocked status"])

    def test_json_retrieval_returns_relevant_source_facts_and_digests(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "machine.json"
            source.write_text('{"machine_id":"process.lifecycle","states":["RUNNING","STOPPED"],'
                              '"transitions":{"RUNNING":["DEGRADED","STOPPING","FAILED","RESTARTING"]},'
                              '"owner":"CME"}', encoding="utf-8")
            results = retrieve(source, "knowledge.1",
                               "List every state permitted immediately after RUNNING")
            self.assertTrue(results)
            self.assertEqual(len(results), 1)
            self.assertTrue(all(item["source_id"] == "knowledge.1" for item in results))
            self.assertEqual(results[0]["source_path"], "transitions.RUNNING")
            for state in ("DEGRADED", "STOPPING", "FAILED", "RESTARTING"):
                self.assertIn(state, results[0]["content"])
            self.assertTrue(all(len(item["sha256"]) == 64 and len(item["source_sha256"]) == 64
                                for item in results))
            self.assertFalse(any("owner" in item["source_path"] for item in results))
            explicit = retrieve(source, "knowledge.1",
                                "Name all destinations in the transitions.RUNNING knowledge fact")
            self.assertEqual([item["source_path"] for item in explicit], ["transitions.RUNNING"])

    def test_unmatched_query_returns_no_knowledge_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "machine.json"
            source.write_text('{"machine_id":"process.lifecycle","states":["RUNNING"]}', encoding="utf-8")
            self.assertEqual(retrieve(source, "knowledge.1", "Quest avatar rendering"), [])


if __name__ == "__main__":
    unittest.main()
