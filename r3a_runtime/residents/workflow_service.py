"""Authenticated service facade for the resident character lifecycle.

The caller supplies gateways backed by HR and institutional authorization.
This module contains no HTTP identity parsing and no resident roster.
"""

from __future__ import annotations

from typing import Any, Callable

from .governance import (
    GovernedActor,
    GovernancePolicy,
    authorize_workflow_action,
)
from .postgres_repository import PostgresDossierRepository


class CharacterWorkflowService:
    """Coordinate HR identity checks, domain authorization, and durable writes.

    ``resolve_hr_identity`` must call the established authenticated HR authority
    for each request and return its canonical ID, authoritative status, and
    current HR revision. ``authorize_capability`` must enforce the existing
    institutional/CME grant contract for the requested action and scope. The
    supplied actor must have been established by that trusted transport.
    """

    def __init__(self, repository: PostgresDossierRepository, policy: GovernancePolicy, *,
                 verify_actor: Callable[[GovernedActor], bool],
                 resolve_hr_identity: Callable[[GovernedActor, str], dict[str, Any]],
                 authorize_capability: Callable[[GovernedActor, str, str], bool]):
        if not callable(verify_actor):
            raise TypeError("server-side actor verifier is required")
        self.repository = repository
        self.policy = policy
        self._verify_actor = verify_actor
        self._resolve_hr_identity = resolve_hr_identity
        self._authorize_capability = authorize_capability

    @staticmethod
    def _require_nonprotected_dossier(dossier: dict[str, Any]) -> None:
        """Protected HR/personnel material is stored only through its own HR interface."""
        prohibited = {"protected", "personnel_sensitive"}
        safe = {"public", "institutional"}
        def visit(value: Any) -> None:
            if isinstance(value, dict):
                classification = value.get("classification")
                if classification in prohibited or (classification is not None and classification not in safe):
                    raise PermissionError("non-public HR/protected content cannot enter the character dossier store")
                for nested in value.values():
                    visit(nested)
            elif isinstance(value, list):
                for nested in value:
                    visit(nested)
        visit(dossier)

    def read(self, actor: GovernedActor, resident_id: str, *, revision: str | None = None) -> dict[str, Any]:
        self._identity(actor, resident_id)
        action = "character.dossier.read" if revision is None else "character.history.read"
        self._authorize(actor, action, resident_id)
        if revision is None:
            return self.repository.get(resident_id)
        return self.repository.get(resident_id, revision)

    def history(self, actor: GovernedActor, resident_id: str) -> tuple[dict[str, Any], ...]:
        self._identity(actor, resident_id)
        self._authorize(actor, "character.history.read", resident_id)
        return self.repository.history(resident_id)

    def propose(self, actor: GovernedActor, dossier: dict[str, Any], *,
                expected_active_revision: str | None, reason: str,
                source_refs: tuple[str, ...], durable_canon_change: bool) -> str:
        if not isinstance(dossier, dict) or not isinstance(dossier.get("identity"), dict):
            raise ValueError("resident dossier identity is required")
        resident_id = dossier["identity"].get("resident_id")
        identity = self._identity(actor, resident_id)
        self._authorize(actor, "character.propose", resident_id)
        authorize_workflow_action(actor, self.policy, "character.propose")
        if identity["institutional_id"] != resident_id:
            raise PermissionError("proposal dossier must use the canonical HR identity")
        if not source_refs:
            raise ValueError("character proposals require source evidence or an explicit proposal source")
        self._require_nonprotected_dossier(dossier)
        return self.repository.propose(
            dossier,
            expected_active_revision=expected_active_revision,
            hr_identity_revision=str(identity["revision"]),
            actor_ref=actor.principal_id,
            reason=reason,
            source_refs=source_refs,
            durable_canon_change=durable_canon_change,
        )

    def submit_for_review(self, actor: GovernedActor, resident_id: str, revision: str, *,
                          reason: str, source_refs: tuple[str, ...] = ()) -> None:
        self._identity(actor, resident_id)
        self._authorize(actor, "character.propose", resident_id)
        authorize_workflow_action(actor, self.policy, "character.propose")
        self.repository.transition(resident_id, revision, event_type="submitted_for_review",
                                   actor_ref=actor.principal_id,
                                   owner_domain="character_architecture", reason=reason,
                                   source_refs=source_refs)

    def approve(self, actor: GovernedActor, resident_id: str, revision: str, *,
                reason: str, source_refs: tuple[str, ...] = ()) -> None:
        self._identity(actor, resident_id)
        metadata = self.repository.revision_metadata(resident_id, revision)
        durable = bool(metadata["durable_canon_change"])
        authorize_workflow_action(
            actor, self.policy, "character.approve",
            revision_author_id=metadata["author_id"], durable_canon_change=durable,
        )
        self._authorize(actor, "character.approve", resident_id)
        self.repository.transition(resident_id, revision, event_type="approved",
                                   actor_ref=actor.principal_id,
                                   owner_domain="character_architecture", reason=reason,
                                   source_refs=source_refs,
                                   evidence={"review_policy_ref": self.policy.policy_ref})

    def reject(self, actor: GovernedActor, resident_id: str, revision: str, *,
               reason: str, source_refs: tuple[str, ...] = ()) -> None:
        self._identity(actor, resident_id)
        metadata = self.repository.revision_metadata(resident_id, revision)
        authorize_workflow_action(
            actor, self.policy, "character.approve",
            revision_author_id=metadata["author_id"],
            durable_canon_change=bool(metadata["durable_canon_change"]),
        )
        self._authorize(actor, "character.approve", resident_id)
        self.repository.transition(resident_id, revision, event_type="rejected",
                                   actor_ref=actor.principal_id,
                                   owner_domain="character_architecture", reason=reason,
                                   source_refs=source_refs,
                                   evidence={"review_policy_ref": self.policy.policy_ref})

    def publish(self, actor: GovernedActor, resident_id: str, revision: str, *, reason: str) -> None:
        self._identity(actor, resident_id)
        authorize_workflow_action(actor, self.policy, "character.publish")
        self._authorize(actor, "character.publish", resident_id)
        self.repository.transition(resident_id, revision, event_type="published",
                                   actor_ref=actor.principal_id,
                                   owner_domain="character_architecture", reason=reason)

    def activate(self, actor: GovernedActor, resident_id: str, revision: str, *, reason: str) -> None:
        self._identity(actor, resident_id)
        authorize_workflow_action(actor, self.policy, "character.activate")
        self._authorize(actor, "character.activate", resident_id)
        self.repository.transition(resident_id, revision, event_type="activated",
                                   actor_ref=actor.principal_id,
                                   owner_domain="engineering", reason=reason)

    def rollback(self, actor: GovernedActor, resident_id: str, revision: str, *, reason: str) -> None:
        self._identity(actor, resident_id)
        authorize_workflow_action(actor, self.policy, "character.rollback")
        self._authorize(actor, "character.rollback", resident_id)
        self.repository.transition(resident_id, revision, event_type="rollback",
                                   actor_ref=actor.principal_id,
                                   owner_domain="engineering", reason=reason)

    def retire(self, actor: GovernedActor, resident_id: str, revision: str, *,
               reason: str, source_refs: tuple[str, ...] = ()) -> None:
        """Deactivate an active character revision while retaining history and pins.

        Retirement is an execution-lifecycle action, separate from editing canon or
        changing HR identity. A previously pinned boundary remains resolvable; new
        boundaries have no current character revision until a later activation.
        """
        self._identity(actor, resident_id)
        current = self.repository.get(resident_id)
        if current["revision"] != revision or current["governance"]["approval_status"] != "active":
            raise PermissionError("only the current active character revision can be retired")
        authorize_workflow_action(actor, self.policy, "character.retire")
        self._authorize(actor, "character.retire", resident_id)
        self.repository.transition(resident_id, revision, event_type="retired",
                                   actor_ref=actor.principal_id,
                                   owner_domain="engineering", reason=reason,
                                   source_refs=source_refs,
                                   evidence={"retirement_policy_ref": self.policy.policy_ref})

    def _identity(self, actor: GovernedActor, resident_id: str) -> dict[str, Any]:
        if not isinstance(actor, GovernedActor) or not actor.principal_id or not actor.authentication_ref:
            raise PermissionError("server-attested institutional actor required")
        if not self._verify_actor(actor):
            raise PermissionError("institutional actor authentication could not be verified")
        if not isinstance(resident_id, str) or not resident_id:
            raise ValueError("canonical resident ID required")
        identity = self._resolve_hr_identity(actor, resident_id)
        if (not isinstance(identity, dict)
                or identity.get("institutional_id") != resident_id
                or identity.get("status") != "authoritative"
                or identity.get("classification") != "RESIDENT"
                or identity.get("revision") is None):
            raise PermissionError("authoritative HR resident identity and revision are required")
        return identity

    def _authorize(self, actor: GovernedActor, action: str, scope: str) -> None:
        authorize_workflow_action(actor, self.policy, action)
        if not self._authorize_capability(actor, action, scope):
            raise PermissionError("institutional capability grant denied")
