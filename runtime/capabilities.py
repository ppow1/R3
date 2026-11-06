# R3 CONTROLLED SOURCE
# File: runtime/capabilities.py
# Component: R3-CAPABILITY-GATEWAY
# File Revision: 1.2.0
# Created: 2026-11-02 UTC (exact time unverified)
# Created By: Unknown (legacy source)
# Purpose: Native R3 capability catalog and invocation using the owning authority decision.
# Execution Model: In-process R3 grant or explicit authoritative-service decision before/with execution.
# Observability: Durable authorization audit records for authorization, completion, denial, and failure.
# Dependencies: runtime.capability_authority; Python standard library.
# Authority: R3-owned capabilities use exact R3 grants; institutional capabilities may consume a named owning service decision.
# Changed: 2026-11-06T01:39:36Z | GRACE-PROPOSAL-P1 | Codex GPT-6 | Add fixed scope and verified caller context for narrow adapters.
# Changed: 2026-11-06T23:06:45Z | GRACE-AUTHORITY-ARCH-001 | Codex GPT-6 | Let an explicitly authoritative institutional service make its own policy decision without a duplicate R3 grant.
# Supersedes: Revision 1.1.0; default R3-grant path remains unchanged.
# Contracts: docs/r3-native-tool-contract.md; docs/architecture/RESIDENT_AUTHORITY_AND_CAPABILITIES.md
# Tests: tests/test_capabilities.py; tests/test_authenticated_tool_routing.py; tests/test_proposal_submission_integration.py
# History/Predecessor: Git blob 1cd64203d00459c45178e73e1a174290c5a769be at cb162499a5ae94b801cbdbf9e5aa2dcd4c75ebaf.
"""R3-owned capability contracts. No R2 imports, services, or database access."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

AUTHORITATIVE_SERVICE_SOURCES = frozenset({
    "riverview.institutional-proposal-registry",
})


class CapabilityDenied(RuntimeError):
    pass


class AuthorizationExpired(CapabilityDenied):
    """A matching exact grant exists, but its approved lifetime has ended."""

    def __init__(self, grant: dict):
        self.grant = dict(grant)
        super().__init__("Exact capability grant expired")


class GrantExpiryMissing(CapabilityDenied):
    """A proposal grant violates the required temporary seven-day term."""

    def __init__(self, grant: dict):
        self.grant = dict(grant)
        super().__init__("Temporary proposal grant has no expiry")


class AuthorityUnavailable(CapabilityDenied):
    pass


class GrantVerifier(Protocol):
    def authorize(
        self, *, principal: str, resource_id: str,
        action: str, operation: str, scope_ref: str
    ) -> dict:
        """Return verified active grant evidence or raise CapabilityDenied."""


@dataclass(frozen=True)
class Capability:
    name: str
    action: str
    description: str
    parameters: dict
    executor: Callable[[dict], object] | None = None
    read_only: bool = False
    resource_ref: str = ""
    scope_ref: str | None = None
    contextual_executor: Callable[[dict, "CapabilityExecutionContext"], object] | None = None
    authorization_mode: str = "r3-grant"
    authority_source: str | None = None


@dataclass(frozen=True)
class CapabilityExecutionContext:
    principal: str
    grant_id: str | None
    action: str
    resource_ref: str
    operation: str
    scope_ref: str
    correlation_id: str
    authority_source: str = "r3-capability-authority"


class CapabilityRegistry:
    def __init__(self, *, principal: str, verifier: GrantVerifier, audit: Callable[[dict], None]):
        if not principal or verifier is None or not callable(getattr(verifier, "authorize", None)):
            raise AuthorityUnavailable("R3 authority verifier required")
        if not callable(audit):
            raise ValueError("Durable audit writer required")
        self.principal = principal
        self.verifier = verifier
        self.audit = audit
        self._capabilities: dict[str, Capability] = {}

    def register(self, capability: Capability) -> None:
        executors = (callable(capability.executor), callable(capability.contextual_executor))
        if (not capability.name or not capability.action
                or sum(executors) != 1):
            raise ValueError("Invalid capability")
        if capability.authorization_mode not in {"r3-grant", "authoritative-service"}:
            raise ValueError("Unsupported capability authorization mode")
        if capability.authorization_mode == "authoritative-service" and (
                capability.contextual_executor is None
                or capability.authority_source not in AUTHORITATIVE_SERVICE_SOURCES):
            raise ValueError("Authoritative-service capability must use a registered decision service")
        if capability.authorization_mode == "r3-grant" and capability.authority_source is not None:
            raise ValueError("R3 grant capabilities cannot declare an alternate authority")
        if capability.name in self._capabilities:
            raise ValueError("Duplicate capability")
        self._capabilities[capability.name] = capability

    def discover(self) -> list[dict]:
        # Discovery is metadata only; it does not grant execution authority.
        return [{"tool": cap.name, "read_only": cap.read_only,
                 "definition": {"type": "function", "function": {
                     "name": cap.name, "description": cap.description,
                     "parameters": cap.parameters}}}
                for cap in self._capabilities.values()]

    def invoke(self, name: str, params: dict, *, correlation_id: str) -> object:
        if not isinstance(params, dict) or not isinstance(name, str):
            raise CapabilityDenied("Invalid invocation")
        cap = self._capabilities.get(name) if isinstance(name, str) else None
        scope = cap.scope_ref if cap is not None and cap.scope_ref else params.get("scope_ref")
        if not isinstance(scope, str) or not scope or not isinstance(correlation_id, str) or not correlation_id:
            raise CapabilityDenied("Scope and correlation required")
        if cap is None:
            raise CapabilityDenied("Unregistered capability")
        if cap.scope_ref and "scope_ref" in params and params["scope_ref"] != cap.scope_ref:
            raise CapabilityDenied("Capability scope does not match its configured scope")
        event = {"principal": self.principal, "capability": name, "action": cap.action,
                 "scope_ref": scope, "correlation_id": correlation_id,
            "resource_ref": cap.resource_ref if cap else None,
            "operation": ("read" if cap.read_only else "write") if cap else None,
            "outcome": "DENIED"}
        evidence = None
        try:
            if not cap.resource_ref:
                raise CapabilityDenied("Capability resource identity required")
            if cap.authorization_mode == "r3-grant":
                evidence = self.verifier.authorize(
                    principal=self.principal,
                    resource_id=cap.resource_ref,
                    action=cap.action,
                    operation="read" if cap.read_only else "write",
                    scope_ref=scope,
                )
                if not isinstance(evidence, dict) or not evidence.get("grant_id"):
                    raise AuthorityUnavailable("Missing grant evidence")
                event["grant_id"] = evidence["grant_id"]
                event["outcome"] = "AUTHORIZED"
                # Fail closed when the durable authorization audit cannot be written.
                self.audit(dict(event))
        except AuthorizationExpired as exc:
            event["grant_id"] = exc.grant.get("grant_id")
            event["outcome"] = "AUTHORIZATION_EXPIRED"
            self.audit(dict(event))
            raise
        except GrantExpiryMissing as exc:
            event["grant_id"] = exc.grant.get("grant_id")
            event["outcome"] = "GRANT_EXPIRY_MISSING"
            self.audit(dict(event))
            raise
        except Exception:
            event["outcome"] = "DENIED"
            self.audit(dict(event))
            raise
        try:
            if cap.contextual_executor is not None:
                result = cap.contextual_executor(
                    params,
                    CapabilityExecutionContext(
                        principal=self.principal,
                        grant_id=evidence["grant_id"] if evidence else None,
                        action=cap.action,
                        resource_ref=cap.resource_ref,
                        operation="read" if cap.read_only else "write",
                        scope_ref=scope,
                        correlation_id=correlation_id,
                        authority_source=(cap.authority_source if evidence is None
                                          else "r3-capability-authority"),
                    ),
                )
            else:
                result = cap.executor(params)
        except CapabilityDenied:
            event["outcome"] = "DENIED"
            self.audit(dict(event))
            raise
        except Exception:
            event["outcome"] = "FAILED"
            self.audit(dict(event))
            raise
        if evidence is None:
            # The named upstream institutional service authorizes and performs
            # this operation atomically; record its successful decision after
            # the authoritative response. No local grant is fabricated.
            event["outcome"] = "AUTHORIZED"
            self.audit(dict(event))
        event["outcome"] = "COMPLETED"
        self.audit(dict(event))
        return {"status": "ok", "authorization": {
            "principal_id": self.principal,
            "grant_id": evidence["grant_id"] if evidence else None,
            "authority_source": (cap.authority_source if evidence is None
                                  else "r3-capability-authority"),
            "action": cap.action, "scope_ref": scope},
            "correlation_id": correlation_id, "result": result}
