"""Transactional PostgreSQL persistence for governed resident character revisions.

This adapter stores dossier components keyed by canonical HR IDs. It does not
create identities or authenticate actors; callers must pass through the
institutional identity and authorization gateways before invoking mutations.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from typing import Any, Callable

from .repository import DossierError, RevisionConflict
from .validation import validate_dossier


_SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
_TRANSITIONS = {
    "proposed": {"submitted_for_review", "rejected"},
    "submitted_for_review": {"approved", "rejected"},
    "approved": {"published", "rejected"},
    "published": {"activated", "superseded"},
    "active": {"superseded", "rollback"},
    "rejected": set(),
    "superseded": {"rollback"},
}
_EVENT_STATES = {
    "created": "proposed", "proposed": "proposed",
    "submitted_for_review": "submitted_for_review", "approved": "approved",
    "rejected": "rejected", "published": "published", "activated": "active",
    "superseded": "superseded", "rollback": "active",
}


class PostgresDossierRepository:
    """Append-only revision/event store with an activated-version pointer.

    ``connect`` must return a psycopg-compatible connection to the isolated or
    authorized R3A database. This repository does not open connections itself,
    so callers can bind the correct least-privilege database role.
    """

    def __init__(self, connect: Callable[[], Any]):
        if not callable(connect):
            raise TypeError("a configured PostgreSQL connection factory is required")
        self._connect = connect

    def list_ids(self) -> tuple[str, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT DISTINCT resident_id FROM r3a.resident_dossier_revisions ORDER BY resident_id"
            ).fetchall()
        return tuple(row[0] for row in rows)

    def get(self, resident_id: str, revision: str | None = None) -> dict[str, Any]:
        with self._connect() as connection:
            if revision is None:
                row = connection.execute(
                    "SELECT r.dossier,(SELECT e.event_type FROM r3a.resident_dossier_events e "
                    "WHERE e.resident_id=r.resident_id AND e.dossier_revision=r.dossier_revision "
                    "ORDER BY e.event_sequence DESC LIMIT 1) "
                    "FROM r3a.resident_dossier_current c "
                    "JOIN r3a.resident_dossier_revisions r USING (resident_id,dossier_revision) "
                    "WHERE c.resident_id=%s", (resident_id,),
                ).fetchone()
            else:
                row = connection.execute(
                    "SELECT r.dossier,(SELECT e.event_type FROM r3a.resident_dossier_events e "
                    "WHERE e.resident_id=r.resident_id AND e.dossier_revision=r.dossier_revision "
                    "ORDER BY e.event_sequence DESC LIMIT 1) "
                    "FROM r3a.resident_dossier_revisions r "
                    "WHERE r.resident_id=%s AND r.dossier_revision=%s", (resident_id, revision),
                ).fetchone()
        if row is None:
            raise KeyError(resident_id if revision is None else f"{resident_id}@{revision}")
        dossier, latest_event = row
        if isinstance(dossier, str):
            dossier = json.loads(dossier)
        dossier = json.loads(json.dumps(dossier))
        if latest_event is not None:
            dossier.setdefault("governance", {})["approval_status"] = _EVENT_STATES[latest_event]
        validate_dossier(dossier)
        return dossier

    def revision_digest(self, resident_id: str, revision: str) -> str:
        """Return the immutable persisted digest for a dossier revision."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT dossier_sha256 FROM r3a.resident_dossier_revisions "
                "WHERE resident_id=%s AND dossier_revision=%s", (resident_id, revision),
            ).fetchone()
        if not row:
            raise KeyError(f"{resident_id}@{revision}")
        return row[0].strip()

    def has_activation(self, resident_id: str, revision: str) -> bool:
        """Whether an immutable activation event exists for this exact revision."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM r3a.resident_dossier_events WHERE resident_id=%s "
                "AND dossier_revision=%s AND event_type='activated' LIMIT 1",
                (resident_id, revision),
            ).fetchone()
        return row is not None

    def history(self, resident_id: str) -> tuple[dict[str, Any], ...]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT event_sequence,event_id::text,event_type,dossier_revision,prior_revision,"
                "actor_ref,owner_domain,occurred_at,reason,source_refs,evidence "
                "FROM r3a.resident_dossier_events WHERE resident_id=%s "
                "ORDER BY event_sequence", (resident_id,),
            ).fetchall()
        result = []
        for row in rows:
            source_refs, evidence = row[9], row[10]
            result.append({
                "sequence": row[0], "event_id": row[1], "event_type": row[2],
                "revision": row[3], "prior_revision": row[4], "actor_ref": row[5],
                "owner_domain": row[6], "occurred_at": row[7].isoformat(),
                "reason": row[8], "source_refs": source_refs,
                "evidence": evidence,
            })
        return tuple(result)

    def pin_context(self, *, resident_id: str, revision: str, dossier_sha256: str,
                    execution_kind: str, execution_ref: str, identity_revision: str,
                    directory_resident_id: str, binding_revision: int,
                    directory_snapshot_sha256: str, directory_source_ref: str,
                    hr_source_ref: str, hr_principal_association_ref: str,
                    office_id: str, office_role: str,
                    execution_profile_id: str, execution_profile_revision: str,
                    execution_profile_resident_id: str, execution_route_id: str,
                    execution_profile_source_ref: str,
                    provider_id: str, principal_ref: str) -> dict[str, Any]:
        """Pin one immutable approved revision to an inference/conversation boundary.

        Repeated calls for the same boundary are idempotent only when every identity,
        revision, provider, and digest value matches. A later activation cannot silently
        move an existing execution boundary to a different character revision.
        """
        if execution_kind not in {"inference_activity", "conversation_boundary"}:
            raise ValueError("unsupported character context execution boundary")
        required = (resident_id, revision, dossier_sha256, execution_ref,
                    identity_revision, directory_resident_id, directory_source_ref,
                    hr_source_ref, hr_principal_association_ref, office_id, office_role,
                    execution_profile_id, execution_profile_revision,
                    execution_profile_resident_id, execution_route_id,
                    execution_profile_source_ref,
                    provider_id, principal_ref)
        if any(not isinstance(value, str) or not value.strip() for value in required):
            raise ValueError("character context pin requires identity and revision references")
        if not re.fullmatch(r"[a-f0-9]{64}", dossier_sha256):
            raise ValueError("character context dossier digest is invalid")
        if not isinstance(directory_snapshot_sha256, str) or not re.fullmatch(
                r"[a-f0-9]{64}", directory_snapshot_sha256):
            raise ValueError("directory snapshot digest is required for an identity pin")
        if type(binding_revision) is not int or binding_revision < 1:
            raise ValueError("authoritative office binding revision is required")
        with self._connect() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (resident_id,))
            row = connection.execute(
                "SELECT p.pin_id::text,p.dossier_revision,p.dossier_sha256,p.identity_revision,"
                "p.directory_resident_id,p.binding_revision,p.provider_id,p.principal_ref,"
                "p.directory_snapshot_sha256,p.directory_source_ref,p.hr_source_ref,"
                "p.hr_principal_association_ref,p.office_id,p.office_role,"
                "p.execution_profile_id,p.execution_profile_revision,p.execution_profile_resident_id,"
                "p.execution_route_id,p.execution_profile_source_ref "
                "FROM r3a.resident_character_context_pins p "
                "WHERE p.resident_id=%s AND p.execution_kind=%s AND p.execution_ref=%s FOR UPDATE",
                (resident_id, execution_kind, execution_ref),
            ).fetchone()
            if row:
                existing = (row[1], row[2].strip(), row[3], row[4], row[5], row[6], row[7])
                requested = (revision, dossier_sha256, identity_revision,
                             directory_resident_id, binding_revision, provider_id, principal_ref)
                existing_evidence = (row[8].strip() if row[8] else None, *row[9:14])
                requested_evidence = (directory_snapshot_sha256, directory_source_ref,
                                      hr_source_ref, hr_principal_association_ref, office_id, office_role)
                existing_profile = tuple(row[14:19])
                requested_profile = (execution_profile_id, execution_profile_revision,
                                     execution_profile_resident_id, execution_route_id,
                                     execution_profile_source_ref)
                if (existing != requested or existing_evidence != requested_evidence
                        or existing_profile != requested_profile):
                    raise RevisionConflict("execution boundary is already pinned to another identity or character revision")
                return {"pin_id": row[0], "resident_id": resident_id,
                        "dossier_revision": row[1], "dossier_sha256": row[2].strip(),
                        "identity_revision": row[3], "directory_resident_id": row[4],
                        "binding_revision": row[5], "provider_id": row[6],
                        "principal_ref": row[7], "execution_kind": execution_kind,
                        "execution_ref": execution_ref, "created": False,
                        "directory_snapshot_sha256": row[8].strip() if row[8] else None,
                        "directory_source_ref": row[9], "hr_source_ref": row[10],
                        "hr_principal_association_ref": row[11],
                        "office_id": row[12], "office_role": row[13],
                        "execution_profile_id": row[14],
                        "execution_profile_revision": row[15],
                        "execution_profile_resident_id": row[16],
                        "execution_route_id": row[17],
                        "execution_profile_source_ref": row[18]}
            active = connection.execute(
                "SELECT r.dossier_sha256 FROM r3a.resident_dossier_current c "
                "JOIN r3a.resident_dossier_revisions r USING (resident_id,dossier_revision) "
                "WHERE c.resident_id=%s AND c.dossier_revision=%s FOR UPDATE OF c",
                (resident_id, revision),
            ).fetchone()
            if not active or active[0].strip() != dossier_sha256:
                raise RevisionConflict("only the currently activated, digest-matching dossier can start a new boundary")
            latest = connection.execute(
                "SELECT event_type FROM r3a.resident_dossier_events "
                "WHERE resident_id=%s AND dossier_revision=%s ORDER BY event_sequence DESC LIMIT 1",
                (resident_id, revision),
            ).fetchone()
            if not latest or latest[0] != "activated":
                raise RevisionConflict("dossier revision is not approved and active")
            pin_id = str(uuid.uuid4())
            connection.execute(
                "INSERT INTO r3a.resident_character_context_pins "
                "(pin_id,resident_id,dossier_revision,dossier_sha256,execution_kind,execution_ref,"
                "identity_revision,directory_resident_id,binding_revision,provider_id,principal_ref,"
                "directory_snapshot_sha256,directory_source_ref,hr_source_ref,"
                "hr_principal_association_ref,office_id,office_role,execution_profile_id,"
                "execution_profile_revision,execution_profile_resident_id,execution_route_id,"
                "execution_profile_source_ref) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (pin_id, resident_id, revision, dossier_sha256, execution_kind,
                 execution_ref, identity_revision, directory_resident_id, binding_revision,
                 provider_id, principal_ref, directory_snapshot_sha256, directory_source_ref,
                 hr_source_ref, hr_principal_association_ref, office_id, office_role,
                 execution_profile_id, execution_profile_revision,
                 execution_profile_resident_id, execution_route_id,
                 execution_profile_source_ref),
            )
        return {"pin_id": pin_id, "resident_id": resident_id,
                "dossier_revision": revision, "dossier_sha256": dossier_sha256,
                "identity_revision": identity_revision,
                "directory_resident_id": directory_resident_id,
                "binding_revision": binding_revision,
                "directory_snapshot_sha256": directory_snapshot_sha256,
                "directory_source_ref": directory_source_ref, "hr_source_ref": hr_source_ref,
                "hr_principal_association_ref": hr_principal_association_ref,
                "office_id": office_id, "office_role": office_role,
                "execution_profile_id": execution_profile_id,
                "execution_profile_revision": execution_profile_revision,
                "execution_profile_resident_id": execution_profile_resident_id,
                "execution_route_id": execution_route_id,
                "execution_profile_source_ref": execution_profile_source_ref,
                "provider_id": provider_id,
                "principal_ref": principal_ref, "execution_kind": execution_kind,
                "execution_ref": execution_ref, "created": True}

    def get_context_pin(self, *, resident_id: str, execution_kind: str,
                        execution_ref: str) -> dict[str, Any] | None:
        """Retrieve the immutable revision pinned to an existing execution boundary."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT pin_id::text,dossier_revision,dossier_sha256,identity_revision,"
                "directory_resident_id,binding_revision,provider_id,principal_ref,created_at,"
                "directory_snapshot_sha256,directory_source_ref,hr_source_ref,"
                "hr_principal_association_ref,office_id,office_role,execution_profile_id,"
                "execution_profile_revision,execution_profile_resident_id,execution_route_id,"
                "execution_profile_source_ref "
                "FROM r3a.resident_character_context_pins "
                "WHERE resident_id=%s AND execution_kind=%s AND execution_ref=%s",
                (resident_id, execution_kind, execution_ref),
            ).fetchone()
        if not row:
            return None
        return {"pin_id": row[0], "resident_id": resident_id, "dossier_revision": row[1],
                "dossier_sha256": row[2].strip(), "identity_revision": row[3],
                "directory_resident_id": row[4], "binding_revision": row[5],
                "provider_id": row[6], "principal_ref": row[7],
                "created_at": row[8].isoformat(), "execution_kind": execution_kind,
                "execution_ref": execution_ref, "created": False,
                "directory_snapshot_sha256": row[9].strip() if row[9] else None,
                "directory_source_ref": row[10], "hr_source_ref": row[11],
                "hr_principal_association_ref": row[12],
                "office_id": row[13], "office_role": row[14],
                "execution_profile_id": row[15], "execution_profile_revision": row[16],
                "execution_profile_resident_id": row[17], "execution_route_id": row[18],
                "execution_profile_source_ref": row[19]}

    def revision_metadata(self, resident_id: str, revision: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT created_by,hr_identity_revision FROM r3a.resident_dossier_revisions "
                "WHERE resident_id=%s AND dossier_revision=%s", (resident_id, revision),
            ).fetchone()
            proposal = connection.execute(
                "SELECT evidence FROM r3a.resident_dossier_events "
                "WHERE resident_id=%s AND dossier_revision=%s AND event_type='proposed' "
                "ORDER BY event_sequence LIMIT 1", (resident_id, revision),
            ).fetchone()
        if row is None or proposal is None:
            raise KeyError(f"{resident_id}@{revision}")
        evidence = proposal[0]
        if isinstance(evidence, str):
            evidence = json.loads(evidence)
        return {"author_id": row[0], "hr_identity_revision": row[1],
                "durable_canon_change": bool(evidence.get("durable_canon_change"))}

    def propose(self, dossier: dict[str, Any], *, expected_active_revision: str | None,
                hr_identity_revision: str, actor_ref: str, reason: str,
                source_refs: tuple[str, ...], durable_canon_change: bool) -> str:
        validate_dossier(dossier)
        resident_id, revision = dossier["identity"]["resident_id"], dossier["revision"]
        if not _SEMVER.fullmatch(revision):
            raise DossierError("revision must be semantic version x.y.z")
        if not all(isinstance(value, str) and value.strip() for value in
                   (resident_id, hr_identity_revision, actor_ref, reason)):
            raise ValueError("canonical identity revision, actor, and reason are required")
        if not source_refs or any(not isinstance(ref, str) or not ref.strip() for ref in source_refs):
            raise ValueError("proposal requires source references")
        stored_dossier = json.loads(json.dumps(dossier))
        governance = stored_dossier.setdefault("governance", {})
        governance["approval_status"] = "proposed"
        governance["revision_actor"] = actor_ref
        governance["revision_reason"] = reason
        governance.setdefault("revision_history", []).append({
            "revision": revision, "status": "proposed", "actor": actor_ref, "reason": reason,
        })
        payload = json.dumps(stored_dossier, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        with self._connect() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (resident_id,))
            row = connection.execute(
                "SELECT dossier_revision FROM r3a.resident_dossier_current WHERE resident_id=%s FOR UPDATE",
                (resident_id,),
            ).fetchone()
            current = row[0] if row else None
            if current != expected_active_revision:
                raise RevisionConflict("active resident revision changed before proposal")
            pending = connection.execute(
                "SELECT r.dossier_revision FROM r3a.resident_dossier_revisions r "
                "JOIN LATERAL (SELECT event_type FROM r3a.resident_dossier_events e "
                "WHERE e.resident_id=r.resident_id AND e.dossier_revision=r.dossier_revision "
                "ORDER BY event_sequence DESC LIMIT 1) latest ON TRUE "
                "WHERE r.resident_id=%s AND latest.event_type IN "
                "('proposed','submitted_for_review','approved','published') LIMIT 1",
                (resident_id,),
            ).fetchone()
            if pending:
                raise RevisionConflict(f"resident has an unresolved character revision: {pending[0]}")
            connection.execute(
                "INSERT INTO r3a.resident_dossier_revisions "
                "(resident_id,dossier_revision,schema_version,dossier,dossier_sha256,approval_status,"
                "hr_identity_revision,source_refs,created_by,supersedes_revision) "
                "VALUES (%s,%s,%s,%s::jsonb,%s,'proposed',%s,%s::jsonb,%s,%s)",
                (resident_id, revision, stored_dossier["schema_version"], payload, digest,
                 hr_identity_revision, json.dumps(source_refs), actor_ref, current),
            )
            self._append_event(connection, resident_id, "proposed", revision, current,
                               actor_ref, "character_architecture", reason, source_refs,
                               {"sha256": digest, "durable_canon_change": durable_canon_change})
        return revision

    def transition(self, resident_id: str, revision: str, *, event_type: str,
                   actor_ref: str, owner_domain: str, reason: str,
                   source_refs: tuple[str, ...] = (), evidence: dict[str, Any] | None = None) -> None:
        if event_type not in _EVENT_STATES or event_type == "created":
            raise ValueError("unsupported dossier workflow event")
        with self._connect() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (resident_id,))
            found = connection.execute(
                "SELECT 1 FROM r3a.resident_dossier_revisions "
                "WHERE resident_id=%s AND dossier_revision=%s", (resident_id, revision),
            ).fetchone()
            if found is None:
                raise KeyError(f"{resident_id}@{revision}")
            last = connection.execute(
                "SELECT event_type FROM r3a.resident_dossier_events "
                "WHERE resident_id=%s AND dossier_revision=%s "
                "ORDER BY event_sequence DESC LIMIT 1", (resident_id, revision),
            ).fetchone()
            prior_state = _EVENT_STATES[last[0]] if last else "proposed"
            if event_type not in _TRANSITIONS.get(prior_state, set()):
                raise DossierError(f"invalid character revision transition: {prior_state} -> {event_type}")
            prior_revision = None
            if event_type == "activated":
                prior = connection.execute(
                    "SELECT dossier_revision FROM r3a.resident_dossier_current "
                    "WHERE resident_id=%s FOR UPDATE", (resident_id,),
                ).fetchone()
                prior_revision = prior[0] if prior else None
                connection.execute(
                    "INSERT INTO r3a.resident_dossier_current "
                    "(resident_id,dossier_revision,changed_by) VALUES (%s,%s,%s) "
                    "ON CONFLICT (resident_id) DO UPDATE SET dossier_revision=EXCLUDED.dossier_revision,"
                    "changed_by=EXCLUDED.changed_by,changed_at=clock_timestamp()",
                    (resident_id, revision, actor_ref),
                )
                if prior_revision and prior_revision != revision:
                    self._append_event(connection, resident_id, "superseded", prior_revision,
                                       revision, actor_ref, owner_domain,
                                       "Superseded by activated revision " + revision,
                                       source_refs, {"replacement_revision": revision})
            elif event_type == "rollback":
                current = connection.execute(
                    "SELECT dossier_revision FROM r3a.resident_dossier_current "
                    "WHERE resident_id=%s FOR UPDATE", (resident_id,),
                ).fetchone()
                if current is None:
                    raise DossierError("cannot roll back without an active dossier revision")
                prior_revision = current[0]
                connection.execute(
                    "UPDATE r3a.resident_dossier_current SET dossier_revision=%s,changed_by=%s,"
                    "changed_at=clock_timestamp() WHERE resident_id=%s",
                    (revision, actor_ref, resident_id),
                )
                if prior_revision and prior_revision != revision:
                    self._append_event(connection, resident_id, "superseded", prior_revision,
                                       revision, actor_ref, owner_domain,
                                       "Superseded by rollback to revision " + revision,
                                       source_refs, {"rollback_target_revision": revision})
            self._append_event(connection, resident_id, event_type, revision, prior_revision,
                               actor_ref, owner_domain, reason, source_refs, evidence or {})

    @staticmethod
    def _append_event(connection: Any, resident_id: str, event_type: str, revision: str,
                      prior_revision: str | None, actor_ref: str, owner_domain: str,
                      reason: str, source_refs: tuple[str, ...], evidence: dict[str, Any]) -> None:
        connection.execute(
            "INSERT INTO r3a.resident_dossier_events "
            "(event_id,resident_id,event_type,dossier_revision,prior_revision,actor_ref,owner_domain,"
            "occurred_at,reason,source_refs,evidence) VALUES (%s,%s,%s,%s,%s,%s,%s,"
            "clock_timestamp(),%s,%s::jsonb,%s::jsonb)",
            (str(uuid.uuid4()), resident_id, event_type, revision, prior_revision, actor_ref,
             owner_domain, reason, json.dumps(source_refs), json.dumps(evidence, sort_keys=True)),
        )
