"""Universal packet, authorization, revision, lifecycle, and privacy regressions."""
# R3 CONTROLLED TEST
# File: tests/test_r3a_resident_onboarding.py
# Component: R3A-RESIDENT-ONBOARDING-TESTS
# File Revision: 1.0.0 (first controlled revision; legacy file had no provenance header)
# Created: Unknown (legacy; first committed at e618dd7)
# Created By: Unknown (legacy)
# Purpose: Verify reusable packet workflow, authority boundaries, persistence, privacy, and lifecycle behavior.
# Execution Model: Isolated unittest/pytest suite with in-memory and private database fixtures.
# Observability: Assertion outcomes; database tests use only explicit disposable DSNs.
# Dependencies: R3A resident onboarding service, repositories, packet schema, and state machine.
# Authority: Issue #58; dispatch #61 comment 6808376918; AP4 R3A-015/R3A-021.
# Changed: 2026-11-11T22:23:06Z | HRD-STEP-142 | Codex GPT-6 | Cover awaitable host authorization and evidence ports.
# Supersedes: None
# Superseded By: None
# Contracts: r3a.resident.onboarding.host-composition.v1; universal onboarding packet v1.
# Tests: This module.
# History/Predecessor: Commit 49cdf5e7fb082867c512b8c4890947faf7dd9a5c; prior blob 8823e107d747413b5a5ec32efb60003994e35680.

from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import unittest
import uuid

from r3a_runtime.residents.onboarding import (
    DuplicateOnboarding,
    OnboardingActor,
    OnboardingIdempotencyConflict,
    OnboardingRevisionConflict,
    OnboardingError,
    REQUIRED_FIELDS,
    ResidentOnboardingService,
    _require_activation_evidence,
    new_onboarding_packet,
    public_packet_summary,
    transition_packet,
    validate_json_schema_and_machine,
    validate_packet,
    _canonical_domain_metadata,
)
from r3a_runtime.residents.onboarding_repository import PostgresResidentOnboardingRepository


FIXTURES = Path(__file__).parent / "fixtures"
NOW = "2026-11-10T13:00:00Z"
FUTURE = "2099-01-01T00:00:00Z"


def _new(packet_id: str, resident_id: str | None, label: str, role: str):
    return new_onboarding_packet(
        packet_id=packet_id,
        create_idempotency_key=f"request-{packet_id}",
        resident_id=None,
        display_label=label,
        requested_role=role,
        request_source_ref=f"test://request/{packet_id}",
        created_at=NOW,
    )


def _verified_domain(name: str, owner: str, fields: set[str], *, expires: bool = False):
    approval = f"test://approval/{name}"
    evidence = f"test://evidence/{name}"
    canonical = _canonical_domain_metadata(name, "conditional" if name == "character" else "mandatory")
    return {
        **canonical, "approval_ref": approval,
        "status": "verified",
        "evidence_refs": [evidence], "revision_pins": {name: "revision:1"},
        "blocker_ref": None,
        "fields": [{
            "field_id": field_id, "value_ref": f"test://value/{name}/{field_id}",
            "classification": "institutional",
            "owner": "Independent Auditor" if name == "acceptance" and field_id == "independent_review" else owner,
            "source_ref": f"test://source/{name}/{field_id}",
            "approval_required": True, "approval_ref": approval,
            "validation_contract": f"test://validate/{name}/{field_id}",
            "evidence_refs": [evidence], "revision_pin": f"{name}:1",
            "expires_at": FUTURE if expires else None, "status": "verified",
        } for field_id in sorted(fields)],
    }


def _identity_domain(resident_id: str):
    domain = _verified_domain("identity", "HR", REQUIRED_FIELDS["identity"])
    field = next(item for item in domain["fields"] if item["field_id"] == "canonical_principal")
    field["value_ref"] = f"test://identity/{resident_id}"
    field["evidence_refs"] = [f"test://identity-evidence/{resident_id}"]
    return domain


def _activation_packet():
    packet = _new("4f0a6b4c-75e7-45b1-9598-a70aebf7a0aa", "r3:synthetic-analyst",
                  "Synthetic Analyst", "Research Analyst")
    packet["resident_id"] = "r3:synthetic-analyst"
    owners = {"identity": "HR", "appointment": "HR", "character": "Character Architecture",
              "credentials": "Security", "grants": "Security", "runtime": "Coordinator",
              "communications": "Website", "acceptance": "Steward", "lifecycle": "HR"}
    for domain, fields in REQUIRED_FIELDS.items():
        packet["domains"][domain] = _verified_domain(
            domain, owners[domain], fields, expires=domain in {"credentials", "grants"})
    auditor_field = next(field for field in packet["domains"]["acceptance"]["fields"]
                         if field["field_id"] == "independent_review")
    auditor_field["owner"] = "Independent Auditor"
    packet["domains"]["character"] = {
        "applicability": "conditional", "owner": "Character Architecture",
        "authority_source": "r3a.character-architecture",
        "required_approval": "Character Architecture approval when applicable",
        "approval_ref": "test://approval/character-na",
        "status": "not_applicable", "validation_contract": "r3a.resident.onboarding.character.v1",
        "evidence_refs": ["test://evidence/character-na"], "revision_pins": {},
        "fields": [], "blocker_ref": None,
    }
    packet["state"] = "VALIDATION_PENDING"
    packet["packet_revision"] = 7
    return validate_packet(packet)


