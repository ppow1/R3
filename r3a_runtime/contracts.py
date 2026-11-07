"""
R3 CONTROLLED SOURCE
File: r3a_runtime/contracts.py
Component: R3A-VERSIONED-AUTONOMY-CONTRACTS
File Revision: 1.1.0
Created: 2026-11-06T23:19:46Z
Created By: Codex GPT-6
Purpose: Define versioned resident execution, model-role, readiness, routing, and authorization envelopes.
Execution Model: Typed Python contracts shared by CME and replaceable providers.
Observability: Validated identifiers, revisions, timestamps, readiness freshness, and typed route outcomes.
Dependencies: Python 3.12 standard library.
Authority: R3A AP0/AP1 Modular Autonomy Implementation Slices 1–2; isolated development branch only.
Changed: 2026-11-06T23:19:46Z | R3A-AP1-SLICE-1 | Codex GPT-6 | Add typed versioned contracts and configurable role selection semantics.
Changed: 2026-11-06T23:43:25Z | R3A-AP1-SLICE-1 | Codex GPT-6 | Add typed contract outcomes, provider-backed readiness evidence, and freshness-aware role selection.
Changed: 2026-11-07T00:20:59Z | R3A-AP1-SLICE-2 | Codex GPT-6 | Version provider-backed readiness as v2 with identity evidence and fail-closed freshness routing.
Supersedes: None.
Contracts: AP0-003–010; R3A-019; MOD-006; STM-003/005/006; r3a.model-readiness.v2; r3a.model-readiness-provider.v1.
Tests: tests/test_r3a_modular_autonomy.py.
History/Predecessor: Git blob ae768c8823cb8a56f82b2e879c7619932b884952 at commit ad16700f1e94dd36c81cac5383f9f2e2771a98a1.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID


CONTRACT_ENVELOPE_ID = "r3a.contract-envelope"
CONTRACT_ENVELOPE_VERSION = "1.0.0"
MODEL_ROLE_CONTRACT_ID = "r3a.model-role"
MODEL_ROLE_CONTRACT_VERSION = "1.0.0"
READINESS_CONTRACT_ID = "r3a.model-readiness"
READINESS_CONTRACT_VERSION = "2.0.0"
READINESS_REFRESH_CONTRACT_ID = "r3a.model-readiness-refresh"
READINESS_REFRESH_CONTRACT_VERSION = "1.0.0"
ROUTE_CONTRACT_ID = "r3a.model-route-decision"
ROUTE_CONTRACT_VERSION = "1.0.0"
AUTHORIZATION_CONTRACT_ID = "r3a.authorization-decision"
AUTHORIZATION_CONTRACT_VERSION = "1.0.0"

ReadinessStatus = Literal["ready", "degraded", "unavailable", "stale", "unknown"]
RouteAction = Literal["route", "defer", "block"]


class ContractValidationError(ValueError):
    """A versioned contract envelope or observation is malformed or incompatible."""


def _required_text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractValidationError(f"{name} must be nonempty text")
    return value


def parse_timestamp(value: Any, name: str = "timestamp") -> datetime:
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, str):
        try:
            result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ContractValidationError(f"{name} must be an ISO-8601 timestamp") from exc
    else:
        raise ContractValidationError(f"{name} must be an ISO-8601 timestamp")
    if result.tzinfo is None:
        raise ContractValidationError(f"{name} must include a timezone")
    return result.astimezone(timezone.utc)


@dataclass(frozen=True)
class ContractEnvelope:
    contract_id: str
    contract_version: str
    request_id: str
    activity_id: str
    attempt_id: str
    correlation_id: str
    resident_id: str
    config_revision: str
    created_at: str
    payload: dict[str, Any]

    def __post_init__(self) -> None:
        for field in ("contract_id", "contract_version", "request_id", "activity_id",
                      "attempt_id", "correlation_id", "resident_id", "config_revision"):
            _required_text(getattr(self, field), field)
        parse_timestamp(self.created_at, "created_at")
        if not isinstance(self.payload, dict):
            raise ContractValidationError("payload must be an object")

    def to_dict(self) -> dict[str, Any]:
        return {"contract_id": self.contract_id, "contract_version": self.contract_version,
                "request_id": self.request_id, "activity_id": self.activity_id,
                "attempt_id": self.attempt_id, "correlation_id": self.correlation_id,
                "resident_id": self.resident_id, "config_revision": self.config_revision,
                "created_at": self.created_at, "payload": self.payload}

    @classmethod
    def from_dict(cls, value: Any, *, expected_contract: str | None = None,
                  supported_major: int = 1) -> "ContractEnvelope":
        if not isinstance(value, dict):
            raise ContractValidationError("contract envelope must be an object")
        required = {"contract_id", "contract_version", "request_id", "activity_id", "attempt_id",
                    "correlation_id", "resident_id", "config_revision", "created_at", "payload"}
        if set(value) != required:
            raise ContractValidationError("contract envelope fields do not match the v1 contract")
        contract_id = _required_text(value["contract_id"], "contract_id")
        version = _required_text(value["contract_version"], "contract_version")
        if expected_contract and contract_id != expected_contract:
            raise ContractValidationError("contract identity mismatch")
        pieces = version.split(".")
        if len(pieces) != 3 or not all(part.isdigit() for part in pieces):
            raise ContractValidationError("contract_version must use semantic major.minor.patch form")
        if int(pieces[0]) != supported_major:
            raise ContractValidationError("unsupported contract major version")
        return cls(contract_id, version, value["request_id"], value["activity_id"], value["attempt_id"],
                   value["correlation_id"], value["resident_id"], value["config_revision"],
                   value["created_at"], value["payload"])


@dataclass(frozen=True)
class ContractOutcome:
    contract_id: str
    contract_version: str
    request_id: str
    correlation_id: str
    resident_id: str
    config_revision: str
    observed_at: str
    outcome: Literal["succeeded", "failed", "deferred", "blocked"]
    retryable: bool
    result: dict[str, Any] | None = None
    reason_code: str | None = None
    retry_after_seconds: float | None = None
    error: dict[str, Any] | None = None
    activity_id: str | None = None
    attempt_id: str | None = None

    def __post_init__(self) -> None:
        for field in ("contract_id", "contract_version", "request_id", "correlation_id",
                      "resident_id", "config_revision"):
            _required_text(getattr(self, field), field)
        parse_timestamp(self.observed_at, "observed_at")
        version = self.contract_version.split(".")
        if len(version) != 3 or not all(part.isdigit() for part in version) or version[0] != "1":
            raise ContractValidationError("unsupported outcome contract version")
        if self.outcome not in {"succeeded", "failed", "deferred", "blocked"}:
            raise ContractValidationError("unsupported contract outcome")
        if not isinstance(self.retryable, bool):
            raise ContractValidationError("retryable must be boolean")
        if self.result is not None and not isinstance(self.result, dict):
            raise ContractValidationError("result must be an object")
        if self.error is not None and not isinstance(self.error, dict):
            raise ContractValidationError("error must be an object")
        if self.outcome == "succeeded" and (self.result is None or self.error is not None):
            raise ContractValidationError("succeeded outcome requires result and forbids error")
        if self.outcome in {"failed", "blocked"} and (self.error is None or self.result is not None):
            raise ContractValidationError("failed/blocked outcome requires error and forbids result")
        if self.outcome == "deferred":
            if not self.retryable or not self.reason_code or self.result is not None:
                raise ContractValidationError("deferred outcome requires retryable reason and no result")
            if self.retry_after_seconds is not None and self.retry_after_seconds <= 0:
                raise ContractValidationError("retry_after_seconds must be positive")
        if self.outcome != "deferred" and self.retry_after_seconds is not None:
            raise ContractValidationError("retry_after_seconds is valid only for deferred outcomes")

    def to_dict(self) -> dict[str, Any]:
        return {"contract_id": self.contract_id, "contract_version": self.contract_version,
                "request_id": self.request_id, "correlation_id": self.correlation_id,
                "resident_id": self.resident_id, "config_revision": self.config_revision,
                "observed_at": self.observed_at, "activity_id": self.activity_id,
                "attempt_id": self.attempt_id, "outcome": self.outcome,
                "retryable": self.retryable, "reason_code": self.reason_code,
                "retry_after_seconds": self.retry_after_seconds,
                "result": self.result, "error": self.error}


@dataclass(frozen=True)
class ReadinessObservation:
    resident_id: str
    role_id: str
    model_id: str
    status: ReadinessStatus
    source: str
    observed_at: str
    config_revision: str
    observation_id: str
    reason: str = ""
    evidence_ref: str = ""
    provider_id: str = ""
    evidence: dict[str, Any] | None = None
    contract_id: str = READINESS_CONTRACT_ID
    contract_version: str = READINESS_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for field in ("resident_id", "role_id", "model_id", "source", "config_revision", "observation_id"):
            _required_text(getattr(self, field), field)
        if self.status not in {"ready", "degraded", "unavailable", "stale", "unknown"}:
            raise ContractValidationError("unsupported readiness status")
        if self.contract_id != READINESS_CONTRACT_ID:
            raise ContractValidationError("readiness contract identity mismatch")
        version = self.contract_version.split(".")
        if (len(version) != 3 or not all(part.isdigit() for part in version)
                or version[0] != READINESS_CONTRACT_VERSION.split(".")[0]):
            raise ContractValidationError("unsupported readiness contract version")
        # A host or TCP probe is liveness evidence, not model readiness.
        if self.source not in {"provider_model", "model_protocol"}:
            raise ContractValidationError("readiness source must attest to model/provider protocol readiness")
        parse_timestamp(self.observed_at, "observed_at")
        try:
            UUID(self.observation_id)
        except (ValueError, TypeError) as exc:
            raise ContractValidationError("observation_id must be a UUID") from exc
        if not isinstance(self.reason, str):
            raise ContractValidationError("reason must be text")
        if not isinstance(self.evidence_ref, str):
            raise ContractValidationError("evidence_ref must be text")
        if not isinstance(self.provider_id, str) or not self.provider_id.strip():
            raise ContractValidationError("provider_id must identify the readiness authority")
        if not isinstance(self.evidence, dict):
            raise ContractValidationError("evidence must be an object")
        if not self.evidence_ref.strip() or not self.evidence:
            raise ContractValidationError("readiness outcome requires provider evidence and reference")

    def to_dict(self) -> dict[str, Any]:
        return {"resident_id": self.resident_id, "role_id": self.role_id,
                "model_id": self.model_id, "status": self.status,
                "source": self.source, "observed_at": self.observed_at,
                "config_revision": self.config_revision, "observation_id": self.observation_id,
                "reason": self.reason, "evidence_ref": self.evidence_ref,
                "provider_id": self.provider_id, "evidence": self.evidence,
                "contract_id": self.contract_id,
                "contract_version": self.contract_version}

    @classmethod
    def from_dict(cls, value: Any) -> "ReadinessObservation":
        if not isinstance(value, dict):
            raise ContractValidationError("readiness observation must be an object")
        required = {"resident_id", "role_id", "model_id", "status", "source", "observed_at",
                    "config_revision", "observation_id", "reason", "evidence_ref", "provider_id",
                    "evidence", "contract_id", "contract_version"}
        if set(value) != required:
            raise ContractValidationError("readiness observation fields do not match contract v2")
        return cls(**value)


@dataclass(frozen=True)
class RouteDecision:
    action: RouteAction
    requested_role_id: str
    selected_role_id: str | None
    route_id: str | None
    reason: str
    retryable: bool
    config_revision: str
    readiness_observed_at: str | None = None
    request_id: str | None = None
    activity_id: str | None = None
    attempt_id: str | None = None
    correlation_id: str | None = None
    resident_id: str | None = None
    evaluated_at: str | None = None
    contract_id: str = ROUTE_CONTRACT_ID
    contract_version: str = ROUTE_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_id != ROUTE_CONTRACT_ID:
            raise ContractValidationError("route decision contract identity mismatch")
        version = self.contract_version.split(".")
        if len(version) != 3 or not all(part.isdigit() for part in version) or version[0] != "1":
            raise ContractValidationError("unsupported route decision contract version")
        _required_text(self.requested_role_id, "requested_role_id")
        _required_text(self.reason, "reason")
        _required_text(self.config_revision, "config_revision")
        if self.action not in {"route", "defer", "block"}:
            raise ContractValidationError("unsupported route decision action")
        if not isinstance(self.retryable, bool):
            raise ContractValidationError("retryable must be boolean")
        if self.action == "route" and (not self.selected_role_id or not self.route_id):
            raise ContractValidationError("route outcome requires selected role and route")
        if self.action != "route" and self.route_id is not None:
            raise ContractValidationError("deferred/blocked outcome cannot include a selected route")


def resolve_role(role_registry: tuple[Any, ...], requested_role_id: str,
                 required_capabilities: set[str], observations: dict[str, dict[str, Any]],
                 *, config_revision: str, now: datetime | None = None,
                 permit_fallback: bool = True, request_id: str | None = None,
                 activity_id: str | None = None, attempt_id: str | None = None,
                 correlation_id: str | None = None, resident_id: str | None = None,
                 required_modalities: set[str] | None = None) -> RouteDecision:
    """Resolve only configured roles with required capability and fresh provider readiness."""
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    def decision(action: RouteAction, selected_role_id: str | None, route_id: str | None,
                 reason: str, retryable: bool, readiness_observed_at: str | None = None) -> RouteDecision:
        return RouteDecision(action, requested_role_id, selected_role_id, route_id, reason,
                             retryable, config_revision, readiness_observed_at,
                             request_id, activity_id, attempt_id, correlation_id, resident_id,
                             now.isoformat())
    by_id = {role.role_id: role for role in role_registry}
    requested = by_id.get(requested_role_id)
    if requested is None:
        return decision("block", None, None, "role_not_configured", False)
    candidates = [requested]
    if permit_fallback:
        candidates.extend(by_id[item] for item in requested.fallback_roles if item in by_id)
    reasons: list[str] = []
    capable_candidates = 0
    capability_candidates = 0
    required_modalities = required_modalities or set()
    for role in candidates:
        if not required_capabilities.issubset(set(role.capabilities)):
            reasons.append(f"{role.role_id}:unsupported_capability")
            continue
        capability_candidates += 1
        if not required_modalities.issubset(set(role.modalities)):
            reasons.append(f"{role.role_id}:unsupported_modality")
            continue
        capable_candidates += 1
        observation = observations.get(role.role_id) or {}
        status = observation.get("status", "unknown")
        configured_readiness = getattr(role, "readiness", None)
        expected_provider = (configured_readiness.provider_id
                             if configured_readiness is not None else None)
        observed_at = observation.get("observed_at")
        evidence_valid = (bool(expected_provider)
                          and observation.get("provider_id") == expected_provider
                          and bool(observation.get("evidence_ref"))
                          and isinstance(observation.get("evidence"), dict)
                          and bool(observation.get("evidence")))
        freshness = (observation.get("config_revision") == config_revision and evidence_valid)
        stale = False
        if observed_at:
            try:
                timestamp = parse_timestamp(observed_at, "observed_at")
                age = (now - timestamp).total_seconds()
                freshness = freshness and 0 <= age <= role.readiness_max_age_seconds
                stale = not freshness
            except ContractValidationError:
                freshness = False
        else:
            freshness = False
        if status == "ready" and freshness:
            return decision("route", role.role_id, role.route_id,
                            "requested_role_ready" if role is requested else "configured_fallback_ready",
                            False, str(observed_at))
        if stale:
            status = "stale"
        elif not freshness:
            status = "unknown"
        reasons.append(f"{role.role_id}:{status}")
    if capability_candidates == 0:
        return decision("block", None, None, "unsupported_capability", False)
    if capable_candidates == 0:
        return decision("block", None, None, "unsupported_modality", False)
    reason = ";".join(reasons) or "no_eligible_role"
    action = requested.unavailable_action
    return decision(action, None, None, reason, action == "defer")
