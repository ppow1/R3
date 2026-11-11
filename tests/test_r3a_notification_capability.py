"""CME notification operation packaging and caller-binding regressions."""
from __future__ import annotations

import unittest
import hashlib
import json
import copy
import tarfile
import tempfile
from pathlib import Path
from unittest.mock import patch

from r3a_runtime.capability_contracts import (CapabilityContractError,
                                              operation_from_manifest,
                                              validate_invocation_request,
                                              validate_operation)
from r3a_runtime.config import load_settings
from r3a_plugins.notification_service.capability import NotificationDeliveryProvider
from scripts.package_notification_module import build_package


class NotificationCapabilityTests(unittest.TestCase):
    def test_inbox_manifest_uses_canonical_read_grant_and_pinned_provider(self):
        manifest_path = (Path(__file__).resolve().parents[1] / "r3a_plugins"
                         / "notification_service" / "manifest.read.json")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        operation = operation_from_manifest(manifest)
        self.assertEqual(operation["operation_id"], "notification.delivery.read")
        self.assertEqual(operation["effect_class"], "read")
        self.assertEqual(operation["required_grants"], ["notification.delivery.read"])
        self.assertEqual(operation["provider"]["artifact_sha256"],
                         hashlib.sha256((manifest_path.parent / "capability.py").read_bytes()).hexdigest())
        store_digest = hashlib.sha256(
            (manifest_path.parent / "store.py").read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest()
        self.assertEqual(manifest["supporting_artifacts"][0]["artifact_sha256"], store_digest)

    def test_inbox_operation_registers_through_standard_module_registry_config(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            staged_root = temporary_root / "installed"
            package_path = temporary_root / "notification.tar.gz"
            build_package(package_path)
            with tarfile.open(package_path, "r:gz") as archive:
                for member in archive.getmembers():
                    if not member.isfile():
                        continue
                    target = staged_root / member.name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.extractfile(member).read())
            data_dir = temporary_root / "data"
            data_dir.mkdir()
            operation_config = temporary_root / "notification-config.json"
            operation_config.write_text(json.dumps({
                "dsn_env": "R3A_NOTIFICATION_DATABASE_DSN",
                "presentation_timezone": "UTC",
            }), encoding="utf-8")
            module_source = root / "r3a_runtime" / "observer_module.py"
            module = {"module_id": "foundation.observer", "version": "1.0.0",
                      "contract_id": "r3a.resident-module", "protocol_major": 1,
                      "protocol_minor": 0, "capabilities": ["notification.delivery.read"],
                      "owner": "R3A", "entrypoint": "r3a_runtime.observer_module",
                      "source": str(module_source),
                      "sha256": hashlib.sha256(module_source.read_bytes()).hexdigest()}
            config = {
                "schema_version": 1, "instance_id": "r3a_notification_fixture",
                "paths": {"data_dir": str(data_dir), "postgres_socket_dir": str(data_dir / "pg"),
                          "control_socket": str(data_dir / "control.sock"),
                          "diagnostics_socket": str(data_dir / "diagnostics.sock"),
                          "module_socket": str(data_dir / "module.sock"),
                          "machine_catalog_dir": str(temporary_root / "catalog")},
                "postgres": {"database": "r3a_notification_fixture", "user": "r3a_runtime",
                             "socket_dir": str(data_dir / "pg"), "port": 55432},
                "module": module,
                "timing": {"observer_interval_seconds": 1, "scheduler_interval_seconds": 1,
                           "lease_seconds": 30, "heartbeat_interval_seconds": 5,
                           "heartbeat_stale_after_seconds": 15, "diagnostic_stale_after_seconds": 30,
                           "restart_initial_seconds": 1, "restart_max_seconds": 5,
                           "worker_concurrency": 1},
                "capability_operations": [{
                    "manifest": str(staged_root / "r3a_plugins" / "notification_service" / "manifest.read.json"),
                    "configuration": str(operation_config),
                }],
            }
            bootstrap = temporary_root / "bootstrap.json"
            bootstrap.write_text(json.dumps(config), encoding="utf-8")
            settings = load_settings(bootstrap)
            registered = settings.capability_registry.resolve("notification.delivery.read", "1.0.0")
            self.assertEqual(["notification.delivery.read"],
                             registered.descriptor["required_grants"])
            self.assertEqual("R3A_NOTIFICATION_DATABASE_DSN", registered.configuration["dsn_env"])

    def test_current_steward_write_contract_requires_static_exact_principals(self):
        root = Path(__file__).resolve().parents[1]
        manifest = json.loads((root / "r3a_plugins" / "notification_service"
                               / "manifest.read.json").read_text(encoding="utf-8"))
        write = copy.deepcopy(manifest["operation"])
        write.update({"contract_version": "1.1.0",
                      "operation_id": "notification.delivery.acknowledge",
                      "operation_revision": "1.0.0", "effect_class": "steward_write"})
        write["required_grants"] = ["notification.delivery.acknowledge"]
        write["recovery"]["idempotency_required"] = True
        write["input_schema"] = {
            "type": "object", "required": ["delivery_id", "idempotency_key", "note"],
            "additionalProperties": False,
            "properties": {"delivery_id": {"type": "string"},
                           "idempotency_key": {"type": "string", "minLength": 8},
                           "note": {"type": ["string", "null"]}},
        }
        with self.assertRaisesRegex(CapabilityContractError, "explicit Steward principals"):
            validate_operation(write)

        write["caller_constraints"]["allowed_principals"] = ["steward:approved-fixture"]
        validated = validate_operation(write)
        invocation = {
            "contract_id": "r3a.capability-invocation.v1", "contract_version": "1.1.0",
            "invocation_id": "notification-ack-1", "operation_id": write["operation_id"],
            "operation_contract_version": "1.1.0",
            "caller": {"principal_id": "steward:approved-fixture", "resident_id": None,
                       "service_id": None},
            "target": {}, "input": {"delivery_id": "00000000-0000-4000-8000-000000000001",
                                     "idempotency_key": "ack-fixture-0001", "note": None},
            "activity_id": None, "attempt_id": None,
            "correlation_id": "00000000-0000-4000-8000-000000000002", "work_order": None,
            "budget_reservation": None, "evidence_purpose": "test notification acknowledgment",
            "idempotency_key": "ack-fixture-0001", "deadline": None, "config_revision": "fixture-rev",
        }
        validate_invocation_request(invocation, validated)
        invocation["caller"]["principal_id"] = "steward:unlisted-fixture"
        with self.assertRaisesRegex(CapabilityContractError, "outside allowed_principals"):
            validate_invocation_request(invocation, validated)

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
