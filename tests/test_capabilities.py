# R3 CONTROLLED SOURCE
# File: tests/test_capabilities.py
# Component: R3-CAPABILITY-AUTHORITY-REGRESSION
# File Revision: 1.0.0
# Created: Unknown (legacy)
# Created By: Unknown (legacy)
# Purpose: Protect R3 grant authorization and explicit authoritative-service delegation contracts.
# Execution Model: unittest.
# Observability: Assertions over authorization calls, durable events, and executor calls.
# Dependencies: runtime.capabilities.
# Authority: New capability policy must use an established authority decision; registration alone grants nothing.
# Changed: 2026-11-06T23:06:45Z | GRACE-AUTHORITY-ARCH-001 | Codex GPT-6 | Cover authoritative service decisions without duplicate R3 grants.
# Supersedes: None.
# Contracts: docs/architecture/RESIDENT_AUTHORITY_AND_CAPABILITIES.md
# Tests: This module.
# History/Predecessor: Git history at current branch baseline.
"""Permanent regressions for R3 capability authorization contracts."""
import unittest
from runtime.capabilities import (Capability, CapabilityRegistry,
                                  CapabilityDenied, AuthorityUnavailable)


class Verifier:
    def __init__(self):
        self.allowed = True
        self.calls = []

    def authorize(self, **kwargs):
        self.calls.append(kwargs)
        if not self.allowed:
            raise CapabilityDenied("revoked")
        return {"grant_id": "r3-grant-1"}


class CapabilityTests(unittest.TestCase):
    def setUp(self):
        self.verifier = Verifier()
        self.events = []
        self.executions = []
        self.registry = CapabilityRegistry(principal="resident:grace",
            verifier=self.verifier, audit=self.events.append)
        self.registry.register(Capability(
            "r3.example", "office.update", "Example write capability",
            {"type": "object", "required": ["scope_ref"]},
            lambda args: self.executions.append(args) or {"changed": True},
            read_only=False, resource_ref="r3.example"))

    def test_native_write_authorized_and_audited(self):
        result = self.registry.invoke("r3.example", {"scope_ref": "office:grace", "resource_ref": "r3.example"},
                                      correlation_id="call-1")
        self.assertEqual(result["authorization"]["grant_id"], "r3-grant-1")
        self.assertEqual([x["outcome"] for x in self.events],
                         ["AUTHORIZED", "COMPLETED"])
        self.assertEqual(self.verifier.calls[0], {
            "principal": "resident:grace",
            "resource_id": "r3.example",
            "action": "office.update",
            "operation": "write",
            "scope_ref": "office:grace"})
        self.assertEqual(len(self.executions), 1)

    def test_invocation_cannot_override_registered_resource(self):
        self.registry.invoke(
            "r3.example",
            {"scope_ref": "office:grace",
             "resource_ref": "attacker:resource"},
            correlation_id="resource-override-test",
        )
        self.assertEqual(
            self.verifier.calls[0]["resource_id"],
            "r3.example",
        )

    def test_revocation_denies_before_execution(self):
        self.verifier.allowed = False
        with self.assertRaises(CapabilityDenied):
            self.registry.invoke("r3.example", {"scope_ref": "office:grace"},
                                 correlation_id="call-2")
        self.assertFalse(self.executions)
        self.assertEqual(self.events[-1]["outcome"], "DENIED")

    def test_unregistered_capability_denied(self):
        with self.assertRaises(CapabilityDenied):
            self.registry.invoke("unknown", {"scope_ref": "office:grace"},
                                 correlation_id="call-3")
        self.assertFalse(self.executions)

    def test_scope_required(self):
        with self.assertRaises(CapabilityDenied):
            self.registry.invoke("r3.example", {}, correlation_id="call-4")
        self.assertFalse(self.verifier.calls)

    def test_audit_failure_blocks_execution(self):
        def fail(_):
            raise OSError("audit disk unavailable")
        self.registry.audit = fail
        with self.assertRaises(OSError):
            self.registry.invoke("r3.example", {"scope_ref": "office:grace"},
                                 correlation_id="call-5")
        self.assertFalse(self.executions)

    def test_missing_verifier_denied(self):
        with self.assertRaises(AuthorityUnavailable):
            CapabilityRegistry(principal="resident:grace", verifier=None,
                               audit=self.events.append)

    def test_discovery_does_not_grant_authority(self):
        self.assertFalse(self.registry.discover()[0]["read_only"])
        self.assertFalse(self.verifier.calls)

    def test_authoritative_service_decision_needs_no_duplicate_r3_grant(self):
        calls = []
        def execute(_args, context):
            calls.append(context)
            return {"persisted": True}
        self.registry.register(Capability(
            "r3.institutional.write", "proposal.draft.submit", "Draft proposal",
            {"type": "object", "properties": {}}, read_only=False,
            resource_ref="riverview:institutional-proposals",
            scope_ref="institution:proposal-drafts", contextual_executor=execute,
            authorization_mode="authoritative-service",
            authority_source="riverview.institutional-proposal-registry"))
        result = self.registry.invoke("r3.institutional.write", {}, correlation_id="call-external")
        self.assertEqual(result["result"], {"persisted": True})
        self.assertIsNone(result["authorization"]["grant_id"])
        self.assertEqual(result["authorization"]["authority_source"],
                         "riverview.institutional-proposal-registry")
        self.assertEqual(calls[0].authority_source, "riverview.institutional-proposal-registry")
        self.assertEqual(self.verifier.calls, [])
        self.assertEqual([event["outcome"] for event in self.events], ["AUTHORIZED", "COMPLETED"])

    def test_authoritative_service_denial_is_audited_and_does_not_complete(self):
        def deny(_args, _context):
            raise CapabilityDenied("institutional policy denial")
        self.registry.register(Capability(
            "r3.institutional.denied", "proposal.draft.submit", "Draft proposal",
            {"type": "object", "properties": {}}, read_only=False,
            resource_ref="riverview:institutional-proposals",
            scope_ref="institution:proposal-drafts", contextual_executor=deny,
            authorization_mode="authoritative-service",
            authority_source="riverview.institutional-proposal-registry"))
        with self.assertRaises(CapabilityDenied):
            self.registry.invoke("r3.institutional.denied", {}, correlation_id="call-denied")
        self.assertEqual(self.events[-1]["outcome"], "DENIED")
        self.assertEqual(self.verifier.calls, [])

    def test_alternate_authority_requires_explicit_named_service_and_context(self):
        with self.assertRaises(ValueError):
            self.registry.register(Capability(
                "r3.bad", "proposal.draft.submit", "Bad",
                {"type": "object"}, lambda _: None,
                authorization_mode="authoritative-service"))
        with self.assertRaises(ValueError):
            self.registry.register(Capability(
                "r3.bad", "proposal.draft.submit", "Bad",
                {"type": "object"}, contextual_executor=lambda _args, _ctx: None,
                authorization_mode="authoritative-service",
                authority_source="unregistered.private-policy"))


if __name__ == "__main__":
    unittest.main()
