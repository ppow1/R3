"""CME notification operation packaging and caller-binding regressions."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from r3a_plugins.notification_service.capability import NotificationDeliveryProvider


class NotificationCapabilityTests(unittest.TestCase):
    def test_provider_binds_store_recipient_and_authorization_to_cme_caller(self):
        provider = object.__new__(NotificationDeliveryProvider)
        provider.presentation_timezone = "UTC"
        provider.store = type("Store", (), {"inbox": lambda _self, recipient, **kw: {
            "contract": "r3a.notification-inbox.v1", "deliveries": [],
            "next_cursor": None, "recipient": recipient, **kw}})()
        result = provider.invoke({"cursor": None, "limit": 10}, context={
            "operation_id": "notification.delivery.read",
            "caller": {"principal_id": "steward:session-7"},
            "authorization": {"allowed": True, "decision_id": "cme-decision",
                              "audit_event_id": "cme-audit"}})
        self.assertEqual(result.output["recipient"], "steward:session-7")
        self.assertEqual(result.evidence["authorization_decision_id"], "cme-decision")

    def test_lifecycle_provider_passes_only_cme_authorized_actor_to_owned_store(self):
        provider = object.__new__(NotificationDeliveryProvider)
        captured = {}
        def acknowledge(*args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs
            return {"contract_id": "r3a.notification-delivery", "status": "acknowledged"}
        provider.store = type("Store", (), {"acknowledge": staticmethod(acknowledge)})()
        provider.invoke({"delivery_id": "delivery-1", "idempotency_key": "request-0001", "note": None},
                        context={"operation_id": "notification.delivery.acknowledge",
                                 "caller": {"principal_id": "steward:session-7"},
                                 "authorization": {"allowed": True, "decision_id": "decision-1",
                                                   "audit_event_id": "audit-1"}})
        self.assertEqual(captured["args"][:3], ("delivery-1", "steward:session-7", "request-0001"))
        self.assertEqual(captured["args"][3]["actor_id"], "steward:session-7")
        self.assertEqual(captured["args"][3]["decision_id"], "decision-1")

    def test_provider_rejects_missing_cme_authorization_before_store_access(self):
        provider = object.__new__(NotificationDeliveryProvider)
        provider.store = type("Store", (), {"inbox": lambda *_a, **_k: self.fail("store must not be called")})()
        with self.assertRaises(PermissionError):
            provider.invoke({"cursor": None, "limit": 10}, context={
                "operation_id": "notification.delivery.read",
                "caller": {"principal_id": "steward:session-7"},
                "authorization": {"allowed": False}})


if __name__ == "__main__":
    unittest.main()
