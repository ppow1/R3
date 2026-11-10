# R3 CONTROLLED SOURCE
# File: r3a_plugins/notification_source/plugin.py
# Component: R3A-NOTIFICATION-SOURCE-ADAPTER
# File Revision: 1.0.1
# Created: Unknown (legacy)
# Created By: Unknown (legacy)
# Purpose: Read allowlisted immutable CME events and project versioned notification intake envelopes.
# Execution Model: Registered read-only capability provider and pure intake projection.
# Observability: Source identity, event identity, digest, provenance, and provider failures.
# Dependencies: r3a.notification-intake.v1; r3a.activity-intake.v1; CME capability grants.
# Authority: Issue #48; source reads require the existing notification.source.read grant.
# Changed: 2026-11-10T18:53:48Z | R3A-CORE-FREEZE-CORRECTION | Codex GPT-6 | Emit notification-owned activity type for the generic handler boundary.
# Supersedes: None.
# Contracts: r3a.notification-intake.v1; r3a.activity-intake.v1.
# Tests: tests/test_r3a_notification_source_plugin.py.
# History/Predecessor: Git commit bcae2fc; previous source behavior retained by legacy N1 operation.
"""Read-only capability-operation adapter for the existing CME event ledger."""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from r3a_runtime.capability_contracts import CapabilityProviderResult
from r3a_runtime.notifications import institution_event_envelope


_ACTIVITY_INTAKE_SCHEMA = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "r3a_runtime", "schemas", "activity-intake.v1.schema.json")


class InstitutionEventNotificationSource:
    """Fetch one allowlisted immutable CME event and project the established N1 envelope."""

    def __init__(self, configuration: dict[str, Any], *,
                 connect: Callable[..., Any] | None = None,
                 clock: Callable[[], datetime] | None = None):
        self.configuration = dict(configuration)
        self.connect = connect or self._connect
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def invoke(self, arguments: dict[str, Any], *, context: dict[str, Any]) -> CapabilityProviderResult:
        if not isinstance(arguments, dict) or set(arguments) != {"source_event_id"}:
            raise ValueError("notification source input must contain only source_event_id")
        try:
            event_uuid = uuid.UUID(arguments["source_event_id"])
        except (TypeError, ValueError, AttributeError) as exc:
            raise ValueError("source_event_id must be a UUID") from exc
        event_id = str(event_uuid)
        event_types = self.configuration["event_types"]
        if not event_types:
            raise PermissionError("notification source has no allowlisted event types")
        dsn = os.environ.get(self.configuration["dsn_env"], "")
        if not dsn:
            raise RuntimeError("notification_source_not_configured")

        try:
            connection = self.connect(dsn, connect_timeout=self.configuration["connect_timeout_seconds"])
        except Exception as exc:
            raise RuntimeError(f"notification_source_unavailable:{type(exc).__name__}") from None
        try:
            connection.execute("BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            connection.execute("SELECT set_config('statement_timeout', %s, true)",
                               (str(self.configuration["statement_timeout_ms"]),))
            row = connection.execute(
                "SELECT e.event_id,e.event_type,e.schema_version,e.subject_type,e.subject_id,e.prior_state,e.next_state,"
                "e.occurred_at,e.persisted_at,e.actor,e.correlation_id,e.reason,e.outcome,e.config_revision,"
                "e.implementation_revision,e.evidence FROM r3a.institution_events e WHERE e.event_id=%s "
                "AND NOT EXISTS (SELECT 1 FROM r3a.activities a WHERE a.activity_id=CASE "
                "WHEN e.subject_type='activity' AND e.subject_id ~* '^[0-9a-f-]{36}$' "
                "THEN e.subject_id::uuid ELSE NULL END "
                "AND a.activity_type='foundation.observe')",
                (event_uuid,),
            ).fetchone()
            connection.commit()
        except Exception as exc:
            try:
                connection.rollback()
            except Exception:
                pass
            raise RuntimeError(f"notification_source_unavailable:{type(exc).__name__}") from None
        finally:
            connection.close()
        if row is None:
            raise KeyError(f"notification source event not found: {event_id}")
        if row["event_type"] not in event_types:
            raise PermissionError("source event type is not enabled for notification intake")

        received_at = self.clock().astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        envelope = institution_event_envelope(row, received_at=received_at)
        canonical_row = json.dumps(row, sort_keys=True, separators=(",", ":"), default=_json_value)
        evidence = {
            "source_id": envelope["source_id"],
            "source_event_id": envelope["source_event_id"],
            "payload_sha256": hashlib.sha256(canonical_row.encode("utf-8")).hexdigest(),
            "payload_ref": envelope["payload_ref"],
            "read_only": True,
            "queried_at": received_at,
        }
        return CapabilityProviderResult(output=envelope, evidence=evidence)

    @staticmethod
    def _connect(dsn: str, *, connect_timeout: int):
        import psycopg
        from psycopg.rows import dict_row
        return psycopg.connect(dsn, connect_timeout=connect_timeout, row_factory=dict_row)