class MemoryOnboardingStore:
    """Test-only CAS store; production uses the R3A Postgres repository."""

    def __init__(self):
        self.packets = {}
        self.fail_next_transition = False

    async def create_packet(self, packet, event):
        prior = next((p for p in self.packets.values()
                      if p["create_idempotency_key"] == packet["create_idempotency_key"]), None)
        if prior:
            if prior["request_context"] != packet["request_context"]:
                raise OnboardingIdempotencyConflict("conflicting create retry")
            return deepcopy(prior)
        if packet["resident_id"] and any(
                p["resident_id"] == packet["resident_id"] and p["state"] not in {"REVOKED", "OFFBOARDED"}
                for p in self.packets.values()):
            raise DuplicateOnboarding("active packet exists")
        self.packets[packet["packet_id"]] = deepcopy(packet)
        return deepcopy(packet)

    async def get_packet(self, packet_id):
        packet = self.packets.get(packet_id)
        return deepcopy(packet) if packet else None

    async def transition_packet(self, packet, *, expected_revision, event):
        if self.fail_next_transition:
            self.fail_next_transition = False
            raise RuntimeError("simulated interruption before commit")
        current = self.packets[packet["packet_id"]]
        prior = next((item for item in current["audit"]
                      if item["idempotency_key"] == event["idempotency_key"]), None)
        if prior:
            if prior != event:
                raise OnboardingIdempotencyConflict("conflicting event replay")
            return deepcopy(current)
        if current["packet_revision"] != expected_revision:
            raise OnboardingRevisionConflict("stale packet")
        if packet["resident_id"] and any(
                other_id != packet["packet_id"] and other["resident_id"] == packet["resident_id"]
                and other["state"] not in {"REVOKED", "OFFBOARDED"}
                for other_id, other in self.packets.items()):
            raise DuplicateOnboarding("active packet exists for canonical resident")
        self.packets[packet["packet_id"]] = deepcopy(packet)
        return deepcopy(packet)


class _Cursor:
    def __init__(self, row):
        self.row = row

    async def fetchone(self):
        return self.row


class _AsyncContext:
    def __init__(self, enter, exit):
        self._enter = enter
        self._exit = exit

    async def __aenter__(self):
        return self._enter()

    async def __aexit__(self, exc_type, exc, traceback):
        self._exit(exc_type, exc, traceback)


class _FakePostgresPool:
    def __init__(self, *, fail_event=False):
        self.packets = {}
        self.events = []
        self.statements = []
        self.fail_event = fail_event
        self.conn = _FakePostgresConnection(self)

    def connection(self):
        return _AsyncContext(lambda: self.conn, lambda exc_type, exc, tb: None)


class _FakePostgresConnection:
    def __init__(self, pool):
        self.pool = pool

    def transaction(self):
        def enter():
            self._snapshot = (deepcopy(self.pool.packets), deepcopy(self.pool.events))
            return self
        def exit(exc_type, exc, tb):
            if exc_type:
                self.pool.packets, self.pool.events = self._snapshot
        return _AsyncContext(enter, exit)

    async def execute(self, query, params=()):
        self.pool.statements.append(query)
        if query.startswith("INSERT INTO r3a.resident_onboarding_packets"):
            packet = json.loads(params[5])
            self.pool.packets[params[0]] = packet
            return _Cursor({"packet_id": params[0]})
        if query.startswith("INSERT INTO r3a.resident_onboarding_events"):
            if self.pool.fail_event:
                raise RuntimeError("simulated event insert failure")
            self.pool.events.append(json.loads(params[14]))
            return _Cursor(None)
        if query.startswith("SELECT packet,packet_revision FROM r3a.resident_onboarding_packets"):
            packet = self.pool.packets.get(params[0])
            return _Cursor({"packet": deepcopy(packet),
                            "packet_revision": packet["packet_revision"]} if packet else None)
        if query.startswith("SELECT event FROM r3a.resident_onboarding_events"):
            event = next((item for item in self.pool.events
                          if item.get("idempotency_key") == params[1]), None)
            return _Cursor({"event": deepcopy(event)} if event else None)
        if query.startswith("UPDATE r3a.resident_onboarding_packets"):
            packet_id, expected_revision = params[5], params[6]
            prior = self.pool.packets.get(packet_id)
            if prior is None or prior["packet_revision"] != expected_revision:
                return _Cursor(None)
            packet = json.loads(params[3])
            self.pool.packets[packet_id] = packet
            return _Cursor({"packet_id": packet_id})
        raise AssertionError(f"unexpected SQL in focused repository test: {query}")

