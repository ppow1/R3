"""PostgreSQL-backed notification intake, inbox, and acknowledgment persistence."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import uuid
from typing import Any, Callable

import psycopg
from psycopg.rows import dict_row

from r3a_runtime.notifications import validate_notification_envelope


class NotificationConflict(ValueError):
    """An idempotency key was replayed with different source or delivery content."""


class NotificationForbidden(PermissionError):
    """The notification is outside this module's configured subscriptions or scope."""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _utc(value: datetime | None = None) -> str:
    value = value or datetime.now(timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class NotificationStore:
    """Module-owned durable delivery projection in an isolated PostgreSQL schema."""

    def __init__(self, dsn: str, *, connect: Callable[..., Any] = psycopg.connect):
        if not dsn:
            raise ValueError("notification module database DSN is required")
        self.dsn = dsn
        self.connect = connect

    def initialize(self, module_version: str) -> None:
        with self.connect(self.dsn, row_factory=dict_row) as conn, conn.transaction():
            conn.execute("CREATE SCHEMA IF NOT EXISTS r3a_notification")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS r3a_notification.module_state (
                    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
                    module_id text NOT NULL,
                    module_version text NOT NULL,
                    lifecycle_state text NOT NULL DEFAULT 'INACTIVE' CHECK (lifecycle_state IN ('INSTALLED','ACTIVE','INACTIVE','FAILED')),
                    activated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
                    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
                    schema_version integer NOT NULL
                )
            """)
            # Additive v1.1 migration. Existing delivery and event rows remain untouched.
            conn.execute("ALTER TABLE r3a_notification.module_state ADD COLUMN IF NOT EXISTS "
                         "lifecycle_state text NOT NULL DEFAULT 'INACTIVE'")
            conn.execute("ALTER TABLE r3a_notification.module_state ADD COLUMN IF NOT EXISTS "
                         "updated_at timestamptz NOT NULL DEFAULT clock_timestamp()")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS r3a_notification.deliveries (
                    delivery_id uuid PRIMARY KEY,
                    idempotency_key text NOT NULL UNIQUE,
                    source_id text NOT NULL,
                    source_event_id uuid NOT NULL,
                    event_type text NOT NULL,
                    correlation_id uuid NOT NULL,
                    recipient_kind text NOT NULL CHECK (recipient_kind IN ('resident','office','steward')),
                    recipient_id text NOT NULL,
                    severity text NOT NULL,
                    urgency text NOT NULL CHECK (urgency IN ('low','normal','high','critical')),
                    requires_action boolean NOT NULL,
                    status text NOT NULL CHECK (status IN ('queued','acknowledged','resolved')),
                    notification jsonb NOT NULL,
                    directory_snapshot_sha256 text NOT NULL,
                    content_sha256 text NOT NULL,
                    created_at timestamptz NOT NULL,
                    acknowledged_at timestamptz,
                    acknowledged_by text,
                    acknowledgment_authorization jsonb,
                    ack_idempotency_key text UNIQUE,
                    ack_note text,
                    resolved_at timestamptz,
                    resolved_by text,
                    resolution_authorization jsonb,
                    resolution_idempotency_key text UNIQUE,
                    disposition text,
                    evidence_refs jsonb NOT NULL DEFAULT '[]'::jsonb
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS r3a_notification.delivery_events (
                    event_id uuid PRIMARY KEY,
                    event_type text NOT NULL,
                    delivery_id uuid NOT NULL REFERENCES r3a_notification.deliveries(delivery_id),
                    actor_id text,
                    occurred_at timestamptz NOT NULL,
                    evidence jsonb NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS notification_inbox_recipient_idx "
                         "ON r3a_notification.deliveries(recipient_id, created_at DESC, delivery_id)")
            conn.execute("""
                INSERT INTO r3a_notification.module_state(singleton,module_id,module_version,lifecycle_state,schema_version)
                VALUES (true,'r3a.notifications',%s,'ACTIVE',2)
                ON CONFLICT (singleton) DO UPDATE SET module_version=excluded.module_version,
                    lifecycle_state='ACTIVE',activated_at=clock_timestamp(),updated_at=clock_timestamp(),
                    schema_version=excluded.schema_version
            """, (module_version,))

    def set_lifecycle(self, state: str) -> None:
        if state not in {"INACTIVE","FAILED"}:
            raise ValueError("service shutdown state must be INACTIVE or FAILED")
        with self.connect(self.dsn, row_factory=dict_row) as conn, conn.transaction():
            conn.execute("UPDATE r3a_notification.module_state SET lifecycle_state=%s,updated_at=clock_timestamp() "
                         "WHERE singleton=true", (state,))

    def ingest(self, notification: dict[str, Any], recipients: list[dict[str, str]], *,
               subscription: dict[str, Any], directory_snapshot_sha256: str,
               received_at: datetime | None = None) -> list[dict[str, Any]]:
        notification = validate_notification_envelope(notification)
        if notification["event_type"].startswith("foundation.observe"):
            return []
        if notification["evidence"].get("activity_type") == "foundation.observe":
            return []
        rules = subscription.get("subscriptions", [])
        selected = [rule for rule in rules if rule["event_type"] == notification["event_type"]
                    and _matches_filter(notification, rule.get("filter", {}))]
        if len(selected) != 1:
            return []
        subscription = selected[0]
        if (not isinstance(directory_snapshot_sha256, str) or len(directory_snapshot_sha256)!=64
                or any(c not in "0123456789abcdef" for c in directory_snapshot_sha256)):
            raise ValueError("recipient routing requires an authoritative directory snapshot digest")
        if not recipients:
            return []
        received_at = received_at or datetime.now(timezone.utc)
        delivered = []
        for recipient in recipients:
            if set(recipient) != {"kind", "recipient_id"} or recipient["kind"] not in {"resident", "office", "steward"}:
                raise ValueError("recipient must have a supported kind and directory-derived identity")
            recipient_id = recipient["recipient_id"]
            if not isinstance(recipient_id, str) or not recipient_id.strip():
                raise ValueError("recipient_id must be nonempty")
            key = f"notification:{notification['source_id']}:{notification['source_event_id']}:{recipient_id}"
            delivery_id = uuid.uuid5(uuid.NAMESPACE_URL, f"r3a.notification.delivery:{key}")
            immutable = dict(notification)
            immutable.pop("received_at", None)
            # Directory provenance is retained on the first durable delivery, but it
            # is not part of replay identity: a fresh authoritative snapshot may
            # legitimately have a new digest while resolving the same recipient.
            body = {"notification": immutable, "recipient": recipient,
                    "urgency": subscription["urgency"], "requires_action": subscription["requires_action"]}
            digest = hashlib.sha256(_canonical(body)).hexdigest()
            row = None
            with self.connect(self.dsn, row_factory=dict_row) as conn, conn.transaction():
                conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (key,))
                row = conn.execute("SELECT * FROM r3a_notification.deliveries WHERE idempotency_key=%s", (key,)).fetchone()
                if row:
                    if row["content_sha256"] != digest:
                        raise NotificationConflict("source event replay changed immutable notification or recipient data")
                    result = self._as_delivery(row, duplicate=True)
                else:
                    conn.execute("""
                        INSERT INTO r3a_notification.deliveries
                        (delivery_id,idempotency_key,source_id,source_event_id,event_type,correlation_id,
                         recipient_kind,recipient_id,severity,urgency,requires_action,status,notification,
                         content_sha256,created_at,evidence_refs,directory_snapshot_sha256)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'queued',%s,%s,%s,%s,%s)
                    """, (delivery_id,key,notification["source_id"],uuid.UUID(notification["source_event_id"]),
                          notification["event_type"],uuid.UUID(notification["correlation_id"]),recipient["kind"],
                          recipient_id,notification["severity"],subscription["urgency"],
                          subscription["requires_action"],json.dumps(notification),digest,received_at,
                          json.dumps([notification["payload_ref"]]),directory_snapshot_sha256))
                    event_id = uuid.uuid5(uuid.NAMESPACE_URL, f"r3a.notification.event:{key}:queued")
                    conn.execute("""
                        INSERT INTO r3a_notification.delivery_events
                        (event_id,event_type,delivery_id,occurred_at,evidence)
                        VALUES (%s,'notification.delivery.queued',%s,%s,%s)
                    """, (event_id,delivery_id,received_at,json.dumps({"source_id":notification["source_id"],
                        "source_event_id":notification["source_event_id"],"correlation_id":notification["correlation_id"],
                        "payload_ref":notification["payload_ref"]})))
                    row = conn.execute("SELECT * FROM r3a_notification.deliveries WHERE delivery_id=%s", (delivery_id,)).fetchone()
                    result = self._as_delivery(row, duplicate=False)
            delivered.append(result)
        return delivered

    def inbox(self, recipient_id: str, *, cursor: str | None = None, limit: int = 50) -> dict[str, Any]:
        limit = max(1, min(int(limit), 100))
        cursor_id = uuid.UUID(cursor) if cursor else None
        with self.connect(self.dsn, row_factory=dict_row) as conn:
            rows = conn.execute("""
                SELECT * FROM r3a_notification.deliveries WHERE recipient_id=%s
                  AND (%s::uuid IS NULL OR (created_at,delivery_id)<(
                    SELECT created_at,delivery_id FROM r3a_notification.deliveries WHERE delivery_id=%s))
                ORDER BY created_at DESC,delivery_id DESC LIMIT %s
            """, (recipient_id,cursor_id,cursor_id,limit+1)).fetchall()
        next_cursor = str(rows[limit-1]["delivery_id"]) if len(rows)>limit else None
        return {"contract":"r3a.notification-inbox.v1","contract_version":"1.0.0",
                "freshness":"current","deliveries":[self._as_delivery(row) for row in rows[:limit]],
                "next_cursor":next_cursor}

    def acknowledge(self, delivery_id: str, recipient_id: str, idempotency_key: str,
                    authorization_ref: dict[str, Any], note: str | None = None) -> dict[str, Any]:
        return self._transition(delivery_id, recipient_id, "acknowledged", idempotency_key,
                                authorization_ref=authorization_ref,note=note,evidence_refs=[])

    def resolve(self, delivery_id: str, recipient_id: str, idempotency_key: str,
                disposition: str, evidence_refs: list[str],
                authorization_ref: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(disposition,str) or not disposition.strip() or not evidence_refs:
            raise ValueError("resolution requires a disposition and evidence references")
        return self._transition(delivery_id, recipient_id, "resolved", idempotency_key,
                                disposition=disposition, evidence_refs=evidence_refs,
                                authorization_ref=authorization_ref)

    def _transition(self, delivery_id: str, recipient_id: str, state: str,
                    idempotency_key: str, *, note: str | None = None,
                    disposition: str | None = None, evidence_refs: list[str],
                    authorization_ref: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(idempotency_key,str) or not idempotency_key.strip() or len(idempotency_key)>512:
            raise ValueError("action idempotency key is required")
        transition_key = "ack_idempotency_key" if state=="acknowledged" else "resolution_idempotency_key"
        now = datetime.now(timezone.utc)
        if (not isinstance(authorization_ref,dict) or authorization_ref.get("allowed") is not True
                or authorization_ref.get("actor_id")!=recipient_id
                or not authorization_ref.get("decision_id")):
            raise NotificationForbidden("durable action requires a successful recipient authorization reference")
        with self.connect(self.dsn, row_factory=dict_row) as conn, conn.transaction():
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (f"{delivery_id}:{state}",))
            row = conn.execute("SELECT * FROM r3a_notification.deliveries WHERE delivery_id=%s FOR UPDATE",
                               (uuid.UUID(delivery_id),)).fetchone()
            if not row or row["recipient_id"] != recipient_id:
                raise NotificationForbidden("notification is not visible to this authenticated recipient")
            if row[transition_key]:
                if row[transition_key] != idempotency_key:
                    raise NotificationConflict("notification already has a different durable action key")
                return self._as_delivery(row, duplicate=True)
            if state=="resolved" and row["status"]!="acknowledged":
                raise ValueError("notification must be acknowledged before resolution")
            if state=="acknowledged" and row["status"]!="queued":
                raise ValueError("notification is not awaiting acknowledgment")
            updates = {"status":state,transition_key:idempotency_key}
            if state=="acknowledged":
                updates.update(acknowledged_at=now,acknowledged_by=recipient_id,ack_note=note,
                               acknowledgment_authorization=json.dumps(authorization_ref))
            else:
                updates.update(resolved_at=now,resolved_by=recipient_id,disposition=disposition,
                               evidence_refs=json.dumps(evidence_refs),
                               resolution_authorization=json.dumps(authorization_ref))
            assignments=",".join(f"{key}=%s" for key in updates)
            conn.execute(f"UPDATE r3a_notification.deliveries SET {assignments} WHERE delivery_id=%s",
                         (*updates.values(),uuid.UUID(delivery_id)))
            event_id=uuid.uuid5(uuid.NAMESPACE_URL,f"r3a.notification.event:{delivery_id}:{state}:{idempotency_key}")
            conn.execute("""INSERT INTO r3a_notification.delivery_events
                (event_id,event_type,delivery_id,actor_id,occurred_at,evidence)
                VALUES (%s,%s,%s,%s,%s,%s)""",
                (event_id,f"notification.delivery.{state}",uuid.UUID(delivery_id),recipient_id,now,
                 json.dumps({"idempotency_key":idempotency_key,"note":note,"disposition":disposition,
                             "evidence_refs":evidence_refs,"authorization":authorization_ref})))
            row=conn.execute("SELECT * FROM r3a_notification.deliveries WHERE delivery_id=%s",
                             (uuid.UUID(delivery_id),)).fetchone()
            return self._as_delivery(row, duplicate=False)

    @staticmethod
    def _as_delivery(row: dict[str, Any], *, duplicate: bool | None = None) -> dict[str, Any]:
        raw = row["notification"]
        if isinstance(raw,str): raw=json.loads(raw)
        value = {"contract_id":"r3a.notification-delivery","contract_version":"1.0.0",
                 "delivery_id":str(row["delivery_id"]),"idempotency_key":row["idempotency_key"],
                 "recipient":{"kind":row["recipient_kind"],"recipient_id":row["recipient_id"]},
                 "source_id":row["source_id"],"source_event_id":str(row["source_event_id"]),
                 "event_type":row["event_type"],"notification_event_id":raw["event_id"],
                 "correlation_id":str(row["correlation_id"]),"severity":row["severity"],
                 "urgency":row["urgency"],"requires_action":row["requires_action"],
                 "status":row["status"],"created_at":_utc(row["created_at"]),
                 "directory_snapshot_sha256":row["directory_snapshot_sha256"],
                 "acknowledged_at":_utc(row["acknowledged_at"]) if row["acknowledged_at"] else None,
                 "acknowledged_by":row["acknowledged_by"],"resolved_at":_utc(row["resolved_at"]) if row["resolved_at"] else None,
                 "acknowledgment_authorization":row["acknowledgment_authorization"],
                 "resolved_by":row["resolved_by"],"resolution_authorization":row["resolution_authorization"],
                 "evidence_refs":list(row["evidence_refs"] or []),
                 "notification":raw}
        if duplicate is not None: value["duplicate"]=duplicate
        return value


def _matches_filter(notification: dict[str, Any], event_filter: dict[str, Any]) -> bool:
    evidence = notification.get("evidence", {})
    if event_filter.get("activity_type") is not None:
        if evidence.get("activity_type") != event_filter["activity_type"]:
            return False
    for field, expected in event_filter.get("evidence_equals", {}).items():
        if evidence.get(field) != expected:
            return False
    return True
