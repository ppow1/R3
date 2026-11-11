"""
R3 CONTROLLED SOURCE
File: tests/test_r3a_activity_checkpoint_persistence.py
Component: R3A-ACTIVITY-CHECKPOINT-PERSISTENCE-REGRESSION
File Revision: 1.0.3
Created: 2026-11-10
Created By: Codex GPT-6
Purpose: Verify generic handler checkpoints persist through PostgreSQL progress updates and lease recovery.
Execution Model: Opt-in isolated PostgreSQL integration test using the existing CME activity ledger.
Observability: Reads the activity row after writes, interruption recovery, and retry claim.
Dependencies: psycopg 3; R3A Store migrations; shared #46 activity-handler fixture.
Authority: Steward corrective directive, Autonomy / CME Issue #43.
Changed: 2026-11-10T04:00:00Z | R3A-CHECKPOINT-PERSISTENCE-CORRECTION | Codex GPT-6 | Exercise atomic progress/checkpoint persistence and recovery against PostgreSQL.
Changed: 2026-11-10 | R3A-EXECUTOR-ROLE-P0 | Coordinator | Verify durable v1.1 role promotion preserves primary-module registration and lifecycle state.
Changed: 2026-11-10T20:10:03Z | R3A-GENERIC-OBJECTIVE-CONTINUATION | R3A Coordinator | Verify PostgreSQL parks and resumes objective-waiting handler activities after child completion.
Changed: 2026-11-10 | R3A-FS01-NOTIFICATION-ACK | R3A Coordinator | Verify notification acknowledgment requires a cited final disposition and shares the PostgreSQL completion transaction.
Supersedes: None.
Contracts: r3a.activity-handler.v1; r3a.activity-handler.objective-submission@1.0.0; activity.generic v1; existing CME activity/module ledgers.
Tests: Set R3A_CHECKPOINT_TEST_DSN to a disposable test database and run this module.
History/Predecessor: New permanent persistence regression.
"""
from __future__ import annotations

import json
import os
import uuid
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from psycopg.conninfo import conninfo_to_dict
from psycopg import AsyncConnection

from r3a_runtime.cme import CME
from r3a_runtime.db import Store
from r3a_runtime.provider_runtime import ProviderProcessManager
from tests.r3a_activity_handler_interop_provider import create_provider
from tests.test_r3a_activity_handler_interop import fixture
from r3a_runtime.capability_contracts import validate_module_manifest


ROOT = Path(__file__).resolve().parents[1]
TEST_DSN = os.environ.get("R3A_CHECKPOINT_TEST_DSN")


class SimulatedProcessInterruption(RuntimeError):
    pass


