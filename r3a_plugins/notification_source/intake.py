"""Notification-module adapter from N1 source data to generic CME activity intake."""
from __future__ import annotations

from typing import Any

from r3a_runtime.capability_contracts import CapabilityProviderResult
from .plugin import create_provider as create_source_provider, to_activity_intake


_LIFECYCLE = {
    "received": "grace.notification.received",
    "actionable": "grace.notification.actionable",
    "acknowledged": "grace.notification.acknowledged",
    "resolved": "grace.notification.resolved",
    "blocked": "grace.notification.blocked",
}


class NotificationActivityIntakeProvider:
    """Read one event through the configured source adapter and project generic intake."""

    def __init__(self, configuration: dict[str, Any]):
        self.configuration = dict(configuration)
        self.source = create_source_provider(configuration)

    def invoke(self, arguments: dict[str, Any], *, context: dict[str, Any]) -> CapabilityProviderResult:
        source_result = self.source.invoke(arguments, context=context)
        provider = context.get("provider")
        if not isinstance(provider, dict):
            raise ValueError("CME provider provenance is required for activity intake")
        envelope = to_activity_intake(
            source_result.output,
            source_result.evidence,
            provider={key: provider[key] for key in
                      ("provider_id", "provider_version", "artifact_sha256")},
            configuration_revision=str(context.get("config_revision", "")),
            lifecycle_projection=_LIFECYCLE,
        )
        return CapabilityProviderResult(output=envelope, evidence=source_result.evidence)


def create_provider(configuration: dict[str, Any]) -> NotificationActivityIntakeProvider:
    return NotificationActivityIntakeProvider(configuration)
