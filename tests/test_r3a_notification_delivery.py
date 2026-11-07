from __future__ import annotations

import unittest
import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

from r3a_runtime.notification_delivery import (
    DELIVERY_CONTRACT_ID, DirectoryUnavailable, route_notification, transition_delivery,
    validate_delivery_envelope, validate_routing_policy,
)
from r3a_runtime.authorization import AuthorizationDecision, AuthorizationRequest
from r3a_runtime.contracts import AUTHORIZATION_CONTRACT_ID, AUTHORIZATION_CONTRACT_VERSION
from r3a_runtime.db import Store


def notification(event_type: str = "process.failed") -> dict:
    event_id, correlation_id = str(uuid.uuid4()), str(uuid.uuid4())
    return {
        "contract_id": "r3a.notification-intake", "contract_version": "1.0.0",
        "source_id": "r3a.institution-events", "source_event_id": event_id,
        "event_type": event_type, "event_id": event_id, "correlation_id": correlation_id,
        "occurred_at": "2026-11-07T12:00:00Z", "received_at": "2026-11-07T12:01:00Z",
        "severity": "error", "payload_ref": f"r3a.institution_events/{event_id}",
        "provenance": {"store": "r3a.institution_events"}, "evidence": {"outcome": "failed"},
    }


def directory() -> dict:
    return {
        "schema_id": "r3a.institutional-directory.v1",
        "source": {"availability": "measured", "freshness": "fresh", "snapshot_sha256": "a" * 64},
        "offices": [
            {"office_id": "office.ops", "office_role": "Operations", "status": "active"},
            {"office_id": "office.retired", "office_role": "Operations", "status": "retired"},
        ],
        "residents": [
            {"resident_id": "resident.alpha", "office_id": "office.ops",
             "office_role": "Operations", "office_status": "active"},
            {"resident_id": "resident.archived", "office_id": "office.ops",
             "office_role": "Operations", "office_status": "inactive"},
            {"resident_id": "resident.other", "office_id": "office.other",
             "office_role": "Engineering", "office_status": "active"},
        ],
    }


def policy(kind: str = "resident", *, action: bool = True) -> dict:
    return {"contract_id": DELIVERY_CONTRACT_ID, "contract_version": "1.0.0", "rules": [{
        "source_id": "r3a.institution-events", "event_type": "process.failed",
        "recipient": {"kind": kind, "office_role": "operations"},
        "urgency": "critical", "requires_action": action,
    }]}


