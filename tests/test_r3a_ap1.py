"""
R3 CONTROLLED SOURCE
File: tests/test_r3a_ap1.py
Component: R3A-AP1-TARGETED-TESTS
File Revision: 1.10.0
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
Changed: 2026-11-07 | R3A-019 | Codex GPT-6 | Verify resident-selected capability actions and authorized knowledge dispatch.
Changed: 2026-11-07T02:35:35Z | R3A-019-ACCEPTANCE-CORRECTION | Codex GPT-6 | Reproduce false completion and prove same-activity evidence continuation.
Changed: 2026-11-07T02:41:51Z | R3A-019-ACCEPTANCE-CORRECTION | Codex GPT-6 | Assert actionable missing-edge feedback and verify the durable tool-result checkpoint.
Changed: 2026-11-07T03:34:34Z | R3A-019-INBOX-LOOP | Codex GPT-6 | Verify response schemas expose only exact capability identifiers from the current tool manifest.
Changed: 2026-11-07T03:59:26Z | R3A-019-SUSTAINED-OPERATION | Codex GPT-6 | Verify empty acceptance criteria reject intake and block legacy execution.
Changed: 2026-11-07T04:41:59Z | R3A-AP1-M1-DIAGNOSTICS | Codex GPT-6 | Assert status uses bounded latest-event evidence and skips event history payloads.
Changed: 2026-11-07T04:44:58Z | R3A-AP1-M1-DIAGNOSTICS | Codex GPT-6 | Assert indexed queue-state summary is included in status diagnostics.
Changed: 2026-11-07 | R3A-AP2-ESCALATED-REASONING | Codex GPT-6 | Verify resident-selected escalation is schema-bounded to offered roles and returned for CME enforcement.
Changed: 2026-11-07 | AP2-ESCALATED-REASONING | Codex GPT-6 | Verify Grace escalation dispatches through canonical CME invocation with durable budget context.
Changed: 2026-11-07 | AP2-ESCALATED-REASONING | Codex GPT-6 | Verify diagnostics context does not pre-authorize unused capabilities.
Changed: 2026-11-07 | AP2-ESCALATED-REASONING | Codex GPT-6 | Cover observer activity context while preserving capability authorization at actual invocation.
Changed: 2026-11-07 | R3A-AP1-MODEL-ROUTING | Codex GPT-6 | Keep escalation regression on the configured primary reasoning route.
Changed: 2026-11-07 | R3A-AP1-CME-OBSERVER-QUEUE | Codex GPT-6 | Prevent terminal activities from multiplying an already pending durable observer queue.
Changed: 2026-11-07T23:41:45Z | R3A-AP2-DELEGATION | Codex GPT-6 | Cover Grace's evidence-grounded use of a dynamic office-handoff capability and unavailable handoff behavior.
Changed: 2026-11-07T23:53:20Z | R3A-AP2-DELEGATION-CONTINUATION | Codex GPT-6 | Cover multi-route selection, handoff outcome handling, resumed context, and failed-verification corrective reasoning.
Changed: 2026-11-08T00:04:44Z | R3A-AP2-VERIFICATION-FEEDBACK | Codex GPT-6 | Verify generic institutional result validation, evidence delivery, corrective action selection, and rejection of false healthy completion claims.
Changed: 2026-11-08T01:20:00Z | R3A-AP2-VERIFICATION-FEEDBACK | Codex GPT-6 | Cover CME construction and delivery of generic independent-verifier results.
Supersedes: None.
Contracts: R3A-019 configured model routing and knowledge grounding/retrieval.
Tests: This test module.
History/Predecessor: Prior revision preserved at commit 32d0b71016c77de82b1a1cc98a9cca4152b6a44b, blob 49127b8c0101d158abf81dbea6f38d27abff4178.
"""
from __future__ import annotations

import tempfile
import unittest
import asyncio
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import AsyncMock, Mock
import hashlib
from r3a_runtime.db import Store

from r3a_runtime.acceptance import (AcceptanceCriteriaRequired, validate_acceptance,
                                    validate_criteria, validate_required_criteria)
from r3a_runtime.cme import CME, _RESIDENT_TOOLS, _knowledge_answer_issues, _requires_runtime_evidence
from r3a_runtime.config import (ConfigurationError, ModelReadinessPolicy, ModelRole,
                                ModelRoute, resolve_model_route)
from r3a_runtime.grace_module import GraceResident, resident_action_schema
from r3a_runtime.knowledge import retrieve
from r3a_runtime.diagnostics import DiagnosticProjection
from r3a_runtime.engineering import CriterionResult, VerificationResult


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


class ObserverSchedulingTests(unittest.TestCase):
    class Result:
        def __init__(self, row=None):
            self.row = row

        async def fetchone(self):
            return self.row

    class Connection:
        def __init__(self, active=None):
            self.active = active
            self.statements = []

        async def execute(self, query, params=()):
            self.statements.append((query, params))
            if "SELECT activity_id FROM r3a.activities" in query:
                return ObserverSchedulingTests.Result(self.active)
            if "SELECT revision_id FROM r3a.config_current" in query:
                return ObserverSchedulingTests.Result({"revision_id": "config-r1"})
            return ObserverSchedulingTests.Result()

    def test_activity_completion_does_not_enqueue_another_observer_if_one_is_pending(self):
        async def exercise():
            store = Store.__new__(Store)
            store._transition_on_conn = AsyncMock(return_value=True)
            conn = self.Connection(active={"activity_id": "already-queued"})
            queued = await store._schedule_observer_activity_on_conn(conn, delay_seconds=2)
            return store, conn, queued

        store, conn, queued = asyncio.run(exercise())
        self.assertFalse(queued)
        self.assertTrue(any("pg_advisory_xact_lock" in query for query, _ in conn.statements))
        self.assertFalse(any("INSERT INTO r3a.activities" in query for query, _ in conn.statements))
        store._transition_on_conn.assert_not_awaited()

    def test_observer_is_created_when_none_is_pending_using_configured_delay(self):
        async def exercise():
            store = Store.__new__(Store)
            store._transition_on_conn = AsyncMock(return_value=True)
            conn = self.Connection()
            queued = await store._schedule_observer_activity_on_conn(
                conn, delay_seconds=2, reason="next observer activity scheduled")
            return store, conn, queued

        store, conn, queued = asyncio.run(exercise())
        self.assertTrue(queued)
        inserts = [(query, params) for query, params in conn.statements
                   if "INSERT INTO r3a.activities" in query]
        self.assertEqual(len(inserts), 1)
        self.assertEqual(inserts[0][1][2], 2)
        store._transition_on_conn.assert_awaited_once()


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

    def test_transition_path_acceptance_rejects_missing_edge_then_accepts_cited_complete_path(self):
        source_digest = "a" * 64
        running = {"source_id": "knowledge.1", "source": "process.json",
                   "source_path": "transitions.RUNNING",
                   "content": "Transitions from RUNNING: STOPPING, FAILED",
                   "sha256": hashlib.sha256(
                       b"Transitions from RUNNING: STOPPING, FAILED").hexdigest(),
                   "source_sha256": source_digest}
        stopping = {"source_id": "knowledge.1", "source": "process.json",
                    "source_path": "transitions.STOPPING",
                    "content": "Transitions from STOPPING: STOPPED, FAILED",
                    "sha256": hashlib.sha256(
                        b"Transitions from STOPPING: STOPPED, FAILED").hexdigest(),
                    "source_sha256": source_digest}
        criterion = [{"criterion_id": "shutdown-route", "type": "transition_path",
                      "from_state": "RUNNING", "to_state": "STOPPED"}]
        trusted = {"process.json": {source_digest}}
        incomplete = validate_acceptance(
            validate_criteria(criterion), [running],
            {"status": "healthy", "assessment": "RUNNING cannot transition directly to STOPPED.",
             "evidence_refs": ["knowledge.1"]}, trusted)
        self.assertEqual(incomplete[0]["code"], "evidence_path_incomplete")
        complete = validate_acceptance(
            validate_criteria(criterion), [running, stopping],
            {"status": "healthy", "assessment": "Supported route: RUNNING -> STOPPING -> STOPPED.",
             "evidence_refs": ["knowledge.1"]}, trusted)
        self.assertEqual(complete, [])
        uncited = validate_acceptance(
            validate_criteria(criterion), [running, stopping],
            {"status": "healthy", "assessment": "RUNNING -> STOPPING -> STOPPED.",
             "evidence_refs": []}, trusted)
        self.assertEqual(uncited[0]["code"], "evidence_path_incomplete")

    def test_acceptance_criteria_reject_unsupported_or_ambiguous_contracts(self):
        with self.assertRaisesRegex(AcceptanceCriteriaRequired, "at least one"):
            validate_required_criteria([])
        with self.assertRaisesRegex(AcceptanceCriteriaRequired, "at least one"):
            validate_required_criteria(None)
        missing = validate_acceptance([], [], {"status": "healthy", "assessment": "done"}, {})
        self.assertEqual(missing[0]["code"], "acceptance_criteria_missing")
        with self.assertRaisesRegex(ValueError, "unsupported acceptance criterion"):
            validate_criteria([{"criterion_id": "one", "type": "model_says_ok",
                                "from_state": "RUNNING", "to_state": "STOPPED"}])
        with self.assertRaisesRegex(ValueError, "must be unique"):
            validate_criteria([{"criterion_id": "one", "type": "transition_path",
                                "from_state": "RUNNING", "to_state": "STOPPED"}] * 2)

    def test_unmatched_query_returns_no_knowledge_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "machine.json"
            source.write_text('{"machine_id":"process.lifecycle","states":["RUNNING"]}', encoding="utf-8")
            self.assertEqual(retrieve(source, "knowledge.1", "Quest avatar rendering"), [])


