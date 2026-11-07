"""
R3 CONTROLLED SOURCE
File: r3a_runtime/db.py
Component: R3A-POSTGRES-PERSISTENCE
File Revision: 1.2.0
Created: 2026-11-06T15:06:00Z
Created By: Codex GPT-6
Purpose: Provide PostgreSQL migrations, versioned state transitions, events, registries, and activity recovery.
Execution Model: Async Psycopg 3 connection pool.
Observability: PostgreSQL current-state projections, append-only events, migrations, and activity lineage.
Dependencies: psycopg 3; PostgreSQL; r3a_runtime.config.
Authority: AP0-M1 Issue #42, AP1-M1 Issue #43, and AP1 Slices 1–2 Issue #45 authorized by Steward; R3A database only.
Changed: 2026-11-06T15:06:00Z | R3A-AP0-M1 | Codex GPT-6 | Add durable PostgreSQL store.
Changed: 2026-11-06T15:46:11Z | R3A-AP0-M1 | Codex GPT-6 | Add validated machine definitions, idempotent grants/lifecycle, retry-safe leases and guarded state/event commits.
Changed: 2026-11-06 | R3A-AP1-M1 | Codex GPT-6 | Persist Grace objective inputs/results, deduplicate intake and renew activity/resource leases.
Changed: 2026-11-06T18:02:08Z | R3A-019 | Codex GPT-6 | Persist idempotent objective and notification event metadata in the existing activity ledger.
Changed: 2026-11-06T18:09:37Z | R3A-019 | Codex GPT-6 | Return the durable activity checkpoint to recovered workers.
Changed: 2026-11-06T23:19:46Z | R3A-AP1-SLICE-1 | Codex GPT-6 | Persist model-role observations and use existing WAITING lifecycle for durable role deferral.
Changed: 2026-11-06T23:43:25Z | R3A-AP1-SLICE-1 | Codex GPT-6 | Preserve role readiness in existing registries and atomically requeue or block deferred activities.
Changed: 2026-11-06T23:46:49Z | R3A-AP1-SLICE-1 | Codex GPT-6 | Consolidate model-role deferral operations into one durable state-transition method.
Changed: 2026-11-07T00:20:59Z | R3A-AP1-SLICE-2 | Codex GPT-6 | Persist provider/model identity and evidence; invalidate incompatible prior readiness in the existing registry.
Supersedes: None.
Contracts: AP0-003–010; R3A-019; AP0-M1 D2/D4/D6/D7/D9; STM-001–STM-007; r3a.model-role.v1; r3a.model-readiness.v2; r3a.model-readiness-provider.v1.
Tests: tests/test_r3a_ap1.py; tests/test_r3a_modular_autonomy.py.
History/Predecessor: Git blob 89d7a15f1b63874846bd036ed0acfcbd1b68d2f8 at commit ad16700f1e94dd36c81cac5383f9f2e2771a98a1.
"""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from .config import Settings, sanitized_config
from .contracts import ReadinessObservation, parse_timestamp


IMPLEMENTATION_REVISION = os.environ.get("R3A_IMPLEMENTATION_REVISION", "working-tree")