def _json_value(value: Any) -> Any:
    if isinstance(value, (datetime, uuid.UUID)):
        return value.isoformat() if isinstance(value, datetime) else str(value)
    return str(value)


def create_provider(configuration: dict[str, Any]) -> InstitutionEventNotificationSource:
    return InstitutionEventNotificationSource(configuration)


def to_activity_intake(notification: dict[str, Any], source_evidence: dict[str, Any], *,
                       provider: dict[str, Any], configuration_revision: str,
                       lifecycle_projection: dict[str, str], task_class: str = "objective_reasoning",
                       parent_activity_id: str | None = None,
                       activity_type: str = "notification.event.review") -> dict[str, Any]:
    """Project the established N1 result for CME's generic durable intake boundary.

    This is a pure adapter projection. CME still validates authorization, task
    class policy, replay identity, and lifecycle transitions before persistence.
    """
    from pathlib import Path

    from r3a_runtime.capability_contracts import validate_json
    from r3a_runtime.notifications import validate_notification_envelope

    notification = validate_notification_envelope(notification)
    if not isinstance(source_evidence, dict) or source_evidence.get("source_event_id") != notification["source_event_id"]:
        raise ValueError("source evidence must identify the same notification event")
    required_provider = {"provider_id", "provider_version", "artifact_sha256"}
    if not isinstance(provider, dict) or set(provider) != required_provider:
        raise ValueError("generic intake provider provenance is incomplete")
    if (not isinstance(configuration_revision, str) or not configuration_revision.strip()
            or not isinstance(lifecycle_projection, dict)):
        raise ValueError("generic intake configuration provenance is incomplete")
    if activity_type != "notification.event.review":
        raise ValueError("notification adapter activity type is not registered")
    required_phases = {"received", "actionable", "acknowledged", "resolved", "blocked"}
    if (set(lifecycle_projection) != required_phases
            or any(not isinstance(value, str) or not value.startswith("grace.notification.")
                   for value in lifecycle_projection.values())):
        raise ValueError("notification lifecycle projection must map all phases to grace.notification events")

    event = notification["evidence"]
    transition = f"{event.get('prior_state') or 'unknown'} → {event.get('next_state') or 'no state transition'}"
    objective = (f"Review this {notification['severity']} institutional notification from "
                 f"{notification['source_id']}. Source event {notification['source_event_id']} "
                 f"reports {notification['event_type']} for {event.get('subject_type', 'unknown')} "
                 f"{event.get('subject_id', 'unknown')} ({transition}): {event.get('reason', '')}. "
                 "Decide whether follow-up is warranted. Cite the supplied notification evidence; "
                 "do not claim external side effects.")
    digest = source_evidence.get("payload_sha256")
    if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError("source evidence must carry a lowercase SHA-256 digest")
    envelope = {
        "contract_id": "r3a.activity-intake.v1",
        "contract_version": "1.0.0",
        "intake_id": f"notification:{notification['source_id']}:{notification['source_event_id']}",
        "parent_activity_id": parent_activity_id,
        "correlation_id": notification["correlation_id"],
        "source": {
            "source_id": notification["source_id"],
            "event_id": notification["source_event_id"],
            "revision": str(notification["provenance"].get("schema_version", "1")),
            "idempotency_key": f"notification:{notification['source_id']}:{notification['source_event_id']}",
            "occurred_at": notification["occurred_at"],
            "received_at": notification["received_at"],
            "payload_ref": notification["payload_ref"],
            "payload_sha256": digest,
            "causation_id": None,
        },
        "activity": {
            # Keep N1's Grace objective construction intact for compatibility,
            # while the generic boundary routes this activity through the
            # notification module's registered durable handler contract.
            "activity_type": activity_type,
            "task_class": task_class,
            "objective": objective,
            "input": {"event_kind": "notification", "notification": notification},
            "evidence": [{
                "source_id": f"notification:{notification['source_id']}:{notification['source_event_id']}",
                "source_ref": notification["payload_ref"],
                "sha256": digest,
                "provenance": (f"{notification['provenance'].get('store', 'unknown')}; "
                               f"{notification['provenance'].get('implementation_revision', 'unknown')}; "
                               f"{provider['provider_id']}@{provider['provider_version']}"),
            }],
        },
        "provenance": {
            "module_id": provider["provider_id"],
            "module_version": provider["provider_version"],
            "artifact_sha256": provider["artifact_sha256"],
            "configuration_revision": configuration_revision,
        },
        "lifecycle_projection": lifecycle_projection,
    }
    schema = json.loads(Path(_ACTIVITY_INTAKE_SCHEMA).read_text(encoding="utf-8"))
    validate_json(envelope, schema)
    return envelope
