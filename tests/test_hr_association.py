"""Governed, provenance-bearing authority-principal association regressions."""
from __future__ import annotations

import sys
import tempfile
import types
import unittest
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from runtime.hr_records import ResidentHRRecord
from runtime.hr_store import HRStore


class CapabilityDenied(Exception):
    pass


@dataclass
class GovernedCapability:
    name: str
    resource_id: str
    action: str
    operation: str
    description: str
    parameters: dict
    executor: object


class FakeGateway:
    def __init__(self):
        self.capabilities = {}

    def register(self, capability):
        self.capabilities[capability.name] = capability


def _install_host_contract_stubs():
    capabilities = types.ModuleType("runtime.capabilities")
    capabilities.CapabilityDenied = CapabilityDenied
    governed = types.ModuleType("runtime.governed_tools")
    governed.GovernedCapability = GovernedCapability
    governed.GovernedToolGateway = object
    sys.modules["runtime.capabilities"] = capabilities
    sys.modules["runtime.governed_tools"] = governed


_install_host_contract_stubs()
from runtime.hr_governed_capabilities import register_hr_governed_tools


class HRAssociationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = Path(self.temp.name) / "hr.sqlite3"
        store = HRStore(self.database)
        store.put(ResidentHRRecord("r3:test", "Test Resident", "Engineering Manager",
                                   status="active"))
        store.close()
        self.gateway = FakeGateway()
        self.resolver_calls = []
        register_hr_governed_tools(
            self.gateway, self.database,
            directory_evidence_resolver=self.resolve_evidence)
        self.operation = self.gateway.capabilities[
            "associate_authority_principal_with_provenance"]
        self.params = {"scope_ref": "r3:test", "expected_revision": 1,
                       "evidence_ref": "evidence-ref:test-1",
                       "idempotency_key": "association-idem:test-1"}
        self.context = SimpleNamespace(
            principal_id="steward:test", grant_id="grant:test-1",
            correlation_id="corr:test-1", resource_id="r3:hr",
            action="hr.save", operation="write", scope_ref="r3:test")

    def tearDown(self):
        self.temp.cleanup()

    def resolve_evidence(self, evidence_ref):
        self.resolver_calls.append(evidence_ref)
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        return {"resident_id": "r3:test", "principal_id": "resident:test",
                "office_id": "office:engineering", "office_role": "Engineering Manager",
                "office_status": "active", "binding_status": "active",
                "binding_revision": 7, "snapshot_sha256": "a" * 64,
                "observed_at": now, "freshness": "fresh",
                "source_refs": ["directory-snapshot:test", evidence_ref]}

    def _record(self):
        store = HRStore(self.database)
        try:
            return store.get("r3:test")
        finally:
            store.close()

    def test_operation_is_not_registered_without_trusted_resolver(self):
        gateway = FakeGateway()
        register_hr_governed_tools(gateway, self.database)
        self.assertNotIn("associate_authority_principal_with_provenance", gateway.capabilities)

    def test_exact_hr_write_contract_and_atomic_provenance_success(self):
        self.assertEqual(self.operation.resource_id, "r3:hr")
        self.assertEqual(self.operation.action, "hr.save")
        self.assertEqual(self.operation.operation, "write")
        self.assertFalse(self.operation.parameters["additionalProperties"])
        self.assertEqual(set(self.operation.parameters["properties"]), {
            "scope_ref", "expected_revision", "evidence_ref", "idempotency_key"})
        result = self.operation.executor(self.params, self.context)
        self.assertEqual(result["contract"], "r3.hr.authority-principal-association.v1")
        self.assertEqual(result["principal_id"], "resident:test")
        self.assertEqual(result["revision"], 2)
        self.assertTrue(result["association_ref"].startswith("hr-association:"))
        self.assertTrue(result["audit_event_ref"].startswith("hr-association-event:"))
        self.assertEqual(self._record()[1], 2)
        self.assertEqual(len(self.resolver_calls), 1)
        store = HRStore(self.database)
        try:
            event = store._db.execute(
                "SELECT payload_json FROM hr_association_events WHERE event_ref=?",
                (result["audit_event_ref"],)).fetchone()
            self.assertIsNotNone(event)
            payload = __import__("json").loads(event[0])
            self.assertEqual(payload["actor_principal_id"], "steward:test")
            self.assertEqual(payload["grant_id"], "grant:test-1")
            self.assertEqual(payload["evidence_ref"], self.params["evidence_ref"])
        finally:
            store.close()

    def test_wrong_scope_is_denied_before_directory_resolution(self):
        context = SimpleNamespace(**{**vars(self.context), "scope_ref": "r3:test"})
        params = {**self.params, "scope_ref": "r3:other"}
        with self.assertRaises(CapabilityDenied):
            self.operation.executor(params, context)
        self.assertEqual(self.resolver_calls, [])
        self.assertEqual(self._record()[1], 1)

    def test_wrong_action_or_resource_is_denied_before_directory_resolution(self):
        for changes in ({"action": "hr.read"}, {"resource_id": "r3:other"},
                        {"operation": "read"}):
            with self.subTest(changes=changes):
                context = SimpleNamespace(**{**vars(self.context), **changes})
                with self.assertRaises(CapabilityDenied):
                    self.operation.executor(self.params, context)
        self.assertEqual(self.resolver_calls, [])
        self.assertEqual(self._record()[1], 1)

    def test_stale_revision_and_stale_evidence_have_no_side_effects(self):
        with self.assertRaisesRegex(ValueError, "revision_conflict"):
            self.operation.executor({**self.params, "expected_revision": 2}, self.context)
        self.assertEqual(self._record()[1], 1)

        def stale(ref):
            evidence = self.resolve_evidence(ref)
            evidence["freshness"] = "unavailable"
            return evidence
        gateway = FakeGateway()
        register_hr_governed_tools(gateway, self.database,
                                   directory_evidence_resolver=stale)
        operation = gateway.capabilities["associate_authority_principal_with_provenance"]
        with self.assertRaisesRegex(ValueError, "stale_directory_evidence"):
            operation.executor(self.params, self.context)
        self.assertEqual(self._record()[1], 1)

    def test_onboarding_record_requires_authoritative_active_personnel_decision(self):
        store = HRStore(self.database)
        try:
            store.put(ResidentHRRecord("r3:test", "Test Resident", "Engineering Manager",
                                       status="onboarding"), expected_revision=1)
        finally:
            store.close()
        params = {**self.params, "expected_revision": 2}
        with self.assertRaisesRegex(ValueError, "personnel_decision_not_active"):
            self.operation.executor(params, self.context)
        self.assertEqual(self._record()[1], 2)
        self.assertEqual(self.resolver_calls, [])

    def test_idempotent_replay_returns_same_refs_and_changed_content_conflicts(self):
        first = self.operation.executor(self.params, self.context)
        calls = len(self.resolver_calls)
        replay = self.operation.executor(self.params, self.context)
        self.assertEqual(first, replay)
        self.assertEqual(len(self.resolver_calls), calls)
        with self.assertRaisesRegex(ValueError, "idempotency_conflict"):
            self.operation.executor({**self.params, "evidence_ref": "different-ref"},
                                    self.context)
        self.assertEqual(self._record()[1], 2)

    def test_duplicate_or_conflicting_principal_association_is_rejected(self):
        self.operation.executor(self.params, self.context)
        store = HRStore(self.database)
        try:
            store.put(ResidentHRRecord("r3:other", "Other Resident", "Engineering Manager",
                                       status="active"))
        finally:
            store.close()
        gateway = FakeGateway()
        def conflicting_evidence(ref):
            evidence = self.resolve_evidence(ref)
            evidence["resident_id"] = "r3:other"
            return evidence
        register_hr_governed_tools(gateway, self.database,
                                   directory_evidence_resolver=conflicting_evidence)
        operation = gateway.capabilities["associate_authority_principal_with_provenance"]
        params = {"scope_ref": "r3:other", "expected_revision": 1,
                  "evidence_ref": "evidence-ref:other",
                  "idempotency_key": "association-idem:other"}
        context = SimpleNamespace(**{**vars(self.context), "correlation_id": "corr:other",
                                     "scope_ref": "r3:other"})
        with self.assertRaisesRegex(ValueError, "association_conflict"):
            operation.executor(params, context)
        self.assertEqual(self._record()[1], 2)


if __name__ == "__main__":
    unittest.main()
