"""Durable R3A workflow-packet storage, separate from institutional authorities."""
from __future__ import annotations

import json
import uuid
from typing import Any

from .onboarding import (DuplicateOnboarding, OnboardingIdempotencyConflict,
                         OnboardingRevisionConflict, validate_packet)


class PostgresResidentOnboardingRepository:
    """Persist packet projections and audit events through the supplied R3A pool.

    The repository has no HR/directory/credential/grant write capability. It must
    be composed with the installed R3A Store pool and a server-side authorizer.
    """

    def __init__(self, pool: Any):
        if not callable(getattr(pool, "connection", None)):
            raise TypeError("R3A PostgreSQL connection pool is required")
        self._pool = pool

    async def create_packet(self, packet: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
        validate_packet(packet)
        async with self._pool.connection() as conn, conn.transaction():
            inserted = await (await conn.execute(
                "INSERT INTO r3a.resident_onboarding_packets "
                "(packet_id,resident_id,lifecycle_state,packet_revision,create_idempotency_key,packet) "
                "VALUES (%s,%s,%s,%s,%s,%s::jsonb) ON CONFLICT DO NOTHING RETURNING packet_id",
                (packet["packet_id"], packet["resident_id"], packet["state"],
                 packet["packet_revision"], packet["create_idempotency_key"],
                 json.dumps(packet, sort_keys=True)),
            )).fetchone()
            if not inserted:
                prior = await (await conn.execute(
                    "SELECT packet FROM r3a.resident_onboarding_packets "
                    "WHERE create_idempotency_key=%s OR packet_id=%s",
                    (packet["create_idempotency_key"], packet["packet_id"]),
                )).fetchone()
                if prior:
                    saved = _json_value(prior["packet"])
                    if _create_request(saved) == _create_request(packet):
                        return saved
                    raise OnboardingIdempotencyConflict("create idempotency key conflicts with an existing packet")
                if packet["resident_id"]:
                    active = await (await conn.execute(
                        "SELECT packet_id FROM r3a.resident_onboarding_packets "
                        "WHERE resident_id=%s AND lifecycle_state NOT IN ('REVOKED','OFFBOARDED')",
                        (packet["resident_id"],),
                    )).fetchone()
                    if active:
                        raise DuplicateOnboarding("a nonterminal onboarding packet already exists for this resident")
                raise OnboardingIdempotencyConflict("packet identifier or request key is already in use")
            await _insert_event(conn, packet["packet_id"], event, packet)
        return packet

    async def get_packet(self, packet_id: str) -> dict[str, Any] | None:
        async with self._pool.connection() as conn:
            row = await (await conn.execute(
                "SELECT packet FROM r3a.resident_onboarding_packets WHERE packet_id=%s",
                (packet_id,),
            )).fetchone()
        return validate_packet(_json_value(row["packet"])) if row else None

    async def transition_packet(self, packet: dict[str, Any], *, expected_revision: int,
                                event: dict[str, Any]) -> dict[str, Any]:
        validate_packet(packet)
        async with self._pool.connection() as conn, conn.transaction():
            row = await (await conn.execute(
                "SELECT packet,packet_revision FROM r3a.resident_onboarding_packets "
                "WHERE packet_id=%s FOR UPDATE", (packet["packet_id"],),
            )).fetchone()
            if row is None:
                raise KeyError("resident onboarding packet not found")
            saved = validate_packet(_json_value(row["packet"]))
            replay = await (await conn.execute(
                "SELECT event FROM r3a.resident_onboarding_events "
                "WHERE packet_id=%s AND idempotency_key=%s",
                (packet["packet_id"], event["idempotency_key"]),
            )).fetchone()
            if replay:
                if _event_request(_json_value(replay["event"])) != _event_request(event):
                    raise OnboardingIdempotencyConflict("transition idempotency key was reused with different evidence")
                return saved
            if row["packet_revision"] != expected_revision:
                raise OnboardingRevisionConflict("resident onboarding packet revision changed")
            if packet["packet_revision"] != expected_revision + 1:
                raise OnboardingRevisionConflict("successor packet revision is not the expected next revision")
            try:
                updated = await (await conn.execute(
                    "UPDATE r3a.resident_onboarding_packets SET lifecycle_state=%s,packet_revision=%s,"
                    "resident_id=%s,packet=%s::jsonb,updated_at=%s "
                    "WHERE packet_id=%s AND packet_revision=%s RETURNING packet_id",
                    (packet["state"], packet["packet_revision"], packet["resident_id"],
                     json.dumps(packet, sort_keys=True), packet["updated_at"],
                     packet["packet_id"], expected_revision),
                )).fetchone()
            except Exception as exc:
                if getattr(exc, "sqlstate", None) == "23505":
                    raise DuplicateOnboarding("a nonterminal onboarding packet already exists for this resident") from exc
                raise
            if not updated:
                raise OnboardingRevisionConflict("resident onboarding packet compare-and-swap failed")
            await _insert_event(conn, packet["packet_id"], event, packet)
        return packet


def _create_request(packet: dict[str, Any]) -> dict[str, Any]:
    """Compare only immutable request semantics during a create retry."""
    return {key: packet.get(key) for key in (
        "packet_id", "create_idempotency_key", "request_context", "created_at")}


def _event_request(event: dict[str, Any]) -> dict[str, Any]:
    """Compare caller-controlled request semantics; occurrence time is server-generated."""
    return {key: value for key, value in event.items() if key != "occurred_at"}


def _json_value(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


async def _insert_event(conn: Any, packet_id: str, event: dict[str, Any],
                        packet_snapshot: dict[str, Any]) -> None:
    await conn.execute(
        "INSERT INTO r3a.resident_onboarding_events "
        "(event_id,packet_id,idempotency_key,correlation_id,actor_ref,actor_role,action,prior_state,"
        "next_state,expected_revision,occurred_at,reason_ref,approval_ref,evidence_refs,event,packet_snapshot) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb)",
        (event["event_id"], packet_id, event["idempotency_key"], event["correlation_id"],
         event["actor_ref"], event["actor_role"], event["action"], event["from_state"],
         event["to_state"], event["expected_revision"], event["occurred_at"],
         event["reason_ref"], event["approval_ref"], json.dumps(event["evidence_refs"]),
         json.dumps(event, sort_keys=True), json.dumps(packet_snapshot, sort_keys=True)),
    )
