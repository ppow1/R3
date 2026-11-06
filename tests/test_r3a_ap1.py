"""
R3 CONTROLLED SOURCE
File: tests/test_r3a_ap1.py
Component: R3A-AP1-TARGETED-TESTS
File Revision: 1.0.5
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
Supersedes: None.
Contracts: R3A-019 configured model routing and knowledge grounding/retrieval.
Tests: This test module.
History/Predecessor: Git blob 9beeb6a7b5a0d2076d6116d9064c156e3abc49dd at commit cc9eae1baf691b016666cfc15c8905e04f666ec8.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

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
    def test_json_retrieval_returns_relevant_source_facts_and_digests(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "machine.json"
            source.write_text('{"machine_id":"process.lifecycle","states":["RUNNING","STOPPED"],'
                              '"transitions":{"RUNNING":["DEGRADED","STOPPING","FAILED","RESTARTING"]},'
                              '"owner":"CME"}', encoding="utf-8")
            results = retrieve(source, "knowledge.1",
                               "From the process.lifecycle definition, report transitions from RUNNING")
            self.assertTrue(results)
            self.assertEqual(len(results), 4)
            self.assertTrue(all(item["source_id"] == "knowledge.1" for item in results))
            self.assertTrue(all(item["source_path"].startswith("transitions.RUNNING") for item in results))
            self.assertTrue(all(len(item["sha256"]) == 64 and len(item["source_sha256"]) == 64
                                for item in results))
            self.assertFalse(any("owner" in item["source_path"] for item in results))

    def test_unmatched_query_returns_no_knowledge_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "machine.json"
            source.write_text('{"machine_id":"process.lifecycle","states":["RUNNING"]}', encoding="utf-8")
            self.assertEqual(retrieve(source, "knowledge.1", "Quest avatar rendering"), [])


if __name__ == "__main__":
    unittest.main()
