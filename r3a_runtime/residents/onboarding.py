"""Governed, data-driven resident onboarding packet and lifecycle contracts.

This module coordinates evidence references. It is not an HR, directory,
credential, character, capability-grant, or runtime authority.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Callable, Protocol
import uuid

from ..capability_contracts import validate_json, validate_schema_definition


_ROOT = Path(__file__).parents[1]
PACKET_SCHEMA = json.loads((_ROOT / "schemas" / "resident-onboarding-packet.v1.schema.json").read_text())
STATE_MACHINE = json.loads((_ROOT / "state_machines" / "resident_onboarding.v1.json").read_text())
STATES = frozenset(STATE_MACHINE["states"])
TERMINAL_STATES = frozenset(STATE_MACHINE["terminal"])
ROLES = frozenset({"HR", "Character Architecture", "Security", "Coordinator",
                   "Website", "Independent Auditor", "Steward"})

REQUIRED_FIELDS = {
    "identity": {"authoritative_hr_identity", "canonical_principal", "principal_association",
                 "active_office_binding"},
    "appointment": {"approved_appointment", "title_and_responsibilities", "office_assignment",
                     "reporting_relationships", "appointment_authority", "effective_dates"},
    "character": {"approved_character_identity", "canon_revision", "continuity_association",
                   "protected_relationship_policy", "approved_character_artifacts"},
    "credentials": {"credential_reference", "credential_owner", "credential_expiration",
                     "authentication_verification"},
    "grants": {"approved_capability_grants", "grant_scopes", "grant_expiration",
               "grant_renewal", "grant_revocation"},
    "runtime": {"module_registration", "model_route", "runtime_dependencies",
                "canonical_capability_interface", "cme_registration", "resident_configuration"},
    "communications": {"authenticated_directory_visibility", "chat_availability",
                       "conversation_persistence", "display_name_title_status",
                       "approved_communications_interfaces"},
    "acceptance": {"identity_appointment_checks", "credential_check", "capability_discovery",
                   "authorized_invocation", "inference_execution", "cme_persistence",
                   "independent_review", "steward_acceptance"},
    "lifecycle": {"renewal_procedure", "reassignment_procedure", "suspension_reactivation",
                   "credential_rotation", "grant_revocation", "offboarding", "rollback_recovery"},
}

_ADVANCE_ROLE = {
    ("REQUESTED", "IDENTITY_PENDING"): "HR",
    ("IDENTITY_PENDING", "APPOINTMENT_PENDING"): "HR",
    ("APPOINTMENT_PENDING", "AUTHORIZATION_PENDING"): "HR",
    ("AUTHORIZATION_PENDING", "RUNTIME_PENDING"): "Security",
    ("RUNTIME_PENDING", "VALIDATION_PENDING"): "Coordinator",
    ("VALIDATION_PENDING", "ACTIVE"): "Steward",
}
_STAGE_FOR_STATE = {
    "REQUESTED": "identity", "IDENTITY_PENDING": "identity",
    "APPOINTMENT_PENDING": "appointment", "AUTHORIZATION_PENDING": "grants",
    "RUNTIME_PENDING": "runtime", "VALIDATION_PENDING": "acceptance",
}
_RESUME_STATES = frozenset({*_STAGE_FOR_STATE, "ACTIVE"})


class OnboardingError(ValueError):
    """Packet or lifecycle request does not satisfy the R3A contract."""


class OnboardingRevisionConflict(RuntimeError):
    """A packet changed since the caller's revision pin."""


class OnboardingIdempotencyConflict(RuntimeError):
    """An idempotency key was replayed with a different request."""


class DuplicateOnboarding(RuntimeError):
    """A nonterminal packet already exists for the canonical resident identity."""


@dataclass(frozen=True)
class OnboardingActor:
    """Server-attested actor facts resolved outside packet/request data."""

    principal_ref: str
    role: str
    authentication_ref: str

    def __post_init__(self) -> None:
        if (not self.principal_ref or not self.authentication_ref or self.role not in ROLES):
            raise ValueError("server-authenticated onboarding actor and institutional role are required")


