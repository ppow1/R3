"""R3A-side HR/directory association client contract and fail-closed tests."""
from __future__ import annotations

import copy
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from r3a_runtime.residents.governance import GovernedActor
from r3a_runtime.residents.hr_association import (
    HRPrincipalAssociationAdapter,
    validate_association_evidence,
)
from r3a_runtime.residents.r3_authority_adapter import R3CapabilityGrantAdapter


def _evidence(*, resident_id="r3:fixture", hr_revision=4, principal_id="resident:fixture",
              office_status="active", observed_at=None, evidence_ref="evidence://fixture/edge"):
    now = observed_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "source_id": "riverview_authority.directory",
        "source_contract": "riverview-authority.directory.v1",
        "snapshot_sha256": "a" * 64,
        "observed_at": now,
        "hr_resident_id": resident_id,
        "hr_revision": hr_revision,
        "hr_source_ref": f"hr://record/{resident_id}@{hr_revision}",
        "principal_id": principal_id,
        "office_id": "office:fixture",
        "office_role": "Engineering Manager",
        "office_status": office_status,
        "binding_revision": 8,
        "evidence_refs": ["directory://snapshot/fixture", evidence_ref],
        "verified_at": now,
    }


class AuthorityStub:
    def __init__(self, *, denied=False):
        self.denied = denied
        self.checks = []
        self.audits = []

    def authorize(self, **request):
        self.checks.append(request)
        if self.denied:
            raise PermissionError("exact HR grant absent")
        return {"grant_id": "grant:fixture"}

    def audit(self, event):
        self.audits.append(event)


class HRHostStub:
    def __init__(self, *, status="active", revision=4, result=None, has_operation=True):
        self.status = status
        self.revision = revision
        self.result = result
        self.calls = []
        self.read_calls = []
        if has_operation:
            self.associate_authority_principal_with_provenance = self._associate

    def read(self, principal, resident_id):
        self.read_calls.append((principal.principal_id, resident_id))
        return {"resident_id": resident_id, "revision": self.revision, "status": self.status}

    def _associate(self, **request):
        self.calls.append(request)
        return self.result