class DiagnosticSnapshotPerformanceTests(unittest.TestCase):
    def test_status_skips_recent_event_history_query_but_event_view_keeps_it(self):
        class StoreFake:
            def __init__(self):
                self.include_events = []
                self.queries = []

            async def snapshot(self, *, include_events=True):
                self.include_events.append(include_events)
                return {"configuration": {"revision_id": "config-1"}, "processes": [],
                        "modules": [], "resources": [], "activities": [], "state_machines": [],
                        "events": [{"event_id": "event-1"}] if include_events else []}

            async def rows(self, sql):
                self.queries.append(sql)
                if "GROUP BY state" in sql:
                    return [{"state": "QUEUED", "activity_count": 3}]
                return [{"latest_event_id": "event-1", "latest_event_type": "test",
                         "latest_event_at": "now"}]

        async def exercise():
            store = StoreFake()
            settings = SimpleNamespace(instance_id="test", diagnostic_stale_after_seconds=10)
            projection = DiagnosticProjection(settings, store)
            status = await projection.handle("status", {}, "status-key")
            events = await projection.handle("events", {}, "events-key")
            return store, status, events

        store, status, events = asyncio.run(exercise())
        self.assertEqual(store.include_events, [False, True])
        self.assertIn("ORDER BY persisted_at DESC LIMIT 1", store.queries[0])
        self.assertNotIn("count(*)", store.queries[0].casefold())
        self.assertEqual(status["event_summary"]["latest_event_id"], "event-1")
        self.assertEqual(status["activity_state_counts"], {
            "QUEUED": 3, "RUNNING": 0, "WAITING": 0, "RECOVERING": 0, "BLOCKED": 0})
        self.assertEqual(events["events"], [{"event_id": "event-1"}])


