"""
R3 CONTROLLED SOURCE
File: tests/test_r3a_modular_dispatch.py
Component: TEST-R3A-MODULAR-DISPATCH
File Revision: 1.0.7
Created: 2026-11-10T00:50:00Z
Created By: Codex GPT-6
Purpose: Verify generic resident binding and activity-handler contract resolution and fail-closed behavior.
Execution Model: Python unittest fixtures.
Observability: Assertions identify contract validation and resolution failures.
Dependencies: r3a_runtime.modular_dispatch.
Authority: AD-024 and Steward Directive Issue #43.
Changed: 2026-11-10T00:50:00Z | R3A-AD024-MODULAR-DISPATCH | Codex GPT-6 | Add resident and handler resolver fixture coverage.
Changed: 2026-11-10T00:51:55Z | R3A-AD024-MODULAR-DISPATCH | Codex GPT-6 | Verify CME handler grant denial occurs before worker execution.
Changed: 2026-11-10T00:56:15Z | R3A-AD024-MODULAR-DISPATCH | Codex GPT-6 | Cover authoritative profile joins and digest mismatch denial.
Changed: 2026-11-10T01:00:00Z | R3A-AD024-MODULAR-DISPATCH | Codex GPT-6 | Verify independent resident executor dispatch preserves target identity and binding lineage.
Changed: 2026-11-10T01:15:00Z | R3A-AD024-MODULAR-DISPATCH | Codex GPT-6 | Declare fixture handler capabilities through the module manifest as required by CME.
Changed: 2026-11-10T01:20:00Z | R3A-AD024-MODULAR-DISPATCH | Codex GPT-6 | Verify generic durable intake replay, conflict rejection, authorization, provider provenance, and lineage.
Changed: 2026-11-10T01:25:00Z | R3A-AD024-MODULAR-DISPATCH | Codex GPT-6 | Verify resident execution grants are checked before authoritative lookup or dispatch.
Supersedes: None
Contracts: r3a.resident.module-binding.v1; r3a.activity-handler.v1.
Tests: python -m unittest tests.test_r3a_modular_dispatch
History/Predecessor: New file; initial publication recorded in Git.
"""
import copy
import hashlib
import json
import tempfile
import unittest
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from r3a_runtime.modular_dispatch import (
    DispatchContractError,
    build_resident_execution_profile,
    resolve_activity_handler,
    resolve_resident_binding,
    validate_activity_handler,
)


def binding(resident, module, version, digest_char, record):
    return {
        "contract_id": "r3a.resident.module-binding",
        "contract_version": "1.0.0",
        "resident_id": resident,
        "module_id": module,
        "module_version": version,
        "artifact_digest": digest_char * 64,
        "execution_contract_range": {"contract_id": "r3a.resident.execution", "major": 1,
                                     "min_minor": 0, "max_minor": 0},
        "binding_revision": "bind-" + resident,
        "configuration_ref": "config://" + resident,
        "configuration_revision": "cfg-1",
        "identity_association": {"authority": "hr-directory", "record_id": record,
                                  "record_revision": "hr-r1"},
    }


def registered(module, version, digest_char, **extra):
    manifest = {"module_id": module, "module_version": version,
                "artifact_digest": digest_char * 64,
                "resident_execution_contract_range": {"contract_id": "r3a.resident.execution",
                                                       "major": 1, "min_minor": 0, "max_minor": 0},
                **extra}
    return {"module_id": module, "module_version": version, "lifecycle_state": "ACTIVE",
            "manifest": manifest}


HANDLER = {
    "contract_id": "r3a.activity-handler", "contract_version": "1.0.0",
    "handler_id": "example.handler", "handler_version": "1.0.0",
    "activity_types": ["example.task"],
    "activity_contract_range": {"contract_id": "r3a.activity-intake", "major": 1,
                                "min_minor": 0, "max_minor": 0},
    "request_schema": {"type": "object"}, "result_schema": {"type": "object"},
    "progress_schema": {"type": "object"}, "checkpoint_schema": {"type": "object"},
    "required_capabilities": ["example.read"], "state_namespace": "example.handler",
    "recovery": {"mode": "checkpointed", "idempotency": "stable-key-v1",
                 "checkpoint": "example.checkpoint.v1"},
}


