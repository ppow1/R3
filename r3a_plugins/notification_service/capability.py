# R3 CONTROLLED SOURCE
# File: r3a_plugins/notification_service/capability.py
# Component: R3A-NOTIFICATION-CAPABILITY
# File Revision: 1.0.0
# Created: 2026-11-10
# Created By: Codex GPT-6
# Purpose: Bind authenticated CME capability invocations to the notification-owned store.
# Execution Model: Digest-pinned CME provider process.
# Observability: CME invocation audit plus module-owned durable lifecycle event.
# Dependencies: r3a.notification-inbox.v1; CME capability invocation; NotificationStore.
# Authority: Issue #48; published notification delivery grants and store ownership.
# Changed: 2026-11-10 | AP3 notifications integration | Use CME-derived caller and grant decision for recipient-scoped inbox/actions.
# Supersedes: Website fixed-principal/configured-gateway boundary.
# Contracts: r3a.capability-provider.v1; notification.delivery.read/acknowledge/resolve.
# Tests: tests/test_r3a_notification_capability.py.
# History/Predecessor: notification_service.store.
"""CME registered provider for the existing notification-owned persistence layer."""
from __future__ import annotations

import os
from typing import Any

from r3a_runtime.capability_contracts import CapabilityProviderResult
from .store import NotificationStore


class NotificationDeliveryProvider:
    def __init__(self, configuration: dict[str, Any]):
        env_name = configuration.get("dsn_env")
        if not isinstance(env_name, str) or not env_name:
            raise ValueError("notification capability requires configured DSN environment name")
        dsn = os.environ.get(env_name)
        if not dsn:
            raise ValueError("notification capability database is unavailable")
        self.store = NotificationStore(dsn)
        self.presentation_timezone = configuration.get("presentation_timezone", "UTC")

    def invoke(self, arguments: dict[str, Any], *, context: dict[str, Any]) -> CapabilityProviderResult:
        operation = context.get("operation_id")
        caller = context.get("caller")
        authorization = context.get("authorization")
        if not isinstance(caller, dict) or not isinstance(caller.get("principal_id"), str):
            raise PermissionError("CME authenticated caller is required")
        principal = caller["principal_id"]
        if not isinstance(authorization, dict) or authorization.get("allowed") is not True:
            raise PermissionError("CME authorization decision is required")
        authorization_ref = {**authorization, "actor_id": principal}
        if operation == "notification.delivery.read":
            result = self.store.inbox(principal, cursor=arguments.get("cursor"),
                                      limit=arguments.get("limit", 50))
            result["presentation_timezone"] = self.presentation_timezone
        elif operation == "notification.delivery.acknowledge":
            result = self.store.acknowledge(
                arguments["delivery_id"], principal, arguments["idempotency_key"],
                authorization_ref, arguments.get("note"))
        elif operation == "notification.delivery.resolve":
            result = self.store.resolve(
                arguments["delivery_id"], principal, arguments["idempotency_key"],
                arguments["disposition"], arguments["evidence_refs"], authorization_ref)
        else:
            raise ValueError("unsupported notification delivery operation")
        return CapabilityProviderResult(output=result, evidence={
            "principal_id": principal,
            "authorization_decision_id": authorization["decision_id"],
            "authorization_audit_event_id": authorization["audit_event_id"],
            "operation_id": operation,
            "delivery_id": arguments.get("delivery_id"),
        })


def create_provider(configuration: dict[str, Any]) -> NotificationDeliveryProvider:
    return NotificationDeliveryProvider(configuration)