class HRAssociationAdapterTests(unittest.TestCase):
    def setUp(self):
        self.authority = AuthorityStub()
        self.grants = R3CapabilityGrantAdapter(
            self.authority,
            resolve_verified_principal=lambda actor: SimpleNamespace(
                principal_id=actor.principal_id, role="hr"))
        self.hr = HRHostStub()
        self.resolver_calls = []
        self.evidence = _evidence()

        def resolver(actor, resident_id, evidence_ref):
            self.resolver_calls.append((actor.principal_id, resident_id, evidence_ref))
            return copy.deepcopy(self.evidence)

        self.adapter = HRPrincipalAssociationAdapter(
            self.hr, self.grants, resolve_directory_evidence=resolver)
        self.actor = GovernedActor("principal:hr-fixture", "session:server-verified")
        self.request = {
            "resident_id": "r3:fixture", "expected_hr_revision": 4,
            "evidence_ref": "evidence://fixture/edge",
            "idempotency_key": "hr-association:fixture:4:edge",
            "correlation_id": "corr:hr-association:fixture:4",
        }

    def _successful_host_result(self, call):
        return {
            "resident_id": call["resident_id"],
            "authority_principal": call["authority_principal"],
            "revision": call["expected_revision"] + 1,
            "provenance": call["provenance"],
            "association_ref": "hr-association://fixture/5",
            "audit_event_ref": "audit://fixture/association-1",
            "authorization_ref": "grant:fixture",
            "idempotency_key": call["idempotency_key"],
            "correlation_id": call["correlation_id"],
        }

    def test_valid_source_evidence_is_fresh_and_revision_bound(self):
        result = validate_association_evidence(
            self.evidence, resident_id="r3:fixture", expected_hr_revision=4)
        self.assertEqual(result["principal_id"], "resident:fixture")
        for evidence, message in (
            ({**self.evidence, "hr_resident_id": "r3:other"}, "exact revisioned HR identity"),
            ({**self.evidence, "hr_revision": 3}, "exact revisioned HR identity"),
            ({**self.evidence, "office_status": "inactive"}, "current authoritative office binding"),
        ):
            with self.subTest(evidence=evidence):
                with self.assertRaisesRegex(ValueError, message):
                    validate_association_evidence(
                        evidence, resident_id="r3:fixture", expected_hr_revision=4)

    def test_stale_directory_snapshot_is_rejected(self):
        old = (datetime.now(timezone.utc) - timedelta(minutes=6)).isoformat().replace("+00:00", "Z")
        with self.assertRaisesRegex(ValueError, "directory association evidence is stale"):
            validate_association_evidence(
                _evidence(observed_at=old), resident_id="r3:fixture", expected_hr_revision=4)

    def test_success_uses_server_resolved_principal_and_forwards_stable_audit_keys(self):
        def operation(**request):
            self.hr.calls.append(request)
            return self._successful_host_result(request)
        self.hr.associate_authority_principal_with_provenance = operation

        result = self.adapter.associate(self.actor, **self.request)
        self.assertEqual(result["authority_principal"], "resident:fixture")
        self.assertEqual(result["revision"], 5)
        call = self.hr.calls[0]
        self.assertEqual(call["resident_id"], "r3:fixture")
        self.assertEqual(call["authority_principal"], "resident:fixture")
        self.assertEqual(call["expected_revision"], 4)
        self.assertEqual(call["idempotency_key"], self.request["idempotency_key"])
        self.assertEqual(call["correlation_id"], self.request["correlation_id"])
        self.assertEqual(self.resolver_calls, [(
            self.actor.principal_id, "r3:fixture", self.request["evidence_ref"])])
        self.assertEqual(self.authority.checks[0]["resource_id"], "r3:hr")
        self.assertEqual(self.authority.checks[0]["action"], "hr.write")
        self.assertEqual(self.authority.checks[0]["operation"], "write")
        self.assertEqual(self.authority.checks[0]["scope_ref"], "r3:fixture")
        self.assertEqual(self.authority.audits[-1]["correlation_id"],
                         self.request["correlation_id"])

    def test_missing_hr_host_operation_fails_closed_after_evidence_resolution(self):
        hr = HRHostStub(has_operation=False)
        adapter = HRPrincipalAssociationAdapter(
            hr, self.grants,
            resolve_directory_evidence=lambda actor, resident_id, evidence_ref: copy.deepcopy(self.evidence))
        with self.assertRaisesRegex(NotImplementedError,
                                    "lacks associate_authority_principal_with_provenance"):
            adapter.associate(self.actor, **self.request)

    def test_missing_exact_grant_denies_before_hr_read_or_directory_resolution(self):
        authority = AuthorityStub(denied=True)
        grants = R3CapabilityGrantAdapter(
            authority,
            resolve_verified_principal=lambda actor: SimpleNamespace(
                principal_id=actor.principal_id, role="hr"))
        adapter = HRPrincipalAssociationAdapter(
            self.hr, grants,
            resolve_directory_evidence=lambda *args: self.resolver_calls.append(args))
        with self.assertRaisesRegex(PermissionError, "exact scoped HR write capability denied"):
            adapter.associate(self.actor, **self.request)
        self.assertEqual(self.hr.read_calls, [])
        self.assertEqual(self.resolver_calls, [])
        self.assertEqual(authority.audits[-1]["outcome"], "denied")

    def test_revision_conflict_and_onboarding_status_fail_before_directory_resolution(self):
        self.hr.revision = 5
        with self.assertRaisesRegex(RuntimeError, "HR revision conflict"):
            self.adapter.associate(self.actor, **self.request)
        self.assertEqual(self.resolver_calls, [])

        self.hr.revision = 4
        self.hr.status = "onboarding"
        with self.assertRaisesRegex(PermissionError, "active HR appointment decision"):
            self.adapter.associate(self.actor, **self.request)
        self.assertEqual(self.resolver_calls, [])

    def test_vicky_onboarding_row_cannot_be_associated_without_appointment(self):
        hr = HRHostStub(status="onboarding", revision=1)
        resolver_calls = []
        adapter = HRPrincipalAssociationAdapter(
            hr, self.grants,
            resolve_directory_evidence=lambda *args: resolver_calls.append(args))
        request = {**self.request, "resident_id": "r3:vicky", "expected_hr_revision": 1,
                   "evidence_ref": "opaque-ref-not-personnel-approval"}
        with self.assertRaisesRegex(PermissionError, "active HR appointment decision"):
            adapter.associate(self.actor, **request)
        self.assertEqual(resolver_calls, [])
        self.assertEqual(hr.calls, [])

    def test_host_result_must_include_persisted_provenance_and_audit_references(self):
        self.hr.associate_authority_principal_with_provenance = lambda **request: {
            "resident_id": request["resident_id"],
            "authority_principal": request["authority_principal"],
            "revision": 5,
            "provenance": request["provenance"],
            "idempotency_key": request["idempotency_key"],
            "correlation_id": request["correlation_id"],
        }
        with self.assertRaisesRegex(RuntimeError, "auditable persisted evidence"):
            self.adapter.associate(self.actor, **self.request)


if __name__ == "__main__":
    unittest.main()