class ResidentBindingTests(unittest.TestCase):
    def test_two_authoritative_residents_resolve_separate_artifacts(self):
        grace = binding("resident.alpha", "executor.alpha", "1.0.0", "a", "hr-1")
        beta = binding("resident.beta", "executor.beta", "2.1.0", "b", "hr-2")
        modules = [registered("executor.alpha", "1.0.0", "a"),
                   registered("executor.beta", "2.1.0", "b")]
        resolved_a = resolve_resident_binding([grace, beta], "resident.alpha",
                                               grace["identity_association"], modules)
        resolved_b = resolve_resident_binding([grace, beta], "resident.beta",
                                               beta["identity_association"], modules)
        self.assertEqual(resolved_a["module_id"], "executor.alpha")
        self.assertEqual(resolved_b["module_id"], "executor.beta")
        self.assertNotEqual(resolved_a["binding_revision"], resolved_b["binding_revision"])

    def test_invalid_identity_missing_grant_is_not_inferred_from_binding(self):
        candidate = binding("resident.alpha", "executor.alpha", "1.0.0", "a", "hr-1")
        module = registered("executor.alpha", "1.0.0", "a")
        with self.assertRaisesRegex(DispatchContractError, "association"):
            resolve_resident_binding([candidate], "resident.alpha",
                                     {"authority": "hr-directory", "record_id": "other",
                                      "record_revision": "hr-r1"}, [module])
        # The binding resolver returns no authorization field or grant implication.
        resolved = resolve_resident_binding([candidate], "resident.alpha",
                                             candidate["identity_association"], [module])
        self.assertNotIn("authorized", resolved)
        self.assertNotIn("grants", resolved)

    def test_execution_profile_joins_fresh_authority_and_digest_pinned_config(self):
        candidate = binding("resident.alpha", "executor.alpha", "1.0.0", "a", "resident.alpha")
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "resident.json"
            config_data = {"grace": {"default_route": "alpha-route"}}
            encoded = json.dumps(config_data, separators=(",", ":")).encode()
            config_path.write_bytes(encoded)
            candidate["configuration_ref"] = str(config_path)
            candidate["configuration_revision"] = hashlib.sha256(encoded).hexdigest()
            directory = {"source": {"source_id": "riverview_authority.directory",
                                    "availability": "measured", "freshness": "fresh",
                                    "snapshot_sha256": "f" * 64, "observed_at": "2026-11-10T00:00:00Z"},
                         "residents": [{"resident_id": "resident.alpha", "office_id": "office.alpha",
                                        "office_role": "Research", "binding_revision": "resident.alpha",
                                        "display_name": "Alpha"}]}
            candidate["identity_association"] = {"authority": "riverview_authority.directory",
                                                  "record_id": "resident.alpha",
                                                  "record_revision": "resident.alpha"}
            profile = build_resident_execution_profile(candidate, directory, config_path)
            self.assertEqual(profile["resident_id"], "resident.alpha")
            self.assertEqual(profile["model_route_id"], "alpha-route")
            self.assertEqual(profile["config_revision"], hashlib.sha256(encoded).hexdigest())
            candidate["configuration_revision"] = "0" * 64
            with self.assertRaisesRegex(DispatchContractError, "configuration revision"):
                build_resident_execution_profile(candidate, directory, config_path)

    def test_missing_duplicate_inactive_and_digest_mismatch_fail_closed(self):
        candidate = binding("resident.alpha", "executor.alpha", "1.0.0", "a", "hr-1")
        identity = candidate["identity_association"]
        module = registered("executor.alpha", "1.0.0", "a")
        for modules in ([], [module, module], [{**module, "lifecycle_state": "DISABLED"}],
                        [registered("executor.alpha", "1.0.0", "c")]):
            with self.subTest(modules=modules), self.assertRaises(DispatchContractError):
                resolve_resident_binding([candidate], "resident.alpha", identity, modules)
        with self.assertRaisesRegex(DispatchContractError, "ambiguous"):
            resolve_resident_binding([candidate, candidate], "resident.alpha", identity, [module])


