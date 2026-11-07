"""Recipient routing and versioned delivery projection for CME notifications.

This module consumes the authoritative directory projection and a bootstrap
policy. It never invents recipients or performs delivery/acknowledgment itself;
the caller must persist the returned envelopes and enforce CME authorization.
"""
from __future__ import annotations

from datetime import datetime, timezone
import uuid
from typing import Any

from .contracts import parse_timestamp
from .notifications import validate_notification_envelope


DELIVERY_CONTRACT_ID = "r3a.notification-delivery"
DELIVERY_CONTRACT_VERSION = "1.0.0"
DIRECTORY_SCHEMA_ID = "r3a.institutional-directory.v1"
_TARGET_KINDS = {"resident", "office", "steward"}
_URGENCY = {"low", "normal", "high", "critical"}


class DirectoryUnavailable(ValueError):
    """Routing cannot proceed without a fresh authoritative directory snapshot."""


def delivery_visible_to(value: dict[str, Any], principal_id: str,
                        directory: dict[str, Any]) -> bool:
    """Check recipient scope using the current directory binding, not caller filters."""
    value = validate_delivery_envelope(value)
    recipient = value["recipient"]
    if recipient["kind"] in {"resident", "steward"}:
        return principal_id == recipient["recipient_id"]
    if not isinstance(directory, dict) or directory.get("schema_id") != DIRECTORY_SCHEMA_ID:
        raise DirectoryUnavailable("directory is required to check office-scoped visibility")
    source = directory.get("source", {})
    if source.get("availability") != "measured" or source.get("freshness") != "fresh":
        raise DirectoryUnavailable("fresh directory is required to check office-scoped visibility")
    return any(isinstance(row, dict) and row.get("resident_id") == principal_id
               and row.get("office_id") == recipient["recipient_id"]
               and row.get("office_status") == "active"
               for row in directory.get("residents", []))


def validate_routing_policy(policy: Any) -> dict[str, Any]:
    required = {"contract_id", "contract_version", "rules"}
    if not isinstance(policy, dict) or set(policy) != required:
        raise ValueError("notification routing policy fields are invalid")
    if policy["contract_id"] != DELIVERY_CONTRACT_ID or policy["contract_version"] != DELIVERY_CONTRACT_VERSION:
        raise ValueError("unsupported notification delivery policy")
    if not isinstance(policy["rules"], list):
        raise ValueError("notification delivery rules must be an array")
    seen = set()
    for i, rule in enumerate(policy["rules"]):
        fields = {"source_id", "event_type", "recipient", "urgency", "requires_action"}
        if not isinstance(rule, dict) or set(rule) != fields:
            raise ValueError(f"notification delivery rule {i} has invalid fields")
        if not all(isinstance(rule[k], str) and rule[k].strip()
                   for k in ("source_id", "event_type", "urgency")):
            raise ValueError(f"notification delivery rule {i} has empty text fields")
        if rule["urgency"] not in _URGENCY or not isinstance(rule["requires_action"], bool):
            raise ValueError(f"notification delivery rule {i} has invalid action metadata")
        recipient = rule["recipient"]
        if (not isinstance(recipient, dict) or set(recipient) != {"kind", "office_role"}
                or recipient["kind"] not in _TARGET_KINDS
                or not isinstance(recipient["office_role"], str) or not recipient["office_role"].strip()):
            raise ValueError(f"notification delivery rule {i} has invalid directory selector")
        key = (rule["source_id"], rule["event_type"])
        if key in seen:
            raise ValueError("notification delivery rules must be unique by source and event type")
        seen.add(key)
    return policy