class OnboardingStore(Protocol):
    async def create_packet(self, packet: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]: ...
    async def get_packet(self, packet_id: str) -> dict[str, Any] | None: ...
    async def transition_packet(self, packet: dict[str, Any], *, expected_revision: int,
                                event: dict[str, Any]) -> dict[str, Any]: ...


def validate_packet(packet: Any) -> dict[str, Any]:
    """Validate the versioned packet and its evidence/approval invariants."""
    validate_schema_definition(PACKET_SCHEMA)
    validate_json(packet, PACKET_SCHEMA)
    domains = packet["domains"]
    for domain_id, domain in domains.items():
        if not isinstance(domain["owner"], str) or domain["owner"] not in ROLES:
            raise OnboardingError(f"domains.{domain_id}.owner is not an institutional authority")
        if domain["status"] == "verified":
            if not domain["evidence_refs"] or not domain["fields"]:
                raise OnboardingError(f"verified domain {domain_id} requires field and stage evidence")
            if domain["required_approval"] != "none" and not domain["approval_ref"]:
                raise OnboardingError(f"verified domain {domain_id} requires its separate approval reference")
        if domain["status"] == "blocked" and not domain["blocker_ref"]:
            raise OnboardingError(f"blocked domain {domain_id} requires a source or issue reference")
        field_ids: set[str] = set()
        for field in domain["fields"]:
            if field["field_id"] in field_ids:
                raise OnboardingError(f"duplicate evidence field in {domain_id}: {field['field_id']}")
            field_ids.add(field["field_id"])
            if field["status"] == "verified":
                if not field["evidence_refs"] or not field["revision_pin"]:
                    raise OnboardingError(f"verified field {domain_id}.{field['field_id']} requires evidence and revision")
                if field["approval_required"] and not field["approval_ref"]:
                    raise OnboardingError(f"verified field {domain_id}.{field['field_id']} requires approval")
        if domain["status"] == "verified" and any(f["status"] != "verified" for f in domain["fields"]):
            raise OnboardingError(f"verified domain {domain_id} contains an unverified field")
        if domain_id in {"credentials", "grants"} and domain["status"] == "verified":
            expiry_field = ("credential_expiration" if domain_id == "credentials" else "grant_expiration")
            field = next((f for f in domain["fields"] if f["field_id"] == expiry_field), None)
            if field is None or field["expires_at"] is None:
                raise OnboardingError(f"verified {domain_id} requires an explicit expiry")
        if domain["status"] == "not_applicable" and domain["applicability"] == "mandatory":
            raise OnboardingError(f"mandatory domain {domain_id} cannot be marked not applicable")
        if domain["status"] == "not_applicable" and not domain["approval_ref"]:
            raise OnboardingError(f"not-applicable decision for {domain_id} requires an authority reference")
    if packet["resident_id"] is None and packet["domains"]["identity"]["status"] == "verified":
        raise OnboardingError("verified identity requires a canonical HR resident ID")
    if packet["state"] == "ACTIVE":
        _require_activation_evidence(packet, check_expiration=False)
    if packet["state"] in {"BLOCKED", "SUSPENDED"} and packet["resume_state"] not in _RESUME_STATES:
        raise OnboardingError("blocked or suspended packet must preserve a resumable checkpoint")
    if packet["state"] not in {"BLOCKED", "SUSPENDED"} and packet["resume_state"] is not None:
        raise OnboardingError("resume checkpoint is only valid while blocked or suspended")
    return packet


def _require_domain(packet: dict[str, Any], domain_id: str, *, check_expiration: bool = True) -> None:
    domain = packet["domains"][domain_id]
    if domain["status"] != "verified":
        raise OnboardingError(f"{domain_id} authority evidence is not verified")
    missing = REQUIRED_FIELDS[domain_id] - {field["field_id"] for field in domain["fields"]
                                            if field["status"] == "verified"}
    if missing:
        raise OnboardingError(f"{domain_id} is missing required evidence fields: {sorted(missing)}")
    if check_expiration:
        now = datetime.now(timezone.utc)
        for field in domain["fields"]:
            if field["expires_at"] and datetime.fromisoformat(
                    field["expires_at"].replace("Z", "+00:00")).astimezone(timezone.utc) <= now:
                raise OnboardingError(f"verified field {domain_id}.{field['field_id']} is expired")