class ActivityHandlerTests(unittest.TestCase):
    def test_non_grace_activity_resolves_from_one_active_registered_handler(self):
        row = registered("example.module", "1.0.0", "c", activity_handler=HANDLER)
        resolved = resolve_activity_handler([row], "example.task")
        self.assertEqual(resolved["handler"]["handler_id"], "example.handler")
        self.assertEqual(resolved["artifact_digest"], "c" * 64)

    def test_missing_ambiguous_disabled_incompatible_and_invalid_handlers_deny(self):
        active = registered("example.module", "1.0.0", "c", activity_handler=HANDLER)
        disabled = {**active, "lifecycle_state": "DISABLED"}
        incompatible_handler = copy.deepcopy(HANDLER)
        incompatible_handler["contract_version"] = "2.0.0"
        incompatible = registered("example.module2", "1.0.0", "d",
                                  activity_handler=incompatible_handler)
        for rows in ([], [disabled], [active, active], [incompatible]):
            with self.subTest(rows=rows), self.assertRaises(DispatchContractError):
                resolve_activity_handler(rows, "example.task")
        bad = copy.deepcopy(HANDLER)
        bad["activity_types"] = ["example.task", "example.task"]
        with self.assertRaisesRegex(DispatchContractError, "unique"):
            validate_activity_handler(bad)

    def test_registry_binding_is_not_authorization(self):
        row = registered("example.module", "1.0.0", "c", activity_handler=HANDLER)
        resolved = resolve_activity_handler([row], "example.task")
        self.assertEqual(resolved["handler"]["required_capabilities"], ["example.read"])
        self.assertNotIn("authorized", resolved)
        self.assertNotIn("authorization", resolved)


class CMEResidentAuthorizationTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_resident_execution_grant_denies_before_directory_or_executor(self):
        from r3a_runtime.cme import CME

        candidate = binding("resident.alpha", "executor.alpha", "1.0.0", "a", "hr-1")
        cme = object.__new__(CME)
        cme.settings = SimpleNamespace(resident_module_bindings=(candidate,))
        cme._authorization_decision = AsyncMock(side_effect=PermissionError("execution grant missing"))
        cme.invoke_capability = AsyncMock()
        activity = {"activity_id": "00000000-0000-0000-0000-000000000040",
                    "attempt_id": "00000000-0000-0000-0000-000000000041",
                    "input": {"resident_id": "resident.alpha"}}
        with self.assertRaisesRegex(PermissionError, "execution grant missing"):
            await CME._resolve_resident_executor(cme, activity)
        cme.invoke_capability.assert_not_awaited()


class CMEHandlerExecutionTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_capability_grant_denies_before_handler_execution(self):
        from r3a_runtime.cme import CME

        cme = object.__new__(CME)
        cme.store = SimpleNamespace(record_progress=AsyncMock(), finish_activity=AsyncMock(),
                                    block_activity=AsyncMock())
        cme.settings = SimpleNamespace(lease_seconds=30)
        cme.module_id = "resident.alpha"
        cme._authorization_decision = AsyncMock(side_effect=PermissionError("grant missing"))
        cme._registered_module_call = AsyncMock()
        module = registered("example.module", "1.0.0", "c", entrypoint="fixture.module", capability_refs=["example.read"])
        resolved = {"module": module, "handler": HANDLER, "module_id": "example.module",
                    "module_version": "1.0.0", "artifact_digest": "c" * 64}
        activity = {"activity_id": "00000000-0000-0000-0000-000000000010",
                    "attempt_id": "00000000-0000-0000-0000-000000000011",
                    "idempotency_key": "task:one", "activity_type": "example.task",
                    "input": {"correlation_id": "00000000-0000-0000-0000-000000000012",
                              "activity_input": {"task": "inspect"}, "resident_id": "resident.alpha"},
                    "checkpoint": {}}
        with self.assertRaisesRegex(PermissionError, "grant missing"):
            await CME._run_registered_activity(cme, activity, resolved)
        cme._registered_module_call.assert_not_awaited()
        cme.store.finish_activity.assert_not_awaited()

    async def test_authorized_handler_progress_checkpoint_and_completion_are_durable(self):
        from r3a_runtime.cme import CME

        cme = object.__new__(CME)
        cme.store = SimpleNamespace(record_progress=AsyncMock(), finish_activity=AsyncMock(),
                                    block_activity=AsyncMock())
        cme.settings = SimpleNamespace(lease_seconds=30)
        cme.module_id = "resident.alpha"
        cme._authorization_decision = AsyncMock(return_value=SimpleNamespace(
            decision_id="decision-1", audit_event_id="audit-1", policy_revision="policy-1"))
        cme._registered_module_call = AsyncMock(return_value={"result": {
            "outcome": "completed", "progress": {"phase": "done"},
            "checkpoint": {"cursor": 7}, "value": "ok"}})
        module = registered("example.module", "1.0.0", "c", entrypoint="fixture.module", capability_refs=["example.read"])
        resolved = {"module": module, "handler": HANDLER, "module_id": "example.module",
                    "module_version": "1.0.0", "artifact_digest": "c" * 64}
        activity = {"activity_id": "00000000-0000-0000-0000-000000000020",
                    "attempt_id": "00000000-0000-0000-0000-000000000021",
                    "idempotency_key": "task:two", "activity_type": "example.task",
                    "input": {"correlation_id": "00000000-0000-0000-0000-000000000022",
                              "activity_input": {"task": "inspect"}, "resident_id": "resident.alpha"},
                    "checkpoint": {}}
        await CME._run_registered_activity(cme, activity, resolved)
        cme.store.record_progress.assert_awaited()
        cme.store.finish_activity.assert_awaited_once()
        persisted = cme.store.finish_activity.await_args.args[1]
        self.assertEqual(persisted["handler"]["artifact_digest"], "c" * 64)
        self.assertEqual(persisted["authorization"][0]["audit_event_id"], "audit-1")

    async def test_independently_registered_resident_executor_receives_bound_identity(self):
        from r3a_runtime.cme import CME

        cme = object.__new__(CME)
        cme.store = SimpleNamespace(record_progress=AsyncMock(), finish_activity=AsyncMock(),
                                    block_activity=AsyncMock())
        cme._resident_tools = lambda: []
        cme._registered_module_call = AsyncMock(return_value={"result": {
            "action": "final", "decision": {"status": "healthy"}, "model": "fixture"}})
        module = registered("independent.executor", "2.0.0", "e", capability_refs=[])
        profile = {"resident_id": "resident.beta", "config_revision": "cfg-sha"}
        resolved = {"module": module, "module_id": "independent.executor", "module_version": "2.0.0",
                    "artifact_digest": "e" * 64, "binding_revision": "binding-beta",
                    "execution_profile": profile, "configuration_path": "/fixture/resident.json"}
        activity = {"activity_id": "00000000-0000-0000-0000-000000000030",
                    "attempt_id": "00000000-0000-0000-0000-000000000031",
                    "activity_type": "resident.review", "idempotency_key": "review:one",
                    "input": {"resident_id": "resident.beta", "objective": "review"},
                    "checkpoint": {}}
        await CME._run_bound_resident_activity(cme, activity, resolved)
        call = cme._registered_module_call.await_args
        self.assertEqual(call.args[:3], ("independent.executor", "2.0.0", "execute"))
        self.assertEqual(call.args[3]["resident_id"], "resident.beta")
        self.assertEqual(call.args[3]["contract_envelope"]["resident_id"], "resident.beta")
        self.assertEqual(cme.store.finish_activity.await_args.args[1]["binding_revision"], "binding-beta")


