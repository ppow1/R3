# R3 CONTROLLED SOURCE
# File: runtime/governed_tools.py
# Component: R3-GRACE-GOVERNED-EXECUTION
# File Revision: 1.0.0
# Created: 2026-11-04 UTC (date precision only)
# Created By: ChatGPT GPT-6
# Purpose: Authenticated, server-enforced resident tool execution using the ONE shared R3 authority verifier.
# Execution Model: Explicitly injected gateway; never automatically provisions authority or starts a service.
# Observability: Durable canonical authority audit plus execution-attempt ledger for non-replay.
# Dependencies: Python stdlib; Website-owned R3 identity resolver and canonical grant verifier.
# Authority: Steward unified R3 integration directive; no R2 imports or implicit grants.
# Changed: 2026-11-04 UTC | R3-GRACE-AUTH-001 | Add resident execution enforcement and uncertain-write protection.
# Supersedes: None
# Contracts: docs/r3-native-tool-contract.md; GitHub issues #16 and #28.
# Tests: tests/test_governed_tools.py
# History/Predecessor: New module on engineering/grace-native-capabilities-20261104.
"""R3 governed resident execution. Discovery does not authorize execution.

Website owns the canonical grant store, Steward administration and credential
validation. The injected verifier and identity resolver MUST be production
implementations of that same contract; this module never creates grant rows.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import sqlite3
import threading
import time
from typing import Callable, Protocol

from runtime.capabilities import AuthorityUnavailable, CapabilityDenied


class ResidentIdentityResolver(Protocol):
    def __call__(self, bearer_token: str) -> str:
        """Validate a resident credential and return trusted resident principal."""


class CanonicalGrantVerifier(Protocol):
    def authorize(self, *, principal: str, resource_id: str, action: str,
                  operation: str, scope_ref: str) -> dict:
        """Verify exactly one effective canonical R3 grant; return its grant_id."""


@dataclass(frozen=True)
class GovernedCapability:
    name: str
    resource_id: str
    action: str
    operation: str
    description: str
    parameters: dict
    executor: Callable[[dict], object]

    def __post_init__(self):
        if not all(isinstance(value, str) and value for value in
                   (self.name, self.resource_id, self.action)):
            raise ValueError("Capability identity, resource and action required")
        if self.operation not in ("read", "write"):
            raise ValueError("Operation must be independently grantable read or write")
        if not isinstance(self.parameters, dict) or not callable(self.executor):
            raise ValueError("Invalid capability schema or executor")


class UncertainWrite(RuntimeError):
    """Write was dispatched or reserved; never automatically replay."""


class ExecutionAttemptLedger:
    """Execution-only idempotency record, NOT an authority/grant store.

    A write attempt is reserved durably before dispatch. Missing/uncertain
    outcomes are never retried with the same correlation ID.
    """

    def __init__(self, connection: sqlite3.Connection, lock: threading.Lock):
        self.connection = connection
        self.lock = lock
        with self.lock:
            self.connection.execute("""CREATE TABLE IF NOT EXISTS governed_write_attempts (
                principal TEXT NOT NULL, correlation_id TEXT NOT NULL,
                capability TEXT NOT NULL, request_hash TEXT NOT NULL,
                state TEXT NOT NULL, created_at REAL NOT NULL,
                PRIMARY KEY (principal, correlation_id))""")
            self.connection.commit()

    def reserve(self, *, principal: str, correlation_id: str,
                capability: str, parameters: dict) -> None:
        digest = hashlib.sha256(json.dumps(
            [capability, parameters], sort_keys=True, separators=(",", ":")
        ).encode("utf-8")).hexdigest()
        with self.lock:
            try:
                self.connection.execute(
                    """INSERT INTO governed_write_attempts
                       (principal, correlation_id, capability, request_hash, state, created_at)
                       VALUES (?,?,?,?,?,?)""",
                    (principal, correlation_id, capability, digest, "RESERVED", time.time()))
                self.connection.commit()
            except sqlite3.IntegrityError as exc:
                raise UncertainWrite("Prior write attempt exists; no automatic replay") from exc
            except sqlite3.Error as exc:
                raise AuthorityUnavailable("Write-attempt journal unavailable") from exc

    def outcome(self, *, principal: str, correlation_id: str, state: str) -> None:
        if state not in ("COMPLETED", "UNCERTAIN"):
            raise ValueError("Invalid write outcome")
        with self.lock:
            try:
                self.connection.execute(
                    "UPDATE governed_write_attempts SET state=? WHERE principal=? AND correlation_id=?",
                    (state, principal, correlation_id))
                self.connection.commit()
            except sqlite3.Error as exc:
                raise AuthorityUnavailable("Write-outcome journal unavailable") from exc


class GovernedToolGateway:
    """Executed ONLY by the server after validating an independent resident credential."""

    def __init__(self, *, identity_resolver: ResidentIdentityResolver,
                 verifier: CanonicalGrantVerifier,
                 audit: Callable[[dict], None],
                 write_ledger: ExecutionAttemptLedger):
        if not callable(identity_resolver) or not callable(getattr(verifier, "authorize", None)):
            raise AuthorityUnavailable("Trusted identity resolver and canonical verifier required")
        if not callable(audit) or write_ledger is None:
            raise AuthorityUnavailable("Durable authorization audit and write ledger required")
        self.identity_resolver = identity_resolver
        self.verifier = verifier
        self.audit = audit
        self.write_ledger = write_ledger
        self._capabilities: dict[str, GovernedCapability] = {}

    def register(self, capability: GovernedCapability) -> None:
        if capability.name in self._capabilities:
            raise ValueError("Duplicate capability")
        self._capabilities[capability.name] = capability

    def contains(self, name: str) -> bool:
        return name in self._capabilities

    def discover(self) -> list[dict]:
        return [{"tool": c.name, "read_only": c.operation == "read",
                 "resource_id": c.resource_id, "operation": c.operation,
                 "definition": {"type": "function", "function": {
                     "name": c.name, "description": c.description,
                     "parameters": c.parameters}}}
                for c in self._capabilities.values()]

    def invoke(self, payload: dict, *, authorization: str | None) -> object:
        if not isinstance(payload, dict) or (
                set(payload) != {"tool", "params", "correlation_id"}):
            raise CapabilityDenied("Invalid governed invocation envelope")
        name, params, correlation_id = (
            payload["tool"], payload["params"], payload["correlation_id"])
        if not isinstance(name, str) or not isinstance(params, dict):
            raise CapabilityDenied("Invalid capability or parameters")
        capability = self._capabilities.get(name)
        if capability is None:
            raise CapabilityDenied("Unregistered capability")
        if not isinstance(correlation_id, str) or not correlation_id or len(correlation_id) > 200:
            raise CapabilityDenied("Durable correlation ID required")
        scope = params.get("scope_ref")
        if not isinstance(scope, str) or not scope:
            raise CapabilityDenied("Exact scope_ref required")
        if not isinstance(authorization, str) or not authorization.startswith("Bearer "):
            raise CapabilityDenied("Resident credential required")
        token = authorization[len("Bearer "):]
        if not token or token != token.strip():
            raise CapabilityDenied("Malformed resident credential")
        # Never accept a client-provided principal, role, grant or permission.
        principal = self.identity_resolver(token)
        if not isinstance(principal, str) or not principal.startswith("resident:") or len(principal) <= len("resident:"):
            raise CapabilityDenied("Authenticated R3 resident identity required")
        event = {"principal": principal, "capability": name,
                 "resource_id": capability.resource_id, "action": capability.action,
                 "operation": capability.operation, "scope_ref": scope,
                 "correlation_id": correlation_id, "outcome": "DENIED"}
        try:
            evidence = self.verifier.authorize(
                principal=principal, resource_id=capability.resource_id,
                action=capability.action, operation=capability.operation,
                scope_ref=scope)
            if not isinstance(evidence, dict) or not (
                    isinstance(evidence.get("grant_id"), str) and evidence["grant_id"]):
                raise AuthorityUnavailable("Canonical grant evidence required")
            event["grant_id"] = evidence["grant_id"]
            event["outcome"] = "AUTHORIZED"
            # Denial by audit storage must prevent executing any operation.
            self.audit(dict(event))
        except Exception:
            event["outcome"] = "DENIED"
            self.audit(dict(event))
            raise

        if capability.operation == "write":
            self.write_ledger.reserve(
                principal=principal, correlation_id=correlation_id,
                capability=name, parameters=params)
        try:
            result = capability.executor(params)
            event["outcome"] = "COMPLETED"
            self.audit(dict(event))
        except Exception:
            event["outcome"] = "UNCERTAIN" if capability.operation == "write" else "FAILED"
            try:
                self.audit(dict(event))
            finally:
                if capability.operation == "write":
                    self.write_ledger.outcome(
                        principal=principal, correlation_id=correlation_id,
                        state="UNCERTAIN")
            raise
        if capability.operation == "write":
            self.write_ledger.outcome(
                principal=principal, correlation_id=correlation_id,
                state="COMPLETED")
        return {"status": "ok", "authorization": {
            "principal_id": principal, "grant_id": evidence["grant_id"],
            "resource_id": capability.resource_id, "action": capability.action,
            "operation": capability.operation, "scope_ref": scope},
            "correlation_id": correlation_id, "result": result}
