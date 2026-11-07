"""
R3 CONTROLLED SOURCE
File: r3a_runtime/engineering.py
Component: R3A-AP2-ENGINEERING-CONTRACTS
File Revision: 1.0.0
Created: 2026-11-07T05:28:24Z
Created By: Codex GPT-6
Purpose: Define AP2 proposal, work-order, operation-reference, action, and independent-verification contracts.
Execution Model: Typed Python data contracts shared by Grace, CME, Engineering providers, and verifier adapters.
Observability: Strict version and field validation; serializable evidence and lineage.
Dependencies: Python standard library; canonical r3a.capability-operation.v1 and r3a.capability-invocation.v1.
Authority: AP2 R3A-011/R3A-012, Issue #43; unified capability decision, Issue #46 comment 6702794200; isolated R3A only.
Changed: 2026-11-07T05:28:24Z | AP2-IMPLEMENTATION | Codex GPT-6 | Add versioned AP2 engineering and verification contracts.
Changed: 2026-11-07T05:45:10Z | AP2-IMPLEMENTATION | Codex GPT-6 | Add verifier requests, digest checks, workspace path validation, and write-target binding.
Changed: 2026-11-07T05:47:16Z | AP2-IMPLEMENTATION | Codex GPT-6 | Align operation and invocation contract identities with the approved v1 pin.
Supersedes: None.
Contracts: r3a.engineering-proposal.v1; r3a.engineering-work-order.v1; r3a.engineering-action.v1; r3a.verification-request.v1; r3a.verification-result.v1; r3a.capability-operation.v1.
Tests: tests/test_r3a_engineering.py.
History/Predecessor: New file; no predecessor.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID


PROPOSAL_CONTRACT_ID = "r3a.engineering-proposal"
WORK_ORDER_CONTRACT_ID = "r3a.engineering-work-order"
ACTION_CONTRACT_ID = "r3a.engineering-action"
VERIFICATION_REQUEST_CONTRACT_ID = "r3a.verification-request"
VERIFICATION_RESULT_CONTRACT_ID = "r3a.verification-result"
CAPABILITY_OPERATION_CONTRACT_ID = "r3a.capability-operation.v1"
CAPABILITY_INVOCATION_CONTRACT_ID = "r3a.capability-invocation.v1"
CONTRACT_VERSION = "1.0.0"
EFFECT_CLASSES = frozenset({"read", "isolated_write", "external_write"})
VERIFICATION_OUTCOMES = frozenset({"PASS", "FAIL", "INCONCLUSIVE"})
_SEMVER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


class EngineeringContractError(ValueError):
    """Raised when a durable AP2 engineering contract is malformed or incompatible."""


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EngineeringContractError(f"{name} must be nonempty text")
    return value.strip()


def _uuid(value: Any, name: str) -> str:
    text = _text(value, name)
    try:
        return str(UUID(text))
    except (ValueError, TypeError, AttributeError) as exc:
        raise EngineeringContractError(f"{name} must be a UUID") from exc


def _timestamp(value: Any, name: str) -> str:
    text = _text(value, name)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EngineeringContractError(f"{name} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise EngineeringContractError(f"{name} must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _version(value: Any, name: str = "contract_version") -> str:
    version = _text(value, name)
    if not _SEMVER.fullmatch(version):
        raise EngineeringContractError(f"{name} must use semantic major.minor.patch form")
    if version.split(".")[0] != "1":
        raise EngineeringContractError(f"unsupported {name} major version")
    return version


def _object(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EngineeringContractError(f"{name} must be an object")
    return value


def _unique_texts(value: Any, name: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise EngineeringContractError(f"{name} must be an array of nonempty strings")
    normalized = tuple(item.strip() for item in value)
    if not allow_empty and not normalized:
        raise EngineeringContractError(f"{name} must not be empty")
    if len(normalized) != len(set(normalized)):
        raise EngineeringContractError(f"{name} values must be unique")
    return normalized


def _criteria(value: Any, name: str) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, (list, tuple)) or not value:
        raise EngineeringContractError(f"{name} must contain at least one structured criterion")
    normalized = []
    seen = set()
    for criterion in value:
        if not isinstance(criterion, dict):
            raise EngineeringContractError(f"{name} entries must be objects")
        criterion_id = _text(criterion.get("criterion_id"), f"{name}.criterion_id")
        if criterion_id in seen:
            raise EngineeringContractError(f"{name} criterion identifiers must be unique")
        seen.add(criterion_id)
        normalized.append(dict(criterion))
    return tuple(normalized)


def _digests(value: Any, name: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    values = _unique_texts(value, name, allow_empty=allow_empty)
    if any(not _DIGEST.fullmatch(item) for item in values):
        raise EngineeringContractError(f"{name} entries must use sha256:<64 lowercase hex> form")
    return values


def _relative_paths(value: Any, name: str) -> tuple[str, ...]:
    paths = _unique_texts(value, name)
    if any(path.startswith("/") or "\\" in path
           or any(part in {"", ".", ".."} for part in path.split("/")) for path in paths):
        raise EngineeringContractError(f"{name} must contain normalized workspace-relative paths")
    return paths


@dataclass(frozen=True)
class CapabilityOperationRef:
    """AP2 reference to the canonical capability operation; not an authorization grant."""

    operation_id: str
    contract_version: str
    effect_class: str
    target: dict[str, Any]
    inputs: dict[str, Any]

    def __post_init__(self) -> None:
        _text(self.operation_id, "operation_id")
        _version(self.contract_version)
        if self.effect_class not in EFFECT_CLASSES:
            raise EngineeringContractError("unsupported capability effect_class")
        _object(self.target, "target")
        _object(self.inputs, "inputs")

    def to_dict(self) -> dict[str, Any]:
        return {"operation_id": self.operation_id, "contract_id": CAPABILITY_OPERATION_CONTRACT_ID,
                "contract_version": self.contract_version, "effect_class": self.effect_class,
                "target": self.target, "inputs": self.inputs}


@dataclass(frozen=True)
class EngineeringProposal:
    proposal_id: str
    proposal_revision: int
    activity_id: str
    attempt_id: str
    correlation_id: str
    resident_id: str
    config_revision: str
    created_at: str
    objective: str
    criteria: tuple[dict[str, Any], ...]
    repository: str
    baseline_ref: str
    scope: dict[str, Any]
    proposed_operations: tuple[CapabilityOperationRef, ...]
    verification_plan: dict[str, Any]
    reasoning_provenance: dict[str, Any]
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        _uuid(self.proposal_id, "proposal_id")
        for key in ("activity_id", "attempt_id", "correlation_id"):
            _uuid(getattr(self, key), key)
        for key in ("resident_id", "config_revision", "objective", "repository", "baseline_ref"):
            _text(getattr(self, key), key)
        _version(self.contract_version)
        if isinstance(self.proposal_revision, bool) or not isinstance(self.proposal_revision, int) or self.proposal_revision < 1:
            raise EngineeringContractError("proposal_revision must be a positive integer")
        _timestamp(self.created_at, "created_at")
        _criteria(self.criteria, "criteria")
        _object(self.scope, "scope")
        if not self.proposed_operations or any(not isinstance(item, CapabilityOperationRef) for item in self.proposed_operations):
            raise EngineeringContractError("proposed_operations must contain typed operation references")
        _object(self.verification_plan, "verification_plan")
        _object(self.reasoning_provenance, "reasoning_provenance")

    def to_dict(self) -> dict[str, Any]:
        return {"contract_id": PROPOSAL_CONTRACT_ID, "contract_version": self.contract_version,
                "proposal_id": self.proposal_id, "proposal_revision": self.proposal_revision,
                "activity_id": self.activity_id, "attempt_id": self.attempt_id,
                "correlation_id": self.correlation_id, "resident_id": self.resident_id,
                "config_revision": self.config_revision, "created_at": self.created_at,
                "objective": self.objective, "criteria": list(self.criteria),
                "repository": self.repository, "baseline_ref": self.baseline_ref,
                "scope": self.scope, "proposed_operations": [op.to_dict() for op in self.proposed_operations],
                "verification_plan": self.verification_plan,
                "reasoning_provenance": self.reasoning_provenance}


@dataclass(frozen=True)
class EngineeringWorkOrder:
    work_order_id: str
    work_order_version: int
    activity_id: str
    attempt_id: str
    correlation_id: str
    proposal_id: str
    proposal_revision: int
    proposal_digest: str
    resident_id: str
    config_revision: str
    repository: str
    baseline_ref: str
    workspace_id: str
    allowed_paths: tuple[str, ...]
    command_profiles: tuple[str, ...]
    operation_refs: tuple[CapabilityOperationRef, ...]
    authorization_decision_id: str
    authorization_provider_id: str
    policy_revision: str | None
    authorization_expires_at: str | None
    criteria: tuple[dict[str, Any], ...]
    issued_at: str
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        for key in ("work_order_id", "activity_id", "attempt_id", "correlation_id", "proposal_id"):
            _uuid(getattr(self, key), key)
        for key in ("proposal_digest", "resident_id", "config_revision", "repository", "baseline_ref",
                    "workspace_id", "authorization_decision_id", "authorization_provider_id"):
            _text(getattr(self, key), key)
        if not _DIGEST.fullmatch(self.proposal_digest):
            raise EngineeringContractError("proposal_digest must use sha256:<64 lowercase hex> form")
        if self.policy_revision is not None:
            _text(self.policy_revision, "policy_revision")
        _version(self.contract_version)
        for key in ("work_order_version", "proposal_revision"):
            value = getattr(self, key)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise EngineeringContractError(f"{key} must be a positive integer")
        issued = datetime.fromisoformat(_timestamp(self.issued_at, "issued_at").replace("Z", "+00:00"))
        if self.authorization_expires_at is not None:
            expiry = datetime.fromisoformat(
                _timestamp(self.authorization_expires_at, "authorization_expires_at").replace("Z", "+00:00"))
            if expiry <= issued:
                raise EngineeringContractError("authorization_expires_at must follow issued_at")
        _relative_paths(self.allowed_paths, "allowed_paths")
        _unique_texts(self.command_profiles, "command_profiles")
        if not self.operation_refs or any(not isinstance(op, CapabilityOperationRef) for op in self.operation_refs):
            raise EngineeringContractError("operation_refs must contain typed canonical operation references")
        for operation in self.operation_refs:
            if operation.effect_class == "isolated_write":
                if operation.target.get("workspace_id") != self.workspace_id:
                    raise EngineeringContractError("isolated-write target must match the authorized workspace")
                if operation.target.get("repository") not in (None, self.repository):
                    raise EngineeringContractError("isolated-write target must match the authorized repository")
                if operation.target.get("baseline_ref") not in (None, self.baseline_ref):
                    raise EngineeringContractError("isolated-write target must match the authorized baseline")
        _criteria(self.criteria, "criteria")

    def to_dict(self) -> dict[str, Any]:
        return {"contract_id": WORK_ORDER_CONTRACT_ID, "contract_version": self.contract_version,
                "work_order_id": self.work_order_id, "work_order_version": self.work_order_version,
                "activity_id": self.activity_id, "attempt_id": self.attempt_id,
                "correlation_id": self.correlation_id, "proposal_id": self.proposal_id,
                "proposal_revision": self.proposal_revision, "proposal_digest": self.proposal_digest,
                "resident_id": self.resident_id, "config_revision": self.config_revision,
                "repository": self.repository, "baseline_ref": self.baseline_ref,
                "workspace_id": self.workspace_id, "allowed_paths": list(self.allowed_paths),
                "command_profiles": list(self.command_profiles),
                "operation_refs": [op.to_dict() for op in self.operation_refs],
                "authorization_decision_id": self.authorization_decision_id,
                "authorization_provider_id": self.authorization_provider_id,
                "policy_revision": self.policy_revision,
                "authorization_expires_at": self.authorization_expires_at,
                "criteria": list(self.criteria), "issued_at": self.issued_at}


@dataclass(frozen=True)
class EngineeringAction:
    action_id: str
    idempotency_key: str
    work_order_id: str
    work_order_version: int
    activity_id: str
    attempt_id: str
    correlation_id: str
    operation: CapabilityOperationRef
    caller_id: str
    authorization_decision_id: str
    requested_at: str
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        for key in ("action_id", "work_order_id", "activity_id", "attempt_id", "correlation_id"):
            _uuid(getattr(self, key), key)
        for key in ("idempotency_key", "caller_id", "authorization_decision_id"):
            _text(getattr(self, key), key)
        _version(self.contract_version)
        if isinstance(self.work_order_version, bool) or not isinstance(self.work_order_version, int) or self.work_order_version < 1:
            raise EngineeringContractError("work_order_version must be a positive integer")
        if not isinstance(self.operation, CapabilityOperationRef):
            raise EngineeringContractError("operation must be a canonical capability reference")
        _timestamp(self.requested_at, "requested_at")

    def to_dict(self) -> dict[str, Any]:
        return {"contract_id": ACTION_CONTRACT_ID, "contract_version": self.contract_version,
                "action_id": self.action_id, "idempotency_key": self.idempotency_key,
                "work_order_id": self.work_order_id, "work_order_version": self.work_order_version,
                "activity_id": self.activity_id, "attempt_id": self.attempt_id,
                "correlation_id": self.correlation_id,
                "invocation_contract_id": CAPABILITY_INVOCATION_CONTRACT_ID,
                "invocation_contract_version": CONTRACT_VERSION,
                "operation": self.operation.to_dict(),
                "caller_id": self.caller_id,
                "authorization_decision_id": self.authorization_decision_id,
                "requested_at": self.requested_at}


VerificationStatus = Literal["PASS", "FAIL", "INCONCLUSIVE"]


@dataclass(frozen=True)
class CriterionResult:
    criterion_id: str
    status: VerificationStatus
    evidence_refs: tuple[str, ...]
    rationale: str

    def __post_init__(self) -> None:
        _text(self.criterion_id, "criterion_id")
        if self.status not in VERIFICATION_OUTCOMES:
            raise EngineeringContractError("criterion status must be PASS, FAIL, or INCONCLUSIVE")
        _unique_texts(self.evidence_refs, "evidence_refs", allow_empty=True)
        if self.status == "PASS" and not self.evidence_refs:
            raise EngineeringContractError("a passing criterion requires inspectable evidence references")
        _text(self.rationale, "rationale")

    def to_dict(self) -> dict[str, Any]:
        return {"criterion_id": self.criterion_id, "status": self.status,
                "evidence_refs": list(self.evidence_refs), "rationale": self.rationale}


@dataclass(frozen=True)
class VerificationRequest:
    verification_id: str
    activity_id: str
    work_order_id: str
    work_order_version: int
    verifier_id: str
    verifier_version: str
    config_revision: str
    criterion_ids: tuple[str, ...]
    artifact_digests: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    requested_at: str
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        for key in ("verification_id", "activity_id", "work_order_id"):
            _uuid(getattr(self, key), key)
        for key in ("verifier_id", "config_revision"):
            _text(getattr(self, key), key)
        _version(self.verifier_version, "verifier_version")
        _version(self.contract_version)
        if isinstance(self.work_order_version, bool) or not isinstance(self.work_order_version, int) or self.work_order_version < 1:
            raise EngineeringContractError("work_order_version must be a positive integer")
        _unique_texts(self.criterion_ids, "criterion_ids")
        _digests(self.artifact_digests, "artifact_digests", allow_empty=True)
        _unique_texts(self.evidence_refs, "evidence_refs")
        _timestamp(self.requested_at, "requested_at")

    def to_dict(self) -> dict[str, Any]:
        return {"contract_id": VERIFICATION_REQUEST_CONTRACT_ID,
                "contract_version": self.contract_version,
                "verification_id": self.verification_id, "activity_id": self.activity_id,
                "work_order_id": self.work_order_id,
                "work_order_version": self.work_order_version, "verifier_id": self.verifier_id,
                "verifier_version": self.verifier_version, "config_revision": self.config_revision,
                "criterion_ids": list(self.criterion_ids),
                "artifact_digests": list(self.artifact_digests),
                "evidence_refs": list(self.evidence_refs), "requested_at": self.requested_at}


@dataclass(frozen=True)
class VerificationResult:
    verification_id: str
    activity_id: str
    work_order_id: str
    work_order_version: int
    verifier_id: str
    verifier_version: str
    policy_revision: str
    artifact_digests: tuple[str, ...]
    results: tuple[CriterionResult, ...]
    verified_at: str
    outcome: VerificationStatus
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        for key in ("verification_id", "activity_id", "work_order_id"):
            _uuid(getattr(self, key), key)
        for key in ("verifier_id", "policy_revision"):
            _text(getattr(self, key), key)
        _version(self.verifier_version, "verifier_version")
        _version(self.contract_version)
        if isinstance(self.work_order_version, bool) or not isinstance(self.work_order_version, int) or self.work_order_version < 1:
            raise EngineeringContractError("work_order_version must be a positive integer")
        _digests(self.artifact_digests, "artifact_digests", allow_empty=True)
        if not self.results or any(not isinstance(item, CriterionResult) for item in self.results):
            raise EngineeringContractError("results must contain criterion results")
        if len({item.criterion_id for item in self.results}) != len(self.results):
            raise EngineeringContractError("criterion results must have unique identifiers")
        _timestamp(self.verified_at, "verified_at")
        if self.outcome not in VERIFICATION_OUTCOMES:
            raise EngineeringContractError("verification outcome must be PASS, FAIL, or INCONCLUSIVE")
        derived = ("PASS" if all(item.status == "PASS" for item in self.results)
                   else "FAIL" if any(item.status == "FAIL" for item in self.results)
                   else "INCONCLUSIVE")
        if self.outcome != derived:
            raise EngineeringContractError("overall outcome must match criterion results")

    def to_dict(self) -> dict[str, Any]:
        return {"contract_id": VERIFICATION_RESULT_CONTRACT_ID,
                "contract_version": self.contract_version,
                "verification_id": self.verification_id, "activity_id": self.activity_id,
                "work_order_id": self.work_order_id,
                "work_order_version": self.work_order_version, "verifier_id": self.verifier_id,
                "verifier_version": self.verifier_version, "policy_revision": self.policy_revision,
                "artifact_digests": list(self.artifact_digests),
                "results": [result.to_dict() for result in self.results],
                "verified_at": self.verified_at, "outcome": self.outcome}


def validate_completion(work_order: EngineeringWorkOrder, result: VerificationResult) -> None:
    """Raise unless an independent PASS covers this exact order and every required criterion."""
    if result.activity_id != work_order.activity_id or result.work_order_id != work_order.work_order_id:
        raise EngineeringContractError("verification result lineage does not match work order")
    if result.work_order_version != work_order.work_order_version:
        raise EngineeringContractError("verification result references a different work-order version")
    required = {str(item.get("criterion_id", "")) for item in work_order.criteria}
    observed = {item.criterion_id for item in result.results}
    if not required or observed != required:
        raise EngineeringContractError("verification result must cover exactly the work-order criteria")
    if result.outcome != "PASS":
        raise EngineeringContractError("activity completion requires independent verification PASS")
