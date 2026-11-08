"""Test-only wrapper used to prove live provider-version replacement.

This keeps the production telemetry implementation in charge of collection and
adds a response marker so an isolated acceptance run can distinguish the new
provider artifact from the previous version. Do not use as a production build.
"""
from __future__ import annotations

from typing import Any

from .plugin import create_provider as create_telemetry_provider


class ReplacementTelemetryProvider:
    def __init__(self, configuration: dict[str, Any]):
        self.provider = create_telemetry_provider(configuration)

    def invoke(self, arguments: dict[str, Any], *, context: dict[str, Any]) -> list[dict[str, Any]]:
        samples = self.provider.invoke(arguments, context=context)
        return [{**sample, "provider_revision": "2.0.1-live-acceptance-fixture"}
                for sample in samples]


def create_provider(configuration: dict[str, Any]) -> ReplacementTelemetryProvider:
    return ReplacementTelemetryProvider(configuration)
