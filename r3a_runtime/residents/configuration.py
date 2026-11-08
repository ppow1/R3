"""Validated personality override resolution and provider-neutral runtime binding."""

# R3 CONTROLLED SOURCE
# File: r3a_runtime/residents/configuration.py
# Component: R3A-RESIDENT-DOSSIERS
# File Revision: 1.0.0
# Created: 2026-11-08 UTC (exact creation time not captured)
# Created By: Codex GPT-6
# Purpose: Resolve validated personality settings and preserve identity across provider replacement.
# Execution Model: Pure configuration projection; no provider invocation or authorization.
# Observability: Returns the winning setting scope and unchanged continuity references.
# Dependencies: Python standard library; global-config.v1.json and resident dossier v1.
# Authority: Only approved overrides are applied; model/provider configuration does not own identity.
# Changed: 2026-11-08 UTC | CHARACTER-ARCHITECTURE | Codex GPT-6 | Add override and provider binding resolution.
# Supersedes: None
# Contracts: r3a.resident.dossier.v1; r3a.resident.runtime-binding.v1
# Tests: tests/test_r3a_resident_dossiers.py
# History/Predecessor: New file.

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .validation import DIMENSIONS, DossierValidationError


def resolve_personality(defaults: dict[str, int], resident_settings: dict[str, int],
                        overrides: list[dict[str, Any]], *,
                        resident_id: str | None = None) -> tuple[dict[str, int], dict[str, str]]:
    """Apply institution defaults, resident values, then active approved scoped overrides."""
    for label, values in (("defaults", defaults), ("resident", resident_settings)):
        if set(values) != DIMENSIONS:
            raise DossierValidationError(f"{label} personality must define every supported dimension")
        for key, value in values.items():
            if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 100:
                raise DossierValidationError(f"{label}.{key} must be an integer from 0 through 100")
    result = dict(defaults)
    source = {key: "institution_default" for key in DIMENSIONS}
    for key, value in resident_settings.items():
        result[key], source[key] = value, "resident"
    allowed = {"resident", "approved_experiment"}
    active = []
    for position, override in enumerate(overrides):
        if override.get("status") != "approved" or not override.get("active", True):
            continue
        scope, dimension, value = override.get("scope"), override.get("dimension"), override.get("value")
        if scope not in allowed or dimension not in DIMENSIONS:
            raise DossierValidationError("override scope or dimension is not permitted")
        if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 100:
            raise DossierValidationError("override value must be an integer from 0 through 100")
        if scope == "resident" and (resident_id is None or override.get("scope_ref") != resident_id):
            raise DossierValidationError("resident override must target the exact dossier resident ID")
        active.append((0 if scope == "resident" else 1, position, dimension, value, scope))
    for _, _, dimension, value, scope in sorted(active):
        result[dimension], source[dimension] = value, scope
    return result, source


def runtime_binding(dossier: dict[str, Any], provider_id: str, *,
                    configuration_revision: str) -> dict[str, Any]:
    """Attach a provider while keeping dossier identity and continuity external to it."""
    identity = dossier["identity"]
    return {
        "contract_id": "r3a.resident.runtime-binding",
        "contract_version": "1.0.0",
        "resident_id": identity["resident_id"],
        "identity_status": identity["identity_status"],
        "provider_id": provider_id,
        "configuration_revision": configuration_revision,
        "continuity_state_ref": deepcopy(dossier["implementation"].get("continuity_state_ref")),
        "identity_binding_authority": dossier["implementation"]["identity_binding_authority"],
        "authority_ref": None,
        "capabilities": [],
    }
