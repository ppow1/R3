"""Test-only replacement implementation for the provider lifecycle regression."""
from __future__ import annotations

from typing import Any

from .provider import IsolatedWorkspaceProvider


class ReplacementProvider(IsolatedWorkspaceProvider):
    """Distinct provider artifact used to verify immutable implementation replacement."""

    def invoke(self, arguments: dict[str, Any], *, context: dict[str, Any]) -> dict[str, Any]:
        replaced = dict(arguments)
        replaced["content"] = "replacement-provider: " + arguments["content"]
        return super().invoke(replaced, context=context)


def create_provider(configuration: dict[str, Any]) -> ReplacementProvider:
    return ReplacementProvider(configuration)
