"""Approved active character-context lookup and execution-boundary pinning."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Callable

from .configuration import resolve_personality
from .governance import GovernedActor
from .prompts import compose_prompt
from .r3_authority_adapter import R3CapabilityGrantAdapter
from .validation import DIMENSIONS
from .workflow_service import CharacterWorkflowService


CONTEXT_CONTRACT_ID = "r3a.resident.approved-character-context"
CONTEXT_CONTRACT_VERSION = "2.0.0"
_SAFE_CLASSIFICATIONS = frozenset({"public", "institutional"})


class ApprovedCharacterContextProvider:
    """Resolve only approved active dossier context for one verified runtime binding.

    ``workflow._identity`` is intentionally not used: CME context lookup has its own
    exact capability (`character.context.read`) while still resolving canonical HR
    identity through the same authenticated R3 gateway. Repository pin methods persist
    revision selection for a specific inference/conversation boundary.
    """

    def __init__(self, repository: Any, *, resolve_hr_identity: Callable[..., dict[str, Any]],
                 authorize_context: Callable[[GovernedActor, str, str], Any],
                 defaults: dict[str, int], personality_overrides: list[dict[str, Any]] | None = None):
        for method in ("get", "revision_digest", "get_context_pin", "pin_context"):
            if not callable(getattr(repository, method, None)):
                raise TypeError(f"repository must implement {method}")
        if not callable(resolve_hr_identity) or not callable(authorize_context):
            raise TypeError("authenticated HR identity and character-context authorization gateways are required")
        self.repository = repository
        self._resolve_identity = resolve_hr_identity
        self._authorize = authorize_context
        self.defaults = defaults
        self.overrides = personality_overrides or []

    def retrieve(self, actor: GovernedActor, *, resident_id: str,
                 execution_kind: str, execution_ref: str, provider_id: str) -> dict[str, Any]:
        if (not isinstance(actor, GovernedActor) or not actor.principal_id
                or not actor.authentication_ref):
            raise PermissionError("server-authenticated resident execution principal is required")
        if execution_kind not in {"inference_activity", "conversation_boundary"}:
            raise ValueError("character context requires an inference or conversation execution boundary")
        if not all(isinstance(v, str) and v.strip() for v in (resident_id, execution_ref, provider_id)):
            raise ValueError("canonical resident, execution boundary, and provider references are required")

        authorization = self._authorize(actor, "character.context.read", resident_id)
        if authorization is True:
            # A boolean grant has no classification detail; fail to the public tier.
            authorized_classifications = {"public"}
        elif isinstance(authorization, (set, frozenset, tuple, list)):
            authorized_classifications = set(authorization) & _SAFE_CLASSIFICATIONS
        else:
            raise PermissionError("character context capability denied")
        if not authorized_classifications:
            raise PermissionError("character context grant has no usable classification scope")

        identity = self._resolve_identity(actor, resident_id)
        if (not isinstance(identity, dict) or identity.get("institutional_id") != resident_id
                or identity.get("status") != "authoritative"
                or identity.get("classification") != "RESIDENT"
                or not identity.get("revision")
                or not identity.get("directory_resident_id")
                or identity.get("authority_principal") != identity.get("directory_resident_id")
                or not identity.get("principal_association_ref")
                or not identity.get("source_ref")
                or not identity.get("directory_source_ref")
                or identity.get("directory_snapshot_fresh") is not True
                or not isinstance(identity.get("directory_snapshot_sha256"), str)
                or not identity.get("office_id") or not identity.get("office_role")
                or not identity.get("execution_profile_id")
                or not identity.get("execution_profile_revision")
                or identity.get("execution_profile_resident_id") != identity.get("directory_resident_id")
                or not identity.get("execution_route_id")
                or not identity.get("execution_profile_source_ref")
                or type(identity.get("binding_revision")) is not int
                or identity["binding_revision"] < 1):
            raise PermissionError("source-verified HR principal association and current directory office binding are required")
        pin = self.repository.get_context_pin(
            resident_id=resident_id, execution_kind=execution_kind,
            execution_ref=execution_ref,
        )
        identity_revision = str(identity["revision"])
        if pin:
            expected = (pin["identity_revision"], pin["directory_resident_id"],
                        pin["binding_revision"], pin["directory_snapshot_sha256"],
                        pin["directory_source_ref"], pin["hr_source_ref"],
                        pin["hr_principal_association_ref"], pin["office_id"], pin["office_role"],
                        pin["execution_profile_id"], pin["execution_profile_revision"],
                        pin["execution_profile_resident_id"], pin["execution_route_id"],
                        pin["execution_profile_source_ref"],
                        pin["provider_id"], pin["principal_ref"])
            current = (identity_revision, identity["directory_resident_id"],
                       identity["binding_revision"], identity["directory_snapshot_sha256"],
                       identity["directory_source_ref"], identity["source_ref"],
                       identity["principal_association_ref"], identity["office_id"],
                       identity["office_role"], identity["execution_profile_id"],
                       identity["execution_profile_revision"],
                       identity["execution_profile_resident_id"], identity["execution_route_id"],
                       identity["execution_profile_source_ref"], provider_id, actor.principal_id)
            if current != expected:
                raise PermissionError("pinned character context identity, binding, or provider changed")
            revision = pin["dossier_revision"]
            dossier = self.repository.get(resident_id, revision)
            digest = self.repository.revision_digest(resident_id, revision)
            if digest != pin["dossier_sha256"]:
                raise PermissionError("pinned dossier digest does not match immutable revision storage")
            if not self.repository.has_activation(resident_id, revision):
                raise PermissionError("pinned dossier revision has no activation evidence")
            # Historical revisions remain eligible only inside boundaries pinned while
            # active; immutable activation evidence, not their current pointer state,
            # establishes that eligibility after a later safe-boundary switch.
            dossier.setdefault("governance", {})["approval_status"] = "active"
        else:
            dossier = self.repository.get(resident_id)
            if dossier.get("governance", {}).get("approval_status") != "active":
                raise PermissionError("no approved active character dossier exists")
            revision = dossier["revision"]
            digest = self.repository.revision_digest(resident_id, revision)
            pin = self.repository.pin_context(
                resident_id=resident_id, revision=revision, dossier_sha256=digest,
                execution_kind=execution_kind, execution_ref=execution_ref,
                identity_revision=identity_revision,
                directory_resident_id=identity["directory_resident_id"],
                binding_revision=identity["binding_revision"],
                directory_snapshot_sha256=identity["directory_snapshot_sha256"],
                directory_source_ref=identity["directory_source_ref"],
                hr_source_ref=identity["source_ref"],
                hr_principal_association_ref=identity["principal_association_ref"],
                office_id=identity["office_id"], office_role=identity["office_role"],
                execution_profile_id=identity["execution_profile_id"],
                execution_profile_revision=identity["execution_profile_revision"],
                execution_profile_resident_id=identity["execution_profile_resident_id"],
                execution_route_id=identity["execution_route_id"],
                execution_profile_source_ref=identity["execution_profile_source_ref"],
                provider_id=provider_id,
                principal_ref=actor.principal_id,
            )

        if dossier.get("revision") != revision:
            raise PermissionError("loaded character context revision does not match its pin")
        safe_components = [component for component in dossier.get("prompt_components", [])
                           if component.get("classification") in authorized_classifications]
        safe_dossier = {**dossier, "prompt_components": safe_components}
        prompt = compose_prompt(safe_dossier, provider_id=provider_id)
        if prompt.provisional or not prompt.source_refs:
            raise PermissionError("active character context requires approved sourced components")
        used_classifications = sorted({component["classification"] for component in safe_components
                                       if (component.get("component_id"), component.get("version"))
                                       in set(prompt.component_refs)})
        settings, setting_sources = resolve_personality(
            self.defaults, dossier["personality"]["settings"],
            dossier["personality"].get("overrides", []), resident_id=resident_id,
        )
        source_refs = list(dict.fromkeys([
            identity["source_ref"], identity["principal_association_ref"],
            identity["directory_source_ref"], identity["execution_profile_source_ref"],
            f"character-context-pin://{pin['pin_id']}", *prompt.source_refs]))
        composed = {"prompt_text": prompt.text, "personality": settings,
                    "prompt_component_refs": [list(x) for x in prompt.component_refs],
                    "source_refs": source_refs,
                    "personality_sources": setting_sources}
        context_sha256 = hashlib.sha256(json.dumps(
            composed, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")).hexdigest()
        return {
            "contract_id": CONTEXT_CONTRACT_ID,
            "contract_version": CONTEXT_CONTRACT_VERSION,
            "resident_id": resident_id,
            "directory_resident_id": identity["directory_resident_id"],
            "identity_revision": identity_revision,
            "directory_binding_revision": identity["binding_revision"],
            "directory_snapshot_sha256": identity["directory_snapshot_sha256"],
            "directory_source_ref": identity["directory_source_ref"],
            "hr_source_ref": identity["source_ref"],
            "hr_principal_association_ref": identity["principal_association_ref"],
            "office_id": identity["office_id"],
            "office_role": identity["office_role"],
            "execution_profile_id": identity["execution_profile_id"],
            "execution_profile_revision": identity["execution_profile_revision"],
            "execution_profile_resident_id": identity["execution_profile_resident_id"],
            "execution_route_id": identity["execution_route_id"],
            "execution_profile_source_ref": identity["execution_profile_source_ref"],
            "execution_kind": execution_kind,
            "execution_ref": execution_ref,
            "pin_ref": pin["pin_id"],
            "provider_id": provider_id,
            "dossier_revision": revision,
            "dossier_sha256": digest,
            "context_sha256": context_sha256,
            "activation_status": "active",
            "classification_scope": used_classifications,
            "authorization_ref": actor.authentication_ref,
            "prompt_text": prompt.text,
            "prompt_sha256": prompt.sha256,
            "prompt_component_refs": [list(x) for x in prompt.component_refs],
            "source_refs": source_refs,
            "personality": settings,
            "personality_sources": setting_sources,
            "authority_granted": False,
        }


def project_context_for_sink(context: dict[str, Any], *, sink: str,
                             authorized_classifications: frozenset[str],
                             principal_ref: str,
                             audit: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
    """Apply classification before a downstream inference, memory, message, or log sink.

    Only inference receives context text. Memory and communications receive a durable
    reference to the exact context version, while diagnostics receive metadata only.
    Audit callbacks receive no character content.
    """
    validated = validate_approved_context(context)
    if sink not in {"inference", "memory", "communications", "diagnostics"}:
        raise ValueError("unsupported resident context sink")
    if not principal_ref or not callable(audit):
        raise PermissionError("authorized sink principal and audit callback are required")
    authorized = set(authorized_classifications) & _SAFE_CLASSIFICATIONS
    classifications = set(validated["classification_scope"])
    if not classifications <= authorized:
        audit({"principal_ref": principal_ref, "sink": sink, "pin_ref": validated["pin_ref"],
               "context_sha256": validated["context_sha256"], "outcome": "denied"})
        raise PermissionError("character context classification is not authorized for this sink")
    base = {key: validated[key] for key in (
        "resident_id", "directory_resident_id", "identity_revision",
        "directory_snapshot_sha256", "directory_source_ref", "hr_source_ref",
        "hr_principal_association_ref", "office_id", "office_role",
        "execution_profile_id", "execution_profile_revision",
        "execution_profile_resident_id", "execution_route_id",
        "execution_profile_source_ref",
        "directory_binding_revision", "execution_kind", "execution_ref", "pin_ref",
        "provider_id", "dossier_revision", "dossier_sha256", "context_sha256",
        "classification_scope", "source_refs")}
    if sink == "inference":
        projection = {**base, "prompt_text": validated["prompt_text"],
                      "prompt_sha256": validated["prompt_sha256"],
                      "personality": validated["personality"],
                      "prompt_component_refs": validated["prompt_component_refs"]}
    elif sink in {"memory", "communications"}:
        projection = {**base, "context_reference_only": True}
    else:
        projection = {key: value for key, value in base.items()
                      if key not in {"source_refs", "execution_ref"}}
        projection["context_reference_only"] = True
    audit({"principal_ref": principal_ref, "sink": sink, "pin_ref": validated["pin_ref"],
           "context_sha256": validated["context_sha256"], "outcome": "allowed"})
    return projection


def project_for_grace_context_v1(context: dict[str, Any], *,
                                 verified_execution_profile: dict[str, Any]) -> dict[str, Any]:
    """Project v2 into Grace's existing v1 consumer only under an exact profile match.

    The profile must be resolved by the authenticated runtime host, not accepted from a
    message/request. This adapter preserves the v2 identity, binding, profile and pin refs
    as provenance references. It never manufactures an alias between HR, directory, and
    executable IDs.
    """
    context = validate_approved_context(context)
    required_profile_fields = {"profile_id", "profile_revision", "resident_id",
                               "route_id", "source_ref"}
    if (not isinstance(verified_execution_profile, dict)
            or set(verified_execution_profile) != required_profile_fields):
        raise ValueError("server-verified execution profile evidence is required")
    expected = (context["execution_profile_id"], context["execution_profile_revision"],
                context["execution_profile_resident_id"], context["execution_route_id"],
                context["execution_profile_source_ref"])
    observed = tuple(verified_execution_profile[key] for key in (
        "profile_id", "profile_revision", "resident_id", "route_id", "source_ref"))
    if observed != expected or observed[2] != context["directory_resident_id"]:
        raise PermissionError("verified execution profile does not match the approved identity binding")
    source_refs = list(dict.fromkeys([
        *context["source_refs"], context["pin_ref"],
        f"directory-snapshot:sha256:{context['directory_snapshot_sha256']}",
        f"office-binding:{context['office_id']}@{context['directory_binding_revision']}",
        f"dossier-sha256:{context['dossier_sha256']}",
        f"character-context-sha256:{context['context_sha256']}",
    ]))
    return {
        "contract_id": "r3a.resident.runtime-character-context",
        "contract_version": "1.0.0",
        "resident_id": context["resident_id"],
        "directory_resident_id": context["directory_resident_id"],
        "identity_binding_status": "authoritative",
        "identity_revision": context["identity_revision"],
        "dossier_revision": context["dossier_revision"],
        "approval_status": "active",
        "classification_scope": list(context["classification_scope"]),
        "authorization_ref": context["authorization_ref"],
        "prompt_text": context["prompt_text"],
        "prompt_sha256": context["prompt_sha256"],
        "prompt_component_refs": context["prompt_component_refs"],
        "source_refs": source_refs,
        "personality": context["personality"],
        "personality_sources": context["personality_sources"],
        "provider_id": context["provider_id"],
        "authority_granted": False,
    }


def validate_approved_context(value: Any) -> dict[str, Any]:
    """Fail-closed validator for the provider-neutral v2 active-context envelope."""
    required = {"contract_id", "contract_version", "resident_id", "directory_resident_id",
                "identity_revision", "directory_binding_revision", "directory_snapshot_sha256",
                "directory_source_ref", "hr_source_ref", "hr_principal_association_ref",
                "office_id", "office_role", "execution_profile_id",
                "execution_profile_revision", "execution_profile_resident_id",
                "execution_route_id", "execution_profile_source_ref", "execution_kind",
                "execution_ref", "pin_ref", "provider_id", "dossier_revision",
                "dossier_sha256", "context_sha256", "activation_status",
                "classification_scope", "authorization_ref", "prompt_text", "prompt_sha256",
                "prompt_component_refs", "source_refs", "personality", "personality_sources",
                "authority_granted"}
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError("approved character context fields are invalid")
    if value["contract_id"] != CONTEXT_CONTRACT_ID or value["contract_version"] != CONTEXT_CONTRACT_VERSION:
        raise ValueError("approved character context contract is incompatible")
    if value["activation_status"] != "active" or value["authority_granted"] is not False:
        raise PermissionError("only active character context without authority may be consumed")
    if value["execution_kind"] not in {"inference_activity", "conversation_boundary"}:
        raise ValueError("character context is not pinned to a supported boundary")
    if type(value["directory_binding_revision"]) is not int or value["directory_binding_revision"] < 1:
        raise ValueError("authoritative directory binding revision is required")
    for key in ("resident_id", "directory_resident_id", "identity_revision", "execution_ref",
                "pin_ref", "provider_id", "dossier_revision", "dossier_sha256",
                "context_sha256", "authorization_ref", "directory_source_ref",
                "hr_source_ref", "hr_principal_association_ref", "office_id", "office_role",
                "execution_profile_id", "execution_profile_revision",
                "execution_profile_resident_id", "execution_route_id",
                "execution_profile_source_ref"):
        if not isinstance(value[key], str) or not value[key]:
            raise ValueError("approved context identity and provenance fields are required")
    for key in ("dossier_sha256", "context_sha256", "prompt_sha256", "directory_snapshot_sha256"):
        if not isinstance(value[key], str) or len(value[key]) != 64 or any(c not in "0123456789abcdef" for c in value[key]):
            raise ValueError("approved context digest is invalid")
    if hashlib.sha256(value["prompt_text"].encode("utf-8")).hexdigest() != value["prompt_sha256"]:
        raise ValueError("approved context prompt digest mismatch")
    if (not isinstance(value["classification_scope"], list) or not value["classification_scope"]
            or set(value["classification_scope"]) - _SAFE_CLASSIFICATIONS):
        raise PermissionError("protected classifications cannot enter runtime context")
    if not value["source_refs"] or not isinstance(value["source_refs"], list):
        raise ValueError("approved active context requires provenance")
    settings = value["personality"]
    if not isinstance(settings, dict) or set(settings) != DIMENSIONS or any(
            type(setting) is not int or not 0 <= setting <= 100 for setting in settings.values()):
        raise ValueError("approved context personality configuration is invalid")
    if not re.fullmatch(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)", value["dossier_revision"]):
        raise ValueError("approved context dossier revision is invalid")
    components = value["prompt_component_refs"]
    if (not isinstance(components, list) or not components
            or any(not isinstance(pair, list) or len(pair) != 2
                   or any(not isinstance(part, str) or not part for part in pair)
                   for pair in components)):
        raise ValueError("approved context component references are invalid")
    if (not isinstance(value["personality_sources"], dict)
            or any(not isinstance(source, str) for source in value["personality_sources"].values())):
        raise ValueError("approved context personality provenance is invalid")
    if value["execution_profile_resident_id"] != value["directory_resident_id"]:
        raise ValueError("execution profile identity does not match the authoritative directory principal")
    composed = {"prompt_text": value["prompt_text"], "personality": settings,
                "prompt_component_refs": value["prompt_component_refs"],
                "source_refs": value["source_refs"],
                "personality_sources": value["personality_sources"]}
    expected_context_digest = hashlib.sha256(json.dumps(
        composed, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()
    if expected_context_digest != value["context_sha256"]:
        raise ValueError("approved context digest mismatch")
    return json.loads(json.dumps(value))
