# R3 CONTROLLED SOURCE
# File: runtime/capabilities.py
# Purpose: Native R3 capability catalog and fail-closed invocation.
"""R3-owned capability contracts. No R2 imports, services, or database access."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol


class CapabilityDenied(RuntimeError):
    pass


class AuthorityUnavailable(CapabilityDenied):
    pass


class GrantVerifier(Protocol):
    def authorize(self, *, principal: str, action: str, scope_ref: str) -> dict:
        """Return verified active grant evidence or raise CapabilityDenied."""


@dataclass(frozen=True)
class Capability:
    name: str
    action: str
    description: str
    parameters: dict
    executor: Callable[[dict], object]
    read_only: bool = False


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
        if not capability.name or not capability.action or not callable(capability.executor):
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
        scope = params.get("scope_ref")
        if not isinstance(scope, str) or not scope or not isinstance(correlation_id, str) or not correlation_id:
            raise CapabilityDenied("Scope and correlation required")
        cap = self._capabilities.get(name)
        if cap is None:
            raise CapabilityDenied("Unregistered capability")
        event = {"principal": self.principal, "capability": name, "action": cap.action,
                 "scope_ref": scope, "correlation_id": correlation_id, "outcome": "DENIED"}
        try:
            evidence = self.verifier.authorize(principal=self.principal,
                                               action=cap.action, scope_ref=scope)
            if not isinstance(evidence, dict) or not evidence.get("grant_id"):
                raise AuthorityUnavailable("Missing grant evidence")
            event["grant_id"] = evidence["grant_id"]
            event["outcome"] = "AUTHORIZED"
            # Fail closed when the durable authorization audit cannot be written.
            self.audit(dict(event))
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
