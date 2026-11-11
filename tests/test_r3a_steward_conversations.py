"""
R3 CONTROLLED SOURCE
File: tests/test_r3a_steward_conversations.py
Component: R3A-CME-CONVERSATION-TESTS
File Revision: 1.0.1
Created: Unknown (legacy)
Created By: Unknown (legacy)
Purpose: Verify Website conversation dispatch, direct chat authorization, and resident handoff boundaries.
Execution Model: unittest against focused CME control-path fixtures.
Observability: Assertion failures identify authorization and durable activity lineage mismatches.
Dependencies: r3a_runtime.cme; unittest mocks.
Authority: R3A Steward conversation and resident execution contracts.
Changed: 2026-11-10T00:14:15Z | R3A-GRACE-CHAT-AUTH | R3A Coordinator | Assert direct Steward chat requires target execution but not resident-to-resident delegation.
Changed: 2026-11-11 | R3A-RESIDENT-ID-AUDIT | Codex GPT-6 | Use canonical principal IDs for directory-backed resident profiles and conversation targets.
Supersedes: None
Contracts: r3a.steward-conversation.v1; r3a.resident.execution-profile@1.0.0; resident.delegate; resident.objective.execute.
Tests: python -m unittest tests.test_r3a_steward_conversations.
History/Predecessor: Git blob b29624dbdcf68c6295cfbf4df4e3c2cc063f629d.
"""
from __future__ import annotations

import asyncio
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

from r3a_runtime.cme import CME, _conversation_response_issue
from r3a_runtime.db import activity_failure_outcome


