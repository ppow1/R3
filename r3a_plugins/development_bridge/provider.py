"""
R3 CONTROLLED SOURCE
File: r3a_plugins/development_bridge/provider.py
Component: R3A-DEVELOPMENT-BRIDGE-PROVIDER
File Revision: 1.0.0
Created: 2026-11-11T14:16:00Z
Created By: Codex GPT-6
Purpose: Provide contract-validated, side-effect-free dispatch planning and an explicit transport adapter boundary for Bridge v3
Execution Model: CME-supervised capability-provider child process; no polling, database connection, or host transport is enabled here
Observability: Typed route decisions and adapter delivery outcomes; lifecycle/health/events remain CME-owned
Dependencies: r3a_runtime.capability_contracts; configured R3A module/capability contracts
Authority: Step 9 dispatch 6797949457 and Step 10 correction 6797993717; no authority to grant, activate shared runtime, or invoke Windows transport
Changed: 2026-11-11T14:16:00Z | R3-BRIDGE-V3-STEP10 | Codex GPT-6 | Implement source-only router/provider under canonical capability contracts
Supersedes: None
Contracts: r3a.capability-provider.v1; r3a.capability-operation.v1; r3a.module-manifest.v1@1.2.0; module.lifecycle v2; generic CME activity lifecycle
Tests: tests/test_r3a_development_bridge.py
History/Predecessor: None; new file
"""
from __future__ import annotations

from dataclasses import dataclass
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
from typing import Any, Protocol

from r3a_runtime.capability_contracts import CapabilityProviderResult


_MODES = {"QUEUE", "STEER", "PRIORITY"}
_SESSION_STATES = {"AVAILABLE", "BUSY", "UNKNOWN"}
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}$")
_TARGET = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._|:/-]{0,199}$")


@dataclass(frozen=True)
class Dispatch:
    repository: str
    issue_number: int
    comment_id: int
    target: str
    mode: str
    summary: str

    @property
    def idempotency_key(self) -> str:
        material = f"{self.repository}\0{self.issue_number}\0{self.comment_id}".encode("utf-8")
        return "bridge-dispatch:" + hashlib.sha256(material).hexdigest()

    @property
    def source_key(self) -> tuple[str, int, int]:
        return self.repository, self.issue_number, self.comment_id


@dataclass(frozen=True)
class RouteDecision:
    source_key: tuple[str, int, int]
    target: str
    mode: str
    state: str
    reason: str
    idempotency_key: str
    dispatch: Dispatch | None = None
    receipt_ref: str | None = None


@dataclass(frozen=True)
class DeliveryReceipt:
    outcome: str
    receipt_ref: str | None = None
    reason: str | None = None


class IdempotencyConflict(RuntimeError):
    """An existing source identity was replayed with different immutable content."""


class TransportAdapter(Protocol):
    """Host adapter boundary; active-session steer safety must be explicitly proven."""

    supports_safe_steer: bool

    def deliver(self, target: str, dispatch: Dispatch, *, idempotency_key: str) -> DeliveryReceipt:
        """Deliver one authorized dispatch and return confirmed/uncertain/failed evidence."""


