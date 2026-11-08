"""Test-only replacement implementation for the Engineering provider lifecycle test."""
from __future__ import annotations

from typing import Any

from .isolated_workspace import IsolatedWorkspaceProvider


class ReplacementProvider(IsolatedWorkspaceProvider):
    """Distinct implementation used to prove artifact replacement, not just version labels."""

    def invoke(self, arguments: dict[str, Any], *, context: dict[str, Any]) -> dict[str, Any]:
        replaced = dict(arguments)
        replaced["content"] = "replacement-provider: " + arguments["content"]
        return super().invoke(replaced, context=context)


def create_provider(configuration: dict[str, Any]) -> ReplacementProvider:
    return ReplacementProvider(configuration)
