from __future__ import annotations

import unittest
import sys
from types import SimpleNamespace
from unittest.mock import patch

from runtime.proposal_gateway_adapter import (
    RESOURCE,
    SCOPE,
    register_internal_proposal_tools,
)


class RecordingGateway:
    def __init__(self):
        self.capabilities = {}

    def register(self, capability):
        if capability.name in self.capabilities:
            raise ValueError("duplicate")
        self.capabilities[capability.name] = capability


class RecordingClient:
    def __init__(self):
        self.calls = []

    def submit(self, content, *, principal, correlation_id):
        self.calls.append(("submit", content, principal, correlation_id))
        return {"status": "persisted"}

    def proposal_status(self, proposal_id):
        self.calls.append(("read", proposal_id))
        return {"proposal_id": proposal_id, "lifecycle_status": "DRAFT"}


class ProposalGatewayAdapterTests(unittest.TestCase):
    def setUp(self):
        self.gateway = RecordingGateway()
        self.client = RecordingClient()
        register_internal_proposal_tools(self.gateway, self.client)

    def test_registers_only_exact_draft_and_status_grants(self):
        self.assertEqual(set(self.gateway.capabilities), {
            "r3.proposal.submit", "r3.proposal.status"})
        submit = self.gateway.capabilities["r3.proposal.submit"]
        read = self.gateway.capabilities["r3.proposal.status"]
        self.assertEqual((submit.resource_id, submit.action, submit.operation),
                         (RESOURCE, "proposal.draft.submit", "write"))
        self.assertEqual((read.resource_id, read.action, read.operation),
                         (RESOURCE, "proposal.status.read", "read"))
        for capability in (submit, read):
            self.assertEqual(capability.parameters["properties"]["scope_ref"]["enum"],
                             [SCOPE])

    def test_submit_uses_authenticated_execution_context(self):
        capability = self.gateway.capabilities["r3.proposal.submit"]
        content = {key: "value" for key in
                   capability.parameters["properties"]["content"]["required"]}
        context = SimpleNamespace(principal="resident:grace", correlation_id="assignment-42")
        result = capability.executor({"scope_ref": SCOPE, "content": content}, context)
        self.assertEqual(result, {"status": "persisted"})
        self.assertEqual(self.client.calls, [
            ("submit", content, "resident:grace", "assignment-42")])

    def test_composed_production_path_resolves_institutional_identity_from_hr(self):
        content = {key: "value" for key in
                   self.gateway.capabilities["r3.proposal.submit"].parameters[
                       "properties"]["content"]["required"]}
        identity_map = SimpleNamespace(resolve_authority_principal=
            lambda _database, principal: "resident:grace" if principal == "resident:Grace"
            else (_ for _ in ()).throw(ValueError("association not found")))
        with patch.dict(sys.modules,
                {"runtime.hr_identity_association": identity_map}):
            gateway = RecordingGateway()
            register_internal_proposal_tools(gateway, self.client,
                                             hr_database="/var/lib/r3/hr.sqlite3")
            submit = gateway.capabilities["r3.proposal.submit"]
            submit.executor({"scope_ref": SCOPE, "content": content},
                SimpleNamespace(principal="resident:Grace", correlation_id="assignment-43"))
        self.assertEqual(self.client.calls[-1],
            ("submit", content, "resident:grace", "assignment-43"))

    def test_wrong_scope_is_rejected_before_client_call(self):
        capability = self.gateway.capabilities["r3.proposal.submit"]
        with self.assertRaises(ValueError):
            capability.executor({"scope_ref": "institution:all", "content": {}},
                                 SimpleNamespace(principal="resident:grace",
                                                 correlation_id="assignment-42"))
        self.assertEqual(self.client.calls, [])

    def test_status_uses_existing_authoritative_client_read(self):
        capability = self.gateway.capabilities["r3.proposal.status"]
        result = capability.executor({"scope_ref": SCOPE,
                                      "proposal_id": "proposal:known"},
                                     SimpleNamespace(principal="resident:grace"))
        self.assertEqual(result["lifecycle_status"], "DRAFT")
        self.assertEqual(self.client.calls, [("read", "proposal:known")])


if __name__ == "__main__":
    unittest.main()