class TransportAttemptCache:
    """Subordinate crash-recovery cache for transport attempts, not a registry or event log."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        if not self.path.is_absolute():
            raise ValueError("transport attempt cache path must be absolute")
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5.0, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    @contextmanager
    def _connection(self):
        connection = self._connect()
        try:
            yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version not in {0, 1, 2}:
                raise RuntimeError("transport attempt cache schema version is unsupported")
            connection.execute("""CREATE TABLE IF NOT EXISTS transport_attempts (
                idempotency_key TEXT PRIMARY KEY,
                dispatch_fingerprint TEXT,
                target TEXT NOT NULL,
                mode TEXT NOT NULL,
                state TEXT NOT NULL CHECK (state IN ('ATTEMPTING','DELIVERED','UNCERTAIN','FAILED')),
                receipt_ref TEXT,
                reason TEXT,
                updated_at TEXT NOT NULL
            )""")
            columns = {row[1] for row in connection.execute("PRAGMA table_info(transport_attempts)")}
            if "dispatch_fingerprint" not in columns:
                connection.execute("ALTER TABLE transport_attempts ADD COLUMN dispatch_fingerprint TEXT")
            connection.execute("PRAGMA user_version=2")
        self.path.chmod(0o600)

    def begin(self, decision: RouteDecision) -> tuple[bool, dict[str, Any]]:
        if decision.dispatch is None:
            raise ValueError("delivery attempt lacks its source dispatch")
        dispatch = decision.dispatch
        fingerprint_material = json.dumps({
            "repository": dispatch.repository,
            "issue_number": dispatch.issue_number,
            "comment_id": dispatch.comment_id,
            "target": dispatch.target,
            "mode": dispatch.mode,
            "summary": dispatch.summary,
        }, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        fingerprint = hashlib.sha256(fingerprint_material.encode("utf-8")).hexdigest()
        now = datetime.now(timezone.utc).isoformat()
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM transport_attempts WHERE idempotency_key=?",
                                     (decision.idempotency_key,)).fetchone()
            if row is not None:
                prior = dict(row)
                if prior.get("dispatch_fingerprint") != fingerprint:
                    connection.commit()
                    raise IdempotencyConflict(
                        "source comment idempotency key was replayed with a different dispatch fingerprint")
                if prior["state"] == "ATTEMPTING":
                    reason = "process restarted during transport attempt; reconcile before retry"
                    connection.execute(
                        "UPDATE transport_attempts SET state='UNCERTAIN',reason=?,updated_at=? "
                        "WHERE idempotency_key=? AND state='ATTEMPTING'",
                        (reason, now, decision.idempotency_key))
                    prior.update(state="UNCERTAIN", reason=reason, updated_at=now)
                connection.commit()
                return False, prior
            connection.execute(
                "INSERT INTO transport_attempts "
                "(idempotency_key,dispatch_fingerprint,target,mode,state,updated_at) "
                "VALUES (?,?,?,?,'ATTEMPTING',?)",
                (decision.idempotency_key, fingerprint, decision.target, decision.mode, now))
            connection.commit()
        return True, {"idempotency_key": decision.idempotency_key,
                      "dispatch_fingerprint": fingerprint, "target": decision.target,
                      "mode": decision.mode, "state": "ATTEMPTING", "receipt_ref": None,
                      "reason": None, "updated_at": now}

    def finish(self, key: str, receipt: DeliveryReceipt) -> dict[str, Any]:
        state = {"confirmed": "DELIVERED", "uncertain": "UNCERTAIN", "failed": "FAILED"}.get(receipt.outcome)
        if state is None:
            raise ValueError("transport receipt outcome is invalid")
        if receipt.receipt_ref is not None and (not isinstance(receipt.receipt_ref, str)
                                                or len(receipt.receipt_ref) > 512):
            raise ValueError("transport receipt reference is invalid")
        reason = (receipt.reason or receipt.outcome)[:500]
        now = datetime.now(timezone.utc).isoformat()
        with self._connection() as connection:
            cursor = connection.execute(
                "UPDATE transport_attempts SET state=?,receipt_ref=?,reason=?,updated_at=? "
                "WHERE idempotency_key=? AND state='ATTEMPTING'",
                (state, receipt.receipt_ref, reason, now, key))
            if cursor.rowcount != 1:
                raise RuntimeError("transport attempt is no longer pending")
            row = connection.execute("SELECT * FROM transport_attempts WHERE idempotency_key=?",
                                     (key,)).fetchone()
        assert row is not None
        return dict(row)

    def reconcile(self, key: str, receipt: DeliveryReceipt) -> dict[str, Any]:
        """Apply explicit transport evidence to an uncertain attempt; never resend it."""
        state = {"confirmed": "DELIVERED", "failed": "FAILED"}.get(receipt.outcome)
        if state is None:
            raise ValueError("reconciliation must resolve to confirmed or failed")
        if receipt.receipt_ref is not None and (not isinstance(receipt.receipt_ref, str)
                                                or len(receipt.receipt_ref) > 512):
            raise ValueError("transport receipt reference is invalid")
        now = datetime.now(timezone.utc).isoformat()
        with self._connection() as connection:
            cursor = connection.execute(
                "UPDATE transport_attempts SET state=?,receipt_ref=?,reason=?,updated_at=? "
                "WHERE idempotency_key=? AND state='UNCERTAIN'",
                (state, receipt.receipt_ref, (receipt.reason or "explicitly reconciled")[:500], now, key))
            if cursor.rowcount != 1:
                raise RuntimeError("only an uncertain transport attempt can be reconciled")
            row = connection.execute("SELECT * FROM transport_attempts WHERE idempotency_key=?",
                                     (key,)).fetchone()
        assert row is not None
        return dict(row)

    def get(self, key: str) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM transport_attempts WHERE idempotency_key=?",
                                     (key,)).fetchone()
            return dict(row) if row is not None else None


def _parse_dispatch(value: Any) -> Dispatch:
    required = {"repository", "issue_number", "comment_id", "target", "mode", "summary"}
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError("dispatch must contain exactly the declared source, target, mode, and summary fields")
    repository, target, summary, mode = (value[k] for k in ("repository", "target", "summary", "mode"))
    if not isinstance(repository, str) or not _ID.fullmatch(repository):
        raise ValueError("dispatch repository identity is invalid")
    if not isinstance(target, str) or not _TARGET.fullmatch(target):
        raise ValueError("dispatch target is invalid")
    if not isinstance(summary, str) or not summary.strip() or len(summary) > 500:
        raise ValueError("dispatch summary must contain 1 to 500 characters")
    if not isinstance(mode, str) or mode not in _MODES:
        raise ValueError("dispatch mode is unsupported")
    for field in ("issue_number", "comment_id"):
        if isinstance(value[field], bool) or not isinstance(value[field], int) or value[field] < 1:
            raise ValueError(f"dispatch {field} must be a positive integer")
    return Dispatch(repository, value["issue_number"], value["comment_id"], target, mode, summary.strip())


def route_batch(dispatches: Any, sessions: Any, *, safe_steer_available: bool = False) -> list[RouteDecision]:
    """Plan one scan using explicit targets; make no I/O and persist no parallel state."""
    if not isinstance(dispatches, list) or not isinstance(sessions, list):
        raise ValueError("dispatches and sessions must be arrays")
    target_states: dict[str, str] = {}
    for item in sessions:
        if (not isinstance(item, dict) or set(item) != {"target", "state"}
                or not isinstance(item["target"], str) or not _TARGET.fullmatch(item["target"])
                or not isinstance(item["state"], str) or item["state"] not in _SESSION_STATES):
            raise ValueError("session entry must declare a valid target and observed state")
        if item["target"] in target_states:
            target_states[item["target"]] = "AMBIGUOUS"
        else:
            target_states[item["target"]] = item["state"]

    decisions: list[RouteDecision] = []
    seen: set[tuple[str, int, int]] = set()
    for raw in dispatches:
        dispatch = _parse_dispatch(raw)
        if dispatch.source_key in seen:
            decisions.append(RouteDecision(dispatch.source_key, dispatch.target, dispatch.mode,
                                           "DUPLICATE", "duplicate comment within this poll batch",
                                           dispatch.idempotency_key))
            continue
        seen.add(dispatch.source_key)
        session_state = target_states.get(dispatch.target)
        if session_state is None or session_state == "AMBIGUOUS":
            state, reason = "REJECTED", "target is not uniquely registered"
        elif dispatch.mode == "PRIORITY":
            state, reason = "REVIEW_REQUIRED", "priority dispatch requires an explicit operator decision"
        elif dispatch.mode == "QUEUE":
            state, reason = (("READY", "target is observed available") if session_state == "AVAILABLE"
                             else ("QUEUED", "target is busy or its state is unknown"))
        elif session_state == "BUSY" and safe_steer_available:
            state, reason = "READY", "active target is observed and adapter declares safe steer support"
        elif session_state == "BUSY":
            state, reason = "STEER_PENDING", "active-session delivery requires a transport proven safe for steer"
        else:
            state, reason = "REJECTED", "steer requires an observed active target session"
        decisions.append(RouteDecision(dispatch.source_key, dispatch.target, dispatch.mode,
                                       state, reason, dispatch.idempotency_key, dispatch))
    return decisions


def deliver_ready(decisions: list[RouteDecision], adapter: TransportAdapter | None,
                  cache: TransportAttemptCache) -> list[RouteDecision]:
    """Attempt only READY work; retain uncertain receipts and never retry implicitly."""
    results: list[RouteDecision] = []
    for decision in decisions:
        if decision.state != "READY":
            results.append(decision)
            continue
        if adapter is None or decision.dispatch is None:
            results.append(RouteDecision(decision.source_key, decision.target, decision.mode,
                                         "TRANSPORT_UNAVAILABLE", "no transport adapter is configured",
                                         decision.idempotency_key, decision.dispatch))
            continue
        if decision.mode == "STEER" and not adapter.supports_safe_steer:
            results.append(RouteDecision(decision.source_key, decision.target, decision.mode,
                                        "STEER_PENDING", "adapter has no proven safe steer channel",
                                        decision.idempotency_key, decision.dispatch))
            continue
        try:
            claimed, prior = cache.begin(decision)
        except IdempotencyConflict as exc:
            results.append(RouteDecision(decision.source_key, decision.target, decision.mode,
                                         "IDEMPOTENCY_CONFLICT", str(exc),
                                         decision.idempotency_key, decision.dispatch, None))
            continue
        if not claimed:
            results.append(RouteDecision(decision.source_key, decision.target, decision.mode,
                                         prior["state"], "duplicate suppressed; reconcile prior attempt if uncertain",
                                         decision.idempotency_key, decision.dispatch,
                                         prior.get("receipt_ref")))
            continue
        try:
            receipt = adapter.deliver(decision.target, decision.dispatch,
                                      idempotency_key=decision.idempotency_key)
            if (not isinstance(receipt, DeliveryReceipt)
                    or receipt.outcome not in {"confirmed", "uncertain", "failed"}):
                raise ValueError("transport adapter returned an invalid delivery receipt")
        except Exception as exc:
            receipt = DeliveryReceipt("uncertain", reason=f"adapter raised {type(exc).__name__}; reconcile before retry")
        stored = cache.finish(decision.idempotency_key, receipt)
        results.append(RouteDecision(decision.source_key, decision.target, decision.mode,
                                     stored["state"], stored["reason"], decision.idempotency_key,
                                     decision.dispatch, stored.get("receipt_ref")))
    return results


class DevelopmentBridgeProvider:
    """R3A provider exposing pure route planning; CME owns durable activity and authorization."""

    def __init__(self, configuration: dict[str, Any]):
        if (not isinstance(configuration, dict) or configuration.get("transport") != "unavailable"
                or set(configuration) != {"transport", "transport_state_path_env"}):
            raise ValueError("only the disabled host transport configuration is supported in this source build")
        variable = configuration["transport_state_path_env"]
        if not isinstance(variable, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]*", variable):
            raise ValueError("transport_state_path_env must name an allowlisted environment variable")
        path = os.environ.get(variable)
        if not path:
            raise RuntimeError("transport attempt cache path environment reference is unavailable")
        self.attempt_cache_path = Path(path)
        if not self.attempt_cache_path.is_absolute():
            raise ValueError("transport attempt cache path must be absolute")
        self.transport: TransportAdapter | None = None

    def invoke(self, arguments: dict[str, Any], *, context: dict[str, Any]) -> CapabilityProviderResult:
        if not isinstance(arguments, dict):
            raise ValueError("bridge provider invocation must be an object")
        request = arguments.get("request")
        is_activity = isinstance(request, dict) and request.get("operation") == "execute"
        if is_activity:
            envelope = request.get("payload")
            if not isinstance(envelope, dict) or envelope.get("contract_id") != "r3a.activity-handler.request":
                raise ValueError("CME activity-handler envelope is invalid")
            value = envelope.get("input")
        else:
            value = arguments.get("input")
        if not isinstance(value, dict):
            raise ValueError("route-plan invocation requires an object input")
        if set(value) != {"dispatches", "sessions"}:
            raise ValueError("route-plan input must contain dispatches and sessions")
        decisions = route_batch(value["dispatches"], value["sessions"],
                                safe_steer_available=bool(self.transport and self.transport.supports_safe_steer))
        output = [{"repository": d.source_key[0], "issue_number": d.source_key[1],
                   "comment_id": d.source_key[2], "target": d.target, "mode": d.mode,
                   "state": d.state, "reason": d.reason, "idempotency_key": d.idempotency_key}
                  for d in decisions]
        evidence = [{"source_issue": f"{d.source_key[0]}/issues/{d.source_key[1]}",
                     "source_comment_id": d.source_key[2], "target": d.target,
                     "observed_route_state": d.state} for d in decisions]
        if is_activity:
            result = {"outcome": "completed", "decisions": output,
                      "progress": {"phase": "dispatch_batch_planned", "decision_count": len(output)},
                      "checkpoint": {"source_keys": [
                          f"{d.source_key[0]}:{d.source_key[1]}:{d.source_key[2]}" for d in decisions]}}
            return CapabilityProviderResult(output=result, evidence=evidence)
        # CME has already authorized this read-only capability invocation.
        del context
        return CapabilityProviderResult(output={"decisions": output}, evidence=evidence)


def create_provider(configuration: dict[str, Any]) -> DevelopmentBridgeProvider:
    return DevelopmentBridgeProvider(configuration)
