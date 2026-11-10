"""
R3 CONTROLLED SOURCE
File: tests/test_r3a_activity_checkpoint_persistence.py
Component: R3A-ACTIVITY-CHECKPOINT-PERSISTENCE-REGRESSION
File Revision: 1.0.2
Created: 2026-11-10
Created By: Codex GPT-6
Purpose: Verify generic handler checkpoints persist through PostgreSQL progress updates and lease recovery.
Execution Model: Opt-in isolated PostgreSQL integration test using the existing CME activity ledger.
Observability: Reads the activity row after writes, interruption recovery, and retry claim.
Dependencies: psycopg 3; R3A Store migrations; shared #46 activity-handler fixture.
Authority: Steward corrective directive, Autonomy / CME Issue #43.
Changed: 2026-11-10T04:00:00Z | R3A-CHECKPOINT-PERSISTENCE-CORRECTION | Codex GPT-6 | Exercise atomic progress/checkpoint persistence and recovery against PostgreSQL.
Changed: 2026-11-10T15:16:00Z | R3A-AUTONOMY-EXECUTOR-ROLE-P0 | Codex GPT-6 | Exercise durable promotion of the validated top-level executor role without changing registered artifact identity.
Supersedes: None.
Contracts: r3a.activity-handler.v1; activity.generic v1; existing CME activity ledger.
Tests: Set R3A_CHECKPOINT_TEST_DSN to a disposable test database and run this module.
History/Predecessor: New permanent persistence regression.
Immediate Predecessor: Commit 1dd57e17e81531feaa77099e5d6aecc1debb2b7e, blob fbc0a36416bd6348300d4a0cb826082edf039ad8.
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

    async def test_primary_module_executor_role_promotion_is_persisted_additively(self):
        old = {
            "module_id": "executor.fixture", "module_version": "1.0.0",
            "contract_id": "r3a.module.v1", "protocol_major": 1,
            "protocol_minor": 0, "protocol_min_minor": 0, "protocol_max_minor": 0,
            "owner": "test-owner", "entrypoint": "fixture.module",
            "dependencies": [], "configuration_schema": "r3a.bootstrap.v1",
            "configuration_ref": "/tmp/fixture-bootstrap.json", "capability_refs": [],
            "migration_contract": "none-v1", "artifact_ref": "/tmp/fixture-module.py",
            "artifact_digest": "a" * 64, "recovery_policy": "idempotent",
            "resource_refs": [], "state_namespace": "executor.fixture",
        }
        role = {
            "contract_id": "r3a.resident.executor", "contract_version": "1.0.0",
            "execution_contract_range": {"contract_id": "r3a.resident.execution",
                                         "major": 1, "min_minor": 0, "max_minor": 2},
        }
        await self.store.register_module(old, "ACTIVE", "healthy")
        await self.store.register_module({**old, "resident_executor": role}, "ACTIVE", "healthy")
        async with self.store.pool.connection() as conn:
            row = await (await conn.execute(
                "SELECT manifest,artifact_digest FROM r3a.module_registry "
                "WHERE module_id='executor.fixture' AND module_version='1.0.0'"
            )).fetchone()
            events = await (await conn.execute(
                "SELECT evidence FROM r3a.institution_events "
                "WHERE event_type='module.manifest.promoted' AND subject_type='module' "
                "AND subject_id='executor.fixture@1.0.0'"
            )).fetchall()
        self.assertEqual("a" * 64, row["artifact_digest"])
        self.assertEqual(role, row["manifest"]["resident_executor"])
        self.assertEqual(1, len(events))
        self.assertTrue(events[0]["evidence"]["resident_executor_added"])

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
