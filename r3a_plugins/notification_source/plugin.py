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
                "SELECT event_id,event_type,schema_version,subject_type,subject_id,prior_state,next_state,"
                "occurred_at,persisted_at,actor,correlation_id,reason,outcome,config_revision,"
                "implementation_revision,evidence FROM r3a.institution_events WHERE event_id=%s",
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
