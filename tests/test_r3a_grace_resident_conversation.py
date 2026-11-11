"""Resident-side conversation contract and retry fixtures.

These fixtures test the Grace module boundary only. They are not live inference or
managed CME acceptance evidence.
"""
from __future__ import annotations

import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from r3a_runtime.contracts import ContractEnvelope
from r3a_runtime.grace_module import GraceResident


class GraceResidentConversationTests(unittest.TestCase):
    module_id = "resident.grace"
    principal_id = "resident:grace"
    config_revision = "config-revision-test"
    activity_id = "activity-grace-conversation"
    correlation_id = "correlation-grace-conversation"

    def _resident(self, response: str) -> GraceResident:
        resident = GraceResident.__new__(GraceResident)
        resident.module_id = self.module_id
        resident.module_version = "1.2.14"
        resident.state = "ACTIVE"
        resident.last_activity = None
        route = SimpleNamespace(route_id="route.grace", provider="test-provider",
                                model="test-model", endpoint="http://127.0.0.1:1/chat",
                                timeout_seconds=1, max_tokens=256)
        resident.settings = SimpleNamespace(model_route=lambda _route_id=None: route)
        resident._model_request = AsyncMock(return_value={
            "id": "fixture-inference-result", "usage": {"prompt_tokens": 20, "completion_tokens": 18},
            "choices": [{"finish_reason": "stop", "message": {"content": response}}]})
        return resident

    def _profile(self) -> dict:
        return {"contract_id": "r3a.resident.execution-profile", "contract_version": "1.0.0",
                "resident_id": self.principal_id, "display_name": "Grace",
                "office_id": "office:grace", "office_role": "Director of Operations",
                "directory_evidence": {"source_id": "riverview_authority.directory",
                                        "snapshot_sha256": "a" * 64,
                                        "observed_at": "2026-11-11T00:00:00Z"},
                "model_route_id": "route.grace", "config_revision": self.config_revision}

    def _payload(self, attempt_id: str, *, conversation: list[dict] | None = None) -> dict:
        envelope = ContractEnvelope(
            "r3a.resident.execution", "1.0.0", f"request-{attempt_id}", self.activity_id,
            attempt_id, self.correlation_id, self.principal_id, self.config_revision,
            "2026-11-11T00:00:00Z", {"operation": "execute"}).to_dict()
        return {"contract_envelope": envelope, "activity_type": "grace.objective",
                "activity_id": self.activity_id, "attempt_id": attempt_id,
                "correlation_id": self.correlation_id, "resident_id": self.principal_id,
                "config_revision": self.config_revision, "resident_profile": self._profile(),
                "objective": "Please reply that you are available to continue our conversation.",
                "activity_input": {"event_kind": "conversation"},
                "evidence": [], "conversation": conversation or [], "available_tools": [],
                "request_ref": f"request-ref-{attempt_id}"}

    def test_registered_executor_generates_conversation_response_for_bound_principal(self):
        answer = {"action": "final", "decision": {
            "assessment": "I’m available to continue our conversation.", "status": "healthy",
            "evidence_refs": [], "recommended_action": "none"}}
        resident = self._resident(json.dumps(answer))

        result = asyncio.run(resident.handle("execute", self._payload("attempt-1")))

        self.assertEqual("final", result["action"])
        self.assertEqual(answer["decision"], result["decision"])
        self.assertEqual(self.activity_id, result["activity_id"])
        self.assertEqual(self.principal_id, result["resident_profile"]["resident_id"])
        model_request = resident._model_request.await_args.args[2]
        context = json.loads(model_request["messages"][-1]["content"])
        self.assertEqual("conversation", context["event_kind"])
        self.assertEqual(self.activity_id, resident.last_activity["activity_id"])
        self.assertEqual("healthy", resident.last_activity["decision"]["status"])

    def test_retry_after_interruption_resumes_same_activity_from_supplied_history(self):
        resident = self._resident("")
        resident._model_request = AsyncMock(side_effect=RuntimeError("temporary inference interruption"))
        with self.assertRaisesRegex(RuntimeError, "temporary inference interruption"):
            asyncio.run(resident.handle("execute", self._payload("attempt-1")))

        prior_history = [{"role": "user", "content": "Are you available?"}]
        answer = {"action": "final", "decision": {
            "assessment": "I’m available to continue.", "status": "healthy",
            "evidence_refs": [], "recommended_action": "none"}}
        resident._model_request = AsyncMock(return_value={
            "id": "fixture-retry-result", "usage": {"prompt_tokens": 24, "completion_tokens": 12},
            "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(answer)}}]})

        result = asyncio.run(resident.handle(
            "execute", self._payload("attempt-2", conversation=prior_history)))

        self.assertEqual("final", result["action"])
        self.assertEqual(self.activity_id, result["activity_id"])
        self.assertEqual("attempt-2", result["attempt_id"])
        retry_messages = resident._model_request.await_args.args[2]["messages"]
        self.assertEqual(prior_history, retry_messages[1:-1])
        retry_context = json.loads(retry_messages[-1]["content"])
        self.assertEqual("conversation", retry_context["event_kind"])

    def test_rejects_envelope_for_another_resident_identity(self):
        resident = self._resident("{}")
        payload = self._payload("attempt-1")
        payload["contract_envelope"]["resident_id"] = "resident:someone-else"

        with self.assertRaisesRegex(ValueError, "resident identity mismatch"):
            asyncio.run(resident.handle("execute", payload))
        resident._model_request.assert_not_awaited()

    def test_rejects_profile_that_disagrees_with_cme_resident_identity(self):
        resident = self._resident("{}")
        payload = self._payload("attempt-1")
        payload["resident_profile"]["resident_id"] = "resident:someone-else"

        with self.assertRaisesRegex(ValueError, "profile identity or configuration revision mismatch"):
            asyncio.run(resident.handle("execute", payload))
        resident._model_request.assert_not_awaited()

    def test_bound_identity_requires_directory_profile_and_cme_execution_envelope(self):
        resident = self._resident("{}")
        payload = self._payload("attempt-1")
        payload.pop("resident_profile")
        payload.pop("contract_envelope")

        with self.assertRaisesRegex(ValueError, "directory profile and execution envelope"):
            asyncio.run(resident.handle("execute", payload))
        resident._model_request.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
