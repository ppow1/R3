"""Authorization-first adapter contract for operational resident context loading."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Callable

from .configuration import resolve_personality
from .prompts import compose_prompt
from .validation import DIMENSIONS
from ..resident_identity import resident_principal_id


@dataclass(frozen=True)
class RuntimePrincipal:
    principal_id: str
    purpose: str
    allowed_classifications: frozenset[str]
    authorization_ref: str


def load_runtime_context(*, institutional_id: str, principal: RuntimePrincipal,
                         resolve_identity: Callable[[str], dict[str, Any]],
                         load_dossier: Callable[[str], dict[str, Any]],
                         defaults: dict[str, int], overrides: list[dict[str, Any]],
                         provider_id: str) -> dict[str, Any]:
    """Resolve canonical HR ID first, then apply only activated and permitted dossier material."""
    identity = resolve_identity(institutional_id)
    canonical_id = identity.get("institutional_id")
    if (not canonical_id or identity.get("status") != "authoritative"
            or not identity.get("revision") or not identity.get("directory_resident_id")):
        raise PermissionError("authoritative HR identity and verified runtime crosswalk are required")
    try:
        resident_principal_id(identity.get("directory_resident_id"))
        if principal.principal_id.startswith("resident."):
            resident_principal_id(principal.principal_id)
    except (AttributeError, ValueError) as exc:
        raise PermissionError("directory and authenticated resident identity must use canonical principal IDs") from exc
    if not principal.principal_id or not principal.authorization_ref:
        raise PermissionError("authenticated principal and HR authorization reference are required")
    dossier = load_dossier(canonical_id)
    if dossier["identity"]["resident_id"] != canonical_id:
        raise ValueError("dossier identity does not match authoritative HR identity")
    if dossier["governance"].get("approval_status") != "active":
        raise PermissionError("character dossier must be published and activated before inference")
    effective_classifications = sorted(set(principal.allowed_classifications) & {"public", "institutional"})
    safe = {**dossier, "prompt_components": [component for component in dossier["prompt_components"]
            if component["classification"] in effective_classifications]}
    prompt = compose_prompt(safe, provider_id=provider_id)
    if not prompt.source_refs:
        raise PermissionError("activated prompt context has no source provenance")
    settings, setting_sources = resolve_personality(
        defaults, dossier["personality"]["settings"], dossier["personality"].get("overrides", []),
        resident_id=canonical_id)
    return {"resident_id": canonical_id, "identity_revision": str(identity.get("revision")),
            "dossier_revision": dossier["revision"], "provider_id": provider_id,
            "contract_id": "r3a.resident.runtime-character-context",
            "contract_version": "1.0.0",
            "directory_resident_id": identity.get("directory_resident_id"),
            "identity_binding_status": "authoritative",
            "approval_status": dossier["governance"]["approval_status"],
            "classification_scope": effective_classifications,
            "authorization_ref": principal.authorization_ref,
            "prompt_text": prompt.text, "prompt_sha256": prompt.sha256,
            "prompt_component_refs": [list(reference) for reference in prompt.component_refs], "personality": settings,
            "source_refs": list(prompt.source_refs),
            "personality_sources": setting_sources, "authority_granted": False}


def validate_runtime_character_context(bundle: Any, *, directory_resident_id: str) -> dict[str, Any]:
    """Validate a pre-authorized HR projection before its use in resident inference.

    The capability gateway must authenticate the principal, resolve HR identity,
    and enforce per-component access before creating this envelope. This check
    prevents stale, mismatched, unapproved, or over-classified envelopes from
    being applied by the inference module.
    """
    required = {"contract_id", "contract_version", "resident_id", "directory_resident_id",
                "identity_binding_status", "identity_revision", "dossier_revision", "approval_status",
                "classification_scope", "authorization_ref", "prompt_text", "prompt_sha256",
                "prompt_component_refs", "source_refs", "personality", "personality_sources",
                "provider_id", "authority_granted"}
    if not isinstance(bundle, dict) or set(bundle) != required:
        raise ValueError("resident character context contract fields are invalid")
    if bundle["contract_id"] != "r3a.resident.runtime-character-context" or bundle["contract_version"] != "1.0.0":
        raise ValueError("resident character context contract is incompatible")
    if bundle["directory_resident_id"] != directory_resident_id or bundle["identity_binding_status"] != "authoritative":
        raise ValueError("resident character context identity binding is not authoritative")
    try:
        resident_principal_id(directory_resident_id)
        resident_principal_id(bundle["directory_resident_id"])
    except ValueError as exc:
        raise ValueError("directory resident identity must be a canonical principal") from exc
    if bundle["approval_status"] != "active" or bundle["authority_granted"] is not False:
        raise ValueError("inactive character context or authority-bearing context is forbidden")
    if not all(isinstance(bundle[key], str) and bundle[key] for key in
               ("resident_id", "identity_revision", "dossier_revision", "authorization_ref", "provider_id")):
        raise ValueError("resident character context identity, revisions, and authorization ref are required")
    text = bundle["prompt_text"]
    if not isinstance(text, str) or hashlib.sha256(text.encode()).hexdigest() != bundle["prompt_sha256"]:
        raise ValueError("resident character context digest mismatch")
    if not isinstance(bundle["classification_scope"], list) or set(bundle["classification_scope"]) - {"public", "institutional"}:
        raise ValueError("runtime character context contains disallowed classifications")
    if not isinstance(bundle["source_refs"], list) or not bundle["source_refs"]:
        raise ValueError("resident character context requires provenance")
    if not isinstance(bundle["prompt_component_refs"], (list, tuple)):
        raise ValueError("resident character context component references are invalid")
    personality = bundle["personality"]
    if not isinstance(personality, dict) or set(personality) != DIMENSIONS or any(
            not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 100
            for value in personality.values()):
        raise ValueError("resident character context personality settings are invalid")
    return json.loads(json.dumps(bundle))
