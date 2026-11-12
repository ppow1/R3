"""Coordinator-side integration hook for approved character context v2.

This is deliberately not a CME capability operation: prompt-bearing output must
not enter generic durable invocation output, replay, or diagnostics. The Coordinator
constructs ``CoordinatorExecutionBoundary`` only after its server-side authentication
and execution-profile resolution, then supplies it to this in-process hook.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import hashlib
from pathlib import Path
from typing import Any, Callable

from .approved_context import ApprovedCharacterContextProvider, project_context_for_sink
from .governance import GovernedActor
from ..capability_contracts import validate_json, validate_schema_definition


_PACKAGE_ROOT = Path(__file__).parent
_PACKAGE_SCHEMA = _PACKAGE_ROOT.parent / "schemas" / "resident-character-package.v1.schema.json"
_PACKAGE_MANIFEST = _PACKAGE_ROOT / "coordinator-character-package.v1.json"


def load_coordinator_package_manifest(path: Path = _PACKAGE_MANIFEST) -> dict[str, Any]:
    """Load and validate the data-driven package contract before host integration."""
    schema = json.loads(_PACKAGE_SCHEMA.read_text(encoding="utf-8"))
    manifest = json.loads(path.read_text(encoding="utf-8"))
    validate_schema_definition(schema)
    validate_json(manifest, schema)
    root = _PACKAGE_ROOT.parents[1]
    for artifact in manifest["artifacts"]:
        artifact_path = (root / artifact["path"]).resolve()
        if root.resolve() not in artifact_path.parents:
            raise ValueError("package artifact path escapes the source root")
        digest = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
        if digest != artifact["sha256"]:
            raise ValueError(f"package artifact digest mismatch: {artifact['path']}")
    return manifest


@dataclass(frozen=True)
class CoordinatorExecutionBoundary:
    """Authenticated execution facts injected by Coordinator, never message fields."""

    actor: GovernedActor
    resident_id: str
    execution_kind: str
    execution_ref: str
    provider_id: str
    sink_principal_ref: str

    def __post_init__(self) -> None:
        if not isinstance(self.actor, GovernedActor):
            raise TypeError("Coordinator must inject its server-authenticated actor")
        for name in ("resident_id", "execution_ref", "provider_id", "sink_principal_ref"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Coordinator execution boundary requires {name}")
        if self.execution_kind not in {"inference_activity", "conversation_boundary"}:
            raise ValueError("unsupported Coordinator execution boundary")


class CoordinatorCharacterContextHook:
    """Resolve and privacy-project context before it enters a named host sink."""

    def __init__(self, provider: ApprovedCharacterContextProvider, *,
                 authorize_sink: Callable[[CoordinatorExecutionBoundary, str, str], Any],
                 audit: Callable[[dict[str, Any]], None]):
        if not isinstance(provider, ApprovedCharacterContextProvider):
            raise TypeError("approved context v2 provider is required")
        if not callable(authorize_sink) or not callable(audit):
            raise TypeError("server-side sink authorizer and content-free audit sink are required")
        self._provider = provider
        self._authorize_sink = authorize_sink
        self._audit = audit

    def project(self, boundary: CoordinatorExecutionBoundary, *, sink: str) -> dict[str, Any]:
        if not isinstance(boundary, CoordinatorExecutionBoundary):
            raise TypeError("Coordinator authenticated execution boundary is required")
        context = self._provider.retrieve(
            boundary.actor,
            resident_id=boundary.resident_id,
            execution_kind=boundary.execution_kind,
            execution_ref=boundary.execution_ref,
            provider_id=boundary.provider_id,
        )
        sink_scope = self._authorize_sink(boundary, sink, boundary.resident_id)
        if not isinstance(sink_scope, (set, frozenset, tuple, list)):
            raise PermissionError("Coordinator sink authorization was not granted")
        return project_context_for_sink(
            context,
            sink=sink,
            authorized_classifications=frozenset(sink_scope),
            principal_ref=boundary.sink_principal_ref,
            audit=self._audit,
        )
