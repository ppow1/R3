"""
R3 CONTROLLED SOURCE
File: tests/test_r3a_activity_intake_consumer.py
Component: R3A-GENERIC-ACTIVITY-INTAKE-REGRESSION
File Revision: 1.0.2
Created: 2026-11-09
Created By: Codex GPT-6
Purpose: Verify authorized generic activity intake remains durable and idempotent.
Execution Model: Python unittest using in-memory database and provider fakes.
Observability: Assertions cover authorization, durable identity, event lineage, and replay behavior.
Dependencies: r3a_runtime.cme; r3a_runtime.db; shared activity-intake contracts.
Authority: AD-024; Autonomy / CME Issue #43.
Changed: 2026-11-10T03:20:00Z | R3A-AUTONOMY-BASELINE-RECONCILIATION | Codex GPT-6 | Cover non-Grace activity intake persistence and idempotency.
Changed: 2026-11-11 | R3A-RESIDENT-ID-AUDIT | Codex GPT-6 | Identify CME as its own module in the source-intake fixture rather than mislabeling it as Grace.
Supersedes: None.
Contracts: r3a.activity-intake.v1; r3a.activity-handler.v1.
Tests: This test module.
History/Predecessor: New regression module on the Coordinator integration baseline.
"""
from __future__ import annotations

import copy
import hashlib
import json
import unittest
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import AsyncMock

from r3a_plugins.notification_source import intake as notification_intake_plugin
from r3a_runtime.capability_contracts import (CapabilityProviderResult, CapabilityRegistry,
                                              normalize_provider_result, validate_operation)
from r3a_runtime.cme import CME
from r3a_runtime.config import load_settings
from r3a_runtime.db import Store
from tests.test_r3a_activity_intake_contract import valid_notification_intake
from tests.test_r3a_modular_autonomy import make_config


class Registry:
    def __init__(self, descriptor):
        self.descriptor = descriptor
        self.configuration = {}

    def resolve(self, operation_id, contract_version):
        if operation_id != self.descriptor["operation_id"]:
            raise KeyError(operation_id)
        if contract_version != self.descriptor["contract_version"]:
            raise ValueError("contract version mismatch")
        return SimpleNamespace(descriptor=self.descriptor, configuration=self.configuration)


def invocation_result(intake, provider):
    return {
        "contract_id": "r3a.capability-invocation.v1", "contract_version": "1.0.0",
        "invocation_id": "source-invocation-1", "operation_id": "source.read",
        "operation_contract_version": "1.0.0", "activity_id": None, "attempt_id": None,
        "correlation_id": "invocation-correlation", "provider": provider,
        "outcome": "SUCCEEDED", "started_at": "2026-11-09T00:00:00Z",
        "finished_at": "2026-11-09T00:00:01Z",
        "authorization": {"provider_id": "test-auth", "allowed": True,
                           "decision_id": "decision-1", "audit_event_id": "audit-1",
                           "policy_revision": "policy-1", "config_revision": "c" * 64},
        "effect_disposition": "NOT_STARTED", "output": intake, "error": None,
        "evidence": [], "retryable": False, "reconciliation_ref": None,
    }


class NotificationAdapterTests(unittest.TestCase):
    def test_notification_activity_intake_is_a_versioned_read_operation(self):
        root = Path(__file__).resolve().parents[1]
        manifest_path = root / "r3a_plugins/notification_source/manifest.activity-intake.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        artifact = manifest_path.parent / manifest["artifact_ref"]
        self.assertEqual(manifest["artifact_sha256"], hashlib.sha256(artifact.read_bytes()).hexdigest())
        descriptor = validate_operation(manifest["operation"])
        self.assertEqual("read", descriptor["effect_class"])
        self.assertEqual(["notification.source.read"], descriptor["required_grants"])
        self.assertEqual("r3a.activity-intake.v1", descriptor["output_schema"]["$id"])
        registry = CapabilityRegistry()
        registered = registry.register(descriptor, {}, legacy_manifest=manifest)
        provider = registered.load_provider()
        self.assertIsInstance(provider, notification_intake_plugin.NotificationActivityIntakeProvider)

        event_id = str(uuid.uuid4())
        correlation_id = str(uuid.uuid4())
        provider.source.invoke = lambda _args, context: CapabilityProviderResult(
            output={
                "contract_id": "r3a.notification-intake", "contract_version": "1.0.0",
                "source_id": "r3a.institution-events", "source_event_id": event_id,
                "event_id": event_id, "event_type": "service.failed",
                "correlation_id": correlation_id, "occurred_at": "2026-11-08T00:00:00Z",
                "received_at": "2026-11-08T00:00:01Z", "severity": "error",
                "payload_ref": "r3a.institution_events/event-123",
                "provenance": {"schema_version": 1, "store": "r3a", "implementation_revision": "rev1"},
                "evidence": {"prior_state": "RUNNING", "next_state": "FAILED",
                             "reason": "service failed", "subject_type": "service", "subject_id": "cme"}},
            evidence={"source_id": "r3a.institution-events", "source_event_id": event_id,
                      "payload_sha256": "a" * 64,
                      "payload_ref": "r3a.institution_events/event-123", "read_only": True,
                      "queried_at": "2026-11-08T00:00:01Z"})
        output = provider.invoke({"source_event_id": event_id}, context={
            "provider": descriptor["provider"], "config_revision": "c" * 64})
        validated, _ = normalize_provider_result(output, descriptor)
        self.assertEqual("r3a.activity-intake.v1", validated["contract_id"])
        self.assertEqual(descriptor["provider"]["artifact_sha256"], validated["provenance"]["artifact_sha256"])

        with TemporaryDirectory() as temporary:
            config_path = make_config(Path(temporary))
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config["module"]["capabilities"].extend(["notification.source.read", "notification.activity-intake.prepare"])
            config["capability_operations"] = [{
                "manifest": str(manifest_path),
                "configuration": str(root / "r3a_plugins/notification_source/config.example.json"),
            }]
            config_path.write_text(json.dumps(config), encoding="utf-8")
            settings = load_settings(config_path)
            discovered = settings.capability_registry.resolve("notification.activity-intake.prepare")
            self.assertEqual("r3a.activity-intake.v1", discovered.descriptor["output_schema"]["$id"])


class ActivityIntakeControlTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.digest = "c" * 64
        self.provider = {"provider_id": "source.module", "provider_version": "1.0.0",
                         "artifact_sha256": "a" * 64}
        self.intake = valid_notification_intake()
        self.intake["provenance"].update(module_id=self.provider["provider_id"],
                                          module_version=self.provider["provider_version"],
                                          artifact_sha256=self.provider["artifact_sha256"],
                                          configuration_revision=self.digest)
        self.key = self.intake["source"]["idempotency_key"]
        descriptor = {
            "operation_id": "source.read", "contract_version": "1.0.0",
            "effect_class": "read", "output_schema": {"$id": "r3a.activity-intake.v1"},
            "input_schema": {"type": "object", "additionalProperties": False,
                             "properties": {"event_id": {"type": "string"}}, "required": ["event_id"]},
            "provider": self.provider, "execution": {"timeout_seconds": 5},
        }
        self.cme = CME.__new__(CME)
        self.cme.settings = SimpleNamespace(source_digest=self.digest, module_id="r3a.cme",
                                            capability_registry=Registry(descriptor))
        self.cme.invoke_capability = AsyncMock(return_value=invocation_result(self.intake, self.provider))
        self.cme.store = SimpleNamespace(submit_activity_intake=AsyncMock(
            return_value={"activity_id": "durable-activity-1", "duplicate": False}))

    async def test_accept_invokes_registered_read_provider_and_persists_authorized_intake(self):
        result = await self.cme._control_request(
            "activity.intake.accept", {"operation_id": "source.read", "input": {"event_id": "event-123"}},
            self.key)
        request = self.cme.invoke_capability.await_args.args[0]
        self.assertEqual("r3a.cme", request["caller"]["principal_id"])
        self.assertEqual("r3a.cme", request["caller"]["resident_id"])
        self.assertEqual(self.key, request["idempotency_key"])
        self.cme.store.submit_activity_intake.assert_awaited_once()
        self.assertEqual("durable-activity-1", result["activity_id"])
        self.assertEqual("audit-1", result["source_authorization"]["audit_event_id"])

    async def test_rejects_mutating_provider_before_invocation(self):
        self.cme.settings.capability_registry.descriptor["effect_class"] = "external_write"
        with self.assertRaisesRegex(PermissionError, "read-only"):
            await self.cme._control_request(
                "activity.intake.accept", {"operation_id": "source.read", "input": {"event_id": "event-123"}},
                self.key)
        self.cme.invoke_capability.assert_not_awaited()

    async def test_grant_denial_stops_before_durable_activity_creation(self):
        self.cme.invoke_capability.side_effect = PermissionError("notification.source.read grant missing")
        with self.assertRaisesRegex(PermissionError, "grant missing"):
            await self.cme._control_request(
                "activity.intake.accept", {"operation_id": "source.read", "input": {"event_id": "event-123"}},
                self.key)
        self.cme.store.submit_activity_intake.assert_not_awaited()

    async def test_rejects_source_id_outside_provider_configuration(self):
        self.cme.settings.capability_registry.configuration["source_id"] = "configured.source"
        with self.assertRaisesRegex(Exception, "source identity"):
            await self.cme._control_request(
                "activity.intake.accept", {"operation_id": "source.read", "input": {"event_id": "event-123"}},
                self.key)
        self.cme.store.submit_activity_intake.assert_not_awaited()

    async def test_rejects_unbound_idempotency_or_provider_provenance(self):
        self.cme.invoke_capability.return_value = invocation_result(self.intake, self.provider)
        with self.assertRaisesRegex(Exception, "idempotency key"):
            await self.cme._control_request(
                "activity.intake.accept", {"operation_id": "source.read", "input": {"event_id": "event-123"}},
                "different-key")
        self.cme.store.submit_activity_intake.assert_not_awaited()

        wrong = copy.deepcopy(self.intake)
        wrong["provenance"]["artifact_sha256"] = "b" * 64
        self.cme.invoke_capability.return_value = invocation_result(wrong, self.provider)
        with self.assertRaisesRegex(Exception, "provenance"):
            await self.cme._control_request(
                "activity.intake.accept", {"operation_id": "source.read", "input": {"event_id": "event-123"}},
                self.key)
        self.cme.store.submit_activity_intake.assert_not_awaited()