class ActivityIntakeLedgerTests(unittest.IsolatedAsyncioTestCase):
    def make_intake(self):
        return {
            "contract_id": "r3a.activity-intake.v1", "contract_version": "1.0.0",
            "intake_id": "source-event-1", "parent_activity_id": None,
            "correlation_id": "correlation-1",
            "source": {"source_id": "queue.alpha", "event_id": "event-1", "revision": "r1",
                       "idempotency_key": "queue.alpha:event-1", "occurred_at": "2026-11-09T12:00:00Z",
                       "received_at": "2026-11-09T12:00:01Z", "payload_ref": "queue://event-1",
                       "payload_sha256": "a" * 64, "causation_id": "cause-1"},
            "activity": {"activity_type": "billing.invoice", "task_class": "operations.review",
                         "objective": "Review invoice", "input": {"invoice_id": "inv-1",
                         "resident_id": "resident.beta"}, "evidence": []},
            "provenance": {"module_id": "source.module", "module_version": "1.0.0",
                           "artifact_sha256": "b" * 64, "configuration_revision": "cfg-1"},
            "lifecycle_projection": {"received": "activity.received", "actionable": "activity.actionable",
                                      "acknowledged": "activity.acknowledged", "resolved": "activity.resolved",
                                      "blocked": "activity.blocked"},
        }

    def make_store(self):
        from r3a_runtime.db import Store

        state = {"existing": None, "statements": []}

        class Cursor:
            def __init__(self, value=None): self.value = value
            async def fetchone(self): return self.value

        class Connection:
            async def execute(_self, query, params=()):
                state["statements"].append((query, params))
                if "FROM r3a.activities WHERE idempotency_key" in query:
                    return Cursor(state["existing"])
                if "FROM r3a.config_current" in query:
                    return Cursor({"revision_id": "config-current"})
                if query.startswith("INSERT INTO r3a.activities"):
                    state["existing"] = {"activity_id": params[0], "activity_type": params[1],
                                          "idempotency_key": params[2], "state": "QUEUED",
                                          "attempt_count": 0, "input": json.loads(params[4])}
                return Cursor()

            @asynccontextmanager
            async def transaction(_self):
                yield

        class Pool:
            @asynccontextmanager
            async def connection(_self):
                yield Connection()

        store = object.__new__(Store)
        store.pool = Pool()
        store._event = AsyncMock(return_value="event-durable-1")
        store._transition_on_conn = AsyncMock(return_value=True)
        return store, state

    async def test_generic_intake_replay_and_conflict_keep_lineage(self):
        store, state = self.make_store()
        intake = self.make_intake()
        invocation = {"contract_id": "r3a.capability-invocation.v1", "outcome": "SUCCEEDED",
                      "provider": {"provider_id": "source.module", "provider_version": "1.0.0",
                                   "artifact_sha256": "b" * 64},
                      "authorization": {"allowed": True}, "invocation_id": "invoke-1"}
        first = await store.submit_activity_intake(intake, invocation)
        replay = await store.submit_activity_intake(intake, invocation)
        self.assertFalse(first["duplicate"])
        self.assertTrue(replay["duplicate"])
        self.assertEqual(first["activity_id"], replay["activity_id"])
        self.assertEqual("resident.beta", state["existing"]["input"]["resident_id"])
        event_args = store._event.await_args.args
        self.assertEqual("activity.received", event_args[0])
        self.assertEqual("billing.invoice", state["existing"]["activity_type"])
        self.assertEqual(1, store._event.await_count)
        conflict = copy.deepcopy(intake)
        conflict["activity"]["objective"] = "Different objective"
        with self.assertRaisesRegex(ValueError, "conflicts"):
            await store.submit_activity_intake(conflict, invocation)

    async def test_generic_intake_rejects_unauthorized_or_foreign_provenance(self):
        store, _state = self.make_store()
        intake = self.make_intake()
        invocation = {"contract_id": "r3a.capability-invocation.v1", "outcome": "SUCCEEDED",
                      "provider": {"provider_id": "other.module", "provider_version": "1.0.0",
                                   "artifact_sha256": "b" * 64},
                      "authorization": {"allowed": True}}
        with self.assertRaisesRegex(ValueError, "provenance"):
            await store.submit_activity_intake(intake, invocation)
        invocation["provider"]["provider_id"] = "source.module"
        invocation["authorization"]["allowed"] = False
        with self.assertRaises(PermissionError):
            await store.submit_activity_intake(intake, invocation)


if __name__ == "__main__":
    unittest.main()
