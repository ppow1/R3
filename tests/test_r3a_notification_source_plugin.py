"""Domain tests for the notification source adapter, independent of CME intake."""
from __future__ import annotations

import hashlib
import json
import os
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from r3a_plugins.notification_source import plugin
from r3a_runtime.capability_contracts import (CapabilityRegistry, normalize_provider_result,
                                              validate_operation)
from r3a_runtime.config import _validate_plugin_config, load_settings
from r3a_runtime.notifications import same_notification_input, validate_notification_envelope
from tests.test_r3a_modular_autonomy import make_config


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "r3a_plugins" / "notification_source"
EVENT_ID = uuid.UUID("4b0fdd75-85af-451d-a183-fd3ecc87ff39")
CORRELATION_ID = uuid.UUID("b80bc0e5-1a0c-4b92-98d0-b53008ff7015")


class FakeCursor:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class ReadOnlyEventLedger:
    def __init__(self, row=None, *, failure: Exception | None = None):
        self.row = row
        self.failure = failure
        self.statements = []
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def execute(self, query, params=()):
        self.statements.append((query, params))
        if self.failure:
            raise self.failure
        if "FROM r3a.institution_events" in query:
            if ("a.activity_type='foundation.observe'" in query
                    and isinstance(self.row, dict)
                    and self.row.get("activity_type") == "foundation.observe"):
                return FakeCursor(None)
            return FakeCursor(self.row)
        return FakeCursor(None)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def sample_event():
    return {
        "event_id": EVENT_ID, "event_type": "process.failed", "schema_version": 1,
        "subject_type": "process", "subject_id": "cme", "prior_state": "RUNNING",
        "next_state": "FAILED", "occurred_at": datetime(2026, 11, 7, 12, tzinfo=timezone.utc),
        "persisted_at": datetime(2026, 11, 7, 12, 0, 1, tzinfo=timezone.utc),
        "actor": "pid:123", "correlation_id": CORRELATION_ID,
        "reason": "fixture process failure", "outcome": "accepted",
        "config_revision": "cfg-17", "implementation_revision": "sha-fixture",
        "evidence": {"exit_code": 1},
    }


def setup_contract():
    manifest = json.loads((PACKAGE / "manifest.json").read_text(encoding="utf-8"))
    configuration = json.loads((PACKAGE / "config.example.json").read_text(encoding="utf-8"))
    _validate_plugin_config(configuration, manifest["configuration_schema"], "notification_source.config")
    descriptor = validate_operation(manifest["operation"])
    return manifest, configuration, descriptor