class InvalidTransition(RuntimeError):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Store:
    def __init__(self, settings: Settings):
        self.settings = settings
        from psycopg.conninfo import make_conninfo

        self.conninfo = make_conninfo(**settings.connection_info)
        self.pool = AsyncConnectionPool(self.conninfo, min_size=1, max_size=max(2, settings.worker_concurrency + 1), open=False, kwargs={"row_factory": dict_row})

    async def open(self) -> None:
        await self.pool.open()
        await self.pool.wait()

    async def close(self) -> None:
        await self.pool.close()

    async def migrate(self) -> list[str]:
        """Apply checked-in SQL exactly once under a PostgreSQL advisory lock."""
        applied: list[str] = []
        async with await AsyncConnection.connect(self.conninfo, autocommit=True, row_factory=dict_row) as conn:
            await conn.execute("CREATE SCHEMA IF NOT EXISTS r3a AUTHORIZATION CURRENT_USER")
            await conn.execute("CREATE TABLE IF NOT EXISTS r3a.schema_migrations (version text PRIMARY KEY, checksum char(64) NOT NULL, applied_at timestamptz NOT NULL DEFAULT clock_timestamp())")
            migration_dir = Path(__file__).parent / "migrations"
            for path in sorted(migration_dir.glob("*.sql")):
                sql = path.read_text(encoding="utf-8")
                checksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()
                async with conn.transaction():
                    await conn.execute("SELECT pg_advisory_xact_lock(hashtextextended('r3a-ap0-m1-migrations', 0))")
                    row = await (await conn.execute("SELECT checksum FROM r3a.schema_migrations WHERE version=%s", (path.name,))).fetchone()
                    if row:
                        if row["checksum"].strip() != checksum:
                            raise RuntimeError(f"Applied migration {path.name} checksum changed")
                        continue
                    await conn.execute(sql)
                    await conn.execute("INSERT INTO r3a.schema_migrations(version,checksum) VALUES (%s,%s)", (path.name, checksum))
                    applied.append(path.name)
        return applied

    async def activate_config(self) -> str:
        config = sanitized_config(self.settings)
        revision_id = self.settings.source_digest
        async with self.pool.connection() as conn, conn.transaction():
            await conn.execute(
                "INSERT INTO r3a.config_revisions(revision_id,schema_version,config,source_path,source_digest,actor) "
                "VALUES (%s,1,%s,%s,%s,%s) ON CONFLICT (revision_id) DO NOTHING",
                (revision_id, json.dumps(config), str(self.settings.source_path), self.settings.source_digest, f"uid:{os.getuid()}"),
            )
            await conn.execute(
                "INSERT INTO r3a.config_current(singleton,revision_id) VALUES (true,%s) "
                "ON CONFLICT (singleton) DO UPDATE SET revision_id=EXCLUDED.revision_id,changed_at=clock_timestamp()",
                (revision_id,),
            )
            await self._event(conn, "config.activated", "config", revision_id, "config.lifecycle", 1,
                              None, "ACTIVE", "configuration activated", {"digest": self.settings.source_digest})
        return revision_id

    async def seed_machines(self) -> list[tuple[str, int, str]]:
        loaded = []
        for path in sorted(self.settings.machine_catalog_dir.glob("*.json")):
            raw = path.read_bytes()
            definition = json.loads(raw)
            machine_id = definition.get("machine_id")
            version = definition.get("machine_version")
            expected = {"machine_id", "machine_version", "states", "transitions", "terminal", "recoverable"}
            if not isinstance(definition, dict) or set(definition) != expected:
                raise RuntimeError(f"Invalid machine definition fields: {path}")
            states = definition["states"]
            transitions = definition["transitions"]
            terminal = definition["terminal"]
            recoverable = definition["recoverable"]
            if (not isinstance(machine_id, str) or not machine_id
                    or isinstance(version, bool) or not isinstance(version, int) or version < 1
                    or not isinstance(states, list) or not states
                    or any(not isinstance(state, str) or not state for state in states)
                    or len(set(states)) != len(states)
                    or not isinstance(transitions, dict) or set(transitions) - set(states)
                    or any(not isinstance(targets, list) or any(target not in states for target in targets)
                           for targets in transitions.values())
                    or not isinstance(terminal, list) or any(state not in states for state in terminal)
                    or not isinstance(recoverable, list) or any(state not in states for state in recoverable)):
                raise RuntimeError(f"Invalid machine definition: {path}")
            digest = hashlib.sha256(raw).hexdigest()
            normalized = json.dumps(definition, sort_keys=True)
            async with self.pool.connection() as conn, conn.transaction():
                existing = await (await conn.execute(
                    "SELECT digest FROM r3a.state_machine_definitions WHERE machine_id=%s AND machine_version=%s",
                    (machine_id, version),
                )).fetchone()
                if existing and existing["digest"].strip() != digest:
                    raise RuntimeError(f"Immutable state machine {machine_id} v{version} changed")
                await conn.execute(
                    "INSERT INTO r3a.state_machine_definitions(machine_id,machine_version,definition,digest) "
                    "VALUES (%s,%s,%s,%s) ON CONFLICT (machine_id,machine_version) DO NOTHING",
                    (machine_id, version, normalized, digest),
                )
            loaded.append((machine_id, version, digest))
        if not loaded:
            raise RuntimeError(f"No state-machine definitions found in {self.settings.machine_catalog_dir}")
        return loaded

    async def _event(self, conn, event_type: str, subject_type: str, subject_id: str,
                     machine_id: str | None, machine_version: int | None,
                     prior_state: str | None, next_state: str | None, reason: str,
                     evidence: dict[str, Any] | None = None, *, outcome: str = "accepted",
                     event_id: uuid.UUID | None = None, correlation_id: uuid.UUID | None = None,
                     causation_id: uuid.UUID | None = None) -> uuid.UUID:
        event_id = event_id or uuid.uuid4()
        current = await (await conn.execute("SELECT revision_id FROM r3a.config_current WHERE singleton=true")).fetchone()
        await conn.execute(
            "INSERT INTO r3a.institution_events(event_id,event_type,schema_version,subject_type,subject_id,"
            "machine_id,machine_version,prior_state,next_state,occurred_at,actor,correlation_id,causation_id,"
            "reason,outcome,config_revision,implementation_revision,evidence) VALUES "
            "(%s,%s,1,%s,%s,%s,%s,%s,%s,clock_timestamp(),%s,%s,%s,%s,%s,%s,%s,%s) "
            "ON CONFLICT (event_id) DO NOTHING",
            (event_id, event_type, subject_type, subject_id, machine_id, machine_version,
             prior_state, next_state, f"pid:{os.getpid()}", correlation_id or event_id,
             causation_id, reason, outcome, current["revision_id"] if current else None,
             IMPLEMENTATION_REVISION, json.dumps(evidence or {})),
        )
        return event_id

    async def transition(self, entity_type: str, entity_id: str, machine_id: str,
                         machine_version: int, next_state: str, reason: str,
                         evidence: dict[str, Any] | None = None,
                         *, initial: bool = False, event_id: uuid.UUID | None = None) -> bool:
        """Validate and persist transition plus event atomically, including rejected attempts."""
        event_id = event_id or uuid.uuid4()
        async with self.pool.connection() as conn, conn.transaction():
            return await self._transition_on_conn(conn, entity_type, entity_id, machine_id,
                                                  machine_version, next_state, reason, evidence,
                                                  initial=initial, event_id=event_id)

    async def _transition_on_conn(self, conn, entity_type: str, entity_id: str,
                                  machine_id: str, machine_version: int,
                                  next_state: str, reason: str,
                                  evidence: dict[str, Any] | None = None,
                                  *, initial: bool = False,
                                  event_id: uuid.UUID | None = None) -> bool:
        event_id = event_id or uuid.uuid4()
        definition_row = await (await conn.execute(
            "SELECT definition FROM r3a.state_machine_definitions WHERE machine_id=%s AND machine_version=%s",
            (machine_id, machine_version),
        )).fetchone()
        if definition_row is None:
            raise InvalidTransition(f"Unknown state machine {machine_id} v{machine_version}")
        definition = definition_row["definition"]
        row = await (await conn.execute(
            "SELECT state,version FROM r3a.runtime_entities WHERE entity_type=%s AND entity_id=%s FOR UPDATE",
            (entity_type, entity_id),
        )).fetchone()
        prior = row["state"] if row else None
        allowed = (next_state in definition["states"] if row is None and initial
                   else next_state in definition["transitions"].get(prior, []))
        if not allowed:
            await self._event(conn, "state.transition_rejected", entity_type, entity_id,
                              machine_id, machine_version, prior, next_state,
                              "transition is not allowed by the active versioned definition",
                              {"requested_reason": reason, "requested_evidence": evidence or {}},
                              outcome="rejected", event_id=event_id)
            return False
        current = await (await conn.execute(
            "SELECT revision_id FROM r3a.config_current WHERE singleton=true"
        )).fetchone()
        if row:
            await conn.execute(
                "UPDATE r3a.runtime_entities SET state=%s,details=%s,config_revision=%s,version=version+1,updated_at=clock_timestamp() "
                "WHERE entity_type=%s AND entity_id=%s",
                (next_state, json.dumps(evidence or {}), current["revision_id"] if current else None,
                 entity_type, entity_id),
            )
        else:
            await conn.execute(
                "INSERT INTO r3a.runtime_entities(entity_type,entity_id,machine_id,machine_version,state,details,config_revision) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (entity_type, entity_id, machine_id, machine_version, next_state,
                 json.dumps(evidence or {}), current["revision_id"] if current else None),
            )
        await self._event(conn, f"{entity_type}.state_transition", entity_type, entity_id,
                          machine_id, machine_version, prior, next_state, reason, evidence,
                          event_id=event_id)
        return True

    async def process_heartbeat(self, component_id: str, pid: int, state: str,
                                health: str, details: dict[str, Any] | None = None) -> None:
        async with self.pool.connection() as conn, conn.transaction():
            current = await (await conn.execute("SELECT revision_id FROM r3a.config_current WHERE singleton=true")).fetchone()
            await conn.execute(
                "INSERT INTO r3a.process_observations(component_id,pid,state,health,heartbeat_at,details,config_revision) "
                "VALUES (%s,%s,%s,%s,clock_timestamp(),%s,%s) ON CONFLICT(component_id) DO UPDATE SET "
                "pid=EXCLUDED.pid,state=EXCLUDED.state,health=EXCLUDED.health,heartbeat_at=EXCLUDED.heartbeat_at,"
                "details=EXCLUDED.details,config_revision=EXCLUDED.config_revision,updated_at=clock_timestamp()",
                (component_id, pid, state, health, json.dumps(details or {}), current["revision_id"] if current else None),
            )

    async def record_process_state(self, component_id: str, pid: int, state: str,
                                   health: str, reason: str,
                                   details: dict[str, Any] | None = None,
                                   *, initial: bool = False) -> bool:
        async with self.pool.connection() as conn, conn.transaction():
            prior = await (await conn.execute(
                "SELECT state FROM r3a.runtime_entities WHERE entity_type='process' AND entity_id=%s FOR UPDATE",
                (component_id,),
            )).fetchone()
            accepted = True
            if prior is None or prior["state"] != state:
                accepted = await self._transition_on_conn(
                    conn, "process", component_id, "process.lifecycle", 1, state, reason,
                    {"pid": pid, "health": health, **(details or {})}, initial=initial,
                )
            if accepted:
                current = await (await conn.execute(
                    "SELECT revision_id FROM r3a.config_current WHERE singleton=true"
                )).fetchone()
                await conn.execute(
                    "INSERT INTO r3a.process_observations(component_id,pid,state,health,heartbeat_at,details,config_revision) "
                    "VALUES (%s,%s,%s,%s,clock_timestamp(),%s,%s) ON CONFLICT(component_id) DO UPDATE SET "
                    "pid=EXCLUDED.pid,state=EXCLUDED.state,health=EXCLUDED.health,heartbeat_at=EXCLUDED.heartbeat_at,"
                    "details=EXCLUDED.details,config_revision=EXCLUDED.config_revision,updated_at=clock_timestamp()",
                    (component_id, pid, state, health, json.dumps(details or {}),
                     current["revision_id"] if current else None),
                )
            return accepted

    async def begin_process(self, component_id: str, pid: int) -> None:
        rows = await self.rows(
            "SELECT state FROM r3a.runtime_entities WHERE entity_type='process' AND entity_id=%s",
            (component_id,),
        )
        if not rows:
            await self.record_process_state(component_id, pid, "STARTING", "starting",
                                            "process start observed", initial=True)
            return
        state = rows[0]["state"]
        if state == "STARTING":
            await self.record_process_state(component_id, pid, "STARTING", "starting", "process start resumed")
            return
        if state == "STOPPED":
            await self.record_process_state(component_id, pid, "STARTING", "starting", "process restarted")
            return
        if state != "RESTARTING":
            await self.record_process_state(component_id, pid, "RESTARTING", "starting",
                                            "process start reconciled after prior instance", {"prior_state": state})
        await self.record_process_state(component_id, pid, "STARTING", "starting", "process start observed")

    async def register_capability(self, capability_id: str, owner: str, access_mode: str,
                                  contract_version: str = "1.0.0", metadata: dict[str, Any] | None = None) -> None:
        if access_mode not in {"read_only", "read_write"}:
            raise ValueError("Unsupported capability access mode")
        async with self.pool.connection() as conn, conn.transaction():
            await conn.execute(
                "INSERT INTO r3a.capability_registry(capability_id,contract_version,owner,access_mode,health,observed_at,metadata) "
                "VALUES (%s,%s,%s,%s,'available',clock_timestamp(),%s) ON CONFLICT(capability_id) DO UPDATE SET "
                "contract_version=EXCLUDED.contract_version,owner=EXCLUDED.owner,access_mode=EXCLUDED.access_mode,"
                "health=EXCLUDED.health,observed_at=EXCLUDED.observed_at,metadata=EXCLUDED.metadata",
                (capability_id, contract_version, owner, access_mode, json.dumps(metadata or {})),
            )

    async def grant_capability(self, module_id: str, capability_id: str, reason: str) -> uuid.UUID:
        async with self.pool.connection() as conn, conn.transaction():
            found = await (await conn.execute(
                "SELECT access_mode FROM r3a.capability_registry WHERE capability_id=%s", (capability_id,)
            )).fetchone()
            if found is None:
                raise KeyError(f"Capability is not registered: {capability_id}")
            if found["access_mode"] != "read_only":
                raise PermissionError("AP0-M1 operator grants are restricted to read-only capabilities")
            active = await (await conn.execute(
                "SELECT grant_id FROM r3a.capability_grants WHERE module_id=%s AND capability_id=%s "
                "AND revoked_at IS NULL FOR UPDATE", (module_id, capability_id)
            )).fetchone()
            if active:
                return active["grant_id"]
            grant_id = uuid.uuid4()
            await conn.execute(
                "INSERT INTO r3a.capability_grants(grant_id,module_id,capability_id,granted_by,reason) VALUES (%s,%s,%s,%s,%s)",
                (grant_id, module_id, capability_id, f"uid:{os.getuid()}", reason),
            )
            await self._event(conn, "capability.granted", "capability", capability_id,
                              None, None, None, "ACTIVE", reason,
                              {"module_id": module_id, "grant_id": str(grant_id)})
            return grant_id

    async def require_capability(self, module_id: str, capability_id: str) -> None:
        async with self.pool.connection() as conn:
            row = await (await conn.execute(
                "SELECT 1 FROM r3a.capability_grants WHERE module_id=%s AND capability_id=%s AND revoked_at IS NULL LIMIT 1",
                (module_id, capability_id),
            )).fetchone()
        if row is None:
            raise PermissionError(f"No active grant for {module_id} to invoke {capability_id}")

    async def register_resource(self, resource_id: str, capacity: int, owner: str = "CME") -> None:
        async with self.pool.connection() as conn, conn.transaction():
            await conn.execute(
                "INSERT INTO r3a.resource_registry(resource_id,contract_version,owner,capacity,health,observed_at) "
                "VALUES (%s,'1.0.0',%s,%s,'available',clock_timestamp()) ON CONFLICT(resource_id) DO UPDATE SET "
                "capacity=EXCLUDED.capacity,health='available',observed_at=clock_timestamp()",
                (resource_id, owner, capacity),
            )

    async def register_model_role(self, role: Any, config_revision: str,
                                  resident_id: str, model_id: str) -> None:
        """Persist a configured role in the existing resource registry, initially unknown."""
        resource_id = f"model-role:{role.role_id}"
        metadata = {"registry_contract": "r3a.model-role.v1", "resident_id": resident_id,
                    "role_id": role.role_id,
                    "route_id": role.route_id, "capabilities": list(role.capabilities),
                    "configured_model_id": model_id,
                    "readiness_provider_id": role.readiness.provider_id if role.readiness else None,
                    "modalities": list(role.modalities), "fallback_roles": list(role.fallback_roles),
                    "readiness_max_age_seconds": role.readiness_max_age_seconds,
                    "unavailable_action": role.unavailable_action,
                    "deferral_seconds": role.deferral_seconds,
                    "config_revision": config_revision}
        preserve_readiness = (
            "r3a.resource_registry.metadata->>'config_revision'=EXCLUDED.metadata->>'config_revision' "
            "AND r3a.resource_registry.metadata->>'readiness_provider_id'="
            "EXCLUDED.metadata->>'readiness_provider_id' "
            "AND r3a.resource_registry.metadata->>'configured_model_id'="
            "EXCLUDED.metadata->>'configured_model_id' "
            "AND r3a.resource_registry.metadata#>>'{readiness,provider_id}'="
            "EXCLUDED.metadata->>'readiness_provider_id' "
            "AND r3a.resource_registry.metadata#>>'{readiness,model_id}'="
            "EXCLUDED.metadata->>'configured_model_id' "
            "AND jsonb_typeof(r3a.resource_registry.metadata#>'{readiness,evidence}')='object' "
            "AND r3a.resource_registry.metadata#>'{readiness,evidence}' <> '{}'::jsonb")
        async with self.pool.connection() as conn, conn.transaction():
            await conn.execute(
                "INSERT INTO r3a.resource_registry(resource_id,contract_version,owner,capacity,health,observed_at,metadata) "
                "VALUES (%s,'1.0.0',%s,%s,'unknown',clock_timestamp(),%s) "
                "ON CONFLICT(resource_id) DO UPDATE SET contract_version=EXCLUDED.contract_version,"
                "owner=EXCLUDED.owner,capacity=EXCLUDED.capacity,"
                f"health=CASE WHEN {preserve_readiness} "
                "THEN r3a.resource_registry.health ELSE 'unknown' END,"
                f"observed_at=CASE WHEN {preserve_readiness} "
                "THEN r3a.resource_registry.observed_at ELSE clock_timestamp() END,"
                f"metadata=CASE WHEN {preserve_readiness} "
                "THEN r3a.resource_registry.metadata || EXCLUDED.metadata "
                "ELSE (r3a.resource_registry.metadata - 'readiness') || EXCLUDED.metadata END",
                (resource_id, resident_id, role.concurrency, json.dumps(metadata)),
            )

    async def model_role_observations(self, role_ids: tuple[str, ...]) -> dict[str, dict[str, Any]]:
        if not role_ids:
            return {}
        async with self.pool.connection() as conn:
            rows = await (await conn.execute(
                "SELECT resource_id,health,observed_at,metadata FROM r3a.resource_registry "
                "WHERE resource_id = ANY(%s)",
                ([f"model-role:{role_id}" for role_id in role_ids],),
            )).fetchall()
        observations = {}
        for row in rows:
            metadata = row["metadata"] if isinstance(row["metadata"], dict) else {}
            readiness = metadata.get("readiness", {})
            role_id = metadata.get("role_id")
            if role_id:
                valid = (isinstance(readiness, dict)
                         and readiness.get("source") in {"provider_model", "model_protocol"}
                         and readiness.get("provider_id") == metadata.get("readiness_provider_id")
                         and readiness.get("model_id") == metadata.get("configured_model_id")
                         and readiness.get("evidence_ref")
                         and isinstance(readiness.get("evidence"), dict)
                         and bool(readiness.get("evidence"))
                         and readiness.get("config_revision") == metadata.get("config_revision")
                         and row["health"] in {"ready", "degraded", "unavailable", "stale", "unknown"}
                         and readiness.get("observed_at")
                         )
                observations[role_id] = ({**readiness, "status": row["health"]}
                                         if valid else {"status": "unknown"})
        return observations

    async def observe_model_role(self, observation: ReadinessObservation) -> int:
        resource_id = f"model-role:{observation.role_id}"
        readiness = observation.to_dict()
        async with self.pool.connection() as conn, conn.transaction():
            updated = await conn.execute(
                "UPDATE r3a.resource_registry SET health=%s,observed_at=%s,"
                "metadata=metadata || jsonb_build_object('readiness',%s::jsonb) "
                "WHERE resource_id=%s AND metadata->>'config_revision'=%s "
                "AND metadata->>'readiness_provider_id'=%s AND metadata->>'configured_model_id'=%s",
                (observation.status, parse_timestamp(observation.observed_at), json.dumps(readiness),
                 resource_id, observation.config_revision, observation.provider_id, observation.model_id),
            )
            if updated.rowcount != 1:
                raise ValueError("model role is not registered for this configuration revision")
            await self._event(conn, "model.role.readiness.observed", "resource", resource_id,
                              None, None, None, observation.status,
                              "provider-level model readiness observation recorded",
                              readiness, correlation_id=uuid.UUID(observation.observation_id))
        return 0

    async def waiting_model_activities(self) -> list[dict[str, Any]]:
        async with self.pool.connection() as conn:
            return await (await conn.execute(
                "SELECT activity_id,input FROM r3a.activities WHERE state='WAITING' "
                "AND activity_type='grace.objective' AND input ? 'role_id' "
                "AND available_at<=clock_timestamp() ORDER BY available_at,created_at"
            )).fetchall()

    async def requeue_model_activity(self, activity_id: uuid.UUID, role_id: str,
                                     selected_role_id: str,
                                     causation_id: str | None = None) -> bool:
        async with self.pool.connection() as conn, conn.transaction():
            row = await (await conn.execute(
                "SELECT activity_id,machine_id,machine_version FROM r3a.activities "
                "WHERE activity_id=%s AND state='WAITING' AND available_at<=clock_timestamp() "
                "FOR UPDATE SKIP LOCKED", (activity_id,)
            )).fetchone()
            if row is None:
                return False
            await conn.execute(
                "UPDATE r3a.activities SET state='QUEUED',available_at=clock_timestamp(),"
                "exception=NULL,updated_at=clock_timestamp() WHERE activity_id=%s",
                (row["activity_id"],),
            )
            evidence = {"requested_role_id": role_id, "selected_role_id": selected_role_id}
            event_id = await self._event(
                conn, "activity.model_role_available", "activity", str(row["activity_id"]),
                row["machine_id"], row["machine_version"], "WAITING", "QUEUED",
                "configured model role became eligible", evidence,
                causation_id=uuid.UUID(causation_id) if causation_id else None)
            accepted = await self._transition_on_conn(
                conn, "activity", str(row["activity_id"]), row["machine_id"],
                row["machine_version"], "QUEUED", "configured model role became eligible",
                evidence, event_id=event_id)
            if not accepted:
                raise InvalidTransition(f"Cannot requeue activity {row['activity_id']}")
            await conn.execute("UPDATE r3a.activities SET latest_event_id=%s WHERE activity_id=%s",
                               (event_id, row["activity_id"]))
            return True

    async def block_waiting_model_activity(self, activity_id: uuid.UUID, reason: str,
                                           details: dict[str, Any]) -> bool:
        async with self.pool.connection() as conn, conn.transaction():
            row = await (await conn.execute(
                "SELECT activity_id,machine_id,machine_version FROM r3a.activities "
                "WHERE activity_id=%s AND state='WAITING' FOR UPDATE SKIP LOCKED",
                (activity_id,),
            )).fetchone()
            if row is None:
                return False
            await conn.execute(
                "UPDATE r3a.activities SET state='BLOCKED',lease_owner=NULL,lease_until=NULL,"
                "exception=%s,updated_at=clock_timestamp() WHERE activity_id=%s",
                (json.dumps({"reason": reason, **details}), row["activity_id"]),
            )
            event_id = await self._event(
                conn, "activity.blocked", "activity", str(row["activity_id"]),
                row["machine_id"], row["machine_version"], "WAITING", "BLOCKED",
                reason, details)
            accepted = await self._transition_on_conn(
                conn, "activity", str(row["activity_id"]), row["machine_id"],
                row["machine_version"], "BLOCKED", reason, details, event_id=event_id)
            if not accepted:
                raise InvalidTransition(f"Cannot block activity {row['activity_id']}")
            await conn.execute("UPDATE r3a.activities SET latest_event_id=%s WHERE activity_id=%s",
                               (event_id, row["activity_id"]))
            return True

    async def audit_capability_invocation(self, module_id: str, capability_id: str,
                                          result: str, details: dict[str, Any] | None = None) -> uuid.UUID:
        async with self.pool.connection() as conn, conn.transaction():
            return await self._event(conn, "capability.invoked", "capability", capability_id,
                                     None, None, None, result, "capability invocation audited",
                                     {"module_id": module_id, "result": result, **(details or {})},
                                     outcome="accepted" if result == "allowed" else "denied")

    async def register_module(self, manifest: dict[str, Any], lifecycle: str = "INSTALLED",
                              health: str = "unknown", diagnostic: dict[str, Any] | None = None) -> None:
        async with self.pool.connection() as conn, conn.transaction():
            existing = await (await conn.execute(
                "SELECT artifact_digest,manifest FROM r3a.module_registry WHERE module_id=%s AND module_version=%s FOR UPDATE",
                (manifest["module_id"], manifest["module_version"]),
            )).fetchone()
            if existing and existing["artifact_digest"].strip() != manifest["artifact_digest"]:
                raise RuntimeError("An installed module version is immutable; use a new version for a different artifact")
            await conn.execute(
                "INSERT INTO r3a.module_registry(module_id,module_version,contract_id,protocol_major,protocol_minor,"
                "artifact_ref,artifact_digest,manifest,lifecycle_state,health,observed_at,diagnostic) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,clock_timestamp(),%s) "
                "ON CONFLICT(module_id,module_version) DO UPDATE SET "
                "health=EXCLUDED.health,observed_at=clock_timestamp(),diagnostic=EXCLUDED.diagnostic",
                (manifest["module_id"], manifest["module_version"], manifest["contract_id"],
                 manifest["protocol_major"], manifest["protocol_minor"], manifest["artifact_ref"],
                 manifest["artifact_digest"], json.dumps(manifest), lifecycle, health, json.dumps(diagnostic or {})),
            )

    async def module_state(self, module_id: str, module_version: str, lifecycle: str,
                           health: str, diagnostic: dict[str, Any] | None = None) -> None:
        async with self.pool.connection() as conn, conn.transaction():
            entity_id = f"{module_id}@{module_version}"
            prior = await (await conn.execute(
                "SELECT state FROM r3a.runtime_entities WHERE entity_type='module' AND entity_id=%s FOR UPDATE",
                (entity_id,),
            )).fetchone()
            if prior and prior["state"] == lifecycle:
                await conn.execute(
                    "UPDATE r3a.module_registry SET health=%s,observed_at=clock_timestamp(),diagnostic=%s "
                    "WHERE module_id=%s AND module_version=%s",
                    (health, json.dumps(diagnostic or {}), module_id, module_version),
                )
                return
            if not prior and lifecycle != "INSTALLED":
                await self._transition_on_conn(conn, "module", entity_id, "module.lifecycle", 1,
                                               "INSTALLED", "module installation observed",
                                               {"version": module_version}, initial=True)
            accepted = await self._transition_on_conn(conn, "module", entity_id, "module.lifecycle", 1,
                                                      lifecycle, "module lifecycle observed",
                                                      {"version": module_version, "health": health,
                                                       **(diagnostic or {})},
                                                      initial=not prior and lifecycle == "INSTALLED")
            if not accepted:
                raise InvalidTransition(f"Module lifecycle transition denied: {entity_id} -> {lifecycle}")
            await conn.execute(
                "UPDATE r3a.module_registry SET lifecycle_state=%s,health=%s,observed_at=clock_timestamp(),diagnostic=%s "
                "WHERE module_id=%s AND module_version=%s",
                (lifecycle, health, json.dumps(diagnostic or {}), module_id, module_version),
            )

    async def observe_module(self, module_id: str, module_version: str, health: str,
                             diagnostic: dict[str, Any] | None = None) -> None:
        async with self.pool.connection() as conn, conn.transaction():
            await conn.execute(
                "UPDATE r3a.module_registry SET health=%s,observed_at=clock_timestamp(),diagnostic=%s "
                "WHERE module_id=%s AND module_version=%s",
                (health, json.dumps(diagnostic or {}), module_id, module_version),
            )

    async def record_module_replacement(self, module_id: str, old_version: str,
                                        new_version: str) -> None:
        async with self.pool.connection() as conn, conn.transaction():
            await self._event(conn, "module.replaced", "module",
                              f"{module_id}@{old_version}", "module.lifecycle", 1,
                              "STOPPED", "STOPPED", "module replacement completed",
                              {"module_id": module_id, "old_version": old_version,
                               "new_version": new_version})

    async def ensure_observer_activity(self) -> None:
        async with self.pool.connection() as conn, conn.transaction():
            active = await (await conn.execute(
                "SELECT activity_id FROM r3a.activities WHERE activity_type='foundation.observe' "
                "AND state IN ('QUEUED','RUNNING','WAITING','RECOVERING','BLOCKED') LIMIT 1"
            )).fetchone()
            if active:
                return
            activity_id = uuid.uuid4()
            key = f"foundation.observe:{activity_id}"
            config = await (await conn.execute("SELECT revision_id FROM r3a.config_current WHERE singleton=true")).fetchone()
            await conn.execute(
                "INSERT INTO r3a.activities(activity_id,activity_type,idempotency_key,machine_id,machine_version,state,available_at,recovery_policy,config_revision) "
                "VALUES (%s,'foundation.observe',%s,'activity.generic',1,'QUEUED',clock_timestamp(),'idempotent',%s)",
                (activity_id, key, config["revision_id"] if config else None),
            )
            accepted = await self._transition_on_conn(conn, "activity", str(activity_id), "activity.generic", 1,
                                                      "QUEUED", "observer activity queued",
                                                      {"idempotency_key": key}, initial=True)
            if not accepted:
                raise InvalidTransition("Observer activity could not enter QUEUED")

    async def submit_grace_objective(self, objective: str, idempotency_key: str,
                                     event_kind: str = "objective",
                                     route_id: str | None = None,
                                     role_id: str | None = None,
                                     required_capabilities: tuple[str, ...] = (),
                                     required_modalities: tuple[str, ...] = ()) -> dict[str, Any]:
        """Durably enqueue one objective/notification; duplicate keys return the same activity."""
        if not objective.strip() or len(objective) > 4000:
            raise ValueError("event content must contain 1 to 4000 characters")
        if not idempotency_key.strip() or len(idempotency_key) > 200:
            raise ValueError("idempotency_key must contain 1 to 200 characters")
        if event_kind not in {"objective", "notification"}:
            raise ValueError("event_kind must be objective or notification")
        if not isinstance(required_capabilities, (tuple, list)) or any(
                not isinstance(item, str) or not item.strip() for item in required_capabilities):
            raise ValueError("required_capabilities must be capability identifiers")
        if len(set(required_capabilities)) != len(required_capabilities):
            raise ValueError("required_capabilities must be unique")
        if not isinstance(required_modalities, (tuple, list)) or any(
                not isinstance(item, str) or not item.strip() for item in required_modalities):
            raise ValueError("required_modalities must be modality identifiers")
        if len(set(required_modalities)) != len(required_modalities):
            raise ValueError("required_modalities must be unique")
        if role_id is None and self.settings.model_roles:
            if route_id is None:
                role_id = self.settings.default_model_role
            else:
                matching_roles = [entry for entry in self.settings.model_roles if entry.route_id == route_id]
                if len(matching_roles) != 1:
                    raise ValueError("an explicit route must resolve to exactly one configured model role")
                role_id = matching_roles[0].role_id
        if role_id is not None:
            role = next((entry for entry in self.settings.model_roles if entry.role_id == role_id), None)
            if role is None:
                raise ValueError("requested model role is not configured")
            if route_id is not None and route_id != role.route_id:
                raise ValueError("route_id must match the configured route for the requested role")
            selected_route_id = role.route_id
            selected_role_id = role.role_id
        else:
            selected_route_id = self.settings.model_route(route_id).route_id
            selected_role_id = None
        event_input = {"objective": objective, "event_kind": event_kind,
                       "route_id": selected_route_id if selected_role_id is None else None,
                       "role_id": selected_role_id,
                       "required_capabilities": list(required_capabilities),
                       "required_modalities": list(required_modalities),
                       "role_config_revision": self.settings.source_digest if selected_role_id else None}
        async with self.pool.connection() as conn, conn.transaction():
            existing = await (await conn.execute(
                "SELECT activity_id,state,activity_type,idempotency_key,input,attempt_count "
                "FROM r3a.activities WHERE idempotency_key=%s FOR UPDATE", (idempotency_key,)
            )).fetchone()
            if existing:
                prior_input = dict(existing["input"] or {})
                prior_input.setdefault("event_kind", "objective")
                prior_input.setdefault("route_id", self.settings.default_model_route)
                prior_input.setdefault("role_id", None)
                prior_input.setdefault("required_capabilities", [])
                prior_input.setdefault("required_modalities", [])
                prior_input.setdefault("role_config_revision", None)
                prior_input.pop("authorized_capability", None)
                if existing["activity_type"] != "grace.objective" or prior_input != event_input:
                    raise ValueError("idempotency key already belongs to a different request")
                return {**existing, "duplicate": True}
            activity_id = uuid.uuid4()
            correlation_id = uuid.uuid4()
            config = await (await conn.execute(
                "SELECT revision_id FROM r3a.config_current WHERE singleton=true"
            )).fetchone()
            await conn.execute(
                "INSERT INTO r3a.activities(activity_id,activity_type,idempotency_key,machine_id,machine_version,state,"
                "available_at,recovery_policy,config_revision,input) "
                "VALUES (%s,'grace.objective',%s,'activity.generic',1,'QUEUED',clock_timestamp(),'idempotent',%s,%s)",
                (activity_id, idempotency_key, config["revision_id"] if config else None,
                 json.dumps(event_input)),
            )
            event_type = ("grace.notification.received" if event_kind == "notification"
                          else "grace.objective.received")
            event_id = await self._event(conn, event_type, "activity", str(activity_id),
                                         "activity.generic", 1, None, "QUEUED", f"Grace {event_kind} accepted into durable inbox",
                                         {"idempotency_key": idempotency_key, "objective_sha256": hashlib.sha256(objective.encode()).hexdigest(),
                                          "event_kind": event_kind, "route_id": selected_route_id,
                                          "role_id": selected_role_id,
                                          "required_capabilities": list(required_capabilities),
                                          "required_modalities": list(required_modalities)},
                                         correlation_id=correlation_id)
            accepted = await self._transition_on_conn(conn, "activity", str(activity_id),
                                                       "activity.generic", 1, "QUEUED",
                                                       f"Grace {event_kind} durably accepted",
                                                       {"idempotency_key": idempotency_key,
                                                        "received_event_id": str(event_id)}, initial=True)
            if not accepted:
                raise InvalidTransition("Grace objective could not enter QUEUED")
            await conn.execute("UPDATE r3a.activities SET latest_event_id=%s WHERE activity_id=%s",
                               (event_id, activity_id))
            return {"activity_id": activity_id, "state": "QUEUED", "activity_type": "grace.objective",
                    "idempotency_key": idempotency_key, "attempt_count": 0, "duplicate": False,
                    "event_kind": event_kind, "route_id": selected_route.route_id,
                    "received_event_id": event_id}

    async def requeue_blocked_activities(self) -> int:
        async with self.pool.connection() as conn, conn.transaction():
            rows = await (await conn.execute(
                "SELECT activity_id,machine_id,machine_version FROM r3a.activities "
                "WHERE activity_type='foundation.observe' AND state='BLOCKED' FOR UPDATE SKIP LOCKED"
            )).fetchall()
            for row in rows:
                await conn.execute(
                    "UPDATE r3a.activities SET state='RECOVERING',available_at=clock_timestamp(),exception=NULL,updated_at=clock_timestamp() "
                    "WHERE activity_id=%s", (row["activity_id"],)
                )
                accepted = await self._transition_on_conn(conn, "activity", str(row["activity_id"]),
                                                          row["machine_id"], row["machine_version"], "RECOVERING",
                                                          "operator resolved capability block")
                if not accepted:
                    raise InvalidTransition(f"Cannot recover blocked activity {row['activity_id']}")
            return len(rows)

    async def block_activity(self, activity: dict[str, Any], reason: str,
                             details: dict[str, Any] | None = None) -> None:
        async with self.pool.connection() as conn, conn.transaction():
            await conn.execute(
                "UPDATE r3a.activities SET state='BLOCKED',lease_owner=NULL,lease_until=NULL,exception=%s,updated_at=clock_timestamp() "
                "WHERE activity_id=%s AND attempt_id=%s",
                (json.dumps({"reason": reason, **(details or {})}), activity["activity_id"], activity["attempt_id"]),
            )
            released = await conn.execute(
                "UPDATE r3a.resource_leases SET released_at=clock_timestamp() WHERE lease_id=%s AND released_at IS NULL",
                (activity["lease_id"],),
            )
            if released.rowcount:
                await conn.execute(
                    "UPDATE r3a.resource_registry SET allocated=GREATEST(0,allocated-1),observed_at=clock_timestamp() WHERE resource_id=%s",
                    (activity["resource_id"],),
                )
            accepted = await self._transition_on_conn(conn, "activity", str(activity["activity_id"]),
                                                      "activity.generic", 1, "BLOCKED", reason, details)
            if not accepted:
                raise InvalidTransition(f"Cannot block activity {activity['activity_id']}")

    async def defer_activity(self, activity: dict[str, Any], reason: str,
                             retry_after_seconds: float, details: dict[str, Any] | None = None) -> None:
        evidence = {"reason": reason, "retryable": True, **(details or {})}
        async with self.pool.connection() as conn, conn.transaction():
            updated = await conn.execute(
                "UPDATE r3a.activities SET state='WAITING',available_at=clock_timestamp()+(%s * interval '1 second'),"
                "lease_owner=NULL,lease_until=NULL,exception=%s,updated_at=clock_timestamp() "
                "WHERE activity_id=%s AND attempt_id=%s AND state='RUNNING'",
                (retry_after_seconds, json.dumps(evidence), activity["activity_id"], activity["attempt_id"]),
            )
            if updated.rowcount != 1:
                raise RuntimeError("Activity lease was lost before deferral")
            released = await conn.execute(
                "UPDATE r3a.resource_leases SET released_at=clock_timestamp() WHERE lease_id=%s AND released_at IS NULL",
                (activity["lease_id"],),
            )
            if released.rowcount:
                await conn.execute(
                    "UPDATE r3a.resource_registry SET allocated=GREATEST(0,allocated-1),observed_at=clock_timestamp() "
                    "WHERE resource_id=%s", (activity["resource_id"],))
            accepted = await self._transition_on_conn(
                conn, "activity", str(activity["activity_id"]), "activity.generic", 1,
                "WAITING", reason, evidence)
            if not accepted:
                raise InvalidTransition(f"Cannot defer activity {activity['activity_id']}")
            event_id = await self._event(
                conn, "activity.deferred", "activity", str(activity["activity_id"]),
                "activity.generic", 1, "RUNNING", "WAITING", reason, evidence,
                causation_id=activity["attempt_id"])
            await conn.execute("UPDATE r3a.activities SET latest_event_id=%s WHERE activity_id=%s",
                               (event_id, activity["activity_id"]))

    async def claim_activity(self, owner: str, lease_seconds: float,
                             resource_id: str = "foundation.observer") -> dict[str, Any] | None:
        async with self.pool.connection() as conn, conn.transaction():
            resource = await (await conn.execute(
                "SELECT capacity,allocated,health FROM r3a.resource_registry WHERE resource_id=%s FOR UPDATE",
                (resource_id,),
            )).fetchone()
            if resource is None or resource["health"] != "available" or resource["allocated"] >= resource["capacity"]:
                return None
            row = await (await conn.execute(
                "SELECT activity_id,activity_type,idempotency_key,machine_id,machine_version,state,attempt_count,config_revision,input,checkpoint "
                "FROM r3a.activities WHERE state IN ('QUEUED','RECOVERING') AND available_at<=clock_timestamp() "
                "ORDER BY available_at,created_at FOR UPDATE SKIP LOCKED LIMIT 1"
            )).fetchone()
            if row is None:
                return None
            attempt_id = uuid.uuid4()
            lease_id = uuid.uuid4()
            lease_until = utcnow() + timedelta(seconds=lease_seconds)
            await conn.execute(
                "UPDATE r3a.resource_registry SET allocated=allocated+1,observed_at=clock_timestamp() WHERE resource_id=%s",
                (resource_id,),
            )
            await conn.execute(
                "INSERT INTO r3a.resource_leases(lease_id,resource_id,activity_id,units,lease_until) VALUES (%s,%s,%s,1,%s)",
                (lease_id, resource_id, row["activity_id"], lease_until),
            )
            await conn.execute(
                "UPDATE r3a.activities SET state='RUNNING',attempt_id=%s,attempt_count=attempt_count+1,"
                "lease_owner=%s,lease_until=%s,exception=NULL,updated_at=clock_timestamp() WHERE activity_id=%s",
                (attempt_id, owner, lease_until, row["activity_id"]),
            )
            event_id = await self._event(conn, "activity.claimed", "activity", str(row["activity_id"]),
                                         row["machine_id"], row["machine_version"], row["state"], "RUNNING",
                                         "scheduler claimed eligible activity",
                                         {"attempt_id": str(attempt_id), "lease_owner": owner})
            accepted = await self._transition_on_conn(conn, "activity", str(row["activity_id"]),
                                                       row["machine_id"], row["machine_version"], "RUNNING",
                                                       "scheduler claimed eligible activity",
                                                       {"attempt_id": str(attempt_id), "lease_owner": owner})
            if not accepted:
                raise InvalidTransition(f"Cannot claim activity {row['activity_id']}")
            await conn.execute("UPDATE r3a.activities SET latest_event_id=%s WHERE activity_id=%s",
                               (event_id, row["activity_id"]))
            row.update({"attempt_id": attempt_id, "attempt_count": row["attempt_count"] + 1,
                        "resource_id": resource_id, "lease_id": lease_id, "state": "RUNNING"})
            return row

    async def renew_activity_lease(self, activity: dict[str, Any]) -> None:
        """Extend the database activity and resource lease while an idempotent model call is in flight."""
        async with self.pool.connection() as conn, conn.transaction():
            updated = await conn.execute(
                "UPDATE r3a.activities SET lease_until=clock_timestamp()+(%s * interval '1 second'),updated_at=clock_timestamp() "
                "WHERE activity_id=%s AND state='RUNNING' AND attempt_id=%s",
                (self.settings.lease_seconds, activity["activity_id"], activity["attempt_id"]),
            )
            if updated.rowcount != 1:
                raise RuntimeError("Activity lease was lost during model execution")
            await conn.execute(
                "UPDATE r3a.resource_leases SET lease_until=clock_timestamp()+(%s * interval '1 second') "
                "WHERE lease_id=%s AND released_at IS NULL",
                (self.settings.lease_seconds, activity["lease_id"]),
            )

    async def record_progress(self, activity: dict[str, Any], progress: dict[str, Any],
                              checkpoint: dict[str, Any] | None = None) -> None:
        async with self.pool.connection() as conn, conn.transaction():
            updated = await conn.execute(
                "UPDATE r3a.activities SET progress=%s,checkpoint=%s,lease_until=clock_timestamp()+(%s * interval '1 second'),updated_at=clock_timestamp() "
                "WHERE activity_id=%s AND state='RUNNING' AND attempt_id=%s",
                (json.dumps(progress), json.dumps(checkpoint or {}), self.settings.lease_seconds,
                 activity["activity_id"], activity["attempt_id"]),
            )
            if updated.rowcount != 1:
                raise RuntimeError("Activity lease was lost before progress could be persisted")
            await conn.execute(
                "UPDATE r3a.resource_leases SET lease_until=clock_timestamp()+(%s * interval '1 second') "
                "WHERE lease_id=%s AND released_at IS NULL",
                (self.settings.lease_seconds, activity["lease_id"]),
            )
            await self._event(conn, "activity.progress", "activity", str(activity["activity_id"]),
                              "activity.generic", 1, "RUNNING", "RUNNING", "activity made progress",
                              progress, causation_id=activity["attempt_id"])

    async def finish_activity(self, activity: dict[str, Any], result: dict[str, Any]) -> None:
        async with self.pool.connection() as conn, conn.transaction():
            updated = await conn.execute(
                "UPDATE r3a.activities SET state='COMPLETED',progress=%s,result=%s,exception=NULL,lease_owner=NULL,lease_until=NULL,"
                "updated_at=clock_timestamp() WHERE activity_id=%s AND state='RUNNING' AND attempt_id=%s",
                (json.dumps(result), json.dumps(result), activity["activity_id"], activity["attempt_id"]),
            )
            if updated.rowcount != 1:
                raise RuntimeError("Activity lease was lost before completion")
            released = await conn.execute(
                "UPDATE r3a.resource_leases SET released_at=clock_timestamp() WHERE lease_id=%s AND released_at IS NULL",
                (activity["lease_id"],),
            )
            if released.rowcount:
                await conn.execute(
                    "UPDATE r3a.resource_registry SET allocated=GREATEST(0,allocated-1),observed_at=clock_timestamp() WHERE resource_id=%s",
                    (activity["resource_id"],),
                )
            event_id = await self._event(conn, "activity.completed", "activity", str(activity["activity_id"]),
                                         "activity.generic", 1, "RUNNING", "COMPLETED",
                                         "activity completed with actual evidence", result,
                                         causation_id=activity["attempt_id"])
            await conn.execute("UPDATE r3a.activities SET latest_event_id=%s WHERE activity_id=%s",
                               (event_id, activity["activity_id"]))
            accepted = await self._transition_on_conn(conn, "activity", str(activity["activity_id"]),
                                                      "activity.generic", 1, "COMPLETED",
                                                      "activity completed with evidence", result)
            if not accepted:
                raise InvalidTransition(f"Cannot complete activity {activity['activity_id']}")
            activity_id = uuid.uuid4()
            key = f"foundation.observe:{activity_id}"
            config = await (await conn.execute("SELECT revision_id FROM r3a.config_current WHERE singleton=true")).fetchone()
            await conn.execute(
                "INSERT INTO r3a.activities(activity_id,activity_type,idempotency_key,machine_id,machine_version,state,available_at,recovery_policy,config_revision) "
                "VALUES (%s,'foundation.observe',%s,'activity.generic',1,'QUEUED',clock_timestamp()+(%s * interval '1 second'),'idempotent',%s)",
                (activity_id, key, self.settings.observer_interval_seconds, config["revision_id"] if config else None),
            )
            accepted = await self._transition_on_conn(conn, "activity", str(activity_id), "activity.generic", 1,
                                                      "QUEUED", "next observer activity scheduled",
                                                      {"idempotency_key": key}, initial=True)
            if not accepted:
                raise InvalidTransition("Next observer activity could not enter QUEUED")

    async def recover_expired_activities(self) -> int:
        async with self.pool.connection() as conn, conn.transaction():
            rows = await (await conn.execute(
                "SELECT activity_id,activity_type,attempt_id,recovery_policy,machine_id,machine_version "
                "FROM r3a.activities WHERE state='RUNNING' AND lease_until<clock_timestamp() FOR UPDATE SKIP LOCKED"
            )).fetchall()
            for row in rows:
                safe = row["recovery_policy"] == "idempotent"
                next_state = "RECOVERING" if safe else "BLOCKED"
                await conn.execute(
                    "UPDATE r3a.activities SET state=%s,lease_owner=NULL,lease_until=NULL,available_at=clock_timestamp(),"
                    "exception=%s,updated_at=clock_timestamp() WHERE activity_id=%s",
                    (next_state, json.dumps({"reason": "worker lease expired", "safe_to_resume": safe}), row["activity_id"]),
                )
                event_id = await self._event(conn, "activity.lease_expired", "activity", str(row["activity_id"]),
                                  row["machine_id"], row["machine_version"], "RUNNING", next_state,
                                  "expired worker lease reconciled", {"safe_to_resume": safe},
                                  outcome="recovered" if safe else "blocked",
                                  causation_id=row["attempt_id"])
                accepted = await self._transition_on_conn(conn, "activity", str(row["activity_id"]),
                                                          row["machine_id"], row["machine_version"], next_state,
                                                          "expired worker lease reconciled",
                                                          {"safe_to_resume": safe})
                if not accepted:
                    raise InvalidTransition(f"Cannot recover expired activity {row['activity_id']}")
                await conn.execute("UPDATE r3a.activities SET latest_event_id=%s WHERE activity_id=%s",
                                   (event_id, row["activity_id"]))
                released = await conn.execute(
                    "UPDATE r3a.resource_leases SET released_at=clock_timestamp() WHERE activity_id=%s AND released_at IS NULL",
                    (row["activity_id"],),
                )
                if released.rowcount:
                    await conn.execute(
                        "UPDATE r3a.resource_registry SET allocated=GREATEST(0,allocated-1),observed_at=clock_timestamp() "
                        "WHERE resource_id IN (SELECT resource_id FROM r3a.resource_leases WHERE activity_id=%s)",
                        (row["activity_id"],),
                    )
            return len(rows)

    async def fail_activity(self, activity: dict[str, Any], exc: BaseException,
                            retry_seconds: float) -> None:
        async with self.pool.connection() as conn, conn.transaction():
            row = await (await conn.execute(
                "SELECT recovery_policy FROM r3a.activities WHERE activity_id=%s FOR UPDATE",
                (activity["activity_id"],),
            )).fetchone()
            safe = row and row["recovery_policy"] == "idempotent"
            next_state = "RECOVERING" if safe else "BLOCKED"
            details = {"type": type(exc).__name__, "message": str(exc)[:2000], "safe_to_resume": bool(safe)}
            await conn.execute(
                "UPDATE r3a.activities SET state=%s,available_at=clock_timestamp()+(%s * interval '1 second'),"
                "lease_owner=NULL,lease_until=NULL,exception=%s,updated_at=clock_timestamp() "
                "WHERE activity_id=%s AND attempt_id=%s",
                (next_state, retry_seconds, json.dumps(details), activity["activity_id"], activity["attempt_id"]),
            )
            released = await conn.execute(
                "UPDATE r3a.resource_leases SET released_at=clock_timestamp() WHERE lease_id=%s AND released_at IS NULL",
                (activity["lease_id"],),
            )
            if released.rowcount:
                await conn.execute(
                    "UPDATE r3a.resource_registry SET allocated=GREATEST(0,allocated-1),observed_at=clock_timestamp() WHERE resource_id=%s",
                    (activity["resource_id"],),
                )
            await self._event(conn, "activity.failed", "activity", str(activity["activity_id"]),
                              "activity.generic", 1, "RUNNING", next_state, "module execution failed",
                              details, outcome="retrying" if safe else "blocked",
                              causation_id=activity["attempt_id"])
            accepted = await self._transition_on_conn(conn, "activity", str(activity["activity_id"]),
                                                      "activity.generic", 1, next_state,
                                                      "module execution failed", details)
            if not accepted:
                raise InvalidTransition(f"Cannot fail activity {activity['activity_id']}")

    async def rows(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        async with self.pool.connection() as conn:
            return await (await conn.execute(sql, params)).fetchall()

    async def snapshot(self) -> dict[str, Any]:
        async with self.pool.connection() as conn:
            current_config = await (await conn.execute(
                "SELECT r.revision_id,r.schema_version,r.source_digest,r.activated_at,r.config "
                "FROM r3a.config_current c JOIN r3a.config_revisions r USING(revision_id) WHERE c.singleton=true"
            )).fetchone()
            processes = await (await conn.execute("SELECT * FROM r3a.process_observations ORDER BY component_id")).fetchall()
            modules = await (await conn.execute("SELECT * FROM r3a.module_registry ORDER BY module_id,module_version")).fetchall()
            resources = await (await conn.execute("SELECT * FROM r3a.resource_registry ORDER BY resource_id")).fetchall()
            activities = await (await conn.execute("SELECT * FROM r3a.activities ORDER BY created_at DESC LIMIT 30")).fetchall()
            events = await (await conn.execute("SELECT * FROM r3a.institution_events ORDER BY persisted_at DESC LIMIT 100")).fetchall()
            machines = await (await conn.execute("SELECT machine_id,machine_version,digest,definition FROM r3a.state_machine_definitions ORDER BY machine_id,machine_version")).fetchall()
            return {"configuration": current_config, "processes": processes, "modules": modules,
                    "resources": resources, "activities": activities, "events": events,
                    "state_machines": machines}