def _service(store, *, allowed=True):
    def verify_domain(actor, domain_id, domain):
        if domain_id == "identity" and domain["status"] == "verified":
            identity_field = next((item for item in domain["fields"]
                                   if item["field_id"] == "canonical_principal"), None)
            value_ref = identity_field["value_ref"] if identity_field else ""
            resident_id = value_ref.removeprefix("test://identity/")
            return {"resident_id": resident_id} if resident_id.startswith("r3:") else False
        return True
    return ResidentOnboardingService(
        store, authorize=lambda actor, action, packet: allowed,
        verify_domain_evidence=verify_domain,
        verify_activation_evidence=lambda actor, packet: True)


class ResidentOnboardingTests(unittest.TestCase):
    def test_async_authority_ports_are_awaited_for_create_domain_and_activation(self):
        async def run():
            store = MemoryOnboardingStore()
            calls = []

            async def authorize(actor, action, packet):
                calls.append(("authorize", action))
                return True

            async def verify_domain(actor, domain_id, domain):
                calls.append(("domain", domain_id))
                if domain_id == "identity" and domain["status"] == "verified":
                    identity_field = next(field for field in domain["fields"]
                                          if field["field_id"] == "canonical_principal")
                    return {"resident_id": identity_field["value_ref"].removeprefix(
                        "test://identity/")}
                return True

            async def verify_activation(actor, packet):
                calls.append(("activation", packet["packet_id"]))
                return True

            service = ResidentOnboardingService(
                store, authorize=authorize, verify_domain_evidence=verify_domain,
                verify_activation_evidence=verify_activation)
            hr = OnboardingActor("principal:hr-async", "HR", "session:hr-async")
            packet = _new(str(uuid.uuid4()), None, "Synthetic Async Resident", "Analyst")
            created = await service.create(packet, actor=hr,
                correlation_id=str(uuid.uuid4()), reason_ref="test://reason/request",
                evidence_refs=["test://request/source"])
            pending = await service.transition(created["packet_id"], actor=hr,
                target_state="IDENTITY_PENDING", expected_revision=1,
                idempotency_key="async-identity-start", correlation_id=str(uuid.uuid4()),
                reason_ref="test://reason/identity-start", evidence_refs=["test://hr/source"],
                event_id=str(uuid.uuid4()))
            resident_id = "r3:synthetic-async"
            identity = _identity_domain(resident_id)
            verified = await service.record_domain(pending["packet_id"], "identity",
                domain=identity, actor=hr, expected_revision=2,
                idempotency_key="async-identity-record", correlation_id=str(uuid.uuid4()),
                reason_ref="test://reason/identity-verified", event_id=str(uuid.uuid4()))
            self.assertEqual(resident_id, verified["resident_id"])

            activation = _activation_packet()
            store.packets[activation["packet_id"]] = activation
            steward = OnboardingActor("principal:steward-async", "Steward", "session:steward-async")
            active = await service.transition(activation["packet_id"], actor=steward,
                target_state="ACTIVE", expected_revision=7,
                idempotency_key="async-activation", correlation_id=str(uuid.uuid4()),
                reason_ref="test://reason/activate", evidence_refs=["test://approval/steward"],
                approval_ref="test://approval/steward", event_id=str(uuid.uuid4()))
            self.assertEqual("ACTIVE", active["state"])
            self.assertIn(("activation", activation["packet_id"]), calls)
            self.assertIn(("domain", "identity"), calls)
            self.assertIn(("authorize", "resident.onboarding.request"), calls)
            self.assertIn(("authorize", "resident.onboarding.transition"), calls)
            self.assertIn(("authorize", "resident.onboarding.domain.record"), calls)

        asyncio.run(run())

    def test_schema_machine_vicky_and_second_resident_fixtures_validate(self):
        validate_json_schema_and_machine()
        vicky = json.loads((Path(__file__).parents[1] / "docs/onboarding/vicky.packet.json").read_text())
        synthetic = json.loads((FIXTURES / "resident-onboarding-synthetic.json").read_text())
        validate_packet(vicky)
        validate_packet(synthetic)
        self.assertIsNone(vicky["resident_id"])
        self.assertIsNone(synthetic["resident_id"])
        self.assertEqual("Engineering Manager", vicky["request_context"]["requested_role"])

    def test_required_fields_approval_and_provenance_are_enforced(self):
        packet = _activation_packet()
        packet["domains"]["appointment"]["fields"][0]["evidence_refs"] = []
        with self.assertRaisesRegex(OnboardingError, "requires evidence and revision"):
            validate_packet(packet)

        packet = _activation_packet()
        packet["domains"]["appointment"]["approval_ref"] = None
        with self.assertRaisesRegex(OnboardingError, "requires its separate approval"):
            validate_packet(packet)

        packet = _activation_packet()
        packet["domains"]["identity"]["fields"] = []
        with self.assertRaisesRegex(OnboardingError, "missing required evidence fields"):
            _require_activation_evidence(packet)

    def test_authorized_packet_creation_and_two_roles_share_same_workflow(self):
        async def run():
            store = MemoryOnboardingStore()
            service = _service(store)
            actor = OnboardingActor("principal:hr-fixture", "HR", "session:fixture")
            packets = [
                _new(str(uuid.uuid4()), None, "Synthetic Analyst", "Research Analyst"),
                _new(str(uuid.uuid4()), None, "Synthetic Designer", "Product Designer"),
            ]
            results = []
            for packet in packets:
                results.append(await service.create(
                    packet, actor=actor, correlation_id=str(uuid.uuid4()),
                    reason_ref="test://reason/request", evidence_refs=["test://request/evidence"]))
            for packet, resident_id in zip(results, ("r3:synthetic-analyst", "r3:synthetic-designer")):
                await service.transition(packet["packet_id"], actor=actor, target_state="IDENTITY_PENDING",
                    expected_revision=1, idempotency_key=f"identity-start-{resident_id}",
                    correlation_id=str(uuid.uuid4()), reason_ref="test://reason/identity-start",
                    evidence_refs=["test://evidence/hr"], event_id=str(uuid.uuid4()))
                results[results.index(packet)] = await service.record_domain(
                    packet["packet_id"], "identity", domain=_identity_domain(resident_id), actor=actor,
                    expected_revision=2, idempotency_key=f"identity-record-{resident_id}",
                    correlation_id=str(uuid.uuid4()), reason_ref="test://reason/identity-verified",
                    event_id=str(uuid.uuid4()))
            return results

        results = asyncio.run(run())
        self.assertEqual({"r3:synthetic-analyst", "r3:synthetic-designer"},
                         {packet["resident_id"] for packet in results})
        self.assertEqual({"Research Analyst", "Product Designer"},
                         {packet["request_context"]["requested_role"] for packet in results})

    def test_create_rejects_caller_reassignment_of_security_authority_metadata(self):
        async def run():
            store = MemoryOnboardingStore()
            service = _service(store)
            hr = OnboardingActor("principal:hr", "HR", "session:hr")
            steward = OnboardingActor("principal:steward", "Steward", "session:steward")
            for actor in (hr, steward):
                packet = _new(str(uuid.uuid4()), None, "Candidate", "Requested role")
                packet["domains"]["grants"].update({
                    "owner": actor.role,
                    "authority_source": "caller://invented-security-authority",
                    "required_approval": "caller-selected approval",
                    "validation_contract": "caller.selected.grants.v99",
                })
                with self.assertRaisesRegex(OnboardingError, "authority metadata"):
                    await service.create(packet, actor=actor, correlation_id=str(uuid.uuid4()),
                        reason_ref="test://reason/request", evidence_refs=["test://request/evidence"])
            self.assertEqual({}, store.packets)
        asyncio.run(run())

    def test_hr_cannot_reassign_or_record_security_owned_grant_evidence(self):
        async def run():
            store = MemoryOnboardingStore()
            service = _service(store)
            hr = OnboardingActor("principal:hr", "HR", "session:hr")
            packet = _new(str(uuid.uuid4()), None, "Candidate", "Requested role")
            created = await service.create(packet, actor=hr, correlation_id=str(uuid.uuid4()),
                reason_ref="test://reason/request", evidence_refs=["test://request/evidence"])

            reassigned = deepcopy(created["domains"]["grants"])
            reassigned.update({"owner": "HR", "authority_source": "caller://security",
                               "required_approval": "HR approved", "validation_contract": "hr.grants.v1"})
            with self.assertRaisesRegex(OnboardingError, "authority metadata"):
                await service.record_domain(packet["packet_id"], "grants", domain=reassigned, actor=hr,
                    expected_revision=1, idempotency_key="spoof-grants-owner-0001",
                    correlation_id=str(uuid.uuid4()), reason_ref="test://reason/spoof",
                    event_id=str(uuid.uuid4()))

            forged_field = _verified_domain("grants", "HR", REQUIRED_FIELDS["grants"], expires=True)
            with self.assertRaisesRegex(PermissionError, "authoritative owner"):
                await service.record_domain(packet["packet_id"], "grants", domain=forged_field, actor=hr,
                    expected_revision=1, idempotency_key="spoof-grants-fields-0001",
                    correlation_id=str(uuid.uuid4()), reason_ref="test://reason/spoof-fields",
                    event_id=str(uuid.uuid4()))
            self.assertEqual("pending", (await store.get_packet(packet["packet_id"]))["domains"]["grants"]["status"])
        asyncio.run(run())

    def test_unauthorized_request_and_transition_actor_are_denied(self):
        async def run():
            store = MemoryOnboardingStore()
            packet = _new(str(uuid.uuid4()), None, "Candidate", "Requested role")
            actor = OnboardingActor("principal:unknown", "HR", "session:fixture")
            with self.assertRaisesRegex(PermissionError, "request grant denied"):
                await _service(store, allowed=False).create(
                    packet, actor=actor, correlation_id=str(uuid.uuid4()),
                    reason_ref="test://reason/request", evidence_refs=["test://request/evidence"])

            created = await _service(store).create(
                packet, actor=actor, correlation_id=str(uuid.uuid4()),
                reason_ref="test://reason/request", evidence_refs=["test://request/evidence"])
            wrong_owner = OnboardingActor("principal:security", "Security", "session:security")
            with self.assertRaisesRegex(PermissionError, "required onboarding approval"):
                transition_packet(created, target_state="IDENTITY_PENDING", actor=wrong_owner,
                    expected_revision=1, idempotency_key="transition-identity-001",
                    correlation_id=str(uuid.uuid4()), reason_ref="test://reason/advance",
                    evidence_refs=["test://evidence/advance"], event_id=str(uuid.uuid4()))
        asyncio.run(run())

    def test_revision_conflict_and_idempotent_retry(self):
        packet = _new(str(uuid.uuid4()), None, "Candidate", "Requested role")
        actor = OnboardingActor("principal:hr", "HR", "session:hr")
        event = {"event_id": str(uuid.uuid4()), "idempotency_key": "advance-identity-001",
                 "correlation_id": str(uuid.uuid4()), "actor_ref": actor.principal_ref,
                 "actor_role": actor.role, "action": "resident.onboarding.transition",
                 "from_state": "REQUESTED", "to_state": "IDENTITY_PENDING",
                 "expected_revision": 1, "occurred_at": NOW, "reason_ref": "test://reason/advance",
                 "approval_ref": None, "evidence_refs": ["test://evidence/identity"],
                 "domain_id": None, "payload_digest": None}
        successor = transition_packet(packet, target_state="IDENTITY_PENDING", actor=actor,
            expected_revision=1, idempotency_key=event["idempotency_key"],
            correlation_id=event["correlation_id"], reason_ref=event["reason_ref"],
            evidence_refs=event["evidence_refs"], event_id=event["event_id"], occurred_at=NOW)
        replay = transition_packet(successor, target_state="IDENTITY_PENDING", actor=actor,
            expected_revision=1, idempotency_key=event["idempotency_key"],
            correlation_id=event["correlation_id"], reason_ref=event["reason_ref"],
            evidence_refs=event["evidence_refs"], event_id=event["event_id"], occurred_at=NOW)
        self.assertIs(successor, replay)
        with self.assertRaises(OnboardingRevisionConflict):
            transition_packet(packet, target_state="IDENTITY_PENDING", actor=actor,
                expected_revision=2, idempotency_key="advance-identity-002",
                correlation_id=str(uuid.uuid4()), reason_ref="test://reason/advance",
                evidence_refs=["test://evidence/identity"], event_id=str(uuid.uuid4()))
        with self.assertRaises(OnboardingIdempotencyConflict):
            transition_packet(successor, target_state="BLOCKED", actor=actor,
                expected_revision=1, idempotency_key=event["idempotency_key"],
                correlation_id=event["correlation_id"], reason_ref=event["reason_ref"],
                evidence_refs=event["evidence_refs"], event_id=event["event_id"], occurred_at=NOW)

    def test_duplicate_resident_request_and_create_retry_are_safe(self):
        async def run():
            store = MemoryOnboardingStore()
            service = _service(store)
            actor = OnboardingActor("principal:hr", "HR", "session:hr")
            packet = _new(str(uuid.uuid4()), None, "Synthetic Analyst", "Analyst")
            request = {"actor": actor, "correlation_id": str(uuid.uuid4()),
                       "reason_ref": "test://reason/request", "evidence_refs": ["test://request/evidence"]}
            first = await service.create(packet, **request)
            retry = await service.create(packet, **request)
            self.assertEqual(first["packet_id"], retry["packet_id"])
            await service.transition(packet["packet_id"], actor=actor, target_state="IDENTITY_PENDING",
                expected_revision=1, idempotency_key="identity-start-0001", correlation_id=str(uuid.uuid4()),
                reason_ref="test://reason/identity-start", evidence_refs=["test://evidence/hr"],
                event_id=str(uuid.uuid4()))
            verified_identity = _identity_domain("r3:synthetic-analyst")
            first = await service.record_domain(packet["packet_id"], "identity", domain=verified_identity,
                actor=actor, expected_revision=2, idempotency_key="identity-record-0001",
                correlation_id=str(uuid.uuid4()), reason_ref="test://reason/identity-verified",
                event_id=str(uuid.uuid4()))
            self.assertEqual("r3:synthetic-analyst", first["resident_id"])
            duplicate = _new(str(uuid.uuid4()), None, "Synthetic Analyst Copy", "Analyst")
            second = await service.create(duplicate, **{**request, "correlation_id": str(uuid.uuid4())})
            await service.transition(second["packet_id"], actor=actor, target_state="IDENTITY_PENDING",
                expected_revision=1, idempotency_key="identity-start-0002", correlation_id=str(uuid.uuid4()),
                reason_ref="test://reason/identity-start", evidence_refs=["test://evidence/hr"],
                event_id=str(uuid.uuid4()))
            with self.assertRaises(DuplicateOnboarding):
                await service.record_domain(second["packet_id"], "identity", domain=verified_identity,
                    actor=actor, expected_revision=2, idempotency_key="identity-record-0002",
                    correlation_id=str(uuid.uuid4()), reason_ref="test://reason/identity-verified",
                    event_id=str(uuid.uuid4()))
        asyncio.run(run())

    def test_missing_or_expired_grants_block_runtime_readiness(self):
        packet = _activation_packet()
        packet["state"] = "AUTHORIZATION_PENDING"
        packet["domains"]["grants"]["status"] = "blocked"
        packet["domains"]["grants"]["blocker_ref"] = "test://blocker/denied-grant"
        with self.assertRaisesRegex(OnboardingError, "grants authority evidence is not verified"):
            from r3a_runtime.residents.onboarding import validate_transition
            validate_transition(packet, target_state="RUNTIME_PENDING", actor_role="Security",
                                reason_ref="test://reason/advance", evidence_refs=["test://evidence"],
                                approval_ref="test://approval/security")

        packet = _activation_packet()
        packet["domains"]["grants"]["fields"][0]["expires_at"] = "2020-01-01T00:00:00Z"
        validate_packet(packet)
        with self.assertRaisesRegex(OnboardingError, "is expired"):
            _require_activation_evidence(packet)
        packet["state"] = "ACTIVE"
        validate_packet(packet)
        security = OnboardingActor("principal:security", "Security", "session:security")
        suspended = transition_packet(packet, target_state="SUSPENDED", actor=security,
            expected_revision=7, idempotency_key="expire-suspend-0001", correlation_id=str(uuid.uuid4()),
            reason_ref="test://reason/expired-credential", evidence_refs=["test://evidence/expired"],
            approval_ref="test://approval/security-suspend", event_id=str(uuid.uuid4()))
        self.assertEqual("SUSPENDED", suspended["state"])

    def test_protected_hr_references_are_omitted_from_public_projection(self):
        packet = _new(str(uuid.uuid4()), None, "Private Candidate", "Requested role")
        packet["domains"]["identity"]["status"] = "blocked"
        packet["domains"]["identity"]["blocker_ref"] = "test://blocker/hr-review"
        packet["domains"]["identity"]["fields"] = [{
            "field_id": "personnel_record", "value_ref": "private://personnel/opaque-123",
            "classification": "personnel_sensitive", "owner": "HR",
            "source_ref": "private://hr/opaque-123", "approval_required": True,
            "approval_ref": None, "validation_contract": "test://contract/hr",
            "evidence_refs": ["private://evidence/ssn"], "revision_pin": "rev:1",
            "expires_at": None, "status": "blocked",
        }]
        summary = public_packet_summary(validate_packet(packet))
        serialized = json.dumps(summary)
        for secret_ref in ("Private Candidate", "personnel_record", "private://", "ssn"):
            self.assertNotIn(secret_ref, serialized)
        packet["domains"]["identity"]["fields"][0]["value_ref"] = "SSN=000-00-0000"
        with self.assertRaises(ValueError):
            validate_packet(packet)

    def test_domain_and_activation_evidence_require_authoritative_host_validation(self):
        async def run():
            store = MemoryOnboardingStore()
            hr = OnboardingActor("principal:hr", "HR", "session:hr")
            packet = _new(str(uuid.uuid4()), None, "Candidate", "Requested role")
            await _service(store).create(packet, actor=hr, correlation_id=str(uuid.uuid4()),
                reason_ref="test://reason/request", evidence_refs=["test://request/evidence"])
            await _service(store).transition(packet["packet_id"], actor=hr, target_state="IDENTITY_PENDING",
                expected_revision=1, idempotency_key="identity-start-0003", correlation_id=str(uuid.uuid4()),
                reason_ref="test://reason/identity-start", evidence_refs=["test://evidence/hr"],
                event_id=str(uuid.uuid4()))
            unavailable = ResidentOnboardingService(
                store, authorize=lambda actor, action, packet: True,
                verify_domain_evidence=lambda actor, domain, evidence: False,
                verify_activation_evidence=lambda actor, packet: False)
            with self.assertRaisesRegex(PermissionError, "not confirmed by its authoritative owner"):
                await unavailable.record_domain(packet["packet_id"], "identity",
                    domain=_identity_domain("r3:synthetic-unverified"), actor=hr,
                    expected_revision=2, idempotency_key="identity-unverified-0001",
                    correlation_id=str(uuid.uuid4()), reason_ref="test://reason/unverified",
                    event_id=str(uuid.uuid4()))
            self.assertIsNone((await store.get_packet(packet["packet_id"]))["resident_id"])

            candidate = _activation_packet()
            candidate["state"] = "VALIDATION_PENDING"
            candidate["packet_revision"] = 12
            store.packets[candidate["packet_id"]] = deepcopy(candidate)
            steward = OnboardingActor("principal:steward", "Steward", "session:steward")
            with self.assertRaisesRegex(PermissionError, "current authoritative activation evidence"):
                await unavailable.transition(candidate["packet_id"], actor=steward,
                    target_state="ACTIVE", expected_revision=12, idempotency_key="activation-0001",
                    correlation_id=str(uuid.uuid4()), reason_ref="test://reason/activation",
                    evidence_refs=["test://evidence/activation"], approval_ref="test://approval/steward",
                    event_id=str(uuid.uuid4()))
            self.assertEqual("VALIDATION_PENDING", (await store.get_packet(candidate["packet_id"]))["state"])
        asyncio.run(run())

    def test_postgres_repository_commits_packet_and_audit_atomically(self):
        async def run():
            actor = OnboardingActor("principal:hr", "HR", "session:hr")
            packet = _new(str(uuid.uuid4()), None, "Candidate", "Requested role")
            store = MemoryOnboardingStore()
            created = await _service(store).create(packet, actor=actor,
                correlation_id=str(uuid.uuid4()), reason_ref="test://reason/request",
                evidence_refs=["test://request/evidence"])

            pool = _FakePostgresPool()
            repository = PostgresResidentOnboardingRepository(pool)
            result = await repository.create_packet(created, created["audit"][-1])
            self.assertEqual(created["packet_id"], result["packet_id"])
            self.assertEqual(1, len(pool.packets))
            self.assertEqual(1, len(pool.events))
            self.assertTrue(any("INSERT INTO r3a.resident_onboarding_packets" in sql
                                for sql in pool.statements))
            self.assertTrue(any("INSERT INTO r3a.resident_onboarding_events" in sql
                                for sql in pool.statements))

            successor = transition_packet(created, target_state="IDENTITY_PENDING", actor=actor,
                expected_revision=1, idempotency_key="db-transition-0001",
                correlation_id=str(uuid.uuid4()), reason_ref="test://reason/identity-start",
                evidence_refs=["test://evidence/identity"], event_id=str(uuid.uuid4()))
            transitioned = await repository.transition_packet(
                successor, expected_revision=1, event=successor["audit"][-1])
            self.assertEqual("IDENTITY_PENDING", transitioned["state"])
            self.assertEqual(2, pool.packets[created["packet_id"]]["packet_revision"])
            replayed = await repository.transition_packet(
                successor, expected_revision=1, event=successor["audit"][-1])
            self.assertEqual("IDENTITY_PENDING", replayed["state"])
            stale = transition_packet(created, target_state="IDENTITY_PENDING", actor=actor,
                expected_revision=1, idempotency_key="db-transition-0002",
                correlation_id=str(uuid.uuid4()), reason_ref="test://reason/identity-start",
                evidence_refs=["test://evidence/identity"], event_id=str(uuid.uuid4()))
            with self.assertRaises(OnboardingRevisionConflict):
                await repository.transition_packet(
                    stale, expected_revision=1, event=stale["audit"][-1])

            failing_pool = _FakePostgresPool(fail_event=True)
            failing_repository = PostgresResidentOnboardingRepository(failing_pool)
            with self.assertRaisesRegex(RuntimeError, "event insert failure"):
                await failing_repository.create_packet(created, created["audit"][-1])
            self.assertEqual({}, failing_pool.packets)
            self.assertEqual([], failing_pool.events)
        asyncio.run(run())

    def test_block_resume_partial_failure_and_terminal_offboarding(self):
        async def run():
            store = MemoryOnboardingStore()
            service = _service(store)
            hr = OnboardingActor("principal:hr", "HR", "session:hr")
            packet = _new(str(uuid.uuid4()), None, "Candidate", "Requested role")
            await service.create(packet, actor=hr, correlation_id=str(uuid.uuid4()),
                reason_ref="test://reason/request", evidence_refs=["test://request/evidence"])
            store.fail_next_transition = True
            args = {"actor": hr, "target_state": "IDENTITY_PENDING", "expected_revision": 1,
                    "idempotency_key": "identity-pending-0001", "correlation_id": str(uuid.uuid4()),
                    "reason_ref": "test://reason/identity-start", "evidence_refs": ["test://evidence/identity"],
                    "event_id": str(uuid.uuid4())}
            with self.assertRaisesRegex(RuntimeError, "simulated interruption"):
                await service.transition(packet["packet_id"], **args)
            self.assertEqual("REQUESTED", (await store.get_packet(packet["packet_id"]))["state"])
            resumed = await service.transition(packet["packet_id"], **args)
            self.assertEqual("IDENTITY_PENDING", resumed["state"])

            blocked = await service.transition(packet["packet_id"], actor=hr, target_state="BLOCKED",
                expected_revision=2, idempotency_key="identity-block-0001", correlation_id=str(uuid.uuid4()),
                reason_ref="test://reason/missing-hr", evidence_refs=["test://ticket/hr-source"],
                event_id=str(uuid.uuid4()))
            self.assertEqual("IDENTITY_PENDING", blocked["resume_state"])
            unblocked = await service.transition(packet["packet_id"], actor=hr, target_state="IDENTITY_PENDING",
                expected_revision=3, idempotency_key="identity-resume-0001", correlation_id=str(uuid.uuid4()),
                reason_ref="test://reason/source-ready", evidence_refs=["test://evidence/hr-source"],
                event_id=str(uuid.uuid4()))
            self.assertIsNone(unblocked["resume_state"])

            # A complete synthetic evidence packet demonstrates lifecycle and rollback gates.
            active = _activation_packet()
            active["state"] = "ACTIVE"
            active["packet_revision"] = 8
            security = OnboardingActor("principal:security", "Security", "session:security")
            suspended = transition_packet(active, target_state="SUSPENDED", actor=security,
                expected_revision=8, idempotency_key="suspend-0001", correlation_id=str(uuid.uuid4()),
                reason_ref="test://reason/suspend", evidence_refs=["test://evidence/suspend"],
                approval_ref="test://approval/security-suspend", event_id=str(uuid.uuid4()))
            self.assertEqual("ACTIVE", suspended["resume_state"])
            steward = OnboardingActor("principal:steward", "Steward", "session:steward")
            reactivated = transition_packet(suspended, target_state="ACTIVE", actor=steward,
                expected_revision=9, idempotency_key="reactivate-0001", correlation_id=str(uuid.uuid4()),
                reason_ref="test://reason/reactivate", evidence_refs=["test://evidence/recheck"],
                approval_ref="test://approval/steward", event_id=str(uuid.uuid4()))
            suspension = transition_packet(reactivated, target_state="SUSPENDED", actor=security,
                expected_revision=10, idempotency_key="suspend-for-revoke-0001", correlation_id=str(uuid.uuid4()),
                reason_ref="test://reason/suspend-for-revoke", evidence_refs=["test://evidence/suspend"],
                approval_ref="test://approval/security-suspend", event_id=str(uuid.uuid4()))
            suspension["domains"]["credentials"]["status"] = "revoked"
            suspension["domains"]["grants"]["status"] = "revoked"
            revoked = transition_packet(suspension, target_state="REVOKED", actor=security,
                expected_revision=11, idempotency_key="revoke-0001", correlation_id=str(uuid.uuid4()),
                reason_ref="test://reason/revoke", evidence_refs=["test://evidence/revoke"],
                approval_ref="test://approval/security-revoke", event_id=str(uuid.uuid4()))
            hr_offboard = transition_packet(revoked, target_state="OFFBOARDED", actor=hr,
                expected_revision=12, idempotency_key="offboard-0001", correlation_id=str(uuid.uuid4()),
                reason_ref="test://reason/offboard", evidence_refs=["test://evidence/disablement"],
                approval_ref="test://approval/hr-offboard", event_id=str(uuid.uuid4()))
            self.assertEqual("OFFBOARDED", hr_offboard["state"])
        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
