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
        result = asyncio.run(CME._control_request(cme, "grace.objective.submit", {
            "objective": "Answer a Steward conversation turn", "event_kind": "conversation",
            "target_resident_id": "resident.vicky", "acceptance_criteria": [],
            "task_class": "objective_reasoning"}, "vicky-turn-key"))
        self.assertEqual(result["activity_id"], "activity-vicky")
        self.assertEqual(cme.store.submit_grace_objective.await_args.kwargs["resident_id"],
                         "resident.vicky")
        self.assertEqual(cme.store.submit_grace_objective.await_args.kwargs["resident_profile"], profile)
        self.assertEqual(cme._authorize_capability.await_args_list[0].args[0], "resident.delegate")
        self.assertEqual(cme._authorize_capability.await_args_list[1].args[0], "resident.objective.execute")


if __name__ == "__main__":
    unittest.main()