class NotificationDeliveryTests(unittest.TestCase):
    def test_routes_to_active_directory_resident_without_configured_identity(self):
        result = route_notification(notification(), directory(), policy(),
                                    created_at="2026-11-07T12:02:00Z")
        self.assertEqual(1, len(result))
        delivery = validate_delivery_envelope(result[0])
        self.assertEqual("resident.alpha", delivery["recipient"]["recipient_id"])
        self.assertEqual("office.ops", delivery["recipient"]["office_id"])
        self.assertEqual("queued", delivery["status"])
        self.assertEqual("critical", delivery["urgency"])
        self.assertTrue(delivery["requires_action"])

    def test_duplicate_routing_has_stable_id_and_idempotency_key(self):
        event = notification()
        first = route_notification(event, directory(), policy())
        second = route_notification(event, directory(), policy())
        self.assertEqual(first[0]["delivery_id"], second[0]["delivery_id"])
        self.assertEqual(first[0]["idempotency_key"], second[0]["idempotency_key"])

    def test_routes_to_office_identity_as_office_not_each_member(self):
        result = route_notification(notification(), directory(), policy("office"))
        self.assertEqual(["office.ops"], [item["recipient"]["recipient_id"] for item in result])
        self.assertEqual("office", result[0]["recipient"]["kind"])

    def test_informational_rule_retains_non_actionable_classification(self):
        result = route_notification(notification(), directory(), policy(action=False))
        self.assertFalse(result[0]["requires_action"])

    def test_unmatched_event_is_not_delivered(self):
        self.assertEqual([], route_notification(notification("process.started"), directory(), policy()))

    def test_stale_or_unavailable_directory_blocks_routing(self):
        source = directory()
        source["source"]["availability"] = "unavailable"
        with self.assertRaises(DirectoryUnavailable):
            route_notification(notification(), source, policy())
        source = directory()
        source["source"]["freshness"] = "unavailable"
        with self.assertRaises(DirectoryUnavailable):
            route_notification(notification(), source, policy())

    def test_invalid_selector_and_delivery_contract_are_rejected(self):
        invalid = policy()
        invalid["rules"][0]["recipient"]["resident_id"] = "resident.alpha"
        with self.assertRaises(ValueError):
            validate_routing_policy(invalid)
        envelope = route_notification(notification(), directory(), policy())[0]
        envelope["status"] = "sent"
        with self.assertRaises(ValueError):
            validate_delivery_envelope(envelope)
        envelope = route_notification(notification(), directory(), policy())[0]
        envelope["recipient"]["recipient_id"] = "resident.changed"
        with self.assertRaisesRegex(ValueError, "identity"):
            validate_delivery_envelope(envelope)

    def authorization(self, principal_id: str, capability: str, *, allowed: bool = True):
        request = AuthorizationRequest(
            contract_id=AUTHORIZATION_CONTRACT_ID, contract_version=AUTHORIZATION_CONTRACT_VERSION,
            request_id=str(uuid.uuid4()), correlation_id=str(uuid.uuid4()), resident_id=principal_id,
            capability_id=capability, activity_id=None, attempt_id=None,
            config_revision="cfg-test", created_at="2026-11-07T12:00:00Z", context={},
        )
        decision = AuthorizationDecision(
            contract_id=AUTHORIZATION_CONTRACT_ID, contract_version=AUTHORIZATION_CONTRACT_VERSION,
            provider_id="capability_grants", allowed=allowed,
            reason="active grant" if allowed else "missing grant", retryable=False,
            policy_revision=None, config_revision="cfg-test",
            observed_at="2026-11-07T12:00:01Z", correlation_id=request.correlation_id,
            audit_event_id=str(uuid.uuid4()), decision_id=str(uuid.uuid4()),
        )
        return request, decision

    def test_authorized_recipient_can_acknowledge_then_resolve(self):
        delivery = route_notification(notification(), directory(), policy())[0]
        req, decision = self.authorization("resident.alpha", "notification.delivery.acknowledge")
        acked = transition_delivery(delivery, "acknowledge", principal_id="resident.alpha",
                                    request=req, decision=decision, directory=directory(),
                                    at="2026-11-07T12:03:00Z")
        self.assertEqual("acknowledged", acked["status"])
        self.assertEqual("2026-11-07T12:03:00Z", acked["acknowledged_at"])
        req, decision = self.authorization("resident.alpha", "notification.delivery.resolve")
        resolved = transition_delivery(acked, "resolve", principal_id="resident.alpha",
                                       request=req, decision=decision, directory=directory(),
                                       at="2026-11-07T12:04:00Z")
        self.assertEqual("resolved", resolved["status"])

    def test_acknowledgment_requires_recipient_scope_and_matching_authorization(self):
        delivery = route_notification(notification(), directory(), policy())[0]
        req, denied = self.authorization("resident.alpha", "notification.delivery.acknowledge", allowed=False)
        with self.assertRaises(PermissionError):
            transition_delivery(delivery, "acknowledge", principal_id="resident.alpha",
                                request=req, decision=denied, directory=directory())
        req, allowed = self.authorization("resident.other", "notification.delivery.acknowledge")
        with self.assertRaises(PermissionError):
            transition_delivery(delivery, "acknowledge", principal_id="resident.other",
                                request=req, decision=allowed, directory=directory())

    def test_office_acknowledgment_requires_active_directory_binding(self):
        delivery = route_notification(notification(), directory(), policy("office"))[0]
        req, decision = self.authorization("resident.other", "notification.delivery.acknowledge")
        with self.assertRaises(PermissionError):
            transition_delivery(delivery, "acknowledge", principal_id="resident.other",
                                request=req, decision=decision, directory=directory())
        req, decision = self.authorization("resident.alpha", "notification.delivery.acknowledge")
        acked = transition_delivery(delivery, "acknowledge", principal_id="resident.alpha",
                                    request=req, decision=decision, directory=directory())
        self.assertEqual("acknowledged", acked["status"])


