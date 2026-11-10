"""
# File: r3a_plugins/notification_source/intake.py
# Component: R3A-NOTIFICATION-ACTIVITY-INTAKE
# File Revision: 1.2.0
# Created: 2026-11-10
# Created By: Codex GPT-6
# Purpose: Preserve N1 source reads and execute the registered notification handler contract.
# Execution Model: Digest-pinned provider process invoked by CME's generic module socket.
# Dependencies: r3a.notification-intake.v1; r3a.activity-handler.v1.1; CME handler authorization.
# Authority: Issue #48; registered handler selected by notification.event.review.
# Changed: 2026-11-10 | R3A-CORE-FREEZE-CORRECTION | Codex GPT-6 | Implement handler envelope validation and evidence-bearing fail-closed result pending generic CME objective continuation.
# Contracts: r3a.activity-handler@1.1.0; r3a.capability-provider.v1.
# Tests: tests/test_r3a_notification_source_plugin.py; tests/test_r3a_notification_handler_process.py.
# History/Predecessor: 1.1.0, source intake adapter only.
"""
from __future__ import annotations

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
    """Fail closed until CME exposes a generic durable Grace objective continuation."""
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
    # The v1.1 action socket admits only registered capability operations. The existing
    # CME objective submission is a control operation, and model invocation is an
    # external_write; returning blocked is safer than fabricating Grace's disposition.
    return {"outcome": "blocked",
            "reason": "generic CME Grace objective continuation is unavailable",
            "progress": {"phase": "notification.received"},
            "checkpoint": checkpoint,
            "evidence": evidence,
            "lifecycle_evidence": {
                "received": _LIFECYCLE["received"],
                "actionable": _LIFECYCLE["actionable"],
                "blocked": _LIFECYCLE["blocked"],
                "acknowledged": None,
                "resolved": None}}


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
