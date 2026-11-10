"""Focused regression tests for versioned notification intake and lifecycle."""
from __future__ import annotations

import copy
import json
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import AsyncMock

from r3a_runtime.config import ConfigurationError, load_settings, sanitized_config
from r3a_runtime.cme import CME
from r3a_runtime.db import Store
from r3a_runtime.notifications import (INSTITUTION_EVENT_SOURCE, institution_event_envelope,
                                       same_notification_input, validate_notification_envelope)
from tests.test_r3a_modular_autonomy import make_config


def notification_settings(directory: Path):
    path = make_config(directory)
    config = json.loads(path.read_text(encoding="utf-8"))
    config["notification_intake"] = {
        "contract_id": "r3a.notification-intake", "contract_version": "1.0.0",
        "sources": [{"source_id": INSTITUTION_EVENT_SOURCE,
                     "adapter": "institution_events.v1", "enabled": True,
                     "event_types": ["process.state_transition"]}],
    }
    path.write_text(json.dumps(config), encoding="utf-8")
    return load_settings(path)


class NotificationEnvelopeTests(unittest.TestCase):
    def setUp(self):
        self.event_id = str(uuid.uuid4())
        self.correlation_id = str(uuid.uuid4())
        self.event = {
            "event_id": uuid.UUID(self.event_id), "event_type": "process.state_transition",
            "schema_version": 1, "subject_type": "process", "subject_id": "cme",
            "prior_state": "RUNNING", "next_state": "RESTARTING",
            "occurred_at": datetime(2026, 11, 7, 21, 0, tzinfo=timezone.utc),
            "persisted_at": datetime(2026, 11, 7, 21, 0, 1, tzinfo=timezone.utc),
            "actor": "pid:123", "correlation_id": uuid.UUID(self.correlation_id),
            "reason": "service event fixture", "outcome": "accepted",
            "implementation_revision": "fixture-sha", "evidence": {"pid": 123},
        }

    def test_existing_ledger_row_projects_to_versioned_correlated_envelope(self):
        envelope = institution_event_envelope(self.event, received_at="2026-11-07T21:00:02+00:00")
        self.assertEqual(envelope["contract_id"], "r3a.notification-intake")
        self.assertEqual(envelope["source_id"], INSTITUTION_EVENT_SOURCE)
        self.assertEqual(envelope["source_event_id"], self.event_id)
        self.assertEqual(envelope["event_id"], self.event_id)
        self.assertEqual(envelope["correlation_id"], self.correlation_id)
        self.assertEqual(envelope["severity"], "warning")
        self.assertEqual(envelope["evidence"]["source_evidence"],
                         {"pid": 123, "source_config_revision": None})

    def test_envelope_rejects_missing_timestamp_bad_severity_and_wrong_contract(self):
        envelope = institution_event_envelope(self.event, received_at="2026-11-07T21:00:02+00:00")
        for field, value in (("received_at", "yesterday"), ("severity", "urgent"),
                             ("contract_version", "2.0.0")):
            bad = copy.deepcopy(envelope)
            bad[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_notification_envelope(bad)

    def test_duplicate_delivery_ignores_new_receipt_time_but_not_source_identity(self):
        original = {"objective": "review", "event_kind": "notification",
                    "notification": institution_event_envelope(
                        self.event, received_at="2026-11-07T21:00:02+00:00")}
        replay = copy.deepcopy(original)
        replay["notification"]["received_at"] = "2026-11-07T21:01:02+00:00"
        self.assertTrue(same_notification_input(original, replay))
        replay["notification"]["source_event_id"] = str(uuid.uuid4())
        self.assertFalse(same_notification_input(original, replay))


class NotificationConfigurationTests(unittest.TestCase):
    def test_source_configuration_is_external_allowlisted_and_sanitized(self):
        with TemporaryDirectory() as temporary:
            path = make_config(Path(temporary))
            config = json.loads(path.read_text(encoding="utf-8"))
            config["notification_intake"] = {
                "contract_id": "r3a.notification-intake", "contract_version": "1.0.0",
                "sources": [{"source_id": INSTITUTION_EVENT_SOURCE,
                             "adapter": "institution_events.v1", "enabled": True,
                             "event_types": ["process.state_transition"]}],
            }
            path.write_text(json.dumps(config), encoding="utf-8")
            settings = load_settings(path)
            self.assertEqual(settings.notification_sources[0].event_types,
                             ("process.state_transition",))
            self.assertTrue(sanitized_config(settings)["notification_intake"]["sources"][0]["enabled"])
            config["notification_intake"]["sources"][0]["adapter"] = "another.loop"
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(ConfigurationError, "adapter is unsupported"):
                load_settings(path)


class NotificationIntakeTests(unittest.IsolatedAsyncioTestCase):
    async def test_legacy_notification_ingest_control_route_is_removed(self):
        with TemporaryDirectory() as temporary:
            cme = CME(notification_settings(Path(temporary)))
            event_id = str(uuid.uuid4())
            with self.assertRaisesRegex(ValueError, "Unsupported CME control operation"):
                await cme._control_request(
                    "notification.ingest",
                    {"source_id": INSTITUTION_EVENT_SOURCE, "source_event_id": event_id},
                    f"notification:{INSTITUTION_EVENT_SOURCE}:{event_id}")
            self.assertFalse(hasattr(Store, "ingest_institution_event_notification"))

    async def test_acknowledgment_is_validated_and_atomic_with_completion(self):
        source_id, source_event_id = INSTITUTION_EVENT_SOURCE, str(uuid.uuid4())
        activity = {"activity_id": str(uuid.uuid4()), "attempt_id": str(uuid.uuid4()),
                    "lease_id": str(uuid.uuid4()), "resource_id": "institution.reasoning",
                    "input": {"correlation_id": str(uuid.uuid4()), "notification": {
                        "source_id": source_id, "source_event_id": source_event_id,
                        "event_id": source_event_id,
                        "correlation_id": str(uuid.uuid4()),
                        "payload_ref": f"r3a.institution_events/{source_event_id}"}}}
        source_key = f"notification:{source_id}:{source_event_id}"
        valid = {"decision": {"status": "healthy", "assessment": "Reviewed the source event.",
                              "recommended_action": "No further action is required.",
                              "evidence_refs": [source_key]}}
        invalid_results = [
            {"action": "invoke_capability", "capability": "in_progress"},
            {"decision": {"status": "healthy", "assessment": "Looks good.",
                           "recommended_action": "No action.", "evidence_refs": []}},
            {"decision": {"status": "blocked", "assessment": "The source was unavailable.",
                           "recommended_action": "Retry.", "evidence_refs": [source_key]}},
            {"decision": {"status": "healthy", "assessment": "Reviewed.",
                           "evidence_refs": [source_key]}},
        ]
        for result in invalid_results:
            with self.subTest(result=result), self.assertRaises(ValueError):
                Store._validated_notification_disposition(activity, result)
        self.assertIs(Store._validated_notification_disposition(activity, valid),
                      activity["input"]["notification"])

        class AsyncContext:
            def __init__(self, value):
                self.value = value

            async def __aenter__(self):
                return self.value

            async def __aexit__(self, *_args):
                return False

        class Cursor:
            rowcount = 1

            async def fetchone(self):
                return None

        class Connection:
            async def execute(self, *_args):
                return Cursor()

            def transaction(self):
                return AsyncContext(self)

        class Pool:
            def __init__(self):
                self.opened = 0

            def connection(self):
                self.opened += 1
                return AsyncContext(Connection())

        store = Store.__new__(Store)
        store.pool = Pool()
        store.settings = SimpleNamespace(observer_interval_seconds=10)
        event_types = []

        async def record_event(_conn, event_type, *_args, **_kwargs):
            event_types.append(event_type)
            return uuid.uuid4()

        store._event = AsyncMock(side_effect=record_event)
        store._transition_on_conn = AsyncMock(return_value=True)
        store._schedule_observer_activity_on_conn = AsyncMock()
        for result in invalid_results:
            with self.subTest(invalid_finish=result), self.assertRaises(ValueError):
                await store.finish_activity(activity, result)
        self.assertEqual(store.pool.opened, 0)
        self.assertEqual(event_types, [])

        await store.finish_activity(activity, valid)
        self.assertEqual(event_types,
                         ["activity.completed", "grace.notification.acknowledged",
                          "grace.notification.resolved"])
        self.assertEqual(store.pool.opened, 1)
        ack_args = store._event.await_args_list[1].args
        self.assertEqual(ack_args[1], "grace.notification.acknowledged")
        self.assertEqual(ack_args[6:8], ("COMPLETED", "COMPLETED"))

    async def test_completed_notification_requires_its_evidence_and_disposition(self):
        with TemporaryDirectory() as temporary:
            cme = CME(load_settings(make_config(Path(temporary))))
            source_id = "notification:r3a.institution-events:source-event-1"
            context = {"objective": "Review source event", "notification": {"source_event_id": "source-event-1"},
                       "required_evidence_refs": [source_id]}
            evidence = [{"source_id": source_id, "content": "source event evidence"}]
            self.assertEqual(cme._final_evidence_issues(
                context, evidence,
                {"status": "healthy", "assessment": "Resolved from source evidence.",
                 "recommended_action": "No further action is required.",
                 "evidence_refs": [source_id]}), [])
            missing = cme._final_evidence_issues(
                context, evidence,
                {"status": "healthy", "assessment": "Resolved.", "evidence_refs": []})
            self.assertEqual(missing[0]["code"], "evidence_citations_missing")
            missing_action = cme._final_evidence_issues(
                context, evidence,
                {"status": "healthy", "assessment": "Resolved.",
                 "evidence_refs": [source_id]})
            self.assertEqual(missing_action[0]["code"], "notification_recommended_action_missing")

    async def test_resolved_and_blocked_are_distinct_correlated_durable_events(self):
        store = Store.__new__(Store)
        source_event_id, correlation_id = str(uuid.uuid4()), str(uuid.uuid4())
        store._event = AsyncMock(return_value=uuid.uuid4())
        activity = {"activity_id": str(uuid.uuid4()), "input": {"notification": {
            "source_id": INSTITUTION_EVENT_SOURCE, "source_event_id": source_event_id,
            "event_id": source_event_id, "correlation_id": correlation_id,
            "payload_ref": f"r3a.institution_events/{source_event_id}"}}}
        await store._notification_outcome(object(), activity, "resolved", {"assessment": "evidenced"})
        await store._notification_outcome(object(), activity, "blocked", {"reason": "evidence unavailable"})
        self.assertEqual(store._event.await_args_list[0].args[1], "grace.notification.resolved")
        self.assertEqual(store._event.await_args_list[1].args[1], "grace.notification.blocked")
        for call in store._event.await_args_list:
            self.assertEqual(call.kwargs["correlation_id"], uuid.UUID(correlation_id))
            self.assertEqual(call.kwargs["causation_id"], uuid.UUID(source_event_id))

    async def test_actionable_is_recorded_when_cme_claims_the_notification(self):
        store = Store.__new__(Store)
        source_event_id, correlation_id = str(uuid.uuid4()), str(uuid.uuid4())
        store._event = AsyncMock(return_value=uuid.uuid4())
        activity = {"activity_id": str(uuid.uuid4()), "state": "QUEUED", "input": {"notification": {
            "source_id": INSTITUTION_EVENT_SOURCE, "source_event_id": source_event_id,
            "event_id": source_event_id, "correlation_id": correlation_id,
            "payload_ref": f"r3a.institution_events/{source_event_id}"}}}
        attempt_id = uuid.uuid4()
        await store._notification_actionable(object(), activity, attempt_id)
        self.assertEqual(store._event.await_args.args[1], "grace.notification.actionable")
        self.assertEqual(store._event.await_args.args[6:8], ("QUEUED", "RUNNING"))
        self.assertEqual(store._event.await_args.kwargs["causation_id"], uuid.UUID(source_event_id))


if __name__ == "__main__":
    unittest.main()
