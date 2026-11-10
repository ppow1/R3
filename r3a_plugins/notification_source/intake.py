"""
# File: r3a_plugins/notification_source/intake.py
# Component: R3A-NOTIFICATION-ACTIVITY-INTAKE
# File Revision: 1.3.0
# Created: 2026-11-10
# Created By: Codex GPT-6
# Purpose: Preserve N1 source reads and execute the registered notification handler contract.
# Execution Model: Digest-pinned provider process invoked by CME's generic module socket.
# Dependencies: r3a.notification-intake.v1; r3a.activity-handler.v1.1; CME handler authorization.
# Authority: Issue #48; registered handler selected by notification.event.review.
# Changed: 2026-11-10T20:10:03Z | R3A-GENERIC-OBJECTIVE-CONTINUATION | R3A Coordinator | Submit authorized Grace review objectives through the generic CME continuation socket and return only the durable disposition.
# Contracts: r3a.activity-handler@1.1.0; r3a.capability-provider.v1.
# Tests: tests/test_r3a_notification_source_plugin.py; tests/test_r3a_notification_handler_process.py.
# History/Predecessor: 1.1.0, source intake adapter only.
"""
from __future__ import annotations

import hashlib
from typing import Any

from r3a_runtime.capability_contracts import CapabilityProviderResult
from .plugin import create_provider as create_source_provider, to_activity_intake


_LIFECYCLE = {
    "received": "grace.notification.received",
    "actionable": "grace.notification.actionable",
    "acknowledged": "grace.notification.acknowledged",
    "resolved": "grace.notification.resolved",
    "blocked": "grace.notification.blocked",
}


def _notification_evidence(notification: dict[str, Any], evidence: Any) -> list[dict[str, Any]]:
    """Return source-bound evidence records without manufacturing provenance."""
    if not isinstance(notification, dict):
        raise ValueError("notification handler input must contain a notification object")
    source_id = notification.get("source_id")
    event_id = notification.get("source_event_id")
    payload_ref = notification.get("payload_ref")
    if not all(isinstance(value, str) and value for value in (source_id, event_id, payload_ref)):
        raise ValueError("notification handler input lacks source identity or payload reference")
    if not isinstance(evidence, list) or not evidence:
        raise ValueError("notification handler requires source evidence from CME intake")
    source_key = f"notification:{source_id}:{event_id}"
    matches = []
    for entry in evidence:
        if not isinstance(entry, dict) or set(entry) != {"source_id", "source_ref", "sha256", "provenance"}:
            raise ValueError("notification handler evidence entry is malformed")
        digest = entry.get("sha256")
        if (entry.get("source_id") == source_key and entry.get("source_ref") == payload_ref
                and isinstance(digest, str) and len(digest) == 64
                and all(character in "0123456789abcdef" for character in digest)):
            matches.append(dict(entry))
    if len(matches) != 1:
        raise ValueError("notification handler source evidence is missing or ambiguous")
    return matches


