"""
R3 CONTROLLED SOURCE
File: r3a_runtime/authorization.py
Component: R3A-AUTHORIZATION-PROVIDER-PORT
File Revision: 1.0.0
Created: 2026-11-06T23:19:46Z
Created By: Codex GPT-6
Purpose: Isolate institutional authorization decisions behind a replaceable versioned provider interface.
Execution Model: Async provider protocol and in-process provider registry.
Observability: Typed decisions and existing capability-grant audit events.
Dependencies: Python 3.12 standard library; r3a_runtime.contracts; Store-compatible persistence interface.
Authority: R3A AP0/AP1 Modular Autonomy Implementation Slice 1; existing capability grants remain authoritative.
Changed: 2026-11-06T23:19:46Z | R3A-AP1-SLICE-1 | Codex GPT-6 | Introduce pluggable authorization provider protocol and grant-backed implementation.
Changed: 2026-11-06T23:43:25Z | R3A-AP1-SLICE-1 | Codex GPT-6 | Validate authorization envelopes and preserve scope/policy/audit provenance across providers.
Supersedes: None.
Contracts: AP0-008/010; MOD-006; R3A-019.
Tests: tests/test_r3a_modular_autonomy.py.
History/Predecessor: New file; initial publication recorded in Git.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Protocol

from .contracts import (AUTHORIZATION_CONTRACT_ID, AUTHORIZATION_CONTRACT_VERSION,
                        ContractValidationError, parse_timestamp)


@dataclass(frozen=True)
class AuthorizationRequest:
    contract_id: str
    contract_version: str
    request_id: str
    correlation_id: str
    resident_id: str
    capability_id: str
    activity_id: str | None
    attempt_id: str | None
    config_revision: str
    created_at: str
    context: dict[str, Any]
    resource_scope: dict[str, Any] | None = None
    conditions: dict[str, Any] | None = None
    delegation_ref: str | None = None
    approval_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.contract_id != AUTHORIZATION_CONTRACT_ID:
            raise ContractValidationError("authorization contract identity mismatch")
        _validate_major(self.contract_version, "authorization request")
        for field in ("request_id", "correlation_id", "resident_id", "capability_id", "config_revision"):
            if not isinstance(getattr(self, field), str) or not getattr(self, field).strip():
                raise ContractValidationError(f"{field} must be nonempty text")
        parse_timestamp(self.created_at, "created_at")
        if not isinstance(self.context, dict):
            raise ContractValidationError("context must be an object")
        if self.resource_scope is not None and not isinstance(self.resource_scope, dict):
            raise ContractValidationError("resource_scope must be an object")
        if self.conditions is not None and not isinstance(self.conditions, dict):
            raise ContractValidationError("conditions must be an object")
        if not isinstance(self.approval_refs, tuple):
            raise ContractValidationError("approval_refs must be a tuple")


@dataclass(frozen=True)
class AuthorizationDecision:
    contract_id: str
    contract_version: str
    provider_id: str
    allowed: bool
    reason: str
    retryable: bool
    policy_revision: str | None
    config_revision: str
    observed_at: str
    correlation_id: str
    activity_id: str | None = None
    attempt_id: str | None = None
    audit_event_id: str | None = None

    def __post_init__(self) -> None:
        if self.contract_id != AUTHORIZATION_CONTRACT_ID:
            raise ContractValidationError("authorization decision contract identity mismatch")
        _validate_major(self.contract_version, "authorization decision")
        if not isinstance(self.allowed, bool) or not isinstance(self.retryable, bool):
            raise ContractValidationError("authorization decision flags must be boolean")
        parse_timestamp(self.observed_at, "observed_at")
        if not self.reason:
            raise ContractValidationError("authorization decision requires a reason")


def _validate_major(version: str, label: str) -> None:
    if not isinstance(version, str):
        raise ContractValidationError(f"{label} contract version must be text")
    parts = version.split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts) or parts[0] != "1":
        raise ContractValidationError(f"unsupported {label} contract version")


class AuthorizationProvider(Protocol):
    provider_id: str
    contract_version: str

    async def authorize(self, request: AuthorizationRequest) -> AuthorizationDecision:
        """Evaluate and audit a request; residents cannot submit decisions."""


class CapabilityGrantAuthorizationProvider:
    """Compatibility adapter preserving the AP0 capability-grant enforcement behavior."""

    provider_id = "capability_grants"
    contract_version = AUTHORIZATION_CONTRACT_VERSION

    def __init__(self, store: Any, config_revision: str):
        self.store = store
        self.config_revision = config_revision

    async def authorize(self, request: AuthorizationRequest) -> AuthorizationDecision:
        if request.contract_id != AUTHORIZATION_CONTRACT_ID:
            raise ValueError("authorization contract identity mismatch")
        if request.contract_version.split(".", 1)[0] != "1":
            raise ValueError("unsupported authorization contract major version")
        result = "allowed"
        reason = "active capability grant"
        unsupported_scope = bool(request.resource_scope or request.conditions or
                                 request.delegation_ref or request.approval_refs)
        try:
            if unsupported_scope:
                raise PermissionError("configured capability-grant provider cannot evaluate scoped or delegated authority")
            await self.store.require_capability(request.resident_id, request.capability_id)
            allowed = True
        except PermissionError as exc:
            allowed = False
            result = "denied"
            reason = str(exc)
        details = dict(request.context)
        details.update({"authorization_provider": self.provider_id,
                        "authorization_contract": request.contract_id,
                        "authorization_contract_version": request.contract_version,
                        "config_revision": request.config_revision})
        if request.activity_id is not None:
            details.setdefault("activity_id", request.activity_id)
        details.setdefault("request_id", request.request_id)
        audit_id = await self.store.audit_capability_invocation(
            request.resident_id, request.capability_id, result, details)
        return AuthorizationDecision(AUTHORIZATION_CONTRACT_ID, AUTHORIZATION_CONTRACT_VERSION,
                                     self.provider_id, allowed, reason, False,
                                     None, request.config_revision,
                                     datetime.now(timezone.utc).isoformat(), request.correlation_id,
                                     request.activity_id, request.attempt_id,
                                     str(audit_id) if audit_id else None)


_PROVIDER_FACTORIES: dict[str, Callable[[Any, dict[str, Any], str], AuthorizationProvider]] = {}


def register_authorization_provider(
        provider_id: str,
        factory: Callable[[Any, dict[str, Any], str], AuthorizationProvider], *,
        replace: bool = False) -> None:
    """Register a provider during host composition; registration does not grant authority."""
    if not isinstance(provider_id, str) or not provider_id.strip():
        raise ValueError("provider_id must be nonempty text")
    if provider_id in _PROVIDER_FACTORIES and not replace:
        raise ValueError(f"authorization provider already registered: {provider_id}")
    _PROVIDER_FACTORIES[provider_id] = factory


def _grant_provider_factory(store: Any, options: dict[str, Any], config_revision: str) -> AuthorizationProvider:
    if options:
        raise ValueError("capability_grants provider does not accept provider-specific options")
    return CapabilityGrantAuthorizationProvider(store, config_revision)


register_authorization_provider("capability_grants", _grant_provider_factory)


def create_authorization_provider(provider_id: str, options: dict[str, Any],
                                  config_revision: str, store: Any) -> AuthorizationProvider:
    factory = _PROVIDER_FACTORIES.get(provider_id)
    if factory is None:
        raise ValueError(f"authorization provider is not registered: {provider_id}")
    provider = factory(store, options, config_revision)
    if provider.contract_version.split(".", 1)[0] != "1":
        raise ValueError("authorization provider contract major version is incompatible")
    if provider.provider_id != provider_id:
        raise ValueError("authorization provider identity does not match configured provider")
    return provider