class ResidentCapabilityReasoningTests(unittest.TestCase):
    def test_observer_context_does_not_pre_authorize_uninvoked_module_capabilities(self):
        class ObserverStore:
            async def rows(self, query, _params=()):
                if "process_observations" in query:
                    return []
                return [{"server_version": "16", "observed_at": datetime.now(timezone.utc),
                         "in_recovery": False, "database": "isolated-test"}]

        async def exercise():
            cme = CME.__new__(CME)
            cme.module_id = "resident.grace"
            cme.store = ObserverStore()
            cme.settings = SimpleNamespace(module_capabilities=("reasoning.model.invoke",),
                                           heartbeat_stale_after_seconds=10,
                                           source_digest="test-config")
            cme._authorize_capability = AsyncMock(side_effect=AssertionError(
                "diagnostics context must not authorize a capability it did not invoke"))
            context = await cme._observer_context({"activity_type": "grace.objective",
                                                   "activity_id": "activity-1",
                                                   "attempt_id": "attempt-1"})
            return cme, context

        cme, context = asyncio.run(exercise())
        self.assertEqual(context["postgres"]["database"], "isolated-test")
        cme._authorize_capability.assert_not_awaited()

    def test_capability_schema_uses_exact_manifest_identifiers(self):
        schema = resident_action_schema([
            {"capability_id": "institution.knowledge.read"},
            {"capability_id": "institution.diagnostics.read"},
        ])
        self.assertEqual(schema["properties"]["capability_id"]["enum"], [
            "institution.knowledge.read", "institution.diagnostics.read"])
        self.assertNotIn("institution_knowledge_read",
                         schema["properties"]["capability_id"]["enum"])

    def test_grace_uses_directory_evidence_to_select_a_dynamic_handoff_operation(self):
        directory_tool = {
            "contract_id": "r3a.resident-capability-tool", "contract_version": "1.0.0",
            "capability_id": "directory.operation.from.registry",
            "name": "Institutional Directory", "description": "Returns offices and capability ownership.",
            "arguments_schema": {"type": "object", "properties": {}, "additionalProperties": False},
        }
        handoff_tool = {
            "contract_id": "r3a.resident-capability-tool", "contract_version": "1.0.0",
            "capability_id": "handoff.operation.from.registry",
            "name": "Office Assignment Handoff", "description": "Submits a bounded assignment to a discovered office.",
            "arguments_schema": {"type": "object", "properties": {
                "office_id": {"type": "string"}, "resident_id": {"type": "string"},
                "objective": {"type": "string"}, "evidence_ref": {"type": "string"}},
                "required": ["office_id", "objective", "evidence_ref"], "additionalProperties": False},
        }
        directory_decision = (
            '{"action":"invoke_capability","contract_id":"r3a.resident-capability-tool",'
            '"contract_version":"1.0.0","capability_id":"directory.operation.from.registry",'
            '"arguments":{},"rationale":"I need authoritative office responsibilities before deciding who should handle this."}'
        )
        handoff_decision = (
            '{"action":"invoke_capability","contract_id":"r3a.resident-capability-tool",'
            '"contract_version":"1.0.0","capability_id":"handoff.operation.from.registry",'
            '"arguments":{"office_id":"office:engineering","resident_id":"resident:bound-7",'
            '"objective":"Review the supplied patch against the stated criteria.",'
            '"evidence_ref":"directory-snapshot:sha256:abc"},'
            '"rationale":"The directory assigns this capability to the active office and returns this current resident binding."}'
        )
        resident = self._resident(directory_decision)
        resident._model_request = AsyncMock(side_effect=[
            {"id": "directory-choice", "usage": {}, "choices": [{"finish_reason": "stop",
             "message": {"content": directory_decision}}]},
            {"id": "handoff-choice", "usage": {}, "choices": [{"finish_reason": "stop",
             "message": {"content": handoff_decision}}]},
        ])
        payload = self._payload([directory_tool, handoff_tool])
        payload["objective"] = "Find the responsible office and ask it to review the patch against the criteria."

        first = asyncio.run(resident.handle("execute", payload))
        self.assertEqual(first["action"], "invoke_capability")
        self.assertEqual(first["capability_request"]["capability_id"], directory_tool["capability_id"])

        directory_result = {"outcome": "succeeded", "output": {"offices": [{
            "office_id": "office:engineering", "status": "active",
            "capabilities": [{"capability_id": "capability:review", "enabled": True}],
        }], "residents": [{"resident_id": "resident:bound-7", "office_id": "office:engineering",
                            "office_status": "active", "availability_state": "measured",
                            "availability": "available"}],
            "source": {"source_id": "directory-snapshot", "snapshot_sha256": "abc"}},
            "evidence": [{"source_id": "directory-snapshot:sha256:abc"}]}
        continuation = dict(payload)
        continuation["conversation"] = [
            {"role": "assistant", "content": directory_decision},
            {"role": "user", "content": json.dumps({"capability_result": directory_result})},
        ]
        second = asyncio.run(resident.handle("execute", continuation))
        self.assertEqual(second["action"], "invoke_capability")
        self.assertEqual(second["capability_request"]["capability_id"], handoff_tool["capability_id"])
        self.assertEqual(second["capability_request"]["arguments"]["office_id"], "office:engineering")
        self.assertEqual(second["capability_request"]["arguments"]["resident_id"], "resident:bound-7")
        self.assertEqual(second["capability_request"]["arguments"]["evidence_ref"],
                         "directory-snapshot:sha256:abc")
        request = resident._model_request.await_args_list[1].args[2]
        self.assertIn("does not establish recipient readiness", request["messages"][0]["content"])
        self.assertIn("handoff.operation.from.registry", request["messages"][-1]["content"])
        self.assertNotIn("engineering.workspace.apply_patch", request["messages"][-1]["content"])

    def test_grace_does_not_invent_a_handoff_when_registry_offers_none(self):
        directory_tool = {"capability_id": "directory.operation.from.registry",
                          "name": "Directory", "description": "Discovers offices."}
        decision = ("{\"action\":\"final\",\"decision\":{\"assessment\":"
                    "\"Directory evidence identifies an office, but no registered handoff operation is available.\","
                    "\"status\":\"blocked\",\"evidence_refs\":[\"directory-snapshot\"],"
                    "\"recommended_action\":\"Wait for a registered office handoff capability.\"}}")
        resident = self._resident(decision)
        payload = self._payload([directory_tool])
        directory_result = {"offices": [{"office_id": "office:unbound", "status": "active",
                                          "capabilities": [{"capability_id": "catalog:handoff",
                                                            "enabled": True}]}],
                            "residents": [{"resident_id": "resident:unknown",
                                           "office_id": "office:unbound",
                                           "availability_state": "unavailable"}],
                            "source": {"source_id": "directory-snapshot", "snapshot_sha256": "digest"}}
        payload["conversation"] = [{"role": "user", "content": json.dumps(
            {"capability_result": {"outcome": "succeeded", "output": directory_result}})}]
        payload["evidence"] = [{"source_id": "directory-snapshot", "sha256": "digest",
                                "content": json.dumps(directory_result)}]
        result = asyncio.run(resident.handle("execute", payload))
        self.assertEqual(result["action"], "final")
        self.assertEqual(result["decision"]["status"], "blocked")
        self.assertIn("no registered handoff operation is available",
                      result["decision"]["assessment"])
        schema = resident._model_request.await_args.args[2]["response_format"]["schema"]
        self.assertEqual(schema["properties"]["capability_id"]["enum"],
                         ["directory.operation.from.registry"])

    def test_grace_selects_between_dynamic_handoff_capabilities_using_objective_and_directory_evidence(self):
        tools = [
            {"capability_id": "handoff.for.archive", "name": "Archive Handoff",
             "description": "Route records work to the archive office.",
             "arguments_schema": {"type": "object", "properties": {
                 "office_id": {"type": "string"}, "evidence_ref": {"type": "string"}},
                 "required": ["office_id", "evidence_ref"], "additionalProperties": False}},
            {"capability_id": "handoff.for.engineering", "name": "Engineering Handoff",
             "description": "Route software review work to its owning office.",
             "arguments_schema": {"type": "object", "properties": {
                 "office_id": {"type": "string"}, "evidence_ref": {"type": "string"}},
                 "required": ["office_id", "evidence_ref"], "additionalProperties": False}},
        ]
        decision = ('{"action":"invoke_capability","contract_id":"r3a.resident-capability-tool",'
                    '"contract_version":"1.0.0","capability_id":"handoff.for.engineering",'
                    '"arguments":{"office_id":"office:engineering",'
                    '"evidence_ref":"directory:sha256:eng"},'
                    '"rationale":"The objective requests software review and the directory assigns that responsibility to this office."}')
        resident = self._resident(decision)
        payload = self._payload(tools)
        payload["objective"] = "Ask the office responsible for reviewing this software change to assess it."
        payload["conversation"] = [{"role": "user", "content": json.dumps({
            "capability_result": {"outcome": "succeeded", "output": {
                "offices": [
                    {"office_id": "office:archive", "responsibilities": ["records preservation"]},
                    {"office_id": "office:engineering", "responsibilities": ["software review"]}],
                "source": {"snapshot_sha256": "eng"}},
                "evidence": [{"source_id": "directory:sha256:eng"}]}})}]

        result = asyncio.run(resident.handle("execute", payload))
        self.assertEqual(result["action"], "invoke_capability")
        self.assertEqual(result["capability_request"]["capability_id"], "handoff.for.engineering")
        self.assertEqual(result["capability_request"]["arguments"]["office_id"], "office:engineering")
        request = resident._model_request.await_args.args[2]
        self.assertEqual(set(request["response_format"]["schema"]["properties"]["capability_id"]["enum"]),
                         {"handoff.for.archive", "handoff.for.engineering"})
        request_text = json.dumps(request["messages"])
        self.assertIn("office:engineering", request_text)
        self.assertIn("directory:sha256:eng", request_text)

    def test_grace_handles_returned_handoff_and_blocks_rejected_or_unavailable_results_truthfully(self):
        directory_tool = {"capability_id": "directory.dynamic", "name": "Directory",
                          "description": "Returns authoritative offices."}
        rejected = ("{\"action\":\"final\",\"decision\":{\"assessment\":"
                    "\"The office rejected the request and gave no authorized alternative.\","
                    "\"status\":\"blocked\",\"evidence_refs\":[\"handoff.result\"],"
                    "\"recommended_action\":\"Report the rejection and its reason.\"}}")
        alternate = ("{\"action\":\"invoke_capability\",\"contract_id\":"
                     "\"r3a.resident-capability-tool\",\"contract_version\":\"1.0.0\","
                     "\"capability_id\":\"alternate.handoff.dynamic\","
                     "\"arguments\":{\"office_id\":\"office:alternate\"},"
                     "\"rationale\":\"The first recipient returned the assignment as unavailable; the directory evidence identifies this offered alternate.\"}")
        cases = [
            ("REJECTED", "The work is outside this office's responsibility.", [], rejected, "final", "blocked"),
            ("RETURNED", "Recipient unavailable; directory evidence lists an alternate.", [
                {"capability_id": "alternate.handoff.dynamic", "name": "Alternate handoff",
                 "description": "Submits to an alternate office.",
                 "arguments_schema": {"type": "object", "properties": {"office_id": {"type": "string"}},
                                      "required": ["office_id"], "additionalProperties": False}}],
             alternate, "invoke_capability", "alternate.handoff.dynamic"),
            ("UNAVAILABLE", "The handoff provider is not available.", [], rejected, "final", "blocked"),
        ]
        for outcome, explanation, extra_tools, response, expected_action, expected_value in cases:
            with self.subTest(outcome=outcome):
                resident = self._resident(response)
                payload = self._payload([directory_tool, *extra_tools])
                payload["conversation"] = [{"role": "user", "content": json.dumps({
                    "capability_result": {"outcome": outcome.lower(), "output": {
                        "status": outcome, "explanation": explanation},
                        "authorization": {"allowed": outcome == "RETURNED"}}})}]
                result = asyncio.run(resident.handle("execute", payload))
                self.assertEqual(expected_action, result["action"])
                if expected_action == "final":
                    self.assertEqual(expected_value, result["decision"]["status"])
                else:
                    self.assertEqual(expected_value, result["capability_request"]["capability_id"])
                request = resident._model_request.await_args.args[2]
                self.assertIn(explanation, json.dumps(request["messages"]))

    def test_grace_resumes_from_persisted_handoff_result_without_repeating_the_side_effect(self):
        handoff_tool = {"capability_id": "handoff.dynamic", "name": "Office handoff",
                        "description": "Submits a scoped assignment."}
        followup_tool = {"capability_id": "followup.dynamic", "name": "Review evidence",
                         "description": "Reads the durable office response."}
        response = ('{"action":"invoke_capability","contract_id":"r3a.resident-capability-tool",'
                    '"contract_version":"1.0.0","capability_id":"followup.dynamic",'
                    '"arguments":{},"rationale":"The prior handoff was accepted; inspect its durable result before reporting."}')
        resident = self._resident(response)
        payload = self._payload([handoff_tool, followup_tool])
        payload["activity_id"] = "same-activity-after-recovery"
        payload["conversation"] = [
            {"role": "assistant", "content": "prior model action: handoff.dynamic"},
            {"role": "user", "content": json.dumps({"capability_result": {
                "outcome": "succeeded", "output": {"status": "ACCEPTED", "handoff_id": "handoff-42"},
                "evidence": [{"source_id": "handoff:42", "sha256": "d" * 64}]}})},
        ]
        payload["evidence"] = [{"source_id": "handoff:42", "sha256": "d" * 64,
                                 "content": "ACCEPTED by the office; handoff_id=handoff-42"}]

        result = asyncio.run(resident.handle("execute", payload))
        self.assertEqual(result["activity_id"], "same-activity-after-recovery")
        self.assertEqual(result["action"], "invoke_capability")
        self.assertEqual(result["capability_request"]["capability_id"], "followup.dynamic")
        self.assertEqual(resident._model_request.await_count, 1)
        request = resident._model_request.await_args.args[2]
        self.assertIn("handoff-42", request["messages"][-1]["content"])
        self.assertIn("handoff-42", json.dumps(request["messages"]))

    def test_cme_checkpoints_handoff_result_and_recovers_same_activity_without_reinvoking_it(self):
        class StoreFake:
            def __init__(self):
                self.checkpoint = None
                self.failed = None
                self.blocked = None
                self.progress = []

            async def record_progress(self, _activity, progress, checkpoint):
                self.progress.append(dict(progress))
                self.checkpoint = json.loads(json.dumps(checkpoint))

            async def fail_activity(self, activity, error, retry_seconds):
                self.failed = (activity["activity_id"], str(error), retry_seconds)

            async def block_activity(self, activity, reason, details):
                self.blocked = (activity["activity_id"], reason, details)

            async def finish_activity(self, activity, result):
                raise AssertionError("this recovery fixture ends truthfully blocked")

        async def exercise():
            route = {"route_id": "configured-primary", "provider": "fixture", "model": "fixture-model",
                     "endpoint": "http://127.0.0.1:1/chat", "timeout_seconds": 1, "max_tokens": 64}
            base = {"activity_type": "grace.objective", "activity_id": "activity-42",
                    "attempt_id": "attempt-1", "objective": "Have the responsible office review this change.",
                    "event_kind": "objective", "route_id": "configured-primary", "model_route": route,
                    "evidence_format": "r3a.knowledge-evidence.v1", "required_evidence_refs": [],
                    "evidence": [], "available_tools": [{"contract_id": "r3a.resident-capability-tool",
                    "contract_version": "1.0.0", "capability_id": "handoff.dynamic"}],
                    "available_engineering_operations": [], "engineering_assignment": None,
                    "reasoning_escalation": {"enabled": False}, "conversation": [],
                    "reasoning_state": {}, "pending_final": None, "config_revision": "config-42",
                    "acceptance_criteria": []}
            store = StoreFake()
            cme = CME.__new__(CME)
            cme.settings = SimpleNamespace(restart_initial_seconds=1, restart_max_seconds=2,
                                            module_capabilities=("handoff.dynamic",))
            cme.module_process = SimpleNamespace(returncode=None)
            cme.module_id = "resident.grace"
            cme.module_version = "test"
            cme.store = store
            cme.active_activities = {}
            contexts = []

            async def objective_context(activity):
                checkpoint = activity.get("checkpoint") or {}
                reasoning_state = checkpoint.get("reasoning_state") or {}
                context = dict(base)
                context.update({"activity_id": activity["activity_id"],
                                "attempt_id": activity["attempt_id"],
                                "conversation": list(reasoning_state.get("conversation", [])),
                                "reasoning_state": reasoning_state,
                                "evidence": list(checkpoint.get("evidence", [])),
                                "required_evidence_refs": list(checkpoint.get("required_evidence_refs", [])),
                                "request_ref": f"request-{activity['attempt_id']}"})
                contexts.append(context)
                return context

            cme._objective_context = objective_context
            handoff_action = {"action": "invoke_capability", "contract_id": "r3a.resident-capability-tool",
                              "contract_version": "1.0.0", "capability_id": "handoff.dynamic",
                              "arguments": {"office_ref": "directory-returned-office"},
                              "rationale": "The directory evidence identifies this office as responsible."}
            handoff_result = {"contract_id": "r3a.resident-capability-tool", "contract_version": "1.0.0",
                              "capability_id": "handoff.dynamic", "outcome": "succeeded",
                              "output": {"status": "ACCEPTED", "handoff_id": "handoff-42"},
                              "evidence": [{"source_id": "handoff:42", "sha256": "e" * 64,
                                            "content": "Office accepted handoff-42."}],
                              "authorization": {"audit_event_id": "audit-42"}}
            cme._invoke_resident_capability = AsyncMock(return_value=handoff_result)
            call_count = 0
            resumed_payloads = []

            async def module_call(_operation, payload, **_kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return {"result": {"action": "invoke_capability", "capability_request": handoff_action,
                        "model_content": json.dumps(handoff_action), "model": {"request_ref": "model-1",
                        "request_sha256": "a" * 64, "result_ref": "result-1", "result_sha256": "b" * 64}}}
                if call_count == 2:
                    raise RuntimeError("simulated interruption after durable handoff result")
                resumed_payloads.append(json.loads(json.dumps(payload)))
                blocked = {"action": "final", "decision": {"assessment": "The accepted handoff exists, but no attributable office work result is available yet.",
                           "status": "blocked", "evidence_refs": ["handoff:42"],
                           "recommended_action": "Resume when the office result is available."}}
                return {"result": {"action": "final", "decision": blocked["decision"],
                    "model_content": json.dumps(blocked), "model": {"request_ref": "model-2",
                    "request_sha256": "c" * 64, "result_ref": "result-2", "result_sha256": "d" * 64}}}

            cme._module_call = module_call
            first = {"activity_type": "grace.objective", "activity_id": "activity-42",
                     "attempt_id": "attempt-1", "attempt_count": 0,
                     "input": {"objective": base["objective"], "correlation_id": "correlation-42"},
                     "checkpoint": {}}
            await cme._run_activity(first)
            self.assertIsNotNone(store.failed)
            checkpoint = store.checkpoint
            self.assertIsNotNone(checkpoint)
            self.assertEqual(len(checkpoint["reasoning_state"]["capability_invocations"]), 1)
            self.assertIn("handoff-42", json.dumps(checkpoint["reasoning_state"]["conversation"]))

            resumed = {**first, "attempt_id": "attempt-2", "attempt_count": 1,
                       "checkpoint": checkpoint}
            await cme._run_activity(resumed)
            self.assertEqual(cme._invoke_resident_capability.await_count, 1)
            self.assertEqual(store.blocked[0], "activity-42")
            restored = checkpoint["reasoning_state"]["conversation"]
            self.assertEqual(contexts[1]["conversation"][:len(restored)], restored)
            self.assertIn("handoff-42", json.dumps(resumed_payloads[0]["conversation"]))
            self.assertEqual(contexts[0]["activity_id"], contexts[1]["activity_id"])

        asyncio.run(exercise())


    def test_grace_proposes_a_scoped_correction_after_failed_verification(self):
        operation_id = "registered.operation.from.current-manifest"
        operation = {"operation_id": operation_id, "contract_version": "1.0.0"}
        proposal = ("{\"action\":\"propose_engineering\",\"rationale\":"
                    "\"The verifier found the generated field does not match the requested value; revise that artifact within the assigned workspace.\","
                    "\"proposal\":{\"operation_id\":\"registered.operation.from.current-manifest\","
                    "\"contract_version\":\"1.0.0\",\"target\":{\"workspace_id\":\"workspace:assigned\"},"
                    "\"inputs\":{\"path\":\"deliverables/result.json\",\"content\":\"{\\\"value\\\":\\\"corrected\\\"}\"},"
                    "\"verification_plan\":{\"criteria\":[\"criterion:value-match\"]}}}")
        resident = self._resident(proposal)
        payload = self._payload([])
        payload["engineering_assignment"] = {"workspace_id": "workspace:assigned",
                                              "allowed_paths": ["deliverables/**"],
                                              "criteria": ["criterion:value-match"]}
        payload["available_engineering_operations"] = [operation]
        payload["conversation"] = [{"role": "user", "content": json.dumps({
            "independent_verification": {"outcome": "FAIL", "criterion_results": [
                {"criterion_id": "criterion:value-match", "outcome": "FAIL",
                 "message": "actual value differs from the required value"}]}})}]

        result = asyncio.run(resident.handle("execute", payload))
        self.assertEqual(result["action"], "propose_engineering")
        self.assertEqual(result["engineering_proposal"]["operation_id"], operation_id)
        request = resident._model_request.await_args.args[2]
        self.assertIn("FAIL", json.dumps(request["messages"]))
        self.assertIn("failed criteria", request["messages"][0]["content"])

    def test_grace_reports_failed_verification_blocked_when_no_corrective_operation_is_offered(self):
        response = ("{\"action\":\"engineering_assess\",\"engineering_assessment\":{"
                    "\"status\":\"blocked\",\"assessment\":"
                    "\"Independent verification failed and no authorized corrective operation is available.\","
                    "\"evidence_refs\":[\"verification:42\"]}}")
        resident = self._resident(response)
        payload = self._payload([])
        payload["conversation"] = [{"role": "user", "content": json.dumps({
            "independent_verification": {"outcome": "FAIL", "verification_id": "verification:42",
                                          "criterion_results": [{"criterion_id": "required-value",
                                                                 "outcome": "FAIL"}]}})}]
        result = asyncio.run(resident.handle("execute", payload))
        self.assertEqual(result["action"], "engineering_assess")
        self.assertEqual(result["engineering_assessment"]["status"], "blocked")
        self.assertEqual(resident._model_request.await_count, 1)

    def test_legacy_activity_without_acceptance_criteria_is_blocked_before_resident_execution(self):
        class StoreFake:
            def __init__(self):
                self.blocked = None
                self.finished = None

            async def block_activity(self, _activity, reason, details):
                self.blocked = (reason, details)

            async def finish_activity(self, _activity, result):
                self.finished = result

        async def exercise():
            cme = CME.__new__(CME)
            cme.module_process = SimpleNamespace(returncode=None)
            cme.module_id = "resident.grace"
            cme.store = StoreFake()
            cme.settings = SimpleNamespace(module_capabilities=())
            cme.active_activities = {}
            activity = {"activity_id": "legacy-empty-criteria", "activity_type": "grace.objective",
                        "attempt_id": "attempt-1", "input": {"objective": "unverified legacy task"}}
            await cme._run_activity(activity)
            return cme.store

        store = asyncio.run(exercise())
        self.assertIsNone(store.finished)
        self.assertEqual(store.blocked[0], "objective acceptance criteria are required")
        self.assertEqual(store.blocked[1]["criteria_gaps"][0]["code"],
                         "acceptance_criteria_missing")

    def _resident(self, model_content):
        resident = GraceResident.__new__(GraceResident)
        resident.module_id = "resident.grace"
        resident.module_version = "test"
        resident.state = "ACTIVE"
        resident.last_activity = None
        route = ModelRoute("local", "fixture", "http://127.0.0.1:1/chat", "fixture-model", 1, 128)
        resident.settings = SimpleNamespace(model_route=lambda _route_id=None: route)
        resident._model_request = AsyncMock(return_value={
            "id": "fixture-response", "usage": {"prompt_tokens": 8, "completion_tokens": 5},
            "choices": [{"finish_reason": "stop", "message": {"content": model_content}}]})
        return resident

    def _payload(self, tools):
        return {"activity_id": "activity-1", "attempt_id": "attempt-1", "request_ref": "request-1",
                "config_revision": "config-1", "activity_type": "grace.objective",
                "objective": "Identify the valid successors from STOPPING", "evidence": [],
                "available_tools": tools, "conversation": [], "route_id": "local"}

    def _resident_result(self):
        return {"contract_id": "r3a.resident.result", "contract_version": "1.0.0",
                "activity_id": "activity-1", "attempt_id": "attempt-1",
                "correlation_id": "correlation-1", "resident_id": "resident.grace",
                "config_revision": "config-1", "issued_at": "2026-11-07T23:59:11Z",
                "issuer": {"component_id": "independent-verifier", "decision_ref": "verification-17"},
                "outcome": "FAIL",
                "evidence": [{"evidence_ref": "artifact:result.json", "kind": "artifact",
                              "content": {"observed": "wrong value"}}],
                "failure_reasons": [{"code": "criterion_mismatch", "message": "required value differs",
                                     "evidence_refs": ["artifact:result.json"]}],
                "completion_authority": False}

    def test_generic_failed_result_evidence_is_delivered_for_resident_decision(self):
        tool = {"capability_id": "capability.from.current.registry"}
        response = ('{"action":"invoke_capability","contract_id":"r3a.resident-capability-tool",'
                    '"contract_version":"1.0.0","capability_id":"capability.from.current.registry",'
                    '"arguments":{},"rationale":"Use the offered corrective operation against the verifier finding"}')
        resident = self._resident(response)
        payload = self._payload([tool])
        payload["correlation_id"] = "correlation-1"
        payload["resident_result"] = self._resident_result()

        result = asyncio.run(resident.handle("execute", payload))

        self.assertEqual(result["action"], "invoke_capability")
        self.assertEqual(result["resident_result"]["outcome"], "FAIL")
        request = resident._model_request.await_args.args[2]
        model_input = json.loads(request["messages"][-1]["content"])
        self.assertEqual(model_input["resident_result"]["failure_reasons"][0]["code"], "criterion_mismatch")
        self.assertEqual(model_input["resident_result"]["evidence"][0]["content"]["observed"], "wrong value")

    def test_generic_result_with_mismatched_lineage_is_rejected_before_inference(self):
        resident = self._resident(
            '{"action":"final","decision":{"assessment":"blocked","status":"blocked",'
            '"evidence_refs":[],"recommended_action":"none"}}')
        payload = self._payload([])
        payload["resident_result"] = self._resident_result()
        payload["resident_result"]["activity_id"] = "different-activity"

        with self.assertRaisesRegex(ValueError, "lineage"):
            asyncio.run(resident.handle("execute", payload))
        resident._model_request.assert_not_awaited()

    def test_grace_cannot_report_failed_verification_as_healthy(self):
        resident = self._resident(
            '{"action":"final","decision":{"assessment":"All requirements pass",'
            '"status":"healthy","evidence_refs":["artifact:result.json"],"recommended_action":"none"}}')
        payload = self._payload([])
        payload["correlation_id"] = "correlation-1"
        payload["resident_result"] = self._resident_result()

        with self.assertRaisesRegex(RuntimeError, "cannot report.*healthy"):
            asyncio.run(resident.handle("execute", payload))

    def test_model_selected_capability_call_is_returned_as_resident_action(self):
        tool = {"capability_id": "institution.knowledge.read"}
        resident = self._resident(
            '{"action":"invoke_capability","contract_id":"r3a.resident-capability-tool",'
            '"contract_version":"1.0.0","capability_id":"institution.knowledge.read",'
            '"arguments":{"query":"List successors after STOPPING"},'
            '"rationale":"Need authoritative transition facts"}')
        result = asyncio.run(resident.handle("execute", self._payload([tool])))
        self.assertEqual(result["action"], "invoke_capability")
        self.assertEqual(result["capability_request"]["arguments"]["query"],
                         "List successors after STOPPING")
        actual_request = resident._model_request.await_args.args[2]
        self.assertIn("available_tools", actual_request["messages"][-1]["content"])

    def test_model_cannot_request_capability_outside_supplied_manifest(self):
        resident = self._resident(
            '{"action":"invoke_capability","contract_id":"r3a.resident-capability-tool",'
            '"contract_version":"1.0.0","capability_id":"institution.write",'
            '"arguments":{"query":"x"},"rationale":"unsupported"}')
        with self.assertRaisesRegex(RuntimeError, "not present in its tool manifest"):
            asyncio.run(resident.handle("execute", self._payload([])))

    def test_grace_can_request_only_an_offered_escalation_role(self):
        resident = self._resident(
            '{"action":"escalate_reasoning","target_role_id":"resident.primary",'
            '"rationale":"The 0.6B route cannot reliably compare the two evidence branches."}')
        payload = self._payload([])
        payload["reasoning_escalation"] = {"enabled": True, "available_roles": [
            {"role_id": "resident.primary", "route_id": "primary", "readiness": "ready"}],
            "max_completion_tokens_per_activity": 512, "charged_completion_tokens": 0}
        result = asyncio.run(resident.handle("execute", payload))
        self.assertEqual(result["action"], "escalate_reasoning")
        self.assertEqual(result["reasoning_escalation_request"]["target_role_id"], "resident.primary")
        schema = resident._model_request.await_args.args[2]["response_format"]["schema"]
        self.assertIn("escalate_reasoning", schema["properties"]["action"]["enum"])
        self.assertEqual(schema["properties"]["target_role_id"]["enum"], ["resident.primary"])

    def test_grace_cannot_select_unoffered_escalation_role(self):
        resident = self._resident(
            '{"action":"escalate_reasoning","target_role_id":"resident.external",'
            '"rationale":"Need a stronger route."}')
        payload = self._payload([])
        payload["reasoning_escalation"] = {"enabled": True, "available_roles": [
            {"role_id": "resident.primary", "route_id": "primary", "readiness": "ready"}]}
        with self.assertRaisesRegex(RuntimeError, "not offered by policy"):
            asyncio.run(resident.handle("execute", payload))

    def test_cme_returns_source_digested_knowledge_only_after_authorization(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "process.json"
            source.write_text('{"transitions":{"STOPPING":["STOPPED","FAILED"]}}', encoding="utf-8")
            cme = CME.__new__(CME)
            cme.settings = SimpleNamespace(module_capabilities=("institution.knowledge.read",),
                                           knowledge_sources=(source,))
            cme._authorize_capability = AsyncMock(return_value={"audit_event_id": "audit-1"})
            result = asyncio.run(cme._invoke_resident_capability(
                {"activity_id": "activity-1", "attempt_id": "attempt-1"},
                {"contract_id": "r3a.resident-capability-tool", "contract_version": "1.0.0",
                 "capability_id": "institution.knowledge.read",
                 "arguments": {"query": "List successors after STOPPING"},
                 "rationale": "Need source fact"}))
            cme._authorize_capability.assert_awaited_once()
            self.assertEqual(result["outcome"], "succeeded")
            self.assertEqual(result["evidence"][0]["content"], "Transitions from STOPPING: STOPPED, FAILED")
            self.assertEqual(result["authorization"]["audit_event_id"], "audit-1")

    def test_cme_authorizes_and_routes_grace_requested_escalation_with_durable_budget_evidence(self):
        class StoreFake:
            def __init__(self):
                self.progress = []
                self.blocked = None

            async def record_progress(self, _activity, progress, checkpoint):
                self.progress.append((dict(progress), json.loads(json.dumps(checkpoint))))

            async def block_activity(self, _activity, reason, details):
                self.blocked = (reason, details)

            async def renew_activity_lease(self, _activity):
                return None

        local = ModelRoute("autonomic", "openai-compatible", "http://127.0.0.1:18796/v1/chat/completions",
                           "small", 20, 64)
        primary = ModelRoute("primary", "openai-compatible", "http://127.0.0.1:8080/v1/chat/completions",
                             "large", 30, 128)
        readiness = ModelReadinessPolicy("models", "1.0.0", "http://127.0.0.1:8080/v1/models",
                                         2, 1, 0.1, 5)
        roles = (
            ModelRole("resident.autonomic", "autonomic", ("monitor.health",), ("text",), ("autonomic",), (),
                      45, "block", 5, 1, readiness),
            ModelRole("resident.primary", "primary", ("reason.text", "plan"), ("text",),
                      ("objective_reasoning",), (),
                      45, "block", 5, 1, readiness),
            ModelRole("resident.external", "external", ("reason.text", "plan"), ("text",),
                      ("objective_reasoning",), (), 45, "block", 5, 1, readiness),
        )
        operation = SimpleNamespace(descriptor={"operation_id": "reasoning.model.invoke",
                                                 "contract_version": "1.0.0",
                                                 "effect_class": "external_write"})
        settings = SimpleNamespace(model_roles=roles, model_route=lambda route_id: {
            "autonomic": local, "primary": primary, "external": primary}[route_id], source_digest="config-1",
            capability_registry=SimpleNamespace(resolve=Mock(return_value=operation)),
            module_capabilities=(), lease_seconds=30, restart_initial_seconds=1,
            restart_max_seconds=3)

        async def exercise():
            cme = CME.__new__(CME)
            cme.module_process = SimpleNamespace(returncode=None)
            cme.module_id = "resident.grace"
            cme.module_version = "1.2.3"
            cme.settings = settings
            cme.store = StoreFake()
            cme.active_activities = {}
            cme._lease_heartbeat = AsyncMock()
            cme._objective_context = AsyncMock(return_value={
                "activity_type": "grace.objective", "activity_id": "activity-1", "attempt_id": "attempt-1",
                "objective": "Use stronger reasoning to evaluate the evidence and report limitations.",
                "acceptance_criteria": [{"criterion_id": "result", "type": "evidence_citation"}],
                "event_kind": "objective", "task_class": "objective_reasoning", "route_id": "primary",
                "model_route": {"route_id": "primary", "provider": "openai-compatible", "model": "large",
                                "endpoint": primary.endpoint, "timeout_seconds": 20, "max_tokens": 64},
                "selected_role_id": "resident.primary", "route_decision": {},
                "evidence_format": "r3a.knowledge-evidence.v1", "required_evidence_refs": [],
                "evidence": [], "available_tools": [], "available_engineering_operations": [],
                "reasoning_escalation": {"enabled": True,
                    "available_roles": [{"role_id": "resident.external", "route_id": "external",
                                         "readiness": "ready"}]},
                "conversation": [], "reasoning_state": {}, "pending_final": None,
                "config_revision": "config-1"})
            cme._model_readiness_observations = AsyncMock(return_value={"resident.external": {
                "status": "ready", "observed_at": datetime.now(timezone.utc).isoformat(),
                "provider_id": "models", "evidence_ref": "ready-1", "evidence": {"model_id": "large"},
                "config_revision": "config-1"}})
            cme.invoke_capability = AsyncMock(return_value={
                "contract_id": "r3a.capability-invocation.v1", "contract_version": "1.0.0",
                "invocation_id": "invocation-1", "outcome": "SUCCEEDED",
                "authorization": {"provider_id": "capability_grants", "allowed": True,
                                   "decision_id": "decision-1", "audit_event_id": "audit-1",
                                   "policy_revision": "policy-1", "config_revision": "config-1"},
                "output": {"content": "The evidence is incomplete; inspect the activity contract.",
                           "usage": {"completion_tokens": 26}},
                "evidence": [{"evidence_id": "model-inference:invocation-1"}]})
            escalation = {"action": "escalate_reasoning", "target_role_id": "resident.external",
                          "rationale": "The current route cannot resolve the uncertainty from the evidence."}
            final = {"action": "final", "decision": {"assessment": "Insufficient evidence remains.",
                "status": "blocked", "evidence_refs": [], "recommended_action": "Obtain missing evidence."}}
            calls = [
                {"result": {"action": "escalate_reasoning", "reasoning_escalation_request": escalation,
                            "model_content": json.dumps(escalation),
                            "model": {"route_id": "autonomic", "request_ref": "small-req",
                                      "result_ref": "small-result", "request_sha256": "1"*64,
                                      "result_sha256": "2"*64, "usage": {"completion_tokens": 10}}}},
                {"result": {"action": "final", "decision": final["decision"],
                            "model_content": json.dumps(final),
                            "model": {"route_id": "primary", "request_ref": "large-req",
                                      "result_ref": "large-result", "request_sha256": "3"*64,
                                      "result_sha256": "4"*64, "usage": {"completion_tokens": 26}}}},
            ]
            module_payloads = []

            async def module_call(_operation, payload, **_kwargs):
                module_payloads.append(json.loads(json.dumps(payload)))
                return calls.pop(0)

            cme._module_call = module_call
            activity = {"activity_type": "grace.objective", "activity_id": "activity-1",
                "attempt_id": "attempt-1", "attempt_count": 0,
                "input": {"objective": "Use stronger reasoning to evaluate the evidence and report limitations.",
                    "correlation_id": "correlation-1", "reasoning_escalation": {
                        "contract_id": "r3a.reasoning-escalation-policy", "contract_version": "1.0.0",
                        "enabled": True, "authorization_capability_id": "reasoning.model.invoke",
                    "allowed_role_ids": ["resident.external"], "max_requests_per_activity": 1,
                        "max_completion_tokens_per_activity": 128, "config_revision": "config-1"}},
                "checkpoint": {}}
            await cme._run_activity(activity)
            return cme, module_payloads

        cme, payloads = asyncio.run(exercise())
        cme.invoke_capability.assert_awaited_once()
        invocation = cme.invoke_capability.await_args.args[0]
        self.assertEqual(invocation["operation_id"], "reasoning.model.invoke")
        self.assertIsNone(invocation["work_order"])
        self.assertEqual(invocation["budget_reservation"]["resource"], "completion_tokens")
        self.assertEqual(cme.invoke_capability.await_args.kwargs["_approved_budget_reservation"],
                         invocation["budget_reservation"])
        self.assertEqual(payloads[0]["route_id"], "primary")
        self.assertEqual(payloads[1]["route_id"], "primary")
        self.assertIn("The evidence is incomplete", payloads[1]["conversation"][-1]["content"])
        self.assertEqual(cme.store.blocked[1]["reasoning_trace"]["model_turns"][-1]["result_ref"],
                         "large-result")
        checkpoint = next(item[1] for item in cme.store.progress
                          if item[0]["phase"] == "resident.decision.ready")
        request = checkpoint["reasoning_state"]["escalation"]["requests"][0]
        self.assertEqual(request["status"], "COMPLETED")
        self.assertEqual(request["charged_completion_tokens"], 128)
        self.assertEqual(request["authorization"]["audit_event_id"], "audit-1")

    def test_cme_rejects_false_completion_and_resumes_same_activity_for_missing_evidence(self):
        class StoreFake:
            def __init__(self):
                self.progress = []
                self.completed = None
                self.blocked = None

            async def record_progress(self, _activity, progress, checkpoint):
                self.progress.append((dict(progress), json.loads(json.dumps(checkpoint))))

            async def renew_activity_lease(self, _activity):
                return None

            async def finish_activity(self, _activity, result):
                self.completed = result

            async def block_activity(self, _activity, reason, details):
                self.blocked = (reason, details)

            async def fail_activity(self, _activity, error, _retry):
                raise AssertionError(f"unexpected failure: {error}")

        async def exercise():
            with tempfile.TemporaryDirectory() as directory:
                source = Path(directory) / "process.json"
                source.write_text('{"transitions":{"RUNNING":["STOPPING","FAILED"],'
                                  '"STOPPING":["STOPPED","FAILED"]}}', encoding="utf-8")
                source_digest = hashlib.sha256(source.read_bytes()).hexdigest()
                running_content = "Transitions from RUNNING: STOPPING, FAILED"
                initial_evidence = [
                    {"source_id": "runtime.processes", "source_path": "runtime.processes",
                     "sha256": "1" * 64, "content": [{"component_id": "ring0", "state": "RUNNING"}]},
                    {"source_id": "knowledge.1", "source": "process.json",
                     "source_path": "transitions.RUNNING", "content": running_content,
                     "sha256": hashlib.sha256(running_content.encode()).hexdigest(),
                     "source_sha256": source_digest},
                ]
                criteria = [{"criterion_id": "shutdown-route", "type": "transition_path",
                             "from_state": "RUNNING", "to_state": "STOPPED"}]
                cme = CME.__new__(CME)
                cme.settings = SimpleNamespace(module_capabilities=("institution.knowledge.read",),
                                               knowledge_sources=(source,), lease_seconds=30,
                                               restart_initial_seconds=1, restart_max_seconds=3)
                cme.store = StoreFake()
                cme.module_process = SimpleNamespace(returncode=None)
                cme.module_id = "resident.grace"
                cme.module_version = "1.2.0"
                cme.authorization_provider = None
                cme.active_activities = {}
                cme._objective_context = AsyncMock(return_value={
                    "activity_type": "grace.objective", "activity_id": "activity-1",
                    "attempt_id": "attempt-1",
                    "objective": "Prepare the same on-call reference and prove the process route "
                                "from RUNNING to STOPPED using authoritative evidence.",
                    "acceptance_criteria": criteria,
                    "event_kind": "objective", "route_id": "local",
                    "model_route": {"route_id": "local", "provider": "fixture", "model": "fixture",
                                    "endpoint": "http://127.0.0.1:1/chat", "timeout_seconds": 1,
                                    "max_tokens": 128},
                    "evidence_format": "r3a.knowledge-evidence.v1",
                    "required_evidence_refs": ["runtime.processes", "knowledge.1"],
                    "evidence": initial_evidence, "available_tools": [_RESIDENT_TOOLS[0]], "conversation": [],
                    "reasoning_state": {}, "pending_final": None, "config_revision": "config-1"})
                cme._authorize_capability = AsyncMock(return_value={"audit_event_id": "audit-1"})
                next_action = {"action": "invoke_capability",
                               "contract_id": "r3a.resident-capability-tool", "contract_version": "1.0.0",
                               "capability_id": "institution.knowledge.read",
                               "arguments": {"query": "What transitions are permitted after STOPPING?"},
                               "rationale": "The evidence so far ends at STOPPING and does not prove the route reaches STOPPED."}
                incomplete = {"assessment": "RUNNING cannot transition directly to STOPPED; RUNNING -> STOPPING.",
                              "status": "healthy", "evidence_refs": ["runtime.processes", "knowledge.1"],
                              "recommended_action": "none"}
                complete = {"assessment": "The evidenced route is RUNNING -> STOPPING -> STOPPED.",
                            "status": "healthy", "evidence_refs": ["runtime.processes", "knowledge.1"],
                            "recommended_action": "none"}
                responses = [
                    {"result": {"action": "final", "decision": incomplete,
                                 "model_content": json.dumps({"action": "final", "decision": incomplete}),
                                 "model": {"request_ref": "model-1", "request_sha256": "a" * 64,
                                           "result_ref": "result-1", "result_sha256": "b" * 64}}},
                    {"result": {"action": "invoke_capability", "capability_request": next_action,
                                 "model_content": json.dumps(next_action),
                                 "model": {"request_ref": "model-2", "request_sha256": "c" * 64,
                                           "result_ref": "result-2", "result_sha256": "d" * 64}}},
                    {"result": {"action": "final", "decision": complete,
                                 "model_content": json.dumps({"action": "final", "decision": complete}),
                                 "model": {"request_ref": "model-3", "request_sha256": "e" * 64,
                                           "result_ref": "result-3", "result_sha256": "f" * 64}}},
                ]
                continuation_contexts = []

                async def module_call(_operation, payload, **_kwargs):
                    continuation_contexts.append(json.loads(json.dumps(payload)))
                    return responses.pop(0)

                cme._module_call = module_call
                activity = {"activity_type": "grace.objective", "activity_id": "activity-1",
                            "attempt_id": "attempt-1", "attempt_count": 0,
                            "input": {"objective": "Prepare the same on-call reference and prove the process route "
                                               "from RUNNING to STOPPED using authoritative evidence.",
                                      "acceptance_criteria": criteria}, "checkpoint": {}}
                await cme._run_activity(activity)
                self.assertIsNone(cme.store.blocked)
                self.assertEqual(cme.store.completed["decision"], complete)
                self.assertEqual(len(cme.store.completed["reasoning_trace"]["capability_invocations"]), 1)
                rejection = next((progress, checkpoint) for progress, checkpoint in cme.store.progress
                                 if progress["phase"] == "resident.completion.rejected")
                self.assertEqual(rejection[0]["criteria_gaps"][0]["code"], "evidence_path_incomplete")
                self.assertIn("STOPPING", continuation_contexts[1]["conversation"][-1]["content"])
                self.assertIn("RUNNING -> STOPPING", continuation_contexts[1]["conversation"][0]["content"])
                tool_checkpoint = next(checkpoint for progress, checkpoint in cme.store.progress
                                       if progress["phase"] == "resident.capability.completed")
                self.assertIn("transitions.STOPPING",
                              [item["source_path"] for item in tool_checkpoint["evidence"]])
                self.assertEqual(len(tool_checkpoint["reasoning_state"]["conversation"]), 4)

        asyncio.run(exercise())



class ResidentVerificationFeedbackIntegrationTests(unittest.TestCase):
    def _fixture(self):
        cme = CME.__new__(CME)
        cme.module_id = "resident.grace"
        cme.settings = SimpleNamespace(source_digest="config-r1")
        activity = {
            "activity_id": "11111111-1111-4111-8111-111111111111",
            "attempt_id": "22222222-2222-4222-8222-222222222222",
            "input": {"correlation_id": "33333333-3333-4333-8333-333333333333"},
        }
        verification = VerificationResult(
            verification_id="44444444-4444-4444-8444-444444444444",
            activity_id=activity["activity_id"],
            work_order_id="55555555-5555-4555-8555-555555555555",
            work_order_version=1, verifier_id="independent.verifier", verifier_version="1.0.0",
            policy_revision="policy-r1", artifact_digests=("sha256:" + "a" * 64,),
            results=(CriterionResult("required-value", "FAIL", ("workspace:result.json",),
                                     "Observed value differs from the assigned value."),),
            verified_at="2026-11-08T01:20:00Z", outcome="FAIL")
        return cme, activity, verification

    def test_cme_builds_lineage_bound_non_authoritative_verifier_result(self):
        cme, activity, verification = self._fixture()
        result = cme._resident_result_from_verification(activity, verification)

        self.assertEqual(result["contract_id"], "r3a.resident.result")
        self.assertEqual(result["activity_id"], activity["activity_id"])
        self.assertEqual(result["attempt_id"], activity["attempt_id"])
        self.assertEqual(result["correlation_id"], activity["input"]["correlation_id"])
        self.assertEqual(result["resident_id"], "resident.grace")
        self.assertEqual(result["outcome"], "FAIL")
        self.assertFalse(result["completion_authority"])
        self.assertEqual(result["issuer"]["decision_ref"],
                         "verification:" + verification.verification_id)
        self.assertEqual(result["failure_reasons"][0]["evidence_refs"],
                         ["workspace:result.json"])

    def test_cme_delivers_result_to_grace_with_only_scoped_engineering_actions(self):
        cme, activity, verification = self._fixture()
        result = cme._resident_result_from_verification(activity, verification)
        expected = {"action": "engineering_assess", "engineering_assessment": {
            "status": "blocked", "assessment": "No safe correction is available.",
            "evidence_refs": [result["issuer"]["decision_ref"]]}}
        cme._module_call = AsyncMock(return_value={"result": expected})
        context = {"activity_id": activity["activity_id"], "attempt_id": activity["attempt_id"],
                   "correlation_id": activity["input"]["correlation_id"],
                   "config_revision": "config-r1", "model_route": {"timeout_seconds": 1},
                   "available_tools": [{"capability_id": "unrelated.tool"}],
                   "reasoning_escalation": {"enabled": True}}

        response = asyncio.run(cme._resident_verification_decision(activity, context, result, []))

        self.assertEqual(response, expected)
        payload = cme._module_call.await_args.args[1]
        self.assertEqual(payload["resident_result"], result)
        self.assertEqual(payload["available_tools"], [])
        self.assertEqual(payload["reasoning_escalation"], {"enabled": False, "available_roles": []})
        self.assertIn(result["issuer"]["decision_ref"], payload["conversation"][-1]["content"])

if __name__ == "__main__":
    unittest.main()
