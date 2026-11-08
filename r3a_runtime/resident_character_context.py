"""
R3 CONTROLLED SOURCE
File: r3a_runtime/resident_character_context.py
Component: R3A-RESIDENT-CHARACTER-CONTEXT-CONSUMER
File Revision: 1.0.1
Created: 2026-11-08T15:30:31Z
Created By: Codex GPT-6
Purpose: Validate the governed, approved character-context envelope before resident inference.
Execution Model: Synchronous contract validation inside the existing Grace module execution.
Observability: Returns only pinned revision and digest metadata; never emits prompt text or personality values.
Dependencies: Python standard library; R3A runtime-character-context v1 contract from Issue #56.
Authority: Jessica final architectural approval recorded in GitHub Issue #56; upstream governed provider remains responsible for identity authorization and confidentiality filtering.
Changed: 2026-11-08T15:30:31Z | R3A-CHARACTER-CONTEXT-CONSUMER | Codex GPT-6 | Add a strict, privacy-aware consumer for the approved v1 context envelope.
Changed: 2026-11-08T15:37:17Z | R3A-CHARACTER-CONTEXT-CONSUMER | Codex GPT-6 | Pin only character identity/canon fields while allowing authorization observations to refresh.
Supersedes: None.
Contracts: r3a.resident.runtime-character-context@1.0.0; runtime-character-context.v1.schema.json on the Character Architecture branch.
Tests: tests/test_r3a_ap1.py.
History/Predecessor: New file; contract source is commit a987a5caa8e6ffb41ccd7d31ca5a0193b36b90d4 on engineering/r3a-character-architecture-20261107.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any


CONTRACT_ID = "r3a.resident.runtime-character-context"
CONTRACT_VERSION = "1.0.0"
_CLASSIFICATIONS = {"public", "institutional"}
_PERSONALITY_DIMENSIONS = {
    "warmth", "humor", "formality", "assertiveness", "curiosity", "spontaneity",
    "empathy", "expressiveness", "professional_directness",
}


def validate_resident_character_context(value: Any, *, directory_resident_id: str) -> dict[str, Any]:
    """Validate the provider-issued context envelope against the bound runtime resident.

    The upstream governed HR adapter must authenticate the caller, verify the HR/directory
    crosswalk, select the approved active dossier revision, and filter classifications before
    issuing this bundle. This consumer rejects malformed or mismatched bundles; it does not
    establish HR authority itself.
    """
    fields = {
        "contract_id", "contract_version", "resident_id", "directory_resident_id",
        "identity_binding_status", "identity_revision", "dossier_revision", "approval_status",
        "classification_scope", "authorization_ref", "prompt_text", "prompt_sha256",
        "prompt_component_refs", "source_refs", "personality", "personality_sources",
        "provider_id", "authority_granted",
    }
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError("resident character context contract fields are invalid")
    if value["contract_id"] != CONTRACT_ID or value["contract_version"] != CONTRACT_VERSION:
        raise ValueError("resident character context contract is incompatible")
    if value["directory_resident_id"] != directory_resident_id or \
            value["identity_binding_status"] != "authoritative":
        raise ValueError("resident character context identity binding is not authoritative")
    if value["approval_status"] != "active" or value["authority_granted"] is not False:
        raise ValueError("only approved active authority-free character context may reach inference")
    for field in ("resident_id", "identity_revision", "dossier_revision", "authorization_ref", "provider_id"):
        if not isinstance(value[field], str) or not value[field].strip():
            raise ValueError(f"resident character context {field} is required")
    if re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", value["dossier_revision"]) is None:
        raise ValueError("resident character context dossier revision must be semantic version")
    scope = value["classification_scope"]
    if (not isinstance(scope, list) or not scope or any(not isinstance(item, str) for item in scope)
            or len(scope) != len(set(scope))
            or set(scope) - _CLASSIFICATIONS):
        raise ValueError("resident character context includes an unapproved confidentiality scope")
    text = value["prompt_text"]
    if not isinstance(text, str) or not text.strip():
        raise ValueError("resident character context prompt is empty")
    digest = value["prompt_sha256"]
    if (not isinstance(digest, str) or re.fullmatch(r"[a-f0-9]{64}", digest) is None
            or hashlib.sha256(text.encode("utf-8")).hexdigest() != digest):
        raise ValueError("resident character context digest mismatch")
    sources = value["source_refs"]
    if not isinstance(sources, list) or not sources or any(not isinstance(ref, str) or not ref.strip()
                                                          for ref in sources):
        raise ValueError("resident character context requires source provenance")
    components = value["prompt_component_refs"]
    if (not isinstance(components, list) or any(
            not isinstance(ref, list) or len(ref) != 2 or
            any(not isinstance(part, str) or not part.strip() for part in ref)
            for ref in components)):
        raise ValueError("resident character context component provenance is invalid")
    personality = value["personality"]
    if (not isinstance(personality, dict) or set(personality) != _PERSONALITY_DIMENSIONS
            or any(not isinstance(score, int) or isinstance(score, bool) or not 0 <= score <= 100
                   for score in personality.values())):
        raise ValueError("resident character context personality settings are invalid")
    if (not isinstance(value["personality_sources"], dict) or any(
            not isinstance(key, str) or not isinstance(ref, str) or not ref.strip()
            for key, ref in value["personality_sources"].items())):
        raise ValueError("resident character context personality provenance is invalid")
    return json.loads(json.dumps(value))


def character_context_binding(value: dict[str, Any]) -> dict[str, Any]:
    """Return durable provenance metadata without exposing character content or source labels."""
    return {
        "contract_id": CONTRACT_ID,
        "contract_version": CONTRACT_VERSION,
        "resident_id": value["resident_id"],
        "directory_resident_id": value["directory_resident_id"],
        "identity_revision": value["identity_revision"],
        "dossier_revision": value["dossier_revision"],
        "approval_status": value["approval_status"],
        "classification_scope": list(value["classification_scope"]),
        "prompt_sha256": value["prompt_sha256"],
        "source_refs": list(value["source_refs"]),
        "authorization_ref": value["authorization_ref"],
        "provider_id": value["provider_id"],
    }


def require_character_context_pin(binding: dict[str, Any] | None, reasoning_state: Any) -> None:
    """Fail closed if a resumed activity changes or drops its previously used character revision."""
    if not isinstance(reasoning_state, dict):
        return
    turns = reasoning_state.get("model_turns", [])
    if not isinstance(turns, list):
        raise ValueError("persisted reasoning model turns are malformed")
    prior = []
    for turn in turns:
        usage = turn.get("usage") if isinstance(turn, dict) else None
        if isinstance(usage, dict) and "resident_character_context" in usage:
            pin = usage["resident_character_context"]
            if pin is not None and not isinstance(pin, dict):
                raise ValueError("persisted resident character context pin is malformed")
            prior.append(_character_pin(pin))
    if not prior:
        return
    expected = prior[0]
    if any(pin != expected for pin in prior[1:]):
        raise ValueError("persisted activity contains conflicting resident character context revisions")
    if binding is None:
        observed = None
    else:
        observed = _character_pin(binding)
    if observed != expected:
        raise ValueError("resumed activity character context differs from its pinned revision")


def _character_pin(value: dict[str, Any] | None) -> dict[str, Any] | None:
    """Exclude renewable authorization observations while pinning identity and canon exactly."""
    if value is None:
        return None
    keys = ("contract_id", "contract_version", "resident_id", "directory_resident_id",
            "identity_revision", "dossier_revision", "approval_status", "classification_scope",
            "prompt_sha256", "source_refs")
    expected_fields = set(keys) | {"authorization_ref", "provider_id"}
    if not isinstance(value, dict) or set(value) != expected_fields:
        raise ValueError("persisted resident character context pin fields are invalid")
    return {key: value[key] for key in keys}
