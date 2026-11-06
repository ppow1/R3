# R3 CONTROLLED SOURCE
# File: runtime/capabilities.py
# Component: R3-CAPABILITY-GATEWAY
# File Revision: 1.1.0
# Created: 2026-11-02 UTC (exact time unverified)
# Created By: Unknown (legacy source)
# Purpose: Native R3 capability catalog and fail-closed invocation with verified execution context.
# Execution Model: In-process exact-grant authorization before synchronous capability execution.
# Observability: Durable authorization audit records for authorization, completion, and failure.
# Dependencies: runtime.capability_authority; Python standard library.
# Authority: R3 canonical capability grant contract; no automatic grant creation.
# Changed: 2026-11-06T01:39:36Z | GRACE-PROPOSAL-P1 | Codex GPT-6 | Add fixed scope and verified caller context for narrow adapters.
# Supersedes: Revision 1.0.0; extends callbacks without changing existing capability grants.
# Contracts: docs/r3-native-tool-contract.md
# Tests: tests/test_capabilities.py; tests/test_authenticated_tool_routing.py; tests/test_proposal_submission_integration.py
# History/Predecessor: Git blob 709e8e23a53292c64e37d43f06f04f1d46d98a85
"""R3-owned capability contracts. No R2 imports, services, or database access."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol


class CapabilityDenied(RuntimeError):
    pass


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


@dataclass(frozen=True)
class CapabilityExecutionContext:
    principal: str
    grant_id: str
    action: str
    resource_ref: str
    operation: str
    scope_ref: str
    correlation_id: str


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
        try:
            if not cap.resource_ref:
                raise CapabilityDenied("Capability resource identity required")
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
                        grant_id=evidence["grant_id"],
                        action=cap.action,
                        resource_ref=cap.resource_ref,
                        operation="read" if cap.read_only else "write",
                        scope_ref=scope,
                        correlation_id=correlation_id,
                    ),
                )
            else:
                result = cap.executor(params)
        except Exception:
            event["outcome"] = "FAILED"
            self.audit(dict(event))
            raise
        event["outcome"] = "COMPLETED"
        self.audit(dict(event))
        return {"status": "ok", "authorization": {
            "principal_id": self.principal, "grant_id": evidence["grant_id"],
            "action": cap.action, "scope_ref": scope},
            "correlation_id": correlation_id, "result": result}
