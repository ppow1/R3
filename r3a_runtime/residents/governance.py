"""Configurable HR/Character Architecture ownership policy checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet


@dataclass(frozen=True)
class GovernedActor:
    """Identity and attestation reference supplied by a trusted institutional gateway."""
    principal_id: str
    authentication_ref: str


@dataclass(frozen=True)
class GovernancePolicy:
    hr_managers: FrozenSet[str]
    character_architects: FrozenSet[str]
    independent_character_reviewers: FrozenSet[str]
    character_publishers: FrozenSet[str]
    runtime_activators: FrozenSet[str]
    stewards: FrozenSet[str]
    steward_context_readers: FrozenSet[str]
    dossier_readers: FrozenSet[str]
    policy_ref: str


HR_ACTIONS = frozenset({
    "hr.record.create", "hr.personnel.update", "hr.office.assign", "hr.onboarding.manage",
    "hr.performance.review", "hr.privacy.classify", "hr.history.rollback",
    "relationship.policy.update",
})


def authorize_workflow_action(actor: GovernedActor, policy: GovernancePolicy, action: str, *,
                              target_classification: str = "RESIDENT",
                              revision_author_id: str | None = None,
                              durable_canon_change: bool = False) -> None:
    """Check domain ownership; authentication and capability enforcement remain upstream.

    The supplied actor must come from a server-verified HR/Steward gateway. A
    character record cannot grant operational capabilities or change CME policy.
    """
    if not isinstance(actor, GovernedActor) or not actor.principal_id or not actor.authentication_ref:
        raise PermissionError("server-attested institutional actor required")
    if not policy.policy_ref:
        raise PermissionError("institutional governance policy is not configured")
    principal = actor.principal_id
    if target_classification == "STEWARD":
        if action in {"steward.identity.update", "steward.authority.update", "steward.history.correct"}:
            if principal not in policy.stewards:
                raise PermissionError("Steward record is governed by the Steward")
            return
        if action == "character.interaction_context.read":
            # Only explicitly configured readers may receive this projection.
            if principal in policy.stewards | policy.steward_context_readers:
                return
        raise PermissionError("ordinary resident lifecycle and character procedures do not apply to STEWARD")
    if action in HR_ACTIONS:
        if principal not in policy.hr_managers:
            raise PermissionError("HR governance authority denied")
        return
    if action == "character.dossier.read":
        if principal not in policy.dossier_readers:
            raise PermissionError("character dossier read authority denied")
        return
    if action == "character.history.read":
        if principal not in policy.dossier_readers | policy.character_architects:
            raise PermissionError("character history read authority denied")
        return
    if action in {"character.propose", "character.history.review", "character.drift.review"}:
        if principal not in policy.character_architects:
            raise PermissionError("Character Architecture authority denied")
        return
    if action == "character.approve":
        if durable_canon_change and revision_author_id == principal:
            raise PermissionError("an author cannot independently approve their own durable canon")
        elif principal not in policy.character_architects | policy.independent_character_reviewers:
            raise PermissionError("Character Architecture review authority denied")
        return
    if action == "character.publish":
        if principal not in policy.character_publishers:
            raise PermissionError("character publication authority denied")
        return
    if action == "character.activate":
        if principal not in policy.runtime_activators:
            raise PermissionError("runtime activation authority denied")
        return
    if action == "character.rollback":
        if principal not in policy.runtime_activators:
            raise PermissionError("runtime rollback authority denied")
        return
    raise PermissionError("workflow action is not granted by institutional governance")