@unittest.skipUnless(TEST_DSN, "requires disposable PostgreSQL R3A_CHECKPOINT_TEST_DSN")
class ActivityCheckpointPostgresTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        info = conninfo_to_dict(TEST_DSN)
        database = str(info.get("dbname", "")).lower()
        if not database.startswith("r3a_checkpoint_test"):
            self.skipTest("R3A_CHECKPOINT_TEST_DSN must identify a dedicated test database")
        settings = SimpleNamespace(
            connection_info=info, worker_concurrency=1, lease_seconds=30,
            observer_interval_seconds=60,
            machine_catalog_dir=ROOT / "r3a_runtime" / "state_machines")
        self.store = Store(settings)
        async with await AsyncConnection.connect(self.store.conninfo, autocommit=True) as conn:
            await conn.execute("DROP SCHEMA IF EXISTS r3a CASCADE")
        await self.store.open()
        await self.store.migrate()
        await self.store.seed_machines()

    async def asyncTearDown(self):
        if hasattr(self, "store"):
            await self.store.close()

    async def test_primary_executor_role_promotion_is_durable_and_preserves_module_state(self):
        module_id = f"executor.fixture.{uuid.uuid4().hex}"
        old_manifest = {
            "module_id": module_id, "module_version": "1.0.0",
            "contract_id": "r3a.module.v1", "protocol_major": 1,
            "protocol_minor": 0, "protocol_min_minor": 0, "protocol_max_minor": 0,
            "owner": "test-owner", "entrypoint": "fixture.module",
            "dependencies": [], "configuration_schema": "r3a.bootstrap.v1",
            "configuration_ref": "/tmp/fixture-bootstrap.json", "capability_refs": [],
            "migration_contract": "none-v1", "artifact_ref": "/tmp/fixture-module.py",
            "artifact_digest": "a" * 64, "recovery_policy": "idempotent",
            "resource_refs": [], "state_namespace": module_id,
        }
        role = {
            "contract_id": "r3a.resident.executor", "contract_version": "1.0.0",
            "execution_contract_range": {"contract_id": "r3a.resident.execution",
                                         "major": 1, "min_minor": 0, "max_minor": 2},
        }
        diagnostic = {"source": "executor-role-postgres-regression"}
        await self.store.register_module(old_manifest, "ACTIVE", "healthy", diagnostic)
        promoted = {**old_manifest, "manifest_contract": "r3a.module-manifest.v1@1.1.0",
                    "resident_executor": role}
        await self.store.register_module(promoted, "ACTIVE", "healthy", diagnostic)

        rows = await self.store.rows(
            "SELECT manifest,artifact_digest,lifecycle_state,health,diagnostic FROM r3a.module_registry "
            "WHERE module_id=%s AND module_version='1.0.0'", (module_id,))
        events = await self.store.rows(
            "SELECT evidence FROM r3a.institution_events WHERE event_type='module.manifest.promoted' "
            "AND subject_type='module' AND subject_id=%s", (f"{module_id}@1.0.0",))
        self.assertEqual(1, len(rows))
        self.assertEqual(old_manifest["artifact_digest"], rows[0]["artifact_digest"])
        self.assertEqual(promoted, rows[0]["manifest"])
        self.assertEqual("ACTIVE", rows[0]["lifecycle_state"])
        self.assertEqual("healthy", rows[0]["health"])
        self.assertEqual(diagnostic, rows[0]["diagnostic"])
        self.assertEqual(1, len(events))
        self.assertEqual("r3a.module-manifest.v1@1.1.0", events[0]["evidence"]["manifest_contract"])

        with self.assertRaisesRegex(RuntimeError, "manifest is immutable"):
            await self.store.register_module({**promoted, "owner": "changed-owner"},
                                             "ACTIVE", "healthy", diagnostic)

    async def test_handler_checkpoint_survives_progress_and_process_loss_retry(self):
        sample = fixture()
        declared = validate_module_manifest(sample["module_manifest"], sample["operation"],
                                            sample["source_manifest"])
        self.assertEqual("1.1.0", declared["contract_version"])
        operation = SimpleNamespace(descriptor={
            **sample["operation"], "lifecycle": {"desired_state": "enabled"},
            "execution": {"timeout_seconds": 60}})
        registered = SimpleNamespace(
            descriptor={"provider": sample["operation"]["provider"]},
            legacy_manifest={"module_manifest": sample["module_manifest"],
                             "configuration_schema": sample["source_manifest"]["configuration_schema"]})
        module_manifest = ProviderProcessManager._manifest(
            object.__new__(ProviderProcessManager), registered)
        await self.store.register_module(module_manifest, "ACTIVE", "healthy")

        activity_id, attempt_id, lease_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        resource_id = f"checkpoint-test-{uuid.uuid4()}"
        correlation_id = uuid.uuid4()
        idempotency_key = f"checkpoint-test:{uuid.uuid4()}"
        activity_input = {"correlation_id": str(correlation_id),
                          "activity_input": dict(sample["activity_request"])}
        async with self.store.pool.connection() as conn, conn.transaction():
            await conn.execute(
                "INSERT INTO r3a.resource_registry(resource_id,contract_version,owner,capacity,allocated,health,observed_at) "
                "VALUES (%s,'1.0.0','checkpoint-test',1,1,'available',clock_timestamp())",
                (resource_id,))
            await conn.execute(
                "INSERT INTO r3a.activities(activity_id,activity_type,idempotency_key,machine_id,machine_version,state,"
                "available_at,attempt_id,attempt_count,lease_owner,lease_until,recovery_policy,input) "
                "VALUES (%s,'billing.invoice.review',%s,'activity.generic',1,'RUNNING',clock_timestamp(),%s,1,"
                "'checkpoint-test',clock_timestamp()+interval '1 hour','idempotent',%s)",
                (activity_id, idempotency_key, attempt_id, json.dumps(activity_input)))
            await conn.execute(
                "INSERT INTO r3a.resource_leases(lease_id,resource_id,activity_id,units,lease_until) "
                "VALUES (%s,%s,%s,1,clock_timestamp()+interval '1 hour')",
                (lease_id, resource_id, activity_id))
        if not await self.store.transition("activity", str(activity_id), "activity.generic", 1,
                                           "RUNNING", "checkpoint test begins", initial=True,
                                           correlation_id=correlation_id):
            self.fail("test activity could not enter RUNNING")

        registry_records = [{"descriptor": operation.descriptor}]
        cme = object.__new__(CME)
        cme.store = self.store
        cme.settings = SimpleNamespace(
            capability_registry=SimpleNamespace(
                discover=Mock(return_value=registry_records),
                resolve_provider=Mock(return_value=operation)))
        cme.module_id = "resident.grace"
        cme.module_version = "0.0.0"
        decision = SimpleNamespace(decision_id=str(uuid.uuid4()), audit_event_id=str(uuid.uuid4()),
                                   policy_revision="test-policy")
        cme._authorization_decision = AsyncMock(return_value=decision)
        provider_calls = []

        async def invoke(_operation, arguments, *, context):
            provider_calls.append(arguments["request"]["payload"]["checkpoint"])
            return create_provider({"mode": "fixture"}).invoke(arguments, context=context)

        cme.provider_runtime = SimpleNamespace(invoke=AsyncMock(side_effect=invoke))
        resolved = await cme._registered_handler("billing.invoice.review")
        activity = {
            "activity_id": str(activity_id), "attempt_id": str(attempt_id),
            "attempt_count": 1, "activity_type": "billing.invoice.review",
            "idempotency_key": idempotency_key, "input": activity_input,
            "checkpoint": {}, "resource_id": resource_id, "lease_id": str(lease_id),
        }

        async def interrupt_after_checkpoint(_activity, _result):
            raise SimulatedProcessInterruption("simulated worker loss after checkpoint commit")

        self.store.finish_activity = interrupt_after_checkpoint
        with self.assertRaises(SimulatedProcessInterruption):
            await cme._run_registered_activity(activity, resolved)

        row = (await self.store.rows(
            "SELECT progress,checkpoint FROM r3a.activities WHERE activity_id=%s", (activity_id,)))[0]
        self.assertEqual(sample["expected_result"]["progress"], row["progress"]["progress"])
        self.assertEqual(sample["expected_result"]["checkpoint"], row["checkpoint"]["handler_checkpoint"])

        # A later progress-only write must leave the checkpoint unchanged.
        await self.store.record_progress(activity, {"phase": "handler.progress", "progress": {"phase": "later"}})
        row = (await self.store.rows(
            "SELECT progress,checkpoint FROM r3a.activities WHERE activity_id=%s", (activity_id,)))[0]
        self.assertEqual(sample["expected_result"]["checkpoint"], row["checkpoint"]["handler_checkpoint"])

        # Expire only this test activity's lease and run the existing recovery/claim path.
        async with self.store.pool.connection() as conn, conn.transaction():
            await conn.execute("UPDATE r3a.activities SET lease_until=clock_timestamp()-interval '1 second' "
                               "WHERE activity_id=%s", (activity_id,))
        self.assertEqual(1, await self.store.recover_expired_activities())
        recovered = await self.store.claim_activity("checkpoint-test-retry", 30, resource_id)
        self.assertIsNotNone(recovered)
        self.assertEqual(sample["expected_result"]["checkpoint"],
                         recovered["checkpoint"]["handler_checkpoint"])

        # The stale attempt cannot replace the recovered attempt's checkpoint.
        with self.assertRaisesRegex(RuntimeError, "lease was lost"):
            await self.store.record_progress(
                activity, {"phase": "stale"},
                {"handler": recovered["checkpoint"]["handler"],
                 "handler_checkpoint": {"cursor": 999}})
        row = (await self.store.rows(
            "SELECT checkpoint FROM r3a.activities WHERE activity_id=%s", (activity_id,)))[0]
        self.assertEqual(sample["expected_result"]["checkpoint"], row["checkpoint"]["handler_checkpoint"])

        del self.store.finish_activity
        retry_activity = {**activity, **recovered}
        await cme._run_registered_activity(retry_activity, resolved)
        self.assertEqual([{}, sample["expected_result"]["checkpoint"]], provider_calls)
        final = (await self.store.rows(
            "SELECT state,checkpoint,result FROM r3a.activities WHERE activity_id=%s", (activity_id,)))[0]
        self.assertEqual("COMPLETED", final["state"])
        self.assertEqual(sample["expected_result"]["checkpoint"], final["checkpoint"]["handler_checkpoint"])

    async def test_handler_waits_on_objective_durably_and_requeues_after_child_completion(self):
        parent_id, child_id = uuid.uuid4(), uuid.uuid4()
        attempt_id, lease_id = uuid.uuid4(), uuid.uuid4()
        resource_id = f"objective-continuation-{uuid.uuid4()}"
        correlation_id = uuid.uuid4()
        handler = {"handler_id": "fixture.handler", "handler_version": "1.0.0",
                   "module_id": "fixture.module", "module_version": "1.0.0",
                   "artifact_digest": "a" * 64}
        pending_action = {"handler": handler,
                          "action": {"contract_id": "r3a.activity-handler.objective-submission",
                                     "contract_version": "1.0.0", "action_id": "review-child-1"},
                          "action_sha256": "b" * 64}
        checkpoint = {"handler": handler, "handler_checkpoint": {"phase": "submitted"},
                      "pending_action": pending_action, "action_history": []}
        deadline = "2099-01-01T00:00:00+00:00"
        async with self.store.pool.connection() as conn, conn.transaction():
            await conn.execute(
                "INSERT INTO r3a.resource_registry(resource_id,contract_version,owner,capacity,allocated,health,observed_at) "
                "VALUES (%s,'1.0.0','handler-continuation-test',1,1,'available',clock_timestamp())",
                (resource_id,))
            await conn.execute(
                "INSERT INTO r3a.activities(activity_id,activity_type,idempotency_key,machine_id,machine_version,state,"
                "available_at,attempt_id,attempt_count,lease_owner,lease_until,recovery_policy,input) "
                "VALUES (%s,'fixture.handler.activity',%s,'activity.generic',1,'RUNNING',clock_timestamp(),%s,1,"
                "'handler-continuation-test',clock_timestamp()+interval '1 hour','idempotent',%s)",
                (parent_id, f"handler-parent:{parent_id}", attempt_id,
                 json.dumps({"correlation_id": str(correlation_id)})))
            await conn.execute(
                "INSERT INTO r3a.activities(activity_id,activity_type,idempotency_key,machine_id,machine_version,state,"
                "available_at,recovery_policy,input) "
                "VALUES (%s,'grace.objective',%s,'activity.generic',1,'QUEUED',clock_timestamp(),'idempotent',%s)",
                (child_id, f"handler-child:{child_id}", json.dumps({"objective": "fixture"})))
            await conn.execute(
                "INSERT INTO r3a.resource_leases(lease_id,resource_id,activity_id,units,lease_until) "
                "VALUES (%s,%s,%s,1,clock_timestamp()+interval '1 hour')",
                (lease_id, resource_id, parent_id))
        if not await self.store.transition("activity", str(parent_id), "activity.generic", 1,
                                           "RUNNING", "handler continuation starts", initial=True,
                                           correlation_id=correlation_id):
            self.fail("handler activity could not enter RUNNING")

        activity = {"activity_id": parent_id, "attempt_id": attempt_id,
                    "lease_id": lease_id, "resource_id": resource_id,
                    "input": {"correlation_id": str(correlation_id)}}
        await self.store.park_handler_for_objective(activity, checkpoint, str(child_id), deadline)
        parent = (await self.store.rows(
            "SELECT state,checkpoint FROM r3a.activities WHERE activity_id=%s", (parent_id,)))[0]
        self.assertEqual("WAITING", parent["state"])
        self.assertEqual(str(child_id), parent["checkpoint"]["awaiting_objective"]["activity_id"])
        self.assertEqual(pending_action, parent["checkpoint"]["pending_action"])
        self.assertEqual(0, await self.store.requeue_ready_handler_continuations())

        async with self.store.pool.connection() as conn, conn.transaction():
            await conn.execute(
                "UPDATE r3a.activities SET state='COMPLETED',result=%s,updated_at=clock_timestamp() "
                "WHERE activity_id=%s", (json.dumps({"decision": {"status": "healthy"}}), child_id))
        self.assertEqual(1, await self.store.requeue_ready_handler_continuations())
        resumed = (await self.store.rows(
            "SELECT state,checkpoint,progress FROM r3a.activities WHERE activity_id=%s", (parent_id,)))[0]
        self.assertEqual("QUEUED", resumed["state"])
        self.assertEqual(pending_action, resumed["checkpoint"]["pending_action"])
        self.assertEqual(str(child_id), resumed["checkpoint"]["awaiting_objective"]["activity_id"])
        self.assertEqual(str(child_id), resumed["progress"]["objective_activity_id"])

    async def test_notification_ack_requires_cited_final_and_commits_with_resolution(self):
        source_id = "r3a.institution-events"
        source_event_id, correlation_id = uuid.uuid4(), uuid.uuid4()
        source_key = f"notification:{source_id}:{source_event_id}"

        async def create_running_notification():
            activity_id, attempt_id, lease_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
            resource_id = f"notification-ack-test-{uuid.uuid4()}"
            envelope = {"source_id": source_id, "source_event_id": str(source_event_id),
                        "event_id": str(source_event_id), "correlation_id": str(correlation_id),
                        "payload_ref": f"r3a.institution_events/{source_event_id}"}
            activity_input = {"correlation_id": str(correlation_id), "notification": envelope}
            async with self.store.pool.connection() as conn, conn.transaction():
                await conn.execute(
                    "INSERT INTO r3a.resource_registry(resource_id,contract_version,owner,capacity,allocated,health,observed_at) "
                    "VALUES (%s,'1.0.0','notification-ack-test',1,1,'available',clock_timestamp())",
                    (resource_id,))
                await conn.execute(
                    "INSERT INTO r3a.activities(activity_id,activity_type,idempotency_key,machine_id,machine_version,state,"
                    "available_at,attempt_id,attempt_count,lease_owner,lease_until,recovery_policy,input) "
                    "VALUES (%s,'grace.objective',%s,'activity.generic',1,'RUNNING',clock_timestamp(),%s,1,"
                    "'notification-ack-test',clock_timestamp()+interval '1 hour','idempotent',%s)",
                    (activity_id, f"notification-ack:{activity_id}", attempt_id, json.dumps(activity_input)))
                await conn.execute(
                    "INSERT INTO r3a.resource_leases(lease_id,resource_id,activity_id,units,lease_until) "
                    "VALUES (%s,%s,%s,1,clock_timestamp()+interval '1 hour')",
                    (lease_id, resource_id, activity_id))
            if not await self.store.transition("activity", str(activity_id), "activity.generic", 1,
                                               "RUNNING", "notification acknowledgement test starts",
                                               initial=True, correlation_id=correlation_id):
                self.fail("notification activity could not enter RUNNING")
            return {"activity_id": str(activity_id), "attempt_id": str(attempt_id),
                    "lease_id": str(lease_id), "resource_id": resource_id,
                    "input": activity_input}

        invalid = await create_running_notification()
        invalid_result = {"decision": {"status": "healthy", "assessment": "Incomplete source review.",
                                        "recommended_action": "Review again.", "evidence_refs": []}}
        with self.assertRaisesRegex(ValueError, "exact source event"):
            await self.store.finish_activity(invalid, invalid_result)
        invalid_row = (await self.store.rows(
            "SELECT state FROM r3a.activities WHERE activity_id=%s", (invalid["activity_id"],)))[0]
        invalid_events = await self.store.rows(
            "SELECT event_type FROM r3a.institution_events WHERE subject_type='activity' AND subject_id=%s "
            "AND event_type IN ('grace.notification.acknowledged','grace.notification.resolved')",
            (invalid["activity_id"],))
        self.assertEqual("RUNNING", invalid_row["state"])
        self.assertEqual([], invalid_events)

        valid = await create_running_notification()
        valid_result = {"decision": {"status": "healthy", "assessment": "Reviewed the source event.",
                                      "recommended_action": "No follow-up is required.",
                                      "evidence_refs": [source_key]}}
        await self.store.finish_activity(valid, valid_result)
        valid_row = (await self.store.rows(
            "SELECT state FROM r3a.activities WHERE activity_id=%s", (valid["activity_id"],)))[0]
        valid_events = await self.store.rows(
            "SELECT event_type FROM r3a.institution_events WHERE subject_type='activity' AND subject_id=%s "
            "AND event_type IN ('activity.completed','grace.notification.acknowledged',"
            "'grace.notification.resolved') ORDER BY persisted_at,event_id",
            (valid["activity_id"],))
        self.assertEqual("COMPLETED", valid_row["state"])
        self.assertEqual(["activity.completed", "grace.notification.acknowledged",
                          "grace.notification.resolved"], [row["event_type"] for row in valid_events])
