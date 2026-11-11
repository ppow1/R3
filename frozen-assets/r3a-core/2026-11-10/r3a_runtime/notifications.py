"""Versioned notification envelope and institution-event source adapter."""
from __future__ import annotations

from datetime import datetime
from typing import Any
import uuid

from .contracts import parse_timestamp


NOTIFICATION_CONTRACT_ID = "r3a.notification-intake"
NOTIFICATION_CONTRACT_VERSION = "1.0.0"
INSTITUTION_EVENT_SOURCE = "r3a.institution-events"


def validate_notification_envelope(value: Any) -> dict[str, Any]:
    """Validate the data-only durable envelope imported from an institution event."""
    required = {
        "contract_id", "contract_version", "source_id", "source_event_id", "event_type",
        "event_id", "correlation_id", "occurred_at", "received_at", "severity", "payload_ref",
        "provenance", "evidence",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError("notification envelope fields do not match r3a.notification-intake.v1")
    if value["contract_id"] != NOTIFICATION_CONTRACT_ID or value["contract_version"] != NOTIFICATION_CONTRACT_VERSION:
        raise ValueError("unsupported notification intake contract")
    for key in ("source_id", "source_event_id", "event_type", "event_id", "correlation_id", "severity", "payload_ref"):
        if not isinstance(value[key], str) or not value[key].strip():
            raise ValueError(f"notification {key} must be nonempty text")
    try:
        if uuid.UUID(value["source_event_id"]) != uuid.UUID(value["event_id"]):
            raise ValueError("source_event_id and event_id must identify the same source record")
        uuid.UUID(value["correlation_id"])
    except (TypeError, ValueError) as exc:
        raise ValueError("notification event and correlation IDs must be UUIDs") from exc
    if value["severity"] not in {"info", "warning", "error"}:
        raise ValueError("notification severity must be info, warning, or error")
    parse_timestamp(value["occurred_at"], "notification.occurred_at")
    parse_timestamp(value["received_at"], "notification.received_at")
    if not isinstance(value["provenance"], dict) or not isinstance(value["evidence"], dict):
        raise ValueError("notification provenance and evidence must be objects")
    return value


def institution_event_envelope(event: dict[str, Any], *, received_at: str) -> dict[str, Any]:
    """Project one existing immutable CME event into the notification contract."""
    event_id = str(event["event_id"])
    envelope = {
        "contract_id": NOTIFICATION_CONTRACT_ID,
        "contract_version": NOTIFICATION_CONTRACT_VERSION,
        "source_id": INSTITUTION_EVENT_SOURCE,
        "source_event_id": event_id,
        "event_type": str(event["event_type"]),
        "event_id": event_id,
        "correlation_id": str(event["correlation_id"]),
        "occurred_at": _iso(event["occurred_at"]),
        "received_at": received_at,
        "severity": _severity(event),
        "payload_ref": f"r3a.institution_events/{event_id}",
        "provenance": {
            "store": "r3a.institution_events",
            "schema_version": int(event.get("schema_version", 1)),
            "actor": str(event.get("actor", "unknown")),
            "source_config_revision": event.get("config_revision"),
            "implementation_revision": str(event.get("implementation_revision", "unknown")),
        },
        "evidence": {
            "subject_type": str(event["subject_type"]),
            "subject_id": str(event["subject_id"]),
            "prior_state": event.get("prior_state"),
            "next_state": event.get("next_state"),
            "reason": str(event.get("reason", "")),
            "outcome": str(event.get("outcome", "unknown")),
            "persisted_at": _iso(event["persisted_at"]),
            "source_evidence": {**(event.get("evidence") or {}),
                                "source_config_revision": event.get("config_revision")},
        },
    }
    return validate_notification_envelope(envelope)


def same_notification_input(existing: dict[str, Any], incoming: dict[str, Any]) -> bool:
    """Compare replayed intake while retaining the original durable receipt timestamp."""
    left, right = dict(existing), dict(incoming)
    old_notification, new_notification = left.get("notification"), right.get("notification")
    if not isinstance(old_notification, dict) or not isinstance(new_notification, dict):
        return left == right
    old_notification, new_notification = dict(old_notification), dict(new_notification)
    old_notification.pop("received_at", None)
    new_notification.pop("received_at", None)
    left["notification"], right["notification"] = old_notification, new_notification
    return left == right


def _iso(value: Any) -> str:
    return value.isoformat() if isinstance(value, datetime) else str(value)


def _severity(event: dict[str, Any]) -> str:
    kind = str(event.get("event_type", "")).lower()
    state = str(event.get("next_state", "")).lower()
    if "failed" in kind or state in {"failed", "blocked", "degraded"}:
        return "error"
    if state in {"restarting", "recovering", "stale", "unavailable"}:
        return "warning"
    return "info"