def _require_activation_evidence(packet: dict[str, Any], *, check_expiration: bool = True) -> None:
    for domain_id in ("identity", "appointment", "credentials", "grants", "runtime",
                      "communications", "acceptance", "lifecycle"):
        _require_domain(packet, domain_id, check_expiration=check_expiration)
    character = packet["domains"]["character"]
    if character["applicability"] == "mandatory":
        _require_domain(packet, "character", check_expiration=check_expiration)
    elif character["status"] == "verified":
        _require_domain(packet, "character", check_expiration=check_expiration)
    elif character["status"] != "not_applicable":
        raise OnboardingError("conditional character approval must be verified or explicitly not applicable")


def validate_transition(packet: dict[str, Any], *, target_state: str, actor_role: str,
                        reason_ref: str, evidence_refs: list[str], approval_ref: str | None) -> None:
    current_state = packet["state"]
    if target_state not in STATE_MACHINE["transitions"].get(current_state, []):
        raise OnboardingError(f"invalid resident onboarding transition {current_state} -> {target_state}")
    if not reason_ref or not evidence_refs:
        raise OnboardingError("lifecycle transition requires a reason and auditable evidence references")
    if actor_role not in ROLES:
        raise PermissionError("institutional onboarding authority is unavailable")
    if target_state == "BLOCKED":
        required_role = packet["domains"][_STAGE_FOR_STATE[current_state]]["owner"]
        if actor_role != required_role:
            raise PermissionError("only the current domain authority may block this onboarding stage")
        return
    if target_state == "SUSPENDED":
        if actor_role not in {"Security", "HR", "Steward"} or not approval_ref:
            raise PermissionError("suspension requires Security, HR, or Steward authority and approval evidence")
        return
    if target_state == "REVOKED":
        if actor_role not in {"Security", "HR", "Steward"} or not approval_ref:
            raise PermissionError("revocation requires Security, HR, or Steward authority and approval evidence")
        if (not _domain_revoked_or_never_issued(packet["domains"]["credentials"], "credential_never_issued")
                or not _domain_revoked_or_never_issued(packet["domains"]["grants"], "grant_never_issued")):
            raise OnboardingError("suspension and credential/grant revocation or non-issuance evidence are required before REVOKED")
        return
    if target_state == "OFFBOARDED":
        if actor_role not in {"HR", "Coordinator", "Steward"} or not approval_ref:
            raise PermissionError("offboarding requires HR, Coordinator, or Steward authority and approval evidence")
        if (not _domain_revoked_or_never_issued(packet["domains"]["credentials"], "credential_never_issued")
                or not _domain_revoked_or_never_issued(packet["domains"]["grants"], "grant_never_issued")):
            raise OnboardingError("offboarding requires credential/grant revocation or non-issuance evidence")
        return
    if current_state in {"BLOCKED", "SUSPENDED"}:
        if target_state != packet["resume_state"]:
            raise OnboardingError("resume must continue from the saved onboarding checkpoint")
        required_role = ("Steward" if target_state == "ACTIVE"
                         else packet["domains"][_STAGE_FOR_STATE[target_state]]["owner"])
    else:
        required_role = _ADVANCE_ROLE.get((current_state, target_state))
    if not required_role or actor_role != required_role:
        raise PermissionError("transition actor does not own the required onboarding approval")
    if target_state == "APPOINTMENT_PENDING":
        _require_domain(packet, "identity")
    elif target_state == "AUTHORIZATION_PENDING":
        _require_domain(packet, "appointment")
    elif target_state == "RUNTIME_PENDING":
        _require_domain(packet, "credentials")
        _require_domain(packet, "grants")
    elif target_state == "VALIDATION_PENDING":
        _require_domain(packet, "runtime")
    elif target_state == "ACTIVE":
        if not approval_ref:
            raise PermissionError("activation requires explicit Steward approval evidence")
        _require_activation_evidence(packet)


