"""
R3 CONTROLLED SOURCE
File: r3a_runtime/resident_character_context.py
Component: R3A-RESIDENT-CHARACTER-CONTEXT-CONSUMER
File Revision: 1.0.5
Created: 2026-11-08T15:30:31Z
Created By: Codex GPT-6
Purpose: Validate the governed, approved character-context envelope before resident inference.
Execution Model: Synchronous contract validation inside the existing Grace module execution.
Observability: Returns only pinned revision and digest metadata; never emits prompt text or personality values.
Dependencies: Python standard library; R3A approved-character-context v2 contract from Character Architecture commit 477cb995d58a289c3e8be278a1404fa4747eb34b.
Authority: Jessica final architectural approval recorded in GitHub Issue #56; upstream governed provider remains responsible for identity authorization and confidentiality filtering.
Changed: 2026-11-08T15:30:31Z | R3A-CHARACTER-CONTEXT-CONSUMER | Codex GPT-6 | Add a strict, privacy-aware consumer for the approved v1 context envelope.
Changed: 2026-11-08T15:37:17Z | R3A-CHARACTER-CONTEXT-CONSUMER | Codex GPT-6 | Pin only character identity/canon fields while allowing authorization observations to refresh.
Changed: 2026-11-08T17:31:16Z | R3A-CHARACTER-CONTEXT-V2 | Codex GPT-6 | Align with approved-character-context v2 immutable boundary pins and metadata-only diagnostic projection.
Changed: 2026-11-08T17:33:14Z | R3A-CHARACTER-CONTEXT-V2 | Codex GPT-6 | Validate both approved inference and conversation boundary pins through the same consumer contract.
Changed: 2026-11-08T17:34:06Z | R3A-CHARACTER-CONTEXT-V2 | Codex GPT-6 | Record the immediate predecessor and the canonical v2 schema source.
Supersedes: None.
Contracts: r3a.resident.approved-character-context@2.0.0; approved-character-context.v2.schema.json on the Character Architecture branch.
Tests: tests/test_r3a_ap1.py.
History/Predecessor: Prior consumer preserved at commit 6c4f4e6d5b7f3f5c55b37fe34b0cf09b1fe47d65, blob cbd95b809e0823c3e5276c8c3c8d180995417d0c; contract schema from Character Architecture commit 477cb995d58a289c3e8be278a1404fa4747eb34b.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any


CONTRACT_ID = "r3a.resident.approved-character-context"
CONTRACT_VERSION = "2.0.0"
_CLASSIFICATIONS = {"public", "institutional"}
_PERSONALITY_DIMENSIONS = {
    "warmth", "humor", "formality", "assertiveness", "curiosity", "spontaneity",
    "empathy", "expressiveness", "professional_directness",
}


def validate_resident_character_context(value: Any, *, execution_ref: str,
                                       execution_kind: str = "inference_activity",
                                       directory_resident_id: str | None = None) -> dict[str, Any]:
    """Validate the provider-issued context envelope against the bound runtime resident.

    The upstream governed HR adapter must authenticate the caller, verify the HR/directory
    crosswalk, select the approved active dossier revision, and filter classifications before
    issuing this bundle. This consumer rejects malformed or mismatched bundles; it does not
    establish HR authority itself.
    """
    fields = {
        "contract_id", "contract_version", "resident_id", "directory_resident_id",
        "identity_revision", "directory_binding_revision", "directory_snapshot_sha256",
        "directory_source_ref", "hr_source_ref", "hr_principal_association_ref", "office_id",
        "office_role", "execution_kind", "execution_ref", "pin_ref", "provider_id",
        "dossier_revision", "dossier_sha256", "context_sha256", "activation_status",
        "classification_scope", "authorization_ref", "prompt_text", "prompt_sha256",
        "prompt_component_refs", "source_refs", "personality", "personality_sources",
        "authority_granted",
    }
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError("resident character context contract fields are invalid")
    if value["contract_id"] != CONTRACT_ID or value["contract_version"] != CONTRACT_VERSION:
        raise ValueError("resident character context contract is incompatible")
    if (not isinstance(value["resident_id"], str) or not value["resident_id"].startswith("r3:")
            or not isinstance(value["directory_resident_id"], str)
            or not value["directory_resident_id"].startswith("resident:")):
        raise ValueError("approved character context lacks canonical HR and directory identities")
    if directory_resident_id is not None and value["directory_resident_id"] != directory_resident_id:
        raise ValueError("approved character context directory identity does not match the resident profile")
    if (execution_kind not in {"inference_activity", "conversation_boundary"}
            or value["execution_kind"] != execution_kind or value["execution_ref"] != execution_ref):
        raise ValueError("approved character context is not pinned to this execution boundary")
    if value["activation_status"] != "active" or value["authority_granted"] is not False:
        raise ValueError("only approved active authority-free character context may reach inference")
    for field in ("resident_id", "directory_resident_id", "identity_revision", "dossier_revision",
                  "authorization_ref", "provider_id", "execution_ref", "pin_ref", "directory_source_ref",
                  "hr_source_ref", "hr_principal_association_ref", "office_id", "office_role"):
        if not isinstance(value[field], str) or not value[field].strip():
            raise ValueError(f"resident character context {field} is required")
    if type(value["directory_binding_revision"]) is not int or value["directory_binding_revision"] < 1:
        raise ValueError("approved character context directory binding revision is invalid")
    if re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", value["dossier_revision"]) is None:
        raise ValueError("resident character context dossier revision must be semantic version")
    for field in ("directory_snapshot_sha256", "dossier_sha256", "context_sha256"):
        if not isinstance(value[field], str) or re.fullmatch(r"[a-f0-9]{64}", value[field]) is None:
            raise ValueError(f"resident character context {field} is invalid")
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
    composed = {"prompt_text": text, "personality": personality,
                "prompt_component_refs": value["prompt_component_refs"],
                "source_refs": sources, "personality_sources": value["personality_sources"]}
    context_digest = hashlib.sha256(json.dumps(
        composed, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()
    if context_digest != value["context_sha256"]:
        raise ValueError("resident character context content digest mismatch")
    return json.loads(json.dumps(value))


def character_context_binding(value: dict[str, Any]) -> dict[str, Any]:
    """Return durable provenance metadata without exposing character content or source labels."""
    return {
        "contract_id": CONTRACT_ID,
        "contract_version": CONTRACT_VERSION,
        "resident_id": value["resident_id"],
        "directory_resident_id": value["directory_resident_id"],
        "identity_revision": value["identity_revision"],
        "directory_binding_revision": value["directory_binding_revision"],
        "directory_snapshot_sha256": value["directory_snapshot_sha256"],
        "dossier_revision": value["dossier_revision"],
        "dossier_sha256": value["dossier_sha256"],
        "context_sha256": value["context_sha256"],
        "pin_ref": value["pin_ref"],
        "execution_kind": value["execution_kind"],
        "classification_scope": list(value["classification_scope"]),
        "prompt_sha256": value["prompt_sha256"],
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
            "identity_revision", "directory_binding_revision", "directory_snapshot_sha256",
            "dossier_revision", "dossier_sha256", "context_sha256", "pin_ref", "execution_kind",
            "classification_scope", "prompt_sha256", "provider_id")
    expected_fields = set(keys)
    if not isinstance(value, dict) or set(value) != expected_fields:
        raise ValueError("persisted resident character context pin fields are invalid")
    return {key: value[key] for key in keys}
