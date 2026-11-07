"""
R3 CONTROLLED SOURCE
File: tests/test_r3a_ap1.py
Component: R3A-AP1-TARGETED-TESTS
File Revision: 1.3.0
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
Supersedes: None.
Contracts: R3A-019 configured model routing and knowledge grounding/retrieval.
Tests: This test module.
History/Predecessor: Git blob 10d0d5896ba9027203f652ed10109e1d45f73d59 at commit 8e89ada52fda4768782b712f23281150e71b11e3.
"""
from __future__ import annotations

import tempfile
import unittest
import asyncio
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import AsyncMock
import hashlib

from r3a_runtime.acceptance import (AcceptanceCriteriaRequired, validate_acceptance,
                                    validate_criteria, validate_required_criteria)
from r3a_runtime.cme import CME, _RESIDENT_TOOLS, _knowledge_answer_issues, _requires_runtime_evidence
from r3a_runtime.config import (ConfigurationError, ModelReadinessPolicy, ModelRole,
                                ModelRoute, resolve_model_route)
from r3a_runtime.grace_module import GraceResident, resident_action_schema
from r3a_runtime.knowledge import retrieve
from r3a_runtime.diagnostics import DiagnosticProjection


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
    def test_capability_schema_uses_exact_manifest_identifiers(self):
        schema = resident_action_schema([
            {"capability_id": "institution.knowledge.read"},
            {"capability_id": "institution.diagnostics.read"},
        ])
        self.assertEqual(schema["properties"]["capability_id"]["enum"], [
            "institution.knowledge.read", "institution.diagnostics.read"])
        self.assertNotIn("institution_knowledge_read",
                         schema["properties"]["capability_id"]["enum"])

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
            ModelRole("resident.autonomic", "autonomic", ("reason.text",), ("text",), (),
                      45, "block", 5, 1, readiness),
            ModelRole("resident.primary", "primary", ("reason.text", "plan"), ("text",), (),
                      45, "block", 5, 1, readiness),
        )
        settings = SimpleNamespace(model_roles=roles, model_route=lambda route_id: {
            "autonomic": local, "primary": primary}[route_id], source_digest="config-1",
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
                "event_kind": "objective", "route_id": "autonomic",
                "model_route": {"route_id": "autonomic", "provider": "openai-compatible", "model": "small",
                                "endpoint": local.endpoint, "timeout_seconds": 20, "max_tokens": 64},
                "selected_role_id": "resident.autonomic", "route_decision": {},
                "evidence_format": "r3a.knowledge-evidence.v1", "required_evidence_refs": [],
                "evidence": [], "available_tools": [], "available_engineering_operations": [],
                "reasoning_escalation": {"enabled": True,
                    "available_roles": [{"role_id": "resident.primary", "route_id": "primary",
                                         "readiness": "ready"}]},
                "conversation": [], "reasoning_state": {}, "pending_final": None,
                "config_revision": "config-1"})
            cme._model_readiness_observations = AsyncMock(return_value={"resident.primary": {
                "status": "ready", "observed_at": datetime.now(timezone.utc).isoformat(),
                "provider_id": "models", "evidence_ref": "ready-1", "evidence": {"model_id": "large"},
                "config_revision": "config-1"}})
            cme._authorization_decision = AsyncMock(return_value=SimpleNamespace(
                provider_id="capability_grants", allowed=True,
                decision_id="decision-1", audit_event_id="audit-1", policy_revision=None,
                config_revision="config-1", reason="active capability grant",
                observed_at="2026-11-07T00:00:00Z"))
            escalation = {"action": "escalate_reasoning", "target_role_id": "resident.primary",
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
                        "enabled": True, "authorization_capability_id": "reasoning.escalation.request",
                        "allowed_role_ids": ["resident.primary"], "max_requests_per_activity": 1,
                        "max_completion_tokens_per_activity": 128, "config_revision": "config-1"}},
                "checkpoint": {}}
            await cme._run_activity(activity)
            return cme, module_payloads

        cme, payloads = asyncio.run(exercise())
        cme._authorization_decision.assert_awaited_once()
        self.assertEqual(cme._authorization_decision.await_args.args[0], "reasoning.escalation.request")
        self.assertEqual(payloads[0]["route_id"], "autonomic")
        self.assertEqual(payloads[1]["route_id"], "primary")
        self.assertEqual(cme.store.blocked[1]["reasoning_trace"]["model_turns"][-1]["result_ref"],
                         "large-result")
        checkpoint = next(item[1] for item in cme.store.progress
                          if item[0]["phase"] == "resident.decision.ready")
        request = checkpoint["reasoning_state"]["escalation"]["requests"][0]
        self.assertEqual(request["status"], "SUCCEEDED")
        self.assertEqual(request["charged_completion_tokens"], 26)
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


if __name__ == "__main__":
    unittest.main()
