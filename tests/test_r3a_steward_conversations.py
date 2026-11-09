"""Focused CME checks for the Website conversation handoff contract."""
from __future__ import annotations

import asyncio
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

from r3a_runtime.cme import CME


class ConversationControlTests(unittest.TestCase):
    def cme(self):
        cme = CME.__new__(CME)
        cme.module_id = "resident.grace"
        cme.settings = SimpleNamespace(module_id="resident.grace", source_digest="config-sha",
                                       model_roles=[])
        cme.store = SimpleNamespace()
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
            "resident_id": "resident.grace",
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

    def test_directory_bound_vicky_uses_cme_delegation_route(self):
        cme = self.cme()
        cme.settings.model_roles = [SimpleNamespace(role_id="role.eng", route_id="route.eng",
                                                    task_classes={"objective_reasoning"})]
        cme._authorize_capability = AsyncMock(side_effect=[
            {"audit_event_id": "delegate-audit"}, {"audit_event_id": "execute-audit"}])
        profile = {"resident_id": "resident.vicky", "office_role": "engineering_manager",
                   "model_route_id": "route.eng", "directory_evidence": {"snapshot_sha256": "a" * 64}}
        role = SimpleNamespace(role_id="role.eng", route_id="route.eng",
                               task_classes={"objective_reasoning"})
        cme._resolve_resident_execution_profile = AsyncMock(return_value=(profile, role))
        cme.store.submit_grace_objective = AsyncMock(return_value={"activity_id": "activity-vicky",
                                                                    "state": "QUEUED"})
        result = asyncio.run(CME._control_request(cme, "resident.objective.submit", {
            "objective": "Answer a Steward conversation turn", "event_kind": "conversation",
            "target_resident_id": "resident.vicky", "acceptance_criteria": [],
            "task_class": "objective_reasoning"}, "vicky-turn-key"))
        self.assertEqual(result["activity_id"], "activity-vicky")
        self.assertEqual(cme.store.submit_grace_objective.await_args.kwargs["resident_id"],
                         "resident.vicky")
        self.assertEqual(cme.store.submit_grace_objective.await_args.kwargs["resident_profile"], profile)
        self.assertEqual(cme._authorize_capability.await_args_list[0].args[0], "resident.delegate")
        self.assertEqual(cme._authorize_capability.await_args_list[1].args[0], "resident.objective.execute")

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
                           {"resident_id": "resident.vicky", "display_name": "Vicky",
                            "office_id": "office.eng", "office_role": "engineering_manager"},
                           {"resident_id": "resident.helen", "display_name": "Helen",
                            "office_id": "office.hr", "office_role": "human_resources_manager"}]}})
        cme.store.require_capability = AsyncMock()
        result = asyncio.run(CME._control_request(cme, "steward.residents.discover",
                                                  {"principal_id": "portal:steward-7"}, "discovery-key"))
        self.assertEqual([item["resident_id"] for item in result["residents"]],
                         ["resident.vicky", "resident.helen"])
        self.assertTrue(result["residents"][0]["chat_available"])
        self.assertFalse(result["residents"][1]["chat_available"])
        self.assertTrue(all(item["onboarding_status"] == "unknown" for item in result["residents"]))
        self.assertEqual(result["residents"][0]["authorization_status"], "authorized")
        self.assertEqual(result["residents"][0]["chat_status"], "available")
        self.assertEqual(result["residents"][1]["execution_status"], "unavailable")
        self.assertEqual(result["residents"][1]["chat_status"], "office_role_route_unavailable")
        self.assertEqual(cme.store.require_capability.await_args_list[0].args,
                         ("resident.grace", "resident.delegate"))
        self.assertEqual(cme.store.require_capability.await_args_list[1].args,
                         ("resident.vicky", "resident.objective.execute"))

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
                         ("resident.grace", "resident.delegate"))
        self.assertEqual(cme.store.require_capability.await_args_list[1].args,
                         ("resident:grace", "resident.objective.execute"))


if __name__ == "__main__":
    unittest.main()