class _Cursor:
    def __init__(self, rows):
        self.rows = rows

    async def fetchone(self):
        return self.rows[0] if self.rows else None

    async def fetchall(self):
        return list(self.rows)


class _Connection:
    def __init__(self, events):
        self.events = events

    @asynccontextmanager
    async def transaction(self):
        yield self

    async def execute(self, query, params=()):
        if "event_type='grace.notification.delivery.queued'" in query:
            rows = [row for row in self.events if row["event_type"] == "grace.notification.delivery.queued"
                    and row["evidence"].get("delivery_id") == params[0]]
            return _Cursor(rows)
        if "WHERE subject_type='notification_delivery'" in query:
            rows = [row for row in self.events if row["subject_id"] == params[0]]
            rows.sort(key=lambda row: row["sequence"], reverse=True)
            return _Cursor(rows)
        return _Cursor([])


class _Pool:
    def __init__(self, events):
        self.conn = _Connection(events)

    @asynccontextmanager
    async def connection(self):
        yield self.conn


class NotificationDeliveryPersistenceTests(unittest.IsolatedAsyncioTestCase):
    def _store(self, events):
        store = Store.__new__(Store)
        store.pool = _Pool(events)
        async def append_event(_conn, event_type, subject_type, subject_id, machine_id,
                               machine_version, prior_state, next_state, reason, evidence=None,
                               **kwargs):
            events.append({"event_type": event_type, "subject_type": subject_type,
                           "subject_id": subject_id, "evidence": dict(evidence or {}),
                           "sequence": len(events)})
            return uuid.uuid4()
        store._event = AsyncMock(side_effect=append_event)
        async def list_rows(query, params=()):
            rows = sorted(events, key=lambda row: row["sequence"], reverse=True)
            latest = {}
            for row in rows:
                if row["subject_type"] == "notification_delivery":
                    latest.setdefault(row["subject_id"], row["evidence"])
            return [{"evidence": value} for value in list(latest.values())[:params[0]]]
        store.rows = AsyncMock(side_effect=list_rows)
        return store

    async def test_delivery_survives_store_recreation_and_replays_idempotently(self):
        events = []
        event = notification()
        target_directory = directory()
        target_policy = policy()
        first_store = self._store(events)
        first = await first_store.enqueue_notification_deliveries(event, target_directory, target_policy)
        self.assertEqual(1, len(events))
        second_store = self._store(events)
        replay = await second_store.enqueue_notification_deliveries(event, target_directory, target_policy)
        self.assertTrue(replay[0]["duplicate"])
        self.assertEqual(1, len(events))

        delivery = first[0]
        request, decision = NotificationDeliveryTests().authorization(
            "resident.alpha", "notification.delivery.acknowledge")
        acked = await second_store.transition_notification_delivery(
            delivery["delivery_id"], "acknowledge", principal_id="resident.alpha",
            request=request, decision=decision, directory=target_directory)
        self.assertEqual("acknowledged", acked["status"])

        restarted_store = self._store(events)
        history = await restarted_store.notification_delivery_history()
        self.assertEqual("acknowledged", history[0]["status"])
        self.assertEqual(2, len(events))
        request, decision = NotificationDeliveryTests().authorization(
            "resident.alpha", "notification.delivery.read")
        inbox = await restarted_store.notification_delivery_inbox(
            "resident.alpha", target_directory, request, decision)
        self.assertEqual([delivery["delivery_id"]], [item["delivery_id"] for item in inbox])
        request, decision = NotificationDeliveryTests().authorization(
            "resident.other", "notification.delivery.read")
        hidden = await restarted_store.notification_delivery_inbox(
            "resident.other", target_directory, request, decision)
        self.assertEqual([], hidden)


if __name__ == "__main__":
    unittest.main()