def route_notification(notification: dict[str, Any], directory: dict[str, Any],
                       policy: dict[str, Any], *, created_at: str | None = None) -> list[dict[str, Any]]:
    """Resolve one event to zero or more directory-owned recipient envelopes.

    Zero matches is an explicit empty result; unavailable or stale directory
    data is an error so callers can retain a blocked/pending durable outcome.
    """
    notification = validate_notification_envelope(notification)
    policy = validate_routing_policy(policy)
    if not isinstance(directory, dict) or directory.get("schema_id") != DIRECTORY_SCHEMA_ID:
        raise DirectoryUnavailable("authoritative institutional directory contract is unavailable")
    source = directory.get("source")
    if (not isinstance(source, dict) or source.get("availability") != "measured"
            or source.get("freshness") != "fresh" or not isinstance(source.get("snapshot_sha256"), str)):
        raise DirectoryUnavailable("authoritative institutional directory is unavailable or stale")
    rule = next((item for item in policy["rules"]
                 if item["source_id"] == notification["source_id"]
                 and item["event_type"] == notification["event_type"]), None)
    if rule is None:
        return []
    role = rule["recipient"]["office_role"].casefold()
    kind = rule["recipient"]["kind"]
    offices = directory.get("offices")
    residents = directory.get("residents")
    if not isinstance(offices, list) or not isinstance(residents, list):
        raise DirectoryUnavailable("directory response lacks office or resident records")
    candidates: list[dict[str, Any]] = []
    if kind == "office":
        candidates = [
            {"kind": "office", "recipient_id": row["office_id"], "office_id": row["office_id"]}
            for row in offices if isinstance(row, dict)
            and str(row.get("office_role", "")).casefold() == role
            and str(row.get("status", "")).casefold() == "active"
        ]
    else:
        candidates = [
            {"kind": kind, "recipient_id": row["resident_id"], "office_id": row["office_id"]}
            for row in residents if isinstance(row, dict)
            and str(row.get("office_role", "")).casefold() == role
            and str(row.get("office_status", "")).casefold() == "active"
        ]
    delivered_at = created_at or datetime.now(timezone.utc).isoformat()
    output = []
    for target in sorted(candidates, key=lambda item: (item["recipient_id"], item["office_id"])):
        stable_id = uuid.uuid5(uuid.NAMESPACE_URL,
                               f"r3a.notification.delivery:{notification['event_id']}:{target['kind']}:{target['recipient_id']}")
        output.append({
            "contract_id": DELIVERY_CONTRACT_ID,
            "contract_version": DELIVERY_CONTRACT_VERSION,
            "delivery_id": str(stable_id),
            "idempotency_key": f"notification-delivery:{notification['event_id']}:{target['kind']}:{target['recipient_id']}",
            "notification_event_id": notification["event_id"],
            "source_id": notification["source_id"],
            "source_event_id": notification["source_event_id"],
            "correlation_id": notification["correlation_id"],
            "recipient": target,
            "severity": notification["severity"],
            "urgency": rule["urgency"],
            "requires_action": rule["requires_action"],
            "status": "queued",
            "created_at": delivered_at,
            "acknowledged_at": None,
            "resolved_at": None,
            "resolution_disposition": None,
            "evidence_refs": [notification["payload_ref"], source["snapshot_sha256"]],
        })
    return output


def validate_delivery_envelope(value: Any) -> dict[str, Any]:
    required = {"contract_id", "contract_version", "delivery_id", "idempotency_key",
                "notification_event_id", "source_id", "source_event_id", "correlation_id",
                "recipient", "severity", "urgency", "requires_action", "status",
                "created_at", "acknowledged_at", "resolved_at", "resolution_disposition", "evidence_refs"}
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError("notification delivery envelope fields are invalid")
    if value["contract_id"] != DELIVERY_CONTRACT_ID or value["contract_version"] != DELIVERY_CONTRACT_VERSION:
        raise ValueError("unsupported notification delivery envelope")
    recipient = value["recipient"]
    if (not isinstance(recipient, dict) or set(recipient) != {"kind", "recipient_id", "office_id"}
            or recipient["kind"] not in _TARGET_KINDS
            or not all(isinstance(recipient[k], str) and recipient[k].strip()
                       for k in ("recipient_id", "office_id"))):
        raise ValueError("notification delivery recipient is invalid")
    if value["urgency"] not in _URGENCY or value["severity"] not in {"info", "warning", "error"}:
        raise ValueError("notification delivery severity or urgency is invalid")
    if not isinstance(value["requires_action"], bool):
        raise ValueError("notification delivery requires_action must be boolean")
    if value["status"] not in {"queued", "delivered", "acknowledged", "resolved", "blocked"}:
        raise ValueError("notification delivery status is invalid")
    if (not isinstance(value["evidence_refs"], list) or not value["evidence_refs"]
            or any(not isinstance(item, str) or not item.strip() for item in value["evidence_refs"])):
        raise ValueError("notification delivery requires evidence references")
    for field in ("delivery_id", "notification_event_id", "source_event_id", "correlation_id"):
        try:
            uuid.UUID(value[field])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"notification delivery {field} must be a UUID") from exc
    if not all(isinstance(value[k], str) and value[k].strip()
               for k in ("idempotency_key", "source_id")):
        raise ValueError("notification delivery source and idempotency key are required")
    parse_timestamp(value["created_at"], "notification_delivery.created_at")
    for field in ("acknowledged_at", "resolved_at"):
        if value[field] is not None:
            parse_timestamp(value[field], f"notification_delivery.{field}")
    disposition = value["resolution_disposition"]
    if disposition is not None and (not isinstance(disposition, str) or not disposition.strip()):
        raise ValueError("notification resolution disposition must be nonempty text or null")
    if value["status"] == "resolved" and not disposition:
        raise ValueError("resolved notification delivery requires a disposition")
    if value["notification_event_id"] != value["source_event_id"]:
        raise ValueError("notification delivery event references must identify the source event")
    expected_key = (f"notification-delivery:{value['notification_event_id']}:{recipient['kind']}"
                    f":{recipient['recipient_id']}")
    expected_id = str(uuid.uuid5(uuid.NAMESPACE_URL,
                                 f"r3a.notification.delivery:{value['notification_event_id']}"
                                 f":{recipient['kind']}:{recipient['recipient_id']}"))
    if value["idempotency_key"] != expected_key or value["delivery_id"] != expected_id:
        raise ValueError("notification delivery identity does not match its source and recipient")
    return value


