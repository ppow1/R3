"""Behavior-compatible second artifact for isolated module replacement tests."""
from __future__ import annotations

from typing import Any

from r3a_runtime.providers.isolated_workspace import IsolatedWorkspaceProvider


class ReplacementWorkspaceProvider(IsolatedWorkspaceProvider):
    """Distinct, immutable provider artifact preserving the v1 contract behavior."""

    def invoke(self, arguments: dict[str, Any], *, context: dict[str, Any]) -> dict[str, Any]:
        return super().invoke(arguments, context=context)


def create_provider(configuration: dict[str, Any]) -> ReplacementWorkspaceProvider:
    return ReplacementWorkspaceProvider(configuration)