def _handler_result(payload: dict[str, Any]) -> dict[str, Any]:
    """Submit one source-bound review objective and consume its durable CME continuation."""
    request = payload.get("input")
    if not isinstance(request, dict) or request.get("event_kind") != "notification":
        raise ValueError("notification handler requires event_kind=notification")
    notification = request.get("notification")
    evidence = _notification_evidence(notification, payload.get("evidence", []))
    source_id = notification["source_id"]
    event_id = notification["source_event_id"]
    expected_key = f"notification:{source_id}:{event_id}"
    if payload.get("idempotency_key") != expected_key:
        raise ValueError("notification handler idempotency key is not source-bound")
    if payload.get("correlation_id") != notification.get("correlation_id"):
        raise ValueError("notification handler correlation does not match source event")
    checkpoint = {"source_id": source_id, "source_event_id": event_id,
                  "correlation_id": str(payload.get("correlation_id") or notification.get("correlation_id") or ""),
                  "idempotency_key": str(payload.get("idempotency_key") or ""),
                  "phase": "awaiting_grace_disposition"}
    action_id = "notification.review." + hashlib.sha256(
        f"{source_id}:{event_id}".encode("utf-8")).hexdigest()
    continuation = payload.get("continuation")
    if continuation is None:
        execution_principal = payload.get("execution_principal")
        if not isinstance(execution_principal, str) or not execution_principal:
            raise ValueError("CME handler request lacks its server-derived execution principal")
        event = notification.get("evidence") or {}
        objective = (f"Review this {notification.get('severity', 'unknown')} institutional notification from "
                    f"{source_id}. Source event {event_id} reports {notification.get('event_type', 'unknown')} "
                    f"for {event.get('subject_type', 'unknown')} {event.get('subject_id', 'unknown')}: "
                    f"{event.get('reason', '')}. Decide whether follow-up is warranted, cite the notification "
                    "evidence, and do not claim external side effects.")
        action = {"contract_id": "r3a.activity-handler.objective-submission",
                  "contract_version": "1.0.0", "action_id": action_id,
                  "target_resident_id": execution_principal, "objective": objective,
                  "event_kind": "notification", "task_class": "objective_reasoning",
                  "required_capabilities": [], "required_modalities": [],
                  "acceptance_criteria": [], "notification_envelope": notification,
                  "timeout_seconds": 3600}
        return {"outcome": "action_required", "action": action,
                "progress": {"phase": "notification.received"}, "checkpoint": checkpoint}

    if (not isinstance(continuation, dict)
            or continuation.get("contract_id") != "r3a.activity-handler.continuation"
            or continuation.get("contract_version") != "1.0.0"
            or continuation.get("action_id") != action_id):
        raise ValueError("CME continuation does not match the notification review action")
    invocation = continuation.get("invocation") or {}
    child_id = invocation.get("activity_id") if isinstance(invocation, dict) else None
    child_state = invocation.get("state") if isinstance(invocation, dict) else None
    if continuation.get("outcome") == "succeeded" and child_state == "COMPLETED":
        result = invocation.get("result")
        decision = result.get("decision") if isinstance(result, dict) else None
        source_key = f"notification:{source_id}:{event_id}"
        if (not isinstance(decision, dict)
                or decision.get("status") not in {"healthy", "degraded", "blocked"}
                or not isinstance(decision.get("assessment"), str)
                or not decision["assessment"].strip()
                or not isinstance(decision.get("recommended_action"), str)
                or source_key not in decision.get("evidence_refs", [])):
            raise ValueError("Grace result lacks a source-cited notification disposition")
        checkpoint.update({"phase": "grace_disposition_received", "resident_activity_id": child_id,
                           "resident_status": decision["status"],
                           "assessment": decision["assessment"],
                           "recommended_action": decision["recommended_action"],
                           "evidence_refs": decision["evidence_refs"]})
        return {"outcome": "completed", "reason": "Grace returned a durable source-cited notification disposition.",
                "progress": {"phase": "notification.reviewed"}, "checkpoint": checkpoint,
                "evidence": evidence,
                "lifecycle_evidence": {"received": _LIFECYCLE["received"],
                                       "actionable": _LIFECYCLE["actionable"],
                                       "blocked": _LIFECYCLE["blocked"],
                                       "acknowledged": _LIFECYCLE["acknowledged"],
                                       "resolved": _LIFECYCLE["resolved"]}}

    checkpoint.update({"phase": "grace_disposition_unavailable", "resident_activity_id": child_id,
                       "resident_status": str(child_state or continuation.get("outcome") or "unknown")})
    error = continuation.get("error") or {}
    reason = str(error.get("message") or f"Grace objective ended in {child_state or 'an unknown state'}")
    return {"outcome": "blocked", "reason": reason[:512],
            "progress": {"phase": "notification.blocked"}, "checkpoint": checkpoint,
            "evidence": evidence,
            "lifecycle_evidence": {"received": _LIFECYCLE["received"],
                                   "actionable": _LIFECYCLE["actionable"],
                                   "blocked": _LIFECYCLE["blocked"],
                                   "acknowledged": None, "resolved": None}}


class NotificationActivityIntakeProvider:
    """Read one event through the configured source adapter and project generic intake."""

    def __init__(self, configuration: dict[str, Any]):
        self.configuration = dict(configuration)
        self.source = create_source_provider(configuration)

    def invoke(self, arguments: dict[str, Any], *, context: dict[str, Any]) -> CapabilityProviderResult:
        request = arguments.get("request") if isinstance(arguments, dict) else None
        if isinstance(request, dict) and request.get("operation") == "execute":
            payload = request.get("payload")
            if not isinstance(payload, dict):
                raise ValueError("notification handler execute envelope is invalid")
            result = _handler_result(payload)
            if result.get("outcome") == "action_required":
                # The action-required envelope has a closed schema. Source evidence
                # remains in the provider result envelope, outside that action shape.
                return CapabilityProviderResult(
                    output=result, evidence={"notification": payload.get("evidence", [])})
            return CapabilityProviderResult(output=result,
                                            evidence={"notification": result["evidence"]})
        source_result = self.source.invoke(arguments, context=context)
        provider = context.get("provider")
        if not isinstance(provider, dict):
            raise ValueError("CME provider provenance is required for activity intake")
        envelope = to_activity_intake(
            source_result.output,
            source_result.evidence,
            provider={key: provider[key] for key in
                      ("provider_id", "provider_version", "artifact_sha256")},
            configuration_revision=str(context.get("config_revision", "")),
            lifecycle_projection=_LIFECYCLE,
        )
        return CapabilityProviderResult(output=envelope, evidence=source_result.evidence)


def create_provider(configuration: dict[str, Any]) -> NotificationActivityIntakeProvider:
    return NotificationActivityIntakeProvider(configuration)