def transition_delivery(value: dict[str, Any], operation: str, *, principal_id: str,
                        request: Any, decision: Any, directory: dict[str, Any],
                        at: str | None = None, disposition: str | None = None,
                        resolution_evidence_refs: list[str] | None = None) -> dict[str, Any]:
    """Validate recipient scope and a matching CME authorization decision.

    Persistence and audit-event append remain the caller's CME transaction.
    """
    value = validate_delivery_envelope(value)
    if operation not in {"acknowledge", "resolve"}:
        raise ValueError("notification delivery operation must be acknowledge or resolve")
    required_capability = f"notification.delivery.{operation}"
    if (not isinstance(principal_id, str) or not principal_id.strip()
            or getattr(request, "resident_id", None) != principal_id
            or getattr(request, "capability_id", None) != required_capability):
        raise PermissionError("authorization request does not match the notification actor and operation")
    if (getattr(decision, "allowed", False) is not True
            or getattr(decision, "correlation_id", None) != getattr(request, "correlation_id", None)
            or getattr(decision, "activity_id", None) != getattr(request, "activity_id", None)
            or getattr(decision, "attempt_id", None) != getattr(request, "attempt_id", None)
            or not getattr(decision, "audit_event_id", None)):
        raise PermissionError("matching allowed CME authorization decision with audit evidence is required")
    if not delivery_visible_to(value, principal_id, directory):
        raise PermissionError("notification delivery is outside the caller's directory recipient scope")
    current = value["status"]
    if operation == "acknowledge":
        if current not in {"queued", "delivered"}:
            raise ValueError(f"cannot acknowledge notification in {current} state")
        value["status"] = "acknowledged"
        value["acknowledged_at"] = at or datetime.now(timezone.utc).isoformat()
    else:
        allowed_states = {"acknowledged"}
        if not value["requires_action"]:
            allowed_states.update({"queued", "delivered"})
        if current not in allowed_states:
            raise ValueError(f"cannot resolve notification in {current} state")
        if not isinstance(disposition, str) or not disposition.strip():
            raise ValueError("notification resolution requires a disposition")
        if (not isinstance(resolution_evidence_refs, list) or not resolution_evidence_refs
                or any(not isinstance(item, str) or not item.strip()
                       for item in resolution_evidence_refs)):
            raise ValueError("notification resolution requires evidence references")
        value["status"] = "resolved"
        value["resolved_at"] = at or datetime.now(timezone.utc).isoformat()
        value["resolution_disposition"] = disposition.strip()
        value["evidence_refs"] = list(dict.fromkeys(value["evidence_refs"] + resolution_evidence_refs))
    return validate_delivery_envelope(value)