def _domain_revoked_or_never_issued(domain: dict[str, Any], field_id: str) -> bool:
    if domain["status"] == "revoked" and domain["evidence_refs"] and domain["approval_ref"]:
        return True
    return any(field["field_id"] == field_id and field["status"] == "verified"
               and field["evidence_refs"] and field["approval_ref"] for field in domain["fields"])


def transition_packet(packet: dict[str, Any], *, target_state: str, actor: OnboardingActor,
                      expected_revision: int, idempotency_key: str, correlation_id: str,
                      reason_ref: str, evidence_refs: list[str], approval_ref: str | None = None,
                      event_id: str, occurred_at: str | None = None) -> dict[str, Any]:
    """Build a successor packet; durable CAS and audit commit belong to the repository."""
    validate_packet(packet)
    existing = next((event for event in packet["audit"]
                     if event["idempotency_key"] == idempotency_key), None)
    request_shape = {"to_state": target_state, "expected_revision": expected_revision,
                     "actor_ref": actor.principal_ref, "actor_role": actor.role,
                     "correlation_id": correlation_id,
                     "reason_ref": reason_ref, "approval_ref": approval_ref,
                     "evidence_refs": sorted(evidence_refs)}
    if existing:
        existing_shape = {"to_state": existing["to_state"],
                          "expected_revision": existing["expected_revision"],
                          "actor_ref": existing["actor_ref"], "actor_role": existing["actor_role"],
                          "correlation_id": existing["correlation_id"],
                          "reason_ref": existing["reason_ref"], "approval_ref": existing["approval_ref"],
                          "evidence_refs": sorted(existing["evidence_refs"])}
        if existing_shape != request_shape:
            raise OnboardingIdempotencyConflict("idempotency key was reused for a conflicting transition")
        return packet
    if packet["packet_revision"] != expected_revision:
        raise OnboardingRevisionConflict("resident onboarding packet revision changed")
    if not idempotency_key or len(idempotency_key) > 200 or not correlation_id:
        raise OnboardingError("stable idempotency and correlation identifiers are required")
    validate_transition(packet, target_state=target_state, actor_role=actor.role,
                        reason_ref=reason_ref, evidence_refs=evidence_refs,
                        approval_ref=approval_ref)
    successor = deepcopy(packet)
    prior_state = packet["state"]
    resume_state = packet["resume_state"]
    if target_state == "BLOCKED":
        resume_state = prior_state
    elif target_state == "SUSPENDED":
        resume_state = prior_state
    elif prior_state in {"BLOCKED", "SUSPENDED"}:
        resume_state = None
    successor["state"] = target_state
    successor["resume_state"] = resume_state
    successor["packet_revision"] = expected_revision + 1
    successor["updated_at"] = occurred_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    successor["audit"].append({
        "event_id": event_id, "idempotency_key": idempotency_key,
        "correlation_id": correlation_id, "actor_ref": actor.principal_ref,
        "actor_role": actor.role, "action": "resident.onboarding.transition",
        "from_state": prior_state, "to_state": target_state,
        "expected_revision": expected_revision, "occurred_at": successor["updated_at"],
        "reason_ref": reason_ref, "approval_ref": approval_ref,
        "evidence_refs": list(evidence_refs), "domain_id": None,
        "payload_digest": None,
    })
    return validate_packet(successor)


def public_packet_summary(packet: dict[str, Any]) -> dict[str, Any]:
    """Safe status projection with no names, source refs, evidence, or protected facts."""
    validate_packet(packet)
    return {"packet_id": packet["packet_id"], "packet_revision": packet["packet_revision"],
            "state": packet["state"],
            "domains": {key: {"status": value["status"], "owner": value["owner"]}
                        for key, value in packet["domains"].items()}}