class Cursor:
    def __init__(self, row=None):
        self.row = row

    async def fetchone(self):
        return self.row


class FakeConnection:
    def __init__(self):
        self.activity = None
        self.commands = []

    def transaction(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def execute(self, query, params=()):
        self.commands.append((query, params))
        if "FROM r3a.activities WHERE idempotency_key" in query:
            return Cursor(self.activity)
        if "FROM r3a.config_current" in query:
            return Cursor({"revision_id": "c" * 64})
        if "INSERT INTO r3a.activities" in query:
            self.activity = {"activity_id": params[0], "state": "QUEUED",
                             "activity_type": params[1], "idempotency_key": params[2],
                             "input": json.loads(params[4]), "attempt_count": 0}
        return Cursor()


class FakePool:
    def __init__(self):
        self.connection_value = FakeConnection()

    def connection(self):
        return self.connection_value


class ActivityIntakePersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_persists_source_provenance_and_deduplicates_replay(self):
        provider = {"provider_id": "source.module", "provider_version": "1.0.0",
                    "artifact_sha256": "a" * 64}
        intake = valid_notification_intake()
        intake["provenance"].update(module_id=provider["provider_id"],
                                    module_version=provider["provider_version"],
                                    artifact_sha256=provider["artifact_sha256"])
        result = invocation_result(intake, provider)
        store = Store.__new__(Store)
        store.settings = SimpleNamespace(model_roles=[], default_model_route="grace.80b",
                                         module_id="resident.grace", source_digest="c" * 64)
        store.pool = FakePool()
        store._event = AsyncMock(return_value=uuid.uuid4())
        store._transition_on_conn = AsyncMock(return_value=True)

        first = await store.submit_activity_intake(intake, result)
        second = await store.submit_activity_intake(intake, result)
        self.assertFalse(first["duplicate"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(first["activity_id"], second["activity_id"])
        persisted = store.pool.connection_value.activity["input"]
        self.assertEqual(intake, persisted["activity_intake"])
        self.assertEqual("activity_intake", persisted["event_kind"])
        store._transition_on_conn.assert_awaited_once()

        conflicting = copy.deepcopy(intake)
        conflicting["activity"]["input"] = {"different": "source payload"}
        with self.assertRaisesRegex(ValueError, "already bound to different source data"):
            await store.submit_activity_intake(conflicting, result)

    async def test_persists_non_grace_activity_type_and_handler_input(self):
        provider = {"provider_id": "source.module", "provider_version": "1.0.0",
                    "artifact_sha256": "a" * 64}
        intake = valid_notification_intake()
        intake["activity"].update(activity_type="billing.invoice.review", task_class="operations.review",
                                   input={"invoice_id": "invoice-001"})
        intake["provenance"].update(module_id=provider["provider_id"],
                                    module_version=provider["provider_version"],
                                    artifact_sha256=provider["artifact_sha256"])
        result = invocation_result(intake, provider)
        store = Store.__new__(Store)
        store.settings = SimpleNamespace(model_roles=[], default_model_route="grace.80b",
                                         module_id="resident.grace", source_digest="c" * 64)
        store.pool = FakePool()
        store._event = AsyncMock(return_value=uuid.uuid4())
        store._transition_on_conn = AsyncMock(return_value=True)

        accepted = await store.submit_activity_intake(intake, result)
        persisted = store.pool.connection_value.activity
        self.assertEqual("billing.invoice.review", accepted["activity_type"])
        self.assertEqual("billing.invoice.review", persisted["activity_type"])
        self.assertEqual({"invoice_id": "invoice-001"}, persisted["input"]["activity_input"])
        self.assertEqual(intake, persisted["input"]["activity_intake"])
        self.assertEqual("activity_intake", persisted["input"]["event_kind"])

    async def test_rejects_unauthorized_invocation_result(self):
        intake = valid_notification_intake()
        result = invocation_result(intake, intake["provenance"])
        result["authorization"]["allowed"] = False
        store = Store.__new__(Store)
        with self.assertRaisesRegex(PermissionError, "authorized CME source invocation"):
            await store.submit_activity_intake(intake, result)
