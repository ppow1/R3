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
Supersedes: None.
Contracts: r3a.activity-handler.v1; activity.generic v1; existing CME activity ledger.
Tests: Isolated PostgreSQL 16; focused checkpoint, Engineering, verification, and frozen-digest compatibility regression: 25 passed, 2 existing xfailed.
Changed: 2026-11-11T21:51:02Z | R3A-STEP127-POSTGRES-REGRESSION | Codex GPT-6 | Preserve fixture settings across Store restart in the PostgreSQL regression.
Changed: 2026-11-11T21:57:36Z | R3A-STEP127-POSTGRES-REGRESSION | Codex GPT-6 | Cover frozen-digest upgrade compatibility.
History/Predecessor: Git blob 4d206a799ee471028ba084142516dd82a71d62f3 at commit 4e5ca6201c3a78239e069530950a546a9f2c7273.
"""
from __future__ import annotations

import hashlib
import json
import os
import uuid
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from psycopg.conninfo import conninfo_to_dict
from psycopg import AsyncConnection

from r3a_runtime.cme import CME, _capability_request_digest
from r3a_runtime.db import Store
from r3a_runtime.provider_runtime import ProviderProcessManager
from tests.r3a_activity_handler_interop_provider import create_provider
from tests.test_r3a_activity_handler_interop import fixture
from r3a_runtime.capability_contracts import validate_module_manifest


ROOT = Path(__file__).resolve().parents[1]
TEST_DSN = os.environ.get("R3A_CHECKPOINT_TEST_DSN")


class SimulatedProcessInterruption(RuntimeError):
    pass


class CapabilityRequestDigestTests(unittest.TestCase):
    def test_per_attempt_deadline_is_excluded_but_semantic_fields_remain_bound(self):
        request = {"operation_id": "directory.read", "input": {"resident_id": "resident:grace"},
                   "target": {"source_ids": ["directory"]}, "deadline": "2099-01-01T00:00:00Z"}
        renewed = {**request, "deadline": "2099-01-01T00:01:00Z"}
        self.assertEqual(_capability_request_digest(request), _capability_request_digest(renewed))
        changed_input = {**request, "input": {"resident_id": "resident:vicky"}}
        self.assertNotEqual(_capability_request_digest(request), _capability_request_digest(changed_input))
        changed_target = {**request, "target": {"source_ids": ["secrets"]}}
        self.assertNotEqual(_capability_request_digest(request), _capability_request_digest(changed_target))


@unittest.skipUnless(TEST_DSN, "requires disposable PostgreSQL R3A_CHECKPOINT_TEST_DSN")
class ActivityCheckpointPostgresTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        info = conninfo_to_dict(TEST_DSN)
        database = str(info.get("dbname", "")).lower()
        if not database.startswith("r3a_checkpoint_test"):
            self.skipTest("R3A_CHECKPOINT_TEST_DSN must identify a dedicated test database")
        self.settings = SimpleNamespace(
            connection_info=info, worker_concurrency=1, lease_seconds=30,
            observer_interval_seconds=60,
            machine_catalog_dir=ROOT / "r3a_runtime" / "state_machines")
        self.store = Store(self.settings)
        async with await AsyncConnection.connect(self.store.conninfo, autocommit=True) as conn:
            await conn.execute("DROP SCHEMA IF EXISTS r3a CASCADE")
        await self.store.open()
        await self.store.migrate()
        await self.store.seed_machines()

    async def asyncTearDown(self):
        if hasattr(self, "store"):
            await self.store.close()

    async def test_capability_retry_with_new_deadline_recovers_after_store_restart(self):
        # Preserve the original production failure: full-envelope hashing conflicts
        # when a stable key is retried with only its per-attempt deadline changed.
        legacy_key = f"directory-legacy-deadline:{uuid.uuid4()}"
        legacy_request = {
            "idempotency_key": legacy_key,
            "invocation_id": str(uuid.uuid4()),
            "operation_id": "institutional.directory.discover",
            "correlation_id": str(uuid.uuid4()),
            "deadline": "2099-01-01T00:00:00+00:00",
            "input": {"resident_id": "resident:grace", "limit": 250},
        }

        def full_request_digest(request):
            return hashlib.sha256(json.dumps(request, sort_keys=True,
                                             separators=(",", ":")).encode()).hexdigest()

        await self.store.begin_capability_invocation(
            legacy_request, full_request_digest(legacy_request), {})
        legacy_retry = {**legacy_request, "deadline": "2099-01-01T00:01:00+00:00"}
        with self.assertRaisesRegex(ValueError, "idempotency key already belongs to a different canonical request"):
            await self.store.begin_capability_invocation(
                legacy_retry, full_request_digest(legacy_retry), {})

        key = f"directory-retry:{uuid.uuid4()}"
        first_deadline = "2099-01-01T00:00:00+00:00"
        first_request = {
            **legacy_request,
            "idempotency_key": key,
            "invocation_id": str(uuid.uuid4()),
            "correlation_id": str(uuid.uuid4()),
            "deadline": first_deadline,
        }
        first_digest = _capability_request_digest(first_request)
        created = await self.store.begin_capability_invocation(first_request, first_digest, {})
        self.assertTrue(created["created"])

        # A CME restart reconstructs Store and retries the same semantic request.
        await self.store.close()
        self.store = Store(self.settings)
        await self.store.open()
        retry_request = {**first_request, "deadline": "2099-01-01T00:01:00+00:00"}
        retry_digest = _capability_request_digest(retry_request)
        self.assertEqual(first_digest, retry_digest)
        retry = await self.store.begin_capability_invocation(retry_request, retry_digest, {})
        self.assertFalse(retry["created"])
        self.assertEqual("STARTED", retry["state"])
        persisted = (await self.store.rows(
            "SELECT request FROM r3a.capability_invocations WHERE idempotency_key=%s", (key,)))[0]
        self.assertEqual(first_deadline, persisted["request"]["deadline"])

        result = {"outcome": "SUCCEEDED", "evidence": [], "output": {"residents": []}}
        await self.store.finish_capability_invocation(key, retry["request_digest"], result)
        replay = await self.store.begin_capability_invocation(
            {**retry_request, "deadline": "2099-01-01T00:02:00+00:00"}, retry_digest, {})
        self.assertFalse(replay["created"])
        self.assertEqual("SUCCEEDED", replay["state"])
        self.assertEqual(result, replay["result"])

        changed_input = {**retry_request, "input": {"resident_id": "resident:vicky", "limit": 250}}
        with self.assertRaisesRegex(ValueError, "idempotency key already belongs to a different canonical request"):
            await self.store.begin_capability_invocation(
                changed_input, _capability_request_digest(changed_input), {})

    async def test_frozen_digest_row_conflicts_with_candidate_deadline_omitting_digest(self):
        first_request = {
            "idempotency_key": f"frozen-directory-retry:{uuid.uuid4()}",
            "invocation_id": str(uuid.uuid4()),
            "operation_id": "institutional.directory.discover",
            "correlation_id": str(uuid.uuid4()),
            "deadline": "2099-01-01T00:00:00+00:00",
            "input": {"resident_id": "resident:grace", "limit": 250},
        }
        frozen_digest = hashlib.sha256(json.dumps(
            first_request, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        await self.store.begin_capability_invocation(first_request, frozen_digest, {})

        # Reopen Store as the new code would after an upgrade. The persisted row
        # has the frozen full-envelope digest; the candidate computes deadline-free.
        await self.store.close()
        self.store = Store(self.settings)
        await self.store.open()
        retry_request = {**first_request, "deadline": "2099-01-01T00:01:00+00:00"}
        with self.assertRaisesRegex(ValueError, "idempotency key already belongs to a different canonical request"):
            await self.store.begin_capability_invocation(
                retry_request, _capability_request_digest(retry_request), {})

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