def new_onboarding_packet(*, packet_id: str, create_idempotency_key: str,
                         resident_id: str | None, display_label: str,
                         requested_role: str | None, request_source_ref: str,
                         created_at: str, character_applicability: str = "conditional") -> dict[str, Any]:
    """Create a data-only packet skeleton; it grants no identity or appointment."""
    owner_and_source = {
        "identity": ("HR", "riverview_authority.hr"),
        "appointment": ("HR", "riverview_authority.hr"),
        "character": ("Character Architecture", "r3a.character-architecture"),
        "credentials": ("Security", "institutional.security.credentials"),
        "grants": ("Security", "r3a.authority.capability-grants"),
        "runtime": ("Coordinator", "r3a.cme.module-registry"),
        "communications": ("Website", "r3a.website.resident-roster-and-chat"),
        "acceptance": ("Steward", "r3a.acceptance.evidence"),
        "lifecycle": ("HR", "r3a.resident.lifecycle"),
    }
    domains = {}
    for domain_id, (owner, authority_source) in owner_and_source.items():
        applicability = character_applicability if domain_id == "character" else "mandatory"
        domains[domain_id] = {
            "applicability": applicability, "owner": owner,
            "authority_source": authority_source,
            "required_approval": {
                "identity": "HR identity approval and source association",
                "appointment": "HR appointment authority approval",
                "character": "Character Architecture approval when applicable",
                "credentials": "Security credential issuance approval",
                "grants": "Security capability grant approval",
                "runtime": "Coordinator registration and deployment approval",
                "communications": "Coordinator Website integration approval",
                "acceptance": "Independent Auditor review and Steward acceptance",
                "lifecycle": "HR, Security, and Coordinator lifecycle procedure approvals",
            }[domain_id],
            "approval_ref": None, "status": "pending",
            "validation_contract": f"r3a.resident.onboarding.{domain_id}.v1",
            "evidence_refs": [], "revision_pins": {}, "fields": [], "blocker_ref": None,
        }
    packet = {
        "schema_id": "r3a.resident.onboarding-packet", "schema_version": 1,
        "packet_id": packet_id, "packet_revision": 1,
        "create_idempotency_key": create_idempotency_key,
        "resident_id": resident_id,
        "request_context": {"display_label": display_label, "requested_role": requested_role,
                            "source_ref": request_source_ref,
                            "verification_status": "request_only"},
        "state": "REQUESTED", "resume_state": None,
        "created_at": created_at, "updated_at": created_at,
        "domains": domains, "audit": [],
    }
    return validate_packet(packet)