class ConversationControlTests(unittest.TestCase):
    def cme(self):
        cme = CME.__new__(CME)
        cme.module_id = "resident.grace"
        cme.settings = SimpleNamespace(module_id="resident.grace", source_digest="config-sha",
                                       model_roles=[])
        cme.store = SimpleNamespace()
        role = SimpleNamespace(role_id="role.grace", route_id="route.grace",
                               task_classes={"objective_reasoning"})
        cme._resolve_resident_execution_profile = AsyncMock(return_value=(
            {"resident_id": "resident:grace", "office_role": "Director of Operations",
             "model_route_id": "route.grace",
             "directory_evidence": {"snapshot_sha256": "a" * 64}}, role))
        cme._authorize_capability = AsyncMock(return_value={"allowed": True})
        return cme

    def test_conversation_send_enqueues_one_durable_conversation_activity(self):
        cme = self.cme()
        role = SimpleNamespace(role_id="role.grace", route_id="route.grace",
                               task_classes={"objective_reasoning"})
        cme.settings.model_roles = [role]
        cme.settings.model_role_for_task = lambda _task: role
        conversation_id = str(uuid.uuid4())
        message_id = str(uuid.uuid4())
        cme.store.accept_steward_message = AsyncMock(return_value={
            "message_id": message_id, "activity_id": None, "duplicate": False,
            "resident_id": "resident:grace",
            "transcript": [{"role": "user", "content": "Earlier question"},
                           {"role": "assistant", "content": "Earlier answer"}],
        })
        cme.store.submit_grace_objective = AsyncMock(return_value={
            "activity_id": str(uuid.uuid5(uuid.NAMESPACE_URL,
                f"r3a.steward.conversation.turn:{conversation_id}:{message_id}")),
            "state": "QUEUED"})
        cme.store.link_steward_message_activity = AsyncMock()
        real_dispatch = CME._control_request.__get__(cme, CME)
        observed = []

        async def dispatch(operation, payload, idempotency_key):
            observed.append((operation, payload, idempotency_key))
            return await real_dispatch(operation, payload, idempotency_key)

        cme._control_request = dispatch
        result = asyncio.run(dispatch("steward.conversation.send", {
            "principal_id": "portal:steward-7", "conversation_id": conversation_id,
            "client_message_id": message_id, "text": "Continue our discussion."},
            f"website-message:{conversation_id}:{message_id}"))
        self.assertEqual(result["message"]["delivery_state"], "processing")
        submit_call = cme.store.submit_grace_objective.await_args
        self.assertEqual(submit_call.args[1], f"steward-chat:{conversation_id}:{message_id}")
        self.assertEqual(submit_call.args[2], "conversation")
        self.assertEqual(submit_call.args[7], [])
        self.assertIn("Earlier answer", submit_call.args[0])
        self.assertIn("Continue our discussion.", submit_call.args[0])
        self.assertEqual(observed[1][0], "resident.objective.submit")
        cme.store.link_steward_message_activity.assert_awaited_once()

    def test_resident_tool_projection_skips_failed_optional_providers(self):
        cme = self.cme()
        failed = {"descriptor": {"operation_id": "institution.knowledge.read",
                                  "contract_version": "1.0.0", "effect_class": "read"},
                  "registry_observation": {"state": "FAILED"}}
        active = {"descriptor": {"operation_id": "institutional.directory.discover",
                                  "contract_version": "1.0.0", "effect_class": "read"},
                  "registry_observation": {"state": "ACTIVE"}}
        operation = SimpleNamespace(resident_tool_projection=lambda: {
            "capability_id": "institutional.directory.discover", "name": "directory_discover"})
        registry = SimpleNamespace(discover=lambda: (failed, active),
                                   resolve=lambda operation_id, version: operation)
        cme.settings.capability_registry = registry
        tools = cme._resident_tools()
        self.assertNotIn("institution.knowledge.read", {tool["capability_id"] for tool in tools})
        self.assertIn("institutional.directory.discover", {tool["capability_id"] for tool in tools})

    def test_conversation_final_response_does_not_require_objective_citations(self):
        self.assertIsNone(_conversation_response_issue("conversation", {
            "status": "healthy", "assessment": "Hello. How can I help?", "evidence_refs": []}))
        self.assertIsNone(_conversation_response_issue("objective", {
            "status": "healthy", "assessment": "Result", "evidence_refs": []}))
        self.assertIsNotNone(_conversation_response_issue("conversation", {
            "status": "healthy", "assessment": "  ", "evidence_refs": []}))
        self.assertIsNotNone(_conversation_response_issue("conversation", {
            "status": "blocked", "assessment": "Cannot answer", "evidence_refs": []}))

    def test_conversation_retries_are_bounded_and_report_blocked_failure(self):
        self.assertEqual(activity_failure_outcome("idempotent", "conversation", 7)[0], "RECOVERING")
        state, details = activity_failure_outcome("idempotent", "conversation", 8)
        self.assertEqual(state, "BLOCKED")
        self.assertTrue(details["retry_limit_reached"])
        self.assertEqual(activity_failure_outcome("idempotent", "objective", 50)[0], "RECOVERING")

    def test_directory_bound_vicky_uses_cme_delegation_route(self):
        cme = self.cme()
        cme.settings.model_roles = [SimpleNamespace(role_id="role.eng", route_id="route.eng",
                                                    task_classes={"objective_reasoning"})]
        cme._authorize_capability = AsyncMock(side_effect=[
            {"audit_event_id": "delegate-audit"}, {"audit_event_id": "execute-audit"}])
        profile = {"resident_id": "resident:vicky", "office_role": "engineering_manager",
                   "model_route_id": "route.eng", "directory_evidence": {"snapshot_sha256": "a" * 64}}
        role = SimpleNamespace(role_id="role.eng", route_id="route.eng",
                               task_classes={"objective_reasoning"})
        cme._resolve_resident_execution_profile = AsyncMock(return_value=(profile, role))
        cme.store.submit_grace_objective = AsyncMock(return_value={"activity_id": "activity-vicky",
                                                                    "state": "QUEUED"})
        result = asyncio.run(CME._control_request(cme, "resident.objective.submit", {
            "objective": "Complete an authorized resident objective", "event_kind": "objective",
            "target_resident_id": "resident:vicky", "acceptance_criteria": [],
            "task_class": "objective_reasoning"}, "vicky-turn-key"))
        self.assertEqual(result["activity_id"], "activity-vicky")
        self.assertEqual(cme.store.submit_grace_objective.await_args.kwargs["resident_id"],
                         "resident:vicky")
        self.assertEqual(cme.store.submit_grace_objective.await_args.kwargs["resident_profile"], profile)
        self.assertEqual(cme._authorize_capability.await_args_list[0].args[0], "resident.delegate")
        self.assertEqual(cme._authorize_capability.await_args_list[1].args[0], "resident.objective.execute")

    def test_direct_steward_conversation_requires_target_execution_not_resident_delegation(self):
        cme = self.cme()
        role = SimpleNamespace(role_id="role.grace", route_id="octominer1-primary-80b",
                               task_classes={"objective_reasoning"})
        cme.settings.model_roles = [role]
        cme._authorize_capability = AsyncMock(return_value={"allowed": True})
        cme._resolve_resident_execution_profile = AsyncMock(return_value=(
            {"resident_id": "resident:grace", "office_role": "Director of Operations",
             "model_route_id": role.route_id,
             "directory_evidence": {"snapshot_sha256": "b" * 64}}, role))
        cme.store.submit_grace_objective = AsyncMock(return_value={
            "activity_id": "activity-direct-chat", "state": "QUEUED"})

        result = asyncio.run(CME._control_request(cme, "resident.objective.submit", {
            "objective": "Respond to the Steward's message", "event_kind": "conversation",
            "target_resident_id": "resident:grace", "acceptance_criteria": [],
            "task_class": "objective_reasoning"}, "direct-chat-key"))

        self.assertEqual(result["activity_id"], "activity-direct-chat")
        self.assertEqual([call.args[0] for call in cme._authorize_capability.await_args_list],
                         ["resident.objective.execute"])
        self.assertEqual(cme._authorize_capability.await_args.kwargs["resident_id"],
                         "resident:grace")
        self.assertEqual(cme.store.submit_grace_objective.await_args.kwargs["resident_id"],
                         "resident:grace")

    def test_direct_steward_conversation_creation_requires_target_execution_only(self):
        cme = self.cme()
        role = SimpleNamespace(role_id="resident.primary", route_id="octominer1-primary-80b")
        cme.settings.model_role_for_office = lambda office: role if office == "Director of Operations" else None
        cme._invoke_directory_for_principal = AsyncMock(return_value={
            "outcome": "SUCCEEDED", "invocation_id": "directory-invocation",
            "output": {"schema_id": "r3a.institutional-directory.v1",
                       "source": {"availability": "measured", "freshness": "fresh",
                                  "snapshot_sha256": "c" * 64},
                       "residents": [{"resident_id": "resident:grace", "display_name": "Grace",
                                      "office_id": "office:grace",
                                      "office_role": "Director of Operations"}]}})
        cme.store.require_capability = AsyncMock()
        cme.store.create_steward_conversation = AsyncMock(return_value={
            "conversation_id": "conversation-direct-chat", "resident_id": "resident:grace"})

        result = asyncio.run(CME._control_request(cme, "steward.conversation.create", {
            "principal_id": "portal:steward-7", "resident_id": "resident:grace",
            "client_conversation_id": "client-conversation"}, "create-direct-chat"))

        self.assertEqual(result["conversation"]["conversation_id"], "conversation-direct-chat")
        cme.store.require_capability.assert_awaited_once_with(
            "resident:grace", "resident.objective.execute")

    def test_resident_discovery_preserves_roster_and_uses_configured_route_and_grants(self):
        cme = self.cme()
        cme.settings.model_role_for_office = lambda office: (
            SimpleNamespace(role_id="role.eng", route_id="route.eng")
            if office == "engineering_manager" else (_ for _ in ()).throw(ValueError("unconfigured")))
        cme._invoke_directory_for_principal = AsyncMock(return_value={
            "outcome": "SUCCEEDED", "invocation_id": "directory-invocation",
            "authorization": {"audit_event_id": "directory-auth"},
            "output": {"schema_id": "r3a.institutional-directory.v1",
                       "source": {"availability": "measured", "freshness": "fresh",
                                  "snapshot_sha256": "a" * 64},
                       "residents": [
                           {"resident_id": "resident:vicky", "display_name": "Vicky",
                            "office_id": "office.eng", "office_role": "engineering_manager"},
                           {"resident_id": "resident:helen", "display_name": "Helen",
                            "office_id": "office.hr", "office_role": "human_resources_manager"}]}})
        cme.store.require_capability = AsyncMock()
        result = asyncio.run(CME._control_request(cme, "steward.residents.discover",
                                                  {"principal_id": "portal:steward-7"}, "discovery-key"))
        self.assertEqual([item["resident_id"] for item in result["residents"]],
                         ["resident:vicky", "resident:helen"])
        self.assertTrue(result["residents"][0]["chat_available"])
        self.assertFalse(result["residents"][1]["chat_available"])
        self.assertTrue(all(item["onboarding_status"] == "unknown" for item in result["residents"]))
        self.assertEqual(result["residents"][0]["authorization_status"], "authorized")
        self.assertEqual(result["residents"][0]["chat_status"], "available")
        self.assertEqual(result["residents"][1]["execution_status"], "unavailable")
        self.assertEqual(result["residents"][1]["chat_status"], "office_role_route_unavailable")
        self.assertEqual(cme.store.require_capability.await_args_list[0].args,
                         ("resident:vicky", "resident.objective.execute"))

    def test_directory_principal_route_is_independent_of_configured_module_id(self):
        cme = self.cme()
        cme.settings.model_role_for_office = lambda _office: SimpleNamespace(
            role_id="resident.primary", route_id="octominer1-primary-80b")
        cme._invoke_directory_for_principal = AsyncMock(return_value={
            "outcome": "SUCCEEDED", "invocation_id": "directory-invocation",
            "authorization": {"audit_event_id": "directory-auth"},
            "output": {"schema_id": "r3a.institutional-directory.v1",
                       "source": {"availability": "measured", "freshness": "fresh",
                                  "snapshot_sha256": "a" * 64},
                       "residents": [{"resident_id": "resident:grace", "display_name": "Grace",
                                      "office_id": "office:grace", "office_role": "Director of Operations"}]}})
        cme.store.require_capability = AsyncMock(side_effect=PermissionError("grant missing"))
        result = asyncio.run(CME._control_request(cme, "steward.residents.discover",
                                                  {"principal_id": "portal:steward-7"}, "grace-discovery"))
        self.assertEqual(len(result["residents"]), 1)
        grace = result["residents"][0]
        self.assertEqual(grace["resident_id"], "resident:grace")
        self.assertEqual(grace["execution_status"], "configured")
        self.assertEqual(grace["authorization_status"], "denied")
        self.assertFalse(grace["chat_available"])
        self.assertEqual(grace["chat_status"], "required_execution_grant_missing")
        self.assertEqual(cme.store.require_capability.await_args_list[0].args,
                         ("resident:grace", "resident.objective.execute"))


if __name__ == "__main__":
    unittest.main()
