"""
R3 CONTROLLED SOURCE
File: r3a_runtime/db.py
Component: R3A-POSTGRES-PERSISTENCE
File Revision: 1.11.0
Created: 2026-11-06T15:06:00Z
Created By: Codex GPT-6
Purpose: Provide PostgreSQL migrations, versioned state transitions, events, registries, and activity recovery.
Execution Model: Async Psycopg 3 connection pool.
Observability: PostgreSQL current-state projections, append-only events, migrations, and activity lineage.
Dependencies: psycopg 3; PostgreSQL; r3a_runtime.config; AP1 authorization and AP2 engineering contracts.
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
Changed: 2026-11-07T01:30:00Z | R3A-019 | Codex GPT-6 | Return the resolved configured route ID from durable objective intake.
Changed: 2026-11-07T02:35:35Z | R3A-019-ACCEPTANCE-CORRECTION | Codex GPT-6 | Persist validated objective acceptance criteria in the existing activity input.
Changed: 2026-11-07T03:59:26Z | R3A-019-SUSTAINED-OPERATION | Codex GPT-6 | Reject Grace inbox submissions without nonempty validated acceptance criteria.
Changed: 2026-11-07T04:36:29Z | R3A-AP1-M1-DIAGNOSTICS | Codex GPT-6 | Add resumable concurrent-index migrations and skip unused event-history retrieval.
Changed: 2026-11-07T04:41:59Z | R3A-AP1-M1-DIAGNOSTICS | Codex GPT-6 | Generalize concurrent index validation for event and activity ordering indexes.
Changed: 2026-11-07T05:28:24Z | AP2-IMPLEMENTATION | Codex GPT-6 | Allow generic state-machine transition events to preserve caller-supplied correlation and causation lineage.
Changed: 2026-11-07T05:45:10Z | AP2-IMPLEMENTATION | Codex GPT-6 | Persist authorized work orders and guard terminal order completion with independent verifier evidence.
Changed: 2026-11-07T05:52:05Z | AP2-IMPLEMENTATION | Codex GPT-6 | Persist stable objective correlation and immutable Grace proposal revisions in existing activity checkpoints/events.
Changed: 2026-11-07T05:59:32Z | AP2-IMPLEMENTATION | Codex GPT-6 | Persist authorization decision and audit identities as separate provenance fields.
Changed: 2026-11-07T13:20:00Z | R3A-AP2-CAPABILITY-INTEGRATION | Codex GPT-6 | Store canonical invocation authorization in a nonreserved evidence column and verify durable SQL recovery against isolated PostgreSQL.
Changed: 2026-11-07 | R3A-AP2-AUTONOMY | Codex GPT-6 | Persist typed Engineering assignments in durable Grace inbox intake without relaxing AP1 acceptance criteria.
Changed: 2026-11-07T15:16:00Z | R3A-AP1-AP2-AUTONOMY | Codex GPT-6 | Park objective dependencies durably, requeue after prerequisite completion, and expose bounded lineage evidence.
Changed: 2026-11-07 | R3A-AP2-ESCALATED-REASONING | Codex GPT-6 | Snapshot the configured escalation policy on each durable objective so continuation uses its original budget and allowed routes.
Changed: 2026-11-07 | AP2-ESCALATED-REASONING | Codex GPT-6 | Persist activity-scoped capability grants and atomically reserve per-activity external invocation budgets.
Changed: 2026-11-07 | R3A-AP1-N1 | Codex GPT-6 | Import identified institution events as correlated Grace notifications with durable lifecycle events.
Changed: 2026-11-07 | R3A-AP1-MODEL-ROUTING | Codex GPT-6 | Persist objective task class and selected role with durable intake for route-safe recovery.
Changed: 2026-11-07 | R3A-AP1-CME-OBSERVER-QUEUE | Codex GPT-6 | Keep one pending durable observer activity instead of replenishing an existing backlog.
Changed: 2026-11-07 | R3A-MODULAR-FOUNDATION-002 | Codex GPT-6 | Add versioned generic module replacement transitions while retaining immutable lifecycle machine v1.
Supersedes: None.
Contracts: AP0-003–010; R3A-019; R3A-011/R3A-012; AP0-M1 D2/D4/D6/D7/D9; STM-001–STM-007; module.lifecycle v2; r3a.model-role.v1; r3a.model-readiness.v2; r3a.model-readiness-provider.v1; r3a.engineering-work-order.v1; r3a.capability-invocation.v1.
Tests: tests/test_r3a_ap1.py; tests/test_r3a_modular_autonomy.py; tests/test_r3a_engineering.py; tests/test_r3a_capability_integration_demo.py.
History/Predecessor: Prior revision at AP2 commit 600020fd81b4b1e5ed4d938f95592560963a616d, blob a71a534e88a20df82ae2ea7989ca706dbb283c6e; earlier baseline blob f2cffbc6f44a47b10f6262ee469bd310ca652683.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from .config import Settings, sanitized_config
from .acceptance import (OBJECTIVE_ACCEPTANCE_CONTRACT_ID,
                         OBJECTIVE_ACCEPTANCE_CONTRACT_VERSION, validate_required_criteria)
from .notifications import (INSTITUTION_EVENT_SOURCE, institution_event_envelope,
                            same_notification_input, validate_notification_envelope)
from .contracts import ActivityDependencySet, ReadinessObservation, parse_timestamp
from .authorization import AuthorizationDecision
from .engineering import (EngineeringProposal, EngineeringWorkOrder, VerificationResult,
                          proposal_digest, validate_completion, validate_engineering_assignment)


IMPLEMENTATION_REVISION = os.environ.get("R3A_IMPLEMENTATION_REVISION", "working-tree")


class InvalidTransition(RuntimeError):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _concurrent_index_spec(sql: str) -> tuple[str, str, str]:
    match = re.search(
        r"CREATE\s+INDEX\s+CONCURRENTLY\s+([a-z_][a-z0-9_]*)\s+ON\s+"
        r"(r3a\.[a-z_][a-z0-9_]*)\s*\(([^;()]+)\)\s*;",
        sql,
        re.IGNORECASE,
    )
    if not match:
        raise RuntimeError("Concurrent-index migrations must contain one simple CREATE INDEX CONCURRENTLY")
    return match.group(1), match.group(2), " ".join(match.group(3).split())


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
                if path.name.endswith(".concurrent.sql"):
                    index_name, index_table, index_columns = _concurrent_index_spec(sql)
                    await conn.execute(
                        "SELECT pg_advisory_lock(hashtextextended('r3a-ap0-m1-migrations', 0))"
                    )
                    try:
                        row = await (await conn.execute(
                            "SELECT checksum FROM r3a.schema_migrations WHERE version=%s",
                            (path.name,),
                        )).fetchone()
                        if row and row["checksum"].strip() != checksum:
                            raise RuntimeError(f"Applied migration {path.name} checksum changed")

                        index = await (await conn.execute(
                            "SELECT i.indisvalid, pg_get_indexdef(c.oid) AS definition "
                            "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                            "JOIN pg_index i ON i.indexrelid=c.oid "
                            "WHERE n.nspname='r3a' AND c.relname=%s",
                            (index_name,),
                        )).fetchone()
                        if index and not index["indisvalid"]:
                            await conn.execute(f"DROP INDEX CONCURRENTLY r3a.{index_name}")
                            index = None
                        expected_definition = (
                            f"ON {index_table} USING btree ({index_columns})"
                        ).casefold()
                        if index and expected_definition not in index["definition"].casefold():
                            raise RuntimeError(f"Concurrent index {index_name} exists with an unexpected definition")
                        if not index:
                            await conn.execute(sql)
                            index = await (await conn.execute(
                                "SELECT i.indisvalid, pg_get_indexdef(c.oid) AS definition "
                                "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                                "JOIN pg_index i ON i.indexrelid=c.oid "
                                "WHERE n.nspname='r3a' AND c.relname=%s",
                                (index_name,),
                            )).fetchone()
                            if (not index or not index["indisvalid"]
                                    or expected_definition not in index["definition"].casefold()):
                                raise RuntimeError(f"Concurrent index {index_name} was not valid after creation")
                        if row:
                            continue
                        async with conn.transaction():
                            await conn.execute(
                                "INSERT INTO r3a.schema_migrations(version,checksum) VALUES (%s,%s)",
                                (path.name, checksum),
                            )
                        applied.append(path.name)
                    finally:
                        await conn.execute(
                            "SELECT pg_advisory_unlock(hashtextextended('r3a-ap0-m1-migrations', 0))"
                        )
                    continue
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
                         *, initial: bool = False, event_id: uuid.UUID | None = None,
                         correlation_id: uuid.UUID | None = None,
                         causation_id: uuid.UUID | None = None) -> bool:
        """Validate and persist transition plus event atomically, including rejected attempts."""
        if entity_type == "engineering_work_order" and next_state == "COMPLETED":
            raise PermissionError("engineering work-order completion must use independent verification gate")
        event_id = event_id or uuid.uuid4()
        async with self.pool.connection() as conn, conn.transaction():
            return await self._transition_on_conn(conn, entity_type, entity_id, machine_id,
                                                  machine_version, next_state, reason, evidence,
                                                  initial=initial, event_id=event_id,
                                                  correlation_id=correlation_id,
                                                  causation_id=causation_id)

    async def create_engineering_work_order(self, work_order: dict[str, Any],
                                            authorization: AuthorizationDecision) -> bool:
        """Persist an authorized AP2 order in the existing state-machine/event store."""
        if not isinstance(work_order, dict) or work_order.get("contract_id") != "r3a.engineering-work-order":
            raise ValueError("work_order must use r3a.engineering-work-order")
        if work_order.get("contract_version") != "1.0.0":
            raise ValueError("unsupported engineering work-order contract version")
        if not isinstance(authorization, AuthorizationDecision) or authorization.allowed is not True:
            raise PermissionError("a successful institutional authorization decision is required")
        if not isinstance(authorization.audit_event_id, str) or not authorization.audit_event_id.strip():
            raise ValueError("authorization decision is missing its durable audit reference")
        if not isinstance(authorization.provider_id, str) or not authorization.provider_id.strip():
            raise ValueError("authorization decision is missing its provider identity")
        if (work_order.get("authorization_decision_id") != authorization.decision_id
                or work_order.get("authorization_audit_event_id") != authorization.audit_event_id
                or work_order.get("authorization_provider_id") != authorization.provider_id
                or work_order.get("policy_revision") != authorization.policy_revision
                or work_order.get("config_revision") != authorization.config_revision):
            raise ValueError("work-order authorization provenance does not match the provider decision")
        order_id = str(work_order.get("work_order_id", ""))
        activity_id = str(work_order.get("activity_id", ""))
        attempt_id = str(work_order.get("attempt_id", ""))
        correlation_id = str(work_order.get("correlation_id", ""))
        for key, value in (("work_order_id", order_id), ("activity_id", activity_id),
                           ("attempt_id", attempt_id), ("correlation_id", correlation_id)):
            try:
                uuid.UUID(value)
            except (ValueError, TypeError, AttributeError) as exc:
                raise ValueError(f"{key} must be a UUID") from exc
        auth_evidence = {"authorization_decision_id": authorization.decision_id,
                         "authorization_audit_event_id": authorization.audit_event_id,
                         "provider_id": authorization.provider_id,
                         "allowed": authorization.allowed, "reason": authorization.reason,
                         "retryable": authorization.retryable,
                         "policy_revision": authorization.policy_revision,
                         "config_revision": authorization.config_revision,
                         "observed_at": authorization.observed_at,
                         "correlation_id": authorization.correlation_id,
                         "activity_id": authorization.activity_id,
                         "attempt_id": authorization.attempt_id}
        if authorization.correlation_id != correlation_id:
            raise ValueError("authorization decision correlation does not match the work order")
        if authorization.activity_id not in (None, activity_id):
            raise ValueError("authorization decision activity does not match the work order")
        if authorization.attempt_id not in (None, attempt_id):
            raise ValueError("authorization decision attempt does not match the work order")
        details = {"contract_id": work_order["contract_id"],
                   "contract_version": work_order["contract_version"],
                   "work_order": work_order, "authorization": auth_evidence,
                   "activity_id": activity_id, "attempt_id": attempt_id,
                   "correlation_id": correlation_id}
        existing = await self.get_engineering_work_order(order_id)
        if existing is not None:
            stored = existing.get("details", {})
            if (stored.get("work_order") == work_order
                    and stored.get("authorization") == auth_evidence
                    and stored.get("activity_id") == activity_id
                    and stored.get("correlation_id") == correlation_id):
                return True
            raise ValueError("work_order_id already exists with different durable content")
        return await self.transition(
            "engineering_work_order", order_id, "engineering.work-order", 1,
            "AUTHORIZED", "authorized work order issued", details, initial=True,
            correlation_id=uuid.UUID(correlation_id), causation_id=uuid.UUID(attempt_id))

    async def transition_engineering_work_order(self, work_order_id: str, next_state: str,
                                                activity_id: str, attempt_id: str,
                                                correlation_id: str, reason: str,
                                                details: dict[str, Any], *,
                                                work_order: EngineeringWorkOrder | None = None,
                                                verification: VerificationResult | None = None) -> bool:
        """Record one guarded work-order transition with activity/attempt event lineage."""
        order_id = str(uuid.UUID(work_order_id))
        activity = str(uuid.UUID(activity_id))
        attempt = str(uuid.UUID(attempt_id))
        correlation = str(uuid.UUID(correlation_id))
        if not isinstance(details, dict):
            raise ValueError("work-order transition details must be an object")
        immutable = {"contract_id", "contract_version", "work_order", "authorization",
                     "activity_id", "attempt_id", "correlation_id", "transition_attempt_id"}
        if immutable & details.keys():
            raise ValueError("transition details cannot replace immutable work-order provenance")
        if next_state == "COMPLETED":
            if not isinstance(work_order, EngineeringWorkOrder) or not isinstance(verification, VerificationResult):
                raise PermissionError("COMPLETED requires typed work-order and independent verification contracts")
            if work_order.to_dict().get("work_order_id") != order_id:
                raise ValueError("completion work order identity does not match transition")
            validate_completion(work_order, verification)
            details = {**details, "verification_result": verification.to_dict()}
        elif work_order is not None or verification is not None:
            raise ValueError("verification contracts are accepted only for a COMPLETED transition")
        async with self.pool.connection() as conn, conn.transaction():
            existing = await (await conn.execute(
                "SELECT state,details FROM r3a.runtime_entities "
                "WHERE entity_type='engineering_work_order' AND entity_id=%s FOR UPDATE",
                (order_id,))).fetchone()
            if existing is None:
                raise KeyError(f"unknown engineering work order: {order_id}")
            stored_details = existing.get("details") or {}
            stored_order = stored_details.get("work_order")
            if (stored_details.get("activity_id") != activity
                    or stored_details.get("correlation_id") != correlation):
                raise ValueError("transition lineage does not match the durable work order")
            if next_state == "COMPLETED":
                if work_order.to_dict() != stored_order:
                    raise ValueError("completion work order does not match the immutable durable order")
                if existing.get("state") != "VERIFYING":
                    raise ValueError("work order must be VERIFYING before completion")
            evidence = {**stored_details, **details, "work_order_id": order_id,
                        "activity_id": activity, "attempt_id": stored_details.get("attempt_id"),
                        "transition_attempt_id": attempt, "correlation_id": correlation}
            return await self._transition_on_conn(
                conn, "engineering_work_order", order_id, "engineering.work-order", 1,
                next_state, reason, evidence, correlation_id=uuid.UUID(correlation),
                causation_id=uuid.UUID(attempt))

    async def get_engineering_work_order(self, work_order_id: str) -> dict[str, Any] | None:
        """Read the latest durable order projection without scanning historical events."""
        order_id = str(uuid.UUID(work_order_id))
        rows = await self.rows(
            "SELECT entity_id,state,details,version,updated_at FROM r3a.runtime_entities "
            "WHERE entity_type='engineering_work_order' AND entity_id=%s",
            (order_id,))
        if not rows:
            return None
        return rows[0]

    async def record_engineering_proposal(self, activity: dict[str, Any],
                                          proposal: EngineeringProposal) -> dict[str, Any]:
        """Checkpoint a Grace proposal on its existing activity and append its full revision evidence."""
        if not isinstance(proposal, EngineeringProposal):
            raise TypeError("proposal must be a validated EngineeringProposal")
        activity_id = str(uuid.UUID(str(activity["activity_id"])))
        attempt_id = str(uuid.UUID(str(activity["attempt_id"])))
        objective_input = activity.get("input") or {}
        correlation_id = objective_input.get("correlation_id")
        if not isinstance(correlation_id, str) or str(uuid.UUID(correlation_id)) != proposal.correlation_id:
            raise ValueError("proposal correlation does not match durable objective intake")
        if proposal.activity_id != activity_id or proposal.attempt_id != attempt_id:
            raise ValueError("proposal activity/attempt lineage does not match the current lease")
        if proposal.objective != objective_input.get("objective"):
            raise ValueError("proposal objective does not match the durable assignment")
        digest = proposal_digest(proposal)
        checkpoint = dict(activity.get("checkpoint") or {})
        revisions = list(checkpoint.get("engineering_proposal_revisions") or [])
        same = next((item for item in revisions
                     if item.get("proposal_id") == proposal.proposal_id
                     and item.get("proposal_revision") == proposal.proposal_revision), None)
        if same:
            if same.get("proposal_digest") != digest:
                raise ValueError("proposal revision is immutable once durably recorded")
            return {"recorded": False, "proposal_digest": digest,
                    "proposal_revision": proposal.proposal_revision}
        prior_for_id = [item for item in revisions if item.get("proposal_id") == proposal.proposal_id]
        expected_revision = (max(item["proposal_revision"] for item in prior_for_id) + 1) if prior_for_id else 1
        if proposal.proposal_revision != expected_revision:
            raise ValueError("proposal revision must advance monotonically within its proposal identity")
        revisions.append({"proposal_id": proposal.proposal_id,
                          "proposal_revision": proposal.proposal_revision,
                          "proposal_digest": digest, "created_at": proposal.created_at})
        checkpoint.update({"engineering_proposal": proposal.to_dict(),
                           "engineering_proposal_digest": digest,
                           "engineering_proposal_revisions": revisions})
        await self.record_progress(activity,
            {"phase": "engineering.proposal.recorded", "proposal_id": proposal.proposal_id,
             "proposal_revision": proposal.proposal_revision, "proposal_digest": digest,
             "proposal": proposal.to_dict()}, checkpoint)
        return {"recorded": True, "proposal_digest": digest,
                "proposal_revision": proposal.proposal_revision}

    async def _transition_on_conn(self, conn, entity_type: str, entity_id: str,
                                  machine_id: str, machine_version: int,
                                  next_state: str, reason: str,
                                  evidence: dict[str, Any] | None = None,
                                  *, initial: bool = False,
                                  event_id: uuid.UUID | None = None,
                                  correlation_id: uuid.UUID | None = None,
                                  causation_id: uuid.UUID | None = None) -> bool:
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
                              outcome="rejected", event_id=event_id,
                              correlation_id=correlation_id, causation_id=causation_id)
            return False
        current = await (await conn.execute(
            "SELECT revision_id FROM r3a.config_current WHERE singleton=true"
        )).fetchone()
        if row:
            await conn.execute(
                "UPDATE r3a.runtime_entities SET machine_id=%s,machine_version=%s,state=%s,details=%s,config_revision=%s,version=version+1,updated_at=clock_timestamp() "
                "WHERE entity_type=%s AND entity_id=%s",
                (machine_id, machine_version, next_state, json.dumps(evidence or {}), current["revision_id"] if current else None,
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
                          event_id=event_id, correlation_id=correlation_id,
                          causation_id=causation_id)
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
                                  contract_version: str = "1.0.0", metadata: dict[str, Any] | None = None,
                                  health: str = "available") -> None:
        if access_mode not in {"read_only", "read_write"}:
            raise ValueError("Unsupported capability access mode")
        if health not in {"available", "not_probed", "degraded", "unavailable"}:
            raise ValueError("Unsupported capability provider availability")
        async with self.pool.connection() as conn, conn.transaction():
            await conn.execute(
                "INSERT INTO r3a.capability_registry(capability_id,contract_version,owner,access_mode,health,observed_at,metadata) "
                "VALUES (%s,%s,%s,%s,%s,clock_timestamp(),%s) ON CONFLICT(capability_id) DO UPDATE SET "
                "contract_version=EXCLUDED.contract_version,owner=EXCLUDED.owner,access_mode=EXCLUDED.access_mode,"
                "health=EXCLUDED.health,observed_at=EXCLUDED.observed_at,metadata=EXCLUDED.metadata",
                (capability_id, contract_version, owner, access_mode, health, json.dumps(metadata or {})),
            )

    async def grant_capability(self, module_id: str, capability_id: str, reason: str,
                               activity_id: str | None = None) -> uuid.UUID:
        async with self.pool.connection() as conn, conn.transaction():
            found = await (await conn.execute(
                "SELECT access_mode FROM r3a.capability_registry WHERE capability_id=%s", (capability_id,)
            )).fetchone()
            if found is None:
                raise KeyError(f"Capability is not registered: {capability_id}")
            if found["access_mode"] != "read_only" and activity_id is None:
                raise PermissionError("effectful capability grants must be scoped to one durable activity")
            scope = {"activity_id": str(uuid.UUID(activity_id))} if activity_id is not None else {}
            active = await (await conn.execute(
                "SELECT grant_id FROM r3a.capability_grants WHERE module_id=%s AND capability_id=%s "
                "AND scope=%s::jsonb AND revoked_at IS NULL FOR UPDATE",
                (module_id, capability_id, json.dumps(scope))
            )).fetchone()
            if active:
                return active["grant_id"]
            grant_id = uuid.uuid4()
            await conn.execute(
                "INSERT INTO r3a.capability_grants(grant_id,module_id,capability_id,granted_by,reason,scope) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (grant_id, module_id, capability_id, f"uid:{os.getuid()}", reason, json.dumps(scope)),
            )
            await self._event(conn, "capability.granted", "capability", capability_id,
                              None, None, None, "ACTIVE", reason,
                              {"module_id": module_id, "grant_id": str(grant_id), "scope": scope})
            return grant_id

    async def require_capability(self, module_id: str, capability_id: str,
                                 activity_id: str | None = None) -> None:
        async with self.pool.connection() as conn:
            row = await (await conn.execute(
                "SELECT 1 FROM r3a.capability_grants WHERE module_id=%s AND capability_id=%s "
                "AND revoked_at IS NULL AND (scope='{}'::jsonb OR "
                "(scope ? 'activity_id' AND scope->>'activity_id'=%s)) LIMIT 1",
                (module_id, capability_id, str(activity_id) if activity_id else None),
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
                    "task_classes": list(role.task_classes),
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
                "AND NOT (input ? 'dependencies') "
                "AND available_at<=clock_timestamp() ORDER BY available_at,created_at"
            )).fetchall()

    async def waiting_dependency_activities(self) -> list[dict[str, Any]]:
        async with self.pool.connection() as conn:
            return await (await conn.execute(
                "SELECT activity_id,input FROM r3a.activities WHERE state='WAITING' "
                "AND activity_type='grace.objective' AND input ? 'dependencies' "
                "ORDER BY created_at LIMIT 256"
            )).fetchall()

    async def requeue_dependency_activity(self, activity_id: uuid.UUID) -> str:
        """Requeue a parked objective only after every durable prerequisite completed."""
        async with self.pool.connection() as conn, conn.transaction():
            row = await (await conn.execute(
                "SELECT activity_id,input,machine_id,machine_version FROM r3a.activities "
                "WHERE activity_id=%s AND state='WAITING' FOR UPDATE SKIP LOCKED", (activity_id,)
            )).fetchone()
            if row is None:
                return "unchanged"
            dependencies = ActivityDependencySet.from_value((row["input"] or {}).get("dependencies"))
            if dependencies is None:
                return "unchanged"
            states = await (await conn.execute(
                "SELECT activity_id,state,latest_event_id FROM r3a.activities WHERE activity_id=ANY(%s)",
                ([uuid.UUID(value) for value in dependencies.activity_ids],),
            )).fetchall()
            by_id = {str(item["activity_id"]): item for item in states}
            failed = [item for item in dependencies.activity_ids
                      if by_id.get(item, {}).get("state") == "CANCELLED"]
            if failed:
                reason = "activity_dependency_not_completed"
                evidence = {"dependency_contract": dependencies.to_dict(),
                            "unfulfilled_dependencies": failed,
                            "dependency_states": {item: by_id[item]["state"] for item in failed}}
                await conn.execute(
                    "UPDATE r3a.activities SET state='BLOCKED',lease_owner=NULL,lease_until=NULL,exception=%s,"
                    "updated_at=clock_timestamp() WHERE activity_id=%s",
                    (json.dumps({"reason": reason, **evidence}), row["activity_id"]),
                )
                event_id = await self._event(
                    conn, "activity.dependencies.blocked", "activity", str(row["activity_id"]),
                    row["machine_id"], row["machine_version"], "WAITING", "BLOCKED", reason, evidence,
                    correlation_id=uuid.UUID((row["input"] or {}).get("correlation_id") or str(row["activity_id"])))
                accepted = await self._transition_on_conn(
                    conn, "activity", str(row["activity_id"]), row["machine_id"], row["machine_version"],
                    "BLOCKED", reason, evidence, event_id=event_id)
                if not accepted:
                    raise InvalidTransition(f"Cannot block dependent activity {row['activity_id']}")
                await conn.execute("UPDATE r3a.activities SET latest_event_id=%s WHERE activity_id=%s",
                                   (event_id, row["activity_id"]))
                return "blocked"
            if any(by_id.get(item, {}).get("state") != "COMPLETED"
                   for item in dependencies.activity_ids):
                return "waiting"
            evidence = {"dependency_contract": dependencies.to_dict(),
                        "completed_dependencies": dependencies.activity_ids}
            causation_id = next((by_id[item]["latest_event_id"] for item in dependencies.activity_ids
                                 if by_id.get(item, {}).get("latest_event_id")), None)
            await conn.execute(
                "UPDATE r3a.activities SET state='QUEUED',available_at=clock_timestamp(),exception=NULL,"
                "updated_at=clock_timestamp() WHERE activity_id=%s", (row["activity_id"],),
            )
            event_id = await self._event(
                conn, "activity.dependencies.satisfied", "activity", str(row["activity_id"]),
                row["machine_id"], row["machine_version"], "WAITING", "QUEUED",
                "all prerequisite activities completed", evidence,
                correlation_id=uuid.UUID((row["input"] or {}).get("correlation_id") or str(row["activity_id"])),
                causation_id=causation_id)
            accepted = await self._transition_on_conn(
                conn, "activity", str(row["activity_id"]), row["machine_id"], row["machine_version"],
                "QUEUED", "all prerequisite activities completed", evidence,
                event_id=event_id, causation_id=causation_id)
            if not accepted:
                raise InvalidTransition(f"Cannot requeue dependent activity {row['activity_id']}")
            await conn.execute("UPDATE r3a.activities SET latest_event_id=%s WHERE activity_id=%s",
                               (event_id, row["activity_id"]))
            return "queued"

    async def activity_dependency_context(self, dependencies_value: Any) -> list[dict[str, Any]]:
        dependencies = ActivityDependencySet.from_value(dependencies_value)
        if dependencies is None:
            return []
        async with self.pool.connection() as conn:
            rows = await (await conn.execute(
                "SELECT activity_id,state,result,updated_at FROM r3a.activities WHERE activity_id=ANY(%s)",
                ([uuid.UUID(value) for value in dependencies.activity_ids],),
            )).fetchall()
        by_id = {str(row["activity_id"]): row for row in rows}
        context = []
        for dependency_id in dependencies.activity_ids:
            row = by_id.get(dependency_id)
            result = row.get("result") if row else None
            digest = hashlib.sha256(json.dumps(result, sort_keys=True, separators=(",", ":"),
                                      default=str).encode()).hexdigest() if result is not None else None
            context.append({"activity_id": dependency_id,
                            "state": row["state"] if row else "NOT_FOUND",
                            "updated_at": row["updated_at"].isoformat() if row else None,
                            "result_sha256": digest})
        return context

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

    async def get_capability_invocation(self, idempotency_key: str) -> dict[str, Any] | None:
        """Load a durable canonical invocation by its stable idempotency key."""
        rows = await self.rows(
            "SELECT idempotency_key,request_digest,state,result,evidence,updated_at "
            "FROM r3a.capability_invocations WHERE idempotency_key=%s", (idempotency_key,))
        return rows[0] if rows else None

    async def begin_capability_invocation(self, request: dict[str, Any], request_digest: str,
                                          authorization: dict[str, Any]) -> dict[str, Any]:
        """Persist authorization and STARTED before effects; reserve bounded activity usage atomically."""
        key = request.get("idempotency_key")
        if not isinstance(key, str) or not key:
            raise ValueError("canonical invocation requires an idempotency key")
        async with self.pool.connection() as conn, conn.transaction():
            existing = await (await conn.execute(
                "SELECT idempotency_key,request_digest,state,result,evidence,updated_at "
                "FROM r3a.capability_invocations WHERE idempotency_key=%s FOR UPDATE", (key,))).fetchone()
            if existing:
                if existing["request_digest"] != request_digest:
                    raise ValueError("idempotency key already belongs to a different canonical request")
                return {**existing, "created": False}
            reservation = request.get("budget_reservation")
            if reservation is not None:
                activity_id = uuid.UUID(reservation["activity_id"])
                activity = await (await conn.execute(
                    "SELECT state,attempt_id,config_revision FROM r3a.activities "
                    "WHERE activity_id=%s FOR UPDATE", (activity_id,))).fetchone()
                if (activity is None or activity["state"] != "RUNNING"
                        or str(activity["attempt_id"]) != request["attempt_id"]
                        or str(activity["config_revision"]) != request["config_revision"]
                        or reservation["activity_id"] != request["activity_id"]):
                    raise PermissionError("budget reservation is outside the live activity attempt/configuration")
                prior = await (await conn.execute(
                    "SELECT COALESCE(sum((request->'budget_reservation'->>'units')::bigint),0) AS units, "
                    "COALESCE(bool_and(request->'budget_reservation'->>'policy_revision'=%s "
                    "AND (request->'budget_reservation'->>'limit')::bigint=%s),true) AS compatible "
                    "FROM r3a.capability_invocations "
                    "WHERE request->'budget_reservation'->>'activity_id'=%s "
                    "AND request->'budget_reservation'->>'resource'=%s",
                    (reservation["policy_revision"], reservation["limit"],
                     reservation["activity_id"], reservation["resource"]))).fetchone()
                if not prior["compatible"]:
                    raise ValueError("activity budget policy revision or limit conflicts with prior reservations")
                if int(prior["units"]) + reservation["units"] > reservation["limit"]:
                    raise ValueError("activity budget reservation exceeds its configured limit")
            await conn.execute(
                "INSERT INTO r3a.capability_invocations(idempotency_key,invocation_id,operation_id,"
                "request_digest,state,request,authorization_evidence,evidence) VALUES (%s,%s,%s,%s,'STARTED',%s,%s,%s)",
                (key, request["invocation_id"], request["operation_id"], request_digest,
                 json.dumps(request), json.dumps(authorization), json.dumps({"phase": "authorized"})))
            await self._event(conn, "capability.invocation.started", "capability_invocation",
                              request["invocation_id"], None, None, None, "STARTED",
                              "CME authorized canonical invocation before provider execution",
                              {"idempotency_key": key, "operation_id": request["operation_id"],
                               "authorization": authorization}, correlation_id=uuid.UUID(request["correlation_id"]))
            return {"idempotency_key": key, "request_digest": request_digest,
                    "state": "STARTED", "result": None, "evidence": {"phase": "authorized"},
                    "created": True}

    async def finish_capability_invocation(self, idempotency_key: str, request_digest: str,
                                           result: dict[str, Any]) -> None:
        """Commit canonical invocation result and audit evidence atomically."""
        async with self.pool.connection() as conn, conn.transaction():
            row = await (await conn.execute(
                "SELECT invocation_id,operation_id,request_digest,state,result FROM r3a.capability_invocations "
                "WHERE idempotency_key=%s FOR UPDATE", (idempotency_key,))).fetchone()
            if row is None or row["request_digest"] != request_digest:
                raise ValueError("canonical invocation STARTED record is missing or mismatched")
            if row["state"] == "SUCCEEDED":
                if row["result"] != result:
                    raise ValueError("completed idempotent invocation result changed")
                return
            await conn.execute(
                "UPDATE r3a.capability_invocations SET state=%s,result=%s,evidence=%s,updated_at=clock_timestamp() "
                "WHERE idempotency_key=%s",
                (result["outcome"], json.dumps(result), json.dumps(result["evidence"]), idempotency_key))
            await self._event(conn, "capability.invocation.finished", "capability_invocation",
                              row["invocation_id"], None, None, "STARTED", result["outcome"],
                              "CME persisted canonical invocation result",
                              {"idempotency_key": idempotency_key, "operation_id": row["operation_id"],
                               "invocation_result": result}, outcome=result["outcome"].lower())

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
                "health=EXCLUDED.health,observed_at=clock_timestamp(),"
                "diagnostic=CASE WHEN EXCLUDED.diagnostic='{}'::jsonb "
                "THEN r3a.module_registry.diagnostic ELSE EXCLUDED.diagnostic END",
                (manifest["module_id"], manifest["module_version"], manifest["contract_id"],
                 manifest["protocol_major"], manifest["protocol_minor"], manifest["artifact_ref"],
                 manifest["artifact_digest"], json.dumps(manifest), lifecycle, health, json.dumps(diagnostic or {})),
            )

    async def module_state(self, module_id: str, module_version: str, lifecycle: str,
                           health: str, diagnostic: dict[str, Any] | None = None,
                           *, machine_version: int = 1) -> None:
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
                await self._transition_on_conn(conn, "module", entity_id, "module.lifecycle", machine_version,
                                               "INSTALLED", "module installation observed",
                                               {"version": module_version}, initial=True)
            accepted = await self._transition_on_conn(conn, "module", entity_id, "module.lifecycle", machine_version,
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
                                        new_version: str, *, machine_version: int = 1) -> None:
        async with self.pool.connection() as conn, conn.transaction():
            await self._event(conn, "module.replaced", "module",
                              f"{module_id}@{old_version}", "module.lifecycle", machine_version,
                              "STOPPED", "STOPPED", "module replacement completed",
                              {"module_id": module_id, "old_version": old_version,
                               "new_version": new_version})

    async def _schedule_observer_activity_on_conn(self, conn, delay_seconds: float = 0,
                                                  reason: str = "observer activity queued") -> bool:
        """Keep one durable observer pending across concurrent CME completion/startup paths."""
        await conn.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended('r3a.foundation-observer-activity', 0))"
        )
        active = await (await conn.execute(
            "SELECT activity_id FROM r3a.activities "
            "WHERE state IN ('QUEUED','RUNNING','WAITING','RECOVERING','BLOCKED') "
            "AND activity_type='foundation.observe' LIMIT 1"
        )).fetchone()
        if active:
            return False
        activity_id = uuid.uuid4()
        key = f"foundation.observe:{activity_id}"
        config = await (await conn.execute(
            "SELECT revision_id FROM r3a.config_current WHERE singleton=true"
        )).fetchone()
        await conn.execute(
            "INSERT INTO r3a.activities(activity_id,activity_type,idempotency_key,machine_id,machine_version,state,available_at,recovery_policy,config_revision) "
            "VALUES (%s,'foundation.observe',%s,'activity.generic',1,'QUEUED',"
            "clock_timestamp()+(%s * interval '1 second'),'idempotent',%s)",
            (activity_id, key, delay_seconds, config["revision_id"] if config else None),
        )
        accepted = await self._transition_on_conn(conn, "activity", str(activity_id), "activity.generic", 1,
                                                  "QUEUED", reason,
                                                  {"idempotency_key": key}, initial=True)
        if not accepted:
            raise InvalidTransition("Observer activity could not enter QUEUED")
        return True

    async def ensure_observer_activity(self) -> None:
        async with self.pool.connection() as conn, conn.transaction():
            await self._schedule_observer_activity_on_conn(conn)

    async def submit_grace_objective(self, objective: str, idempotency_key: str,
                                     event_kind: str = "objective",
                                     route_id: str | None = None,
                                     role_id: str | None = None,
                                     required_capabilities: tuple[str, ...] = (),
                                     required_modalities: tuple[str, ...] = (),
                                     acceptance_criteria: list[dict[str, Any]] | None = None,
                                     engineering_assignment: dict[str, Any] | None = None,
                                     depends_on_activity_ids: Any = None,
                                     requested_activity_id: str | None = None,
                                     task_class: str = "objective_reasoning",
                                     notification_envelope: dict[str, Any] | None = None) -> dict[str, Any]:
        """Durably enqueue one objective/notification; duplicate keys return the same activity."""
        if not objective.strip() or len(objective) > 4000:
            raise ValueError("event content must contain 1 to 4000 characters")
        if not idempotency_key.strip() or len(idempotency_key) > 200:
            raise ValueError("idempotency_key must contain 1 to 200 characters")
        if event_kind not in {"objective", "notification"}:
            raise ValueError("event_kind must be objective or notification")
        if (event_kind == "notification") != (notification_envelope is not None):
            raise ValueError("notification event kind requires exactly one versioned notification envelope")
        if notification_envelope is not None:
            notification_envelope = validate_notification_envelope(notification_envelope)
        if event_kind != "objective" and depends_on_activity_ids:
            raise ValueError("only objectives may depend on other activities")
        if task_class not in {"objective_reasoning", "vision"}:
            raise ValueError("Grace objective intake cannot use autonomic-only task classes")
        dependencies = ActivityDependencySet.from_value(depends_on_activity_ids)
        selected_activity_id = uuid.UUID(requested_activity_id) if requested_activity_id else uuid.uuid4()
        if dependencies and str(selected_activity_id) in dependencies.activity_ids:
            raise ValueError("an activity cannot depend on itself")
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
        if engineering_assignment is not None:
            engineering_assignment = validate_engineering_assignment(engineering_assignment)
            if acceptance_criteria:
                raise ValueError("Engineering assignments use their own typed acceptance criteria")
            acceptance_criteria = []
        elif notification_envelope is None:
            acceptance_criteria = validate_required_criteria(acceptance_criteria)
        else:
            acceptance_criteria = []
        if role_id is None and self.settings.model_roles:
            if route_id is None:
                role_id = self.settings.model_role_for_task(task_class).role_id
            else:
                matching_roles = [entry for entry in self.settings.model_roles if entry.route_id == route_id]
                if len(matching_roles) != 1:
                    raise ValueError("an explicit route must resolve to exactly one configured model role")
                role_id = matching_roles[0].role_id
        if role_id is not None:
            role = next((entry for entry in self.settings.model_roles if entry.role_id == role_id), None)
            if role is None:
                raise ValueError("requested model role is not configured")
            if task_class not in role.task_classes:
                raise ValueError(f"model role {role.role_id} is not authorized for {task_class}")
            if route_id is not None and route_id != role.route_id:
                raise ValueError("route_id must match the configured route for the requested role")
            selected_route_id = role.route_id
            selected_role_id = role.role_id
        else:
            selected_route_id = self.settings.model_route(route_id).route_id
            selected_role_id = None
        event_input = {"objective": objective, "event_kind": event_kind,
                       "task_class": task_class,
                       "route_id": selected_route_id if selected_role_id is None else None,
                       "role_id": selected_role_id,
                       "required_capabilities": list(required_capabilities),
                       "required_modalities": list(required_modalities),
                       "acceptance_contract": {"contract_id": OBJECTIVE_ACCEPTANCE_CONTRACT_ID,
                                                "contract_version": OBJECTIVE_ACCEPTANCE_CONTRACT_VERSION,
                                                "criteria": acceptance_criteria},
                       "engineering_assignment": engineering_assignment,
                       "role_config_revision": self.settings.source_digest if selected_role_id else None}
        if notification_envelope is not None:
            event_input["notification"] = notification_envelope
        policy = self.settings.reasoning_escalation
        if policy is not None:
            event_input["reasoning_escalation"] = {
                "contract_id": policy.contract_id,
                "contract_version": policy.contract_version,
                "enabled": policy.enabled,
                "authorization_capability_id": policy.authorization_capability_id,
                "allowed_role_ids": list(policy.allowed_role_ids),
                "max_requests_per_activity": policy.max_requests_per_activity,
                "max_completion_tokens_per_activity": policy.max_completion_tokens_per_activity,
                "config_revision": self.settings.source_digest,
            }
        if dependencies:
            event_input["dependencies"] = dependencies.to_dict()
        if requested_activity_id:
            event_input["requested_activity_id"] = str(selected_activity_id)
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
                prior_input.setdefault("acceptance_contract", {
                    "contract_id": OBJECTIVE_ACCEPTANCE_CONTRACT_ID,
                    "contract_version": OBJECTIVE_ACCEPTANCE_CONTRACT_VERSION,
                    "criteria": []})
                prior_input.setdefault("role_config_revision", None)
                prior_input.setdefault("engineering_assignment", None)
                if not dependencies:
                    prior_input.setdefault("dependencies", None)
                    if prior_input.get("dependencies") is None:
                        prior_input.pop("dependencies", None)
                prior_input.setdefault("requested_activity_id", None)
                if prior_input.get("requested_activity_id") is None:
                    prior_input.pop("requested_activity_id", None)
                prior_input.pop("authorized_capability", None)
                prior_input.pop("correlation_id", None)
                if (existing["activity_type"] != "grace.objective"
                        or not same_notification_input(prior_input, event_input)
                        or (requested_activity_id and str(existing["activity_id"]) != str(selected_activity_id))):
                    raise ValueError("idempotency key already belongs to a different request")
                return {**existing, "duplicate": True}
            activity_id = selected_activity_id
            state = "QUEUED"
            if dependencies:
                rows = await (await conn.execute(
                    "SELECT activity_id,state FROM r3a.activities WHERE activity_id=ANY(%s)",
                    ([uuid.UUID(value) for value in dependencies.activity_ids],),
                )).fetchall()
                dependency_states = {str(row["activity_id"]): row["state"] for row in rows}
                if any(dependency_states.get(value) == "CANCELLED"
                       for value in dependencies.activity_ids):
                    state = "BLOCKED"
                elif any(dependency_states.get(value) != "COMPLETED"
                         for value in dependencies.activity_ids):
                    state = "WAITING"
            correlation_id = (uuid.UUID(notification_envelope["correlation_id"])
                              if notification_envelope else uuid.uuid4())
            durable_input = {**event_input, "correlation_id": str(correlation_id)}
            config = await (await conn.execute(
                "SELECT revision_id FROM r3a.config_current WHERE singleton=true"
            )).fetchone()
            await conn.execute(
                "INSERT INTO r3a.activities(activity_id,activity_type,idempotency_key,machine_id,machine_version,state,"
                "available_at,recovery_policy,config_revision,input) "
                "VALUES (%s,'grace.objective',%s,'activity.generic',1,%s,clock_timestamp(),'idempotent',%s,%s)",
                (activity_id, idempotency_key, state, config["revision_id"] if config else None,
                 json.dumps(durable_input)),
            )
            event_type = ("grace.notification.received" if event_kind == "notification"
                          else "grace.objective.received")
            initial_reason = ("Grace objective parked awaiting prerequisite activities"
                              if state == "WAITING" else
                              "Grace objective has an unfulfillable prerequisite"
                              if state == "BLOCKED" else "Grace objective accepted into durable inbox")
            event_id = await self._event(conn, event_type, "activity", str(activity_id),
                                         "activity.generic", 1, None, state, initial_reason,
                                         {"idempotency_key": idempotency_key, "objective_sha256": hashlib.sha256(objective.encode()).hexdigest(),
                                          "event_kind": event_kind, "route_id": selected_route_id,
                                          "role_id": selected_role_id,
                                          "required_capabilities": list(required_capabilities),
                                         "required_modalities": list(required_modalities),
                                          "dependencies": dependencies.to_dict() if dependencies else None,
                                          "acceptance_contract": event_input["acceptance_contract"],
                                          "notification": notification_envelope},
                                         correlation_id=correlation_id,
                                         causation_id=(uuid.UUID(notification_envelope["event_id"])
                                                       if notification_envelope else None))
            accepted = await self._transition_on_conn(conn, "activity", str(activity_id),
                                                       "activity.generic", 1, state,
                                                       initial_reason,
                                                       {"idempotency_key": idempotency_key,
                                                        "received_event_id": str(event_id),
                                                        "dependencies": dependencies.to_dict() if dependencies else None}, initial=True)
            if not accepted:
                raise InvalidTransition(f"Grace objective could not enter {state}")
            await conn.execute("UPDATE r3a.activities SET latest_event_id=%s WHERE activity_id=%s",
                               (event_id, activity_id))
            return {"activity_id": activity_id, "state": state, "activity_type": "grace.objective",
                    "idempotency_key": idempotency_key, "attempt_count": 0, "duplicate": False,
                    "event_kind": event_kind, "route_id": selected_route_id,
                    "correlation_id": correlation_id, "received_event_id": event_id}

    async def ingest_institution_event_notification(self, source_id: str, source_event_id: str,
                                                    idempotency_key: str) -> dict[str, Any]:
        """Import one existing event into Grace's durable activity path; never mutates the source."""
        source = next((item for item in self.settings.notification_sources
                       if item.source_id == source_id and item.enabled
                       and item.adapter == "institution_events.v1"), None)
        if source is None or source_id != INSTITUTION_EVENT_SOURCE:
            raise PermissionError("notification source is not enabled by bootstrap configuration")
        try:
            source_uuid = uuid.UUID(source_event_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("source_event_id must be a UUID") from exc
        events = await self.rows(
            "SELECT event_id,event_type,schema_version,subject_type,subject_id,prior_state,next_state,"
            "occurred_at,persisted_at,actor,correlation_id,reason,outcome,config_revision,implementation_revision,evidence "
            "FROM r3a.institution_events WHERE event_id=%s", (source_uuid,))
        if not events:
            raise KeyError(f"institution event not found: {source_event_id}")
        event = events[0]
        if source.event_types and event["event_type"] not in source.event_types:
            raise PermissionError("source event type is not enabled for notification intake")
        received_at = datetime.now(timezone.utc).isoformat()
        envelope = institution_event_envelope(event, received_at=received_at)
        prior, next_state = event.get("prior_state"), event.get("next_state")
        transition = (f"{prior} to {next_state}" if prior and next_state else
                      f"new state {next_state}" if next_state else "no state transition")
        objective = (f"Review this {envelope['severity']} service notification from {source_id}. "
                     f"Source event {source_event_id} reports {event['event_type']} for "
                     f"{event['subject_type']} {event['subject_id']} ({transition}): {event['reason']}. "
                     "Decide whether follow-up is warranted. Return a concise evidence-grounded disposition "
                     "and cite the notification evidence. Do not claim to perform external side effects.")
        stable_key = idempotency_key or f"notification:{source_id}:{source_event_id}"
        if stable_key != f"notification:{source_id}:{source_event_id}":
            raise ValueError("notification idempotency key must bind the source identity and event ID")
        return await self.submit_grace_objective(
            objective, stable_key, event_kind="notification", notification_envelope=envelope,
            acceptance_criteria=[])

    async def acknowledge_notification(self, activity: dict[str, Any]) -> None:
        """Record acknowledgment only after Grace returned an actual reasoning response."""
        envelope = (activity.get("input") or {}).get("notification")
        if not isinstance(envelope, dict):
            return
        async with self.pool.connection() as conn, conn.transaction():
            exists = await (await conn.execute(
                "SELECT 1 FROM r3a.institution_events WHERE event_type='grace.notification.acknowledged' "
                "AND subject_type='activity' AND subject_id=%s LIMIT 1", (str(activity["activity_id"]),)
            )).fetchone()
            if exists:
                return
            await self._event(conn, "grace.notification.acknowledged", "activity",
                              str(activity["activity_id"]), "activity.generic", 1, "RUNNING", "RUNNING",
                              "Grace returned a reasoning response to the notification",
                              {"source_id": envelope["source_id"],
                               "source_event_id": envelope["source_event_id"],
                               "payload_ref": envelope["payload_ref"]},
                              correlation_id=uuid.UUID(envelope["correlation_id"]),
                              causation_id=uuid.UUID(envelope["event_id"]))

    async def _notification_actionable(self, conn, activity: dict[str, Any], attempt_id: uuid.UUID) -> None:
        envelope = (activity.get("input") or {}).get("notification")
        if not isinstance(envelope, dict):
            return
        await self._event(
            conn, "grace.notification.actionable", "activity", str(activity["activity_id"]),
            "activity.generic", 1, activity["state"], "RUNNING",
            "CME made the notification available to Grace",
            {"source_id": envelope["source_id"], "source_event_id": envelope["source_event_id"],
             "attempt_id": str(attempt_id), "payload_ref": envelope["payload_ref"]},
            correlation_id=uuid.UUID(envelope["correlation_id"]),
            causation_id=uuid.UUID(envelope["event_id"]))

    async def _notification_outcome(self, conn, activity: dict[str, Any], outcome: str,
                                    details: dict[str, Any]) -> None:
        envelope = (activity.get("input") or {}).get("notification")
        if not isinstance(envelope, dict):
            return
        await self._event(
            conn, f"grace.notification.{outcome}", "activity", str(activity["activity_id"]),
            "activity.generic", 1, "RUNNING", "COMPLETED" if outcome == "resolved" else "BLOCKED",
            f"Grace notification {outcome}",
            {"source_id": envelope["source_id"], "source_event_id": envelope["source_event_id"],
             "payload_ref": envelope["payload_ref"], "details": details},
            correlation_id=uuid.UUID(envelope["correlation_id"]),
            causation_id=uuid.UUID(envelope["event_id"]))

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
            await self._notification_outcome(conn, activity, "blocked",
                                              {"reason": reason, **(details or {})})

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
            await self._notification_actionable(conn, row, attempt_id)
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
                              progress,
                              correlation_id=(uuid.UUID(activity["input"]["correlation_id"])
                                              if activity.get("input", {}).get("correlation_id") else None),
                              causation_id=activity["attempt_id"])

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
            await self._schedule_observer_activity_on_conn(
                conn, delay_seconds=self.settings.observer_interval_seconds,
                reason="next observer activity scheduled")
            await self._notification_outcome(conn, activity, "resolved", result)

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

    async def snapshot(self, *, include_events: bool = True) -> dict[str, Any]:
        async with self.pool.connection() as conn:
            current_config = await (await conn.execute(
                "SELECT r.revision_id,r.schema_version,r.source_digest,r.activated_at,r.config "
                "FROM r3a.config_current c JOIN r3a.config_revisions r USING(revision_id) WHERE c.singleton=true"
            )).fetchone()
            processes = await (await conn.execute("SELECT * FROM r3a.process_observations ORDER BY component_id")).fetchall()
            modules = await (await conn.execute("SELECT * FROM r3a.module_registry ORDER BY module_id,module_version")).fetchall()
            resources = await (await conn.execute("SELECT * FROM r3a.resource_registry ORDER BY resource_id")).fetchall()
            activities = await (await conn.execute("SELECT * FROM r3a.activities ORDER BY created_at DESC LIMIT 30")).fetchall()
            events = []
            if include_events:
                events = await (await conn.execute(
                    "SELECT * FROM r3a.institution_events ORDER BY persisted_at DESC LIMIT 100"
                )).fetchall()
            machines = await (await conn.execute("SELECT machine_id,machine_version,digest,definition FROM r3a.state_machine_definitions ORDER BY machine_id,machine_version")).fetchall()
            return {"configuration": current_config, "processes": processes, "modules": modules,
                    "resources": resources, "activities": activities, "events": events,
                    "state_machines": machines}