class ResidentOnboardingService:
    """Authorize and persist packet transitions through injected R3A boundaries."""

    def __init__(self, store: OnboardingStore, *, authorize: Callable[
            [OnboardingActor, str, dict[str, Any]], bool],
            verify_domain_evidence: Callable[[OnboardingActor, str, dict[str, Any]], Any],
            verify_activation_evidence: Callable[[OnboardingActor, dict[str, Any]], bool]):
        if not callable(authorize) or not callable(verify_domain_evidence) or not callable(verify_activation_evidence):
            raise TypeError("server-side authorization and authoritative evidence validators are required")
        for method in ("create_packet", "get_packet", "transition_packet"):
            if not callable(getattr(store, method, None)):
                raise TypeError(f"durable onboarding store lacks {method}")
        self._store = store
        self._authorize = authorize
        self._verify_domain_evidence = verify_domain_evidence
        self._verify_activation_evidence = verify_activation_evidence

    async def create(self, packet: dict[str, Any], *, actor: OnboardingActor,
                     correlation_id: str, reason_ref: str,
                     evidence_refs: list[str], approval_ref: str | None = None) -> dict[str, Any]:
        if not isinstance(actor, OnboardingActor):
            raise PermissionError("server-authenticated onboarding actor is required")
        validate_packet(packet)
        if packet["state"] != "REQUESTED" or packet["packet_revision"] != 1:
            raise OnboardingError("new packet must begin at REQUESTED revision 1")
        if packet["resident_id"] is not None or packet["request_context"]["verification_status"] != "request_only":
            raise OnboardingError("a request cannot claim a canonical resident identity before HR verification")
        if packet["audit"]:
            raise OnboardingError("new packet cannot carry caller-supplied audit history")
        for domain_id, domain in packet["domains"].items():
            if (domain["status"] != "pending" or domain["fields"] or domain["evidence_refs"]
                    or domain["approval_ref"] is not None or domain["blocker_ref"] is not None):
                raise OnboardingError(f"new request cannot pre-populate authority evidence for {domain_id}")
        if actor.role not in {"HR", "Steward"}:
            raise PermissionError("resident onboarding request requires HR or Steward authority")
        if not correlation_id or not reason_ref or not evidence_refs:
            raise OnboardingError("request requires correlation, reason, and source evidence references")
        try:
            uuid.UUID(correlation_id)
        except ValueError as exc:
            raise OnboardingError("correlation ID must be a UUID") from exc
        if self._authorize(actor, "resident.onboarding.request", packet) is not True:
            raise PermissionError("resident onboarding request grant denied")
        created = deepcopy(packet)
        now = created["created_at"]
        created["audit"].append({
            "event_id": str(uuid.uuid5(uuid.UUID(created["packet_id"]), created["create_idempotency_key"])),
            "idempotency_key": created["create_idempotency_key"],
            "correlation_id": correlation_id, "actor_ref": actor.principal_ref,
            "actor_role": actor.role, "action": "resident.onboarding.request",
            "from_state": None, "to_state": "REQUESTED", "expected_revision": 0,
            "occurred_at": now, "reason_ref": reason_ref,
            "approval_ref": approval_ref, "evidence_refs": list(evidence_refs),
            "domain_id": None, "payload_digest": None,
        })
        validate_packet(created)
        return await self._store.create_packet(created, created["audit"][-1])

    async def transition(self, packet_id: str, *, actor: OnboardingActor,
                         target_state: str, expected_revision: int,
                         idempotency_key: str, correlation_id: str,
                         reason_ref: str, evidence_refs: list[str],
                         approval_ref: str | None = None,
                         event_id: str) -> dict[str, Any]:
        if not isinstance(actor, OnboardingActor):
            raise PermissionError("server-authenticated onboarding actor is required")
        packet = await self._store.get_packet(packet_id)
        if packet is None:
            raise KeyError("resident onboarding packet not found")
        if not isinstance(actor, OnboardingActor):
            raise PermissionError("server-authenticated onboarding actor is required")
        if self._authorize(actor, "resident.onboarding.transition", packet) is not True:
            raise PermissionError("resident onboarding transition grant denied")
        try:
            uuid.UUID(correlation_id)
            uuid.UUID(event_id)
        except (ValueError, TypeError) as exc:
            raise OnboardingError("event and correlation IDs must be UUIDs") from exc
        successor = transition_packet(
            packet, target_state=target_state, actor=actor,
            expected_revision=expected_revision, idempotency_key=idempotency_key,
            correlation_id=correlation_id, reason_ref=reason_ref,
            evidence_refs=evidence_refs, approval_ref=approval_ref,
            event_id=event_id,
        )
        if target_state == "ACTIVE" and self._verify_activation_evidence(actor, packet) is not True:
            raise PermissionError("current authoritative activation evidence could not be verified")
        if successor is packet:
            return packet
        return await self._store.transition_packet(
            successor, expected_revision=expected_revision, event=successor["audit"][-1])

    async def record_domain(self, packet_id: str, domain_id: str, *,
                            domain: dict[str, Any], actor: OnboardingActor,
                            expected_revision: int, idempotency_key: str,
                            correlation_id: str, reason_ref: str,
                            event_id: str) -> dict[str, Any]:
        """Append an owner-attested domain revision without copying source data."""
        import hashlib

        packet = await self._store.get_packet(packet_id)
        if packet is None:
            raise KeyError("resident onboarding packet not found")
        if domain_id not in packet["domains"]:
            raise OnboardingError("unknown resident onboarding domain")
        if packet["state"] == "ACTIVE":
            raise OnboardingError("suspend an active resident before changing onboarding evidence")
        if packet["state"] in TERMINAL_STATES:
            raise OnboardingError("offboarded resident onboarding packets are immutable")
        if packet["state"] == "REVOKED" and domain_id not in {"appointment", "runtime", "communications", "lifecycle"}:
            raise OnboardingError("revoked packets accept only remaining offboarding evidence")
        current_domain = packet["domains"][domain_id]
        current_fields = {f["field_id"]: f for f in current_domain["fields"]}
        next_fields = {f["field_id"]: f for f in domain.get("fields", [])}
        if set(current_fields) - set(next_fields):
            raise OnboardingError("domain evidence fields are append-only; supersede by a new field revision")
        changed_fields = [field for key, field in next_fields.items()
                          if current_fields.get(key) != field]
        for field in changed_fields:
            prior_field = current_fields.get(field["field_id"])
            if (prior_field is not None
                    and prior_field.get("revision_pin") == field.get("revision_pin")):
                raise OnboardingError("changed field evidence requires a new source revision pin")
        metadata_changed = {key: value for key, value in current_domain.items() if key != "fields"} != {
            key: value for key, value in domain.items() if key != "fields"}
        if any(field["owner"] != actor.role for field in changed_fields):
            raise PermissionError("only each field's authoritative owner may change its evidence")
        if actor.role != current_domain["owner"] and (metadata_changed or not changed_fields):
            raise PermissionError("only the domain owner may change domain status, approval, or metadata")
        if self._authorize(actor, "resident.onboarding.domain.record", packet) is not True:
            raise PermissionError("resident onboarding domain evidence grant denied")
        verified = self._verify_domain_evidence(actor, domain_id, domain)
        if verified is not True and not isinstance(verified, dict):
            raise PermissionError("domain evidence was not confirmed by its authoritative owner")
        if not reason_ref or not correlation_id or not idempotency_key:
            raise OnboardingError("domain evidence update requires reason, correlation, and idempotency references")
        try:
            uuid.UUID(correlation_id)
            uuid.UUID(event_id)
        except (ValueError, TypeError) as exc:
            raise OnboardingError("event and correlation IDs must be UUIDs") from exc
        digest = hashlib.sha256(json.dumps(domain, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        existing = next((item for item in packet["audit"]
                         if item["idempotency_key"] == idempotency_key), None)
        if existing:
            same_request = (existing["action"] == "resident.onboarding.domain.record"
                            and existing["domain_id"] == domain_id
                            and existing["payload_digest"] == digest
                            and existing["expected_revision"] == expected_revision
                            and existing["actor_ref"] == actor.principal_ref
                            and existing["correlation_id"] == correlation_id
                            and existing["reason_ref"] == reason_ref)
            if same_request:
                return packet
            raise OnboardingIdempotencyConflict("domain evidence idempotency key conflicts with stored request")
        successor = deepcopy(packet)
        successor["domains"][domain_id] = deepcopy(domain)
        if domain_id == "identity" and domain["status"] == "verified":
            resident_id = verified.get("resident_id") if isinstance(verified, dict) else None
            if (not isinstance(resident_id, str) or not resident_id.startswith("r3:")
                    or packet["resident_id"] not in (None, resident_id)):
                raise OnboardingError("HR evidence validator did not return the canonical resident ID")
            successor["resident_id"] = resident_id
        successor["packet_revision"] = expected_revision + 1
        successor["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        event = {
            "event_id": event_id, "idempotency_key": idempotency_key,
            "correlation_id": correlation_id, "actor_ref": actor.principal_ref,
            "actor_role": actor.role, "action": "resident.onboarding.domain.record",
            "from_state": packet["state"], "to_state": packet["state"],
            "expected_revision": expected_revision, "occurred_at": successor["updated_at"],
            "reason_ref": reason_ref, "approval_ref": domain.get("approval_ref"),
            "evidence_refs": list(domain.get("evidence_refs", [])),
            "domain_id": domain_id, "payload_digest": digest,
        }
        successor["audit"].append(event)
        validate_packet(successor)
        return await self._store.transition_packet(successor,
            expected_revision=expected_revision, event=event)


def validate_json_schema_and_machine() -> None:
    validate_schema_definition(PACKET_SCHEMA)
    if (STATE_MACHINE["machine_id"] != "resident.onboarding"
            or STATE_MACHINE["machine_version"] != 1
            or set(STATE_MACHINE["transitions"]) - STATES):
        raise OnboardingError("resident onboarding state machine contract is invalid")
    for state, targets in STATE_MACHINE["transitions"].items():
        if any(target not in STATES for target in targets):
            raise OnboardingError(f"invalid target state in {state}")
