"""Permanent regressions for R3-owned capabilities; no R2 dependency."""
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
            read_only=False))

    def test_native_write_authorized_and_audited(self):
        result = self.registry.invoke("r3.example", {"scope_ref": "office:grace"},
                                      correlation_id="call-1")
        self.assertEqual(result["authorization"]["grant_id"], "r3-grant-1")
        self.assertEqual([x["outcome"] for x in self.events],
                         ["AUTHORIZED", "COMPLETED"])
        self.assertEqual(self.verifier.calls[0], {
            "principal": "resident:grace", "action": "office.update",
            "scope_ref": "office:grace"})
        self.assertEqual(len(self.executions), 1)

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


if __name__ == "__main__":
    unittest.main()