class NotificationSourceAdapterTests(unittest.TestCase):
    def setUp(self):
        self.manifest, self.configuration, self.descriptor = setup_contract()
        self.connection = ReadOnlyEventLedger(sample_event())
        self.provider = plugin.InstitutionEventNotificationSource(
            self.configuration, connect=lambda dsn, **kwargs: self.connection,
            clock=lambda: datetime(2026, 11, 7, 12, 1, tzinfo=timezone.utc))

    def test_provider_is_registered_through_existing_capability_operation_contract(self):
        self.assertEqual(hashlib.sha256((PACKAGE / "plugin.py").read_bytes()).hexdigest(),
                         self.manifest["artifact_sha256"])
        self.assertEqual(self.manifest["artifact_sha256"], self.descriptor["provider"]["artifact_sha256"])
        self.assertEqual("notification.source.read", self.descriptor["operation_id"])
        self.assertEqual(["notification.source.read"], self.descriptor["required_grants"])
        self.assertEqual("read", self.descriptor["effect_class"])
        registry = CapabilityRegistry()
        registered = registry.register(self.descriptor, self.configuration, legacy_manifest=self.manifest)
        self.assertIsInstance(registered.load_provider(), plugin.InstitutionEventNotificationSource)

    def test_external_capability_operations_config_registers_source_without_core_branch(self):
        with TemporaryDirectory() as temporary:
            config_path = make_config(Path(temporary))
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config["module"]["capabilities"].append("notification.source.read")
            config["capability_operations"] = [{
                "manifest": str(PACKAGE / "manifest.json"),
                "configuration": str(PACKAGE / "config.example.json"),
            }]
            config_path.write_text(json.dumps(config), encoding="utf-8")
            settings = load_settings(config_path)
        registered = settings.capability_registry.resolve("notification.source.read", "1.0.0")
        self.assertEqual("r3a.notification-source", registered.descriptor["provider"]["provider_id"])

    def test_maps_allowlisted_source_event_to_established_notification_envelope(self):
        with patch.dict(os.environ, {"R3A_NOTIFICATION_SOURCE_DSN": "fixture-secret"}):
            result = self.provider.invoke({"source_event_id": str(EVENT_ID)}, context={})
        output, evidence = normalize_provider_result(result, self.descriptor)
        self.assertEqual("r3a.notification-intake", output["contract_id"])
        self.assertEqual("1.0.0", output["contract_version"])
        self.assertEqual("r3a.institution-events", output["source_id"])
        self.assertEqual(str(EVENT_ID), output["source_event_id"])
        self.assertEqual(str(CORRELATION_ID), output["correlation_id"])
        self.assertEqual("error", output["severity"])
        self.assertEqual("2026-11-07T12:01:00Z", output["received_at"])
        self.assertEqual(64, len(evidence["payload_sha256"]))
        self.assertEqual("r3a.institution_events/" + str(EVENT_ID), evidence["payload_ref"])
        self.assertTrue(evidence["read_only"])
        self.assertNotIn("fixture-secret", json.dumps(result, default=str))
        sql = " ".join(statement.upper() for statement, _ in self.connection.statements)
        self.assertIn("READ ONLY", sql)
        self.assertIn("REPEATABLE READ", sql)
        self.assertIn("A.ACTIVITY_TYPE='FOUNDATION.OBSERVE'", sql)
        self.assertNotRegex(sql, r"\b(INSERT|UPDATE|DELETE|ALTER|DROP|TRUNCATE)\b")
        self.assertTrue(self.connection.committed)
        self.assertFalse(self.connection.rolled_back)
        self.assertTrue(self.connection.closed)

    def test_repeat_reads_preserve_event_identity_and_dedup_input(self):
        with patch.dict(os.environ, {"R3A_NOTIFICATION_SOURCE_DSN": "fixture-secret"}):
            one = self.provider.invoke({"source_event_id": str(EVENT_ID)}, context={}).output
            two = self.provider.invoke({"source_event_id": str(EVENT_ID)}, context={}).output
        self.assertTrue(same_notification_input({"notification": one}, {"notification": two}))

    def test_source_output_supplies_proposed_generic_intake_fields_without_repacking_n1(self):
        with patch.dict(os.environ, {"R3A_NOTIFICATION_SOURCE_DSN": "fixture-secret"}):
            provider_result = self.provider.invoke({"source_event_id": str(EVENT_ID)}, context={})
        envelope = validate_notification_envelope(provider_result.output)

        # Compatibility projection from the audit proposal; it is test-local,
        # not a new r3a.activity-intake contract or a production wrapper.
        adapter_fields = {
            "source_id": envelope["source_id"],
            "source_event_id": envelope["source_event_id"],
            "idempotency_key": f"notification:{envelope['source_id']}:{envelope['source_event_id']}",
            "correlation_id": envelope["correlation_id"],
            "payload_ref": envelope["payload_ref"],
            "provenance": envelope["provenance"],
            "evidence": envelope["evidence"],
        }
        self.assertEqual(str(EVENT_ID), adapter_fields["source_event_id"])
        self.assertEqual(str(CORRELATION_ID), adapter_fields["correlation_id"])
        self.assertEqual("notification:r3a.institution-events:" + str(EVENT_ID),
                         adapter_fields["idempotency_key"])
        self.assertTrue(adapter_fields["payload_ref"].endswith(str(EVENT_ID)))
        self.assertEqual("r3a.institution_events", adapter_fields["provenance"]["store"])
        self.assertIn("source_evidence", adapter_fields["evidence"])

        # Parent activity linkage and the reasoning task class belong to CME's
        # generic intake context; neither is guessed or added to N1's envelope.
        self.assertNotIn("parent_activity_id", envelope)
        self.assertNotIn("task_class", envelope)
        self.assertEqual("r3a.notification-intake", envelope["contract_id"])
        self.assertEqual("1.0.0", envelope["contract_version"])

    def test_generic_activity_intake_projection_validates_and_preserves_n1_envelope(self):
        with patch.dict(os.environ, {"R3A_NOTIFICATION_SOURCE_DSN": "fixture-secret"}):
            provider_result = self.provider.invoke({"source_event_id": str(EVENT_ID)}, context={})
        n1 = validate_notification_envelope(provider_result.output)
        projection = plugin.to_activity_intake(
            n1, provider_result.evidence,
            provider={"provider_id": "r3a.notification-source", "provider_version": "1.0.0",
                      "artifact_sha256": self.manifest["artifact_sha256"]},
            configuration_revision="cfg-17",
            lifecycle_projection={
                "received": "grace.notification.received",
                "actionable": "grace.notification.actionable",
                "acknowledged": "grace.notification.acknowledged",
                "resolved": "grace.notification.resolved",
                "blocked": "grace.notification.blocked",
            },
        )
        schema = json.loads((ROOT / "r3a_runtime/schemas/activity-intake.v1.schema.json").read_text())
        from r3a_runtime.capability_contracts import validate_json
        validate_json(projection, schema)
        self.assertEqual("r3a.activity-intake.v1", projection["contract_id"])
        self.assertEqual("notification:r3a.institution-events:" + str(EVENT_ID), projection["intake_id"])
        self.assertEqual(projection["intake_id"], projection["source"]["idempotency_key"])
        self.assertEqual(str(CORRELATION_ID), projection["correlation_id"])
        self.assertEqual(n1["occurred_at"], projection["source"]["occurred_at"])
        self.assertEqual(n1["received_at"], projection["source"]["received_at"])
        self.assertEqual(n1, projection["activity"]["input"]["notification"])
        self.assertEqual(provider_result.evidence["payload_sha256"], projection["source"]["payload_sha256"])
        self.assertEqual("cfg-17", projection["provenance"]["configuration_revision"])
        self.assertEqual("objective_reasoning", projection["activity"]["task_class"])
        self.assertEqual("grace.notification.acknowledged",
                         projection["lifecycle_projection"]["acknowledged"])

    def test_generic_projection_rejects_mismatched_evidence_and_bad_lifecycle(self):
        with patch.dict(os.environ, {"R3A_NOTIFICATION_SOURCE_DSN": "fixture-secret"}):
            result = self.provider.invoke({"source_event_id": str(EVENT_ID)}, context={})
        args = (result.output, result.evidence)
        provider = {"provider_id": "r3a.notification-source", "provider_version": "1.0.0",
                    "artifact_sha256": self.manifest["artifact_sha256"]}
        lifecycle = {phase: f"grace.notification.{phase}" for phase in
                     ("received", "actionable", "acknowledged", "resolved", "blocked")}
        with self.assertRaisesRegex(ValueError, "same notification event"):
            plugin.to_activity_intake(args[0], {**args[1], "source_event_id": str(uuid.uuid4())},
                                      provider=provider, configuration_revision="cfg-17",
                                      lifecycle_projection=lifecycle)
        with self.assertRaises(Exception):
            plugin.to_activity_intake(args[0], args[1], provider=provider,
                                      configuration_revision="cfg-17",
                                      lifecycle_projection={**lifecycle, "received": "activity.completed"})

    def test_routine_foundation_observe_event_is_not_intake_eligible(self):
        observer_event = sample_event()
        observer_event.update(event_type="activity.completed", subject_type="activity",
                              subject_id="observe-activity", activity_type="foundation.observe")
        provider = plugin.InstitutionEventNotificationSource(
            self.configuration, connect=lambda *a, **k: ReadOnlyEventLedger(observer_event))
        with patch.dict(os.environ, {"R3A_NOTIFICATION_SOURCE_DSN": "fixture-secret"}):
            with self.assertRaisesRegex(KeyError, "not found"):
                provider.invoke({"source_event_id": str(EVENT_ID)}, context={})

    def test_rejects_invalid_id_unconfigured_source_missing_event_and_unallowlisted_type(self):
        with self.assertRaisesRegex(ValueError, "UUID"):
            self.provider.invoke({"source_event_id": "bad"}, context={})
        with patch.dict(os.environ, {"R3A_NOTIFICATION_SOURCE_DSN": "fixture"}):
            with self.assertRaisesRegex(KeyError, "not found"):
                plugin.InstitutionEventNotificationSource(
                    self.configuration, connect=lambda *a, **k: ReadOnlyEventLedger(None)
                ).invoke({"source_event_id": str(EVENT_ID)}, context={})
            invalid = sample_event()
            invalid["event_type"] = "private.audit.record"
            with self.assertRaisesRegex(PermissionError, "not enabled"):
                plugin.InstitutionEventNotificationSource(
                    self.configuration, connect=lambda *a, **k: ReadOnlyEventLedger(invalid)
                ).invoke({"source_event_id": str(EVENT_ID)}, context={})
        with patch.dict(os.environ, {"R3A_NOTIFICATION_SOURCE_DSN": ""}):
            with self.assertRaisesRegex(RuntimeError, "not_configured"):
                self.provider.invoke({"source_event_id": str(EVENT_ID)}, context={})

    def test_source_failure_rolls_back_and_remains_an_error(self):
        connection = ReadOnlyEventLedger(failure=OSError("database offline"))
        provider = plugin.InstitutionEventNotificationSource(
            self.configuration, connect=lambda *a, **k: connection)
        with patch.dict(os.environ, {"R3A_NOTIFICATION_SOURCE_DSN": "fixture"}):
            with self.assertRaisesRegex(RuntimeError, "unavailable:OSError") as caught:
                provider.invoke({"source_event_id": str(EVENT_ID)}, context={})
        self.assertNotIn("fixture", str(caught.exception))
        self.assertTrue(connection.rolled_back)
        self.assertTrue(connection.closed)
        connect_failure = plugin.InstitutionEventNotificationSource(
            self.configuration,
            connect=lambda dsn, **kwargs: (_ for _ in ()).throw(OSError(f"dsn={dsn}")))
        with patch.dict(os.environ, {"R3A_NOTIFICATION_SOURCE_DSN": "secret-value"}):
            with self.assertRaisesRegex(RuntimeError, "unavailable:OSError") as caught:
                connect_failure.invoke({"source_event_id": str(EVENT_ID)}, context={})
        self.assertNotIn("secret-value", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
