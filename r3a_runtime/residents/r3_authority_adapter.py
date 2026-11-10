"""Adapt server-attested R3 identities and exact grants to character workflows.

This module intentionally receives the deployed R3 authority and HR capability
as dependencies. The host must resolve the actor from an authenticated R3
session; HTTP/request values are never accepted as identities or grants.
"""

from __future__ import annotations

import uuid
from typing import Any, Callable

from .governance import GovernedActor, GovernancePolicy
from .hr_gateway import HRCapabilityIdentityResolver
from .postgres_repository import PostgresDossierRepository
from .workflow_service import CharacterWorkflowService


class R3CapabilityGrantAdapter:
    """Use R3Authority's exact resource/action/operation/scope grant contract.

    ``resolve_verified_principal`` must validate ``authentication_ref`` against
    the server-side R3 session and return the R3 ``VerifiedPrincipal`` created
    by that host. This adapter never constructs a principal itself.
    """

    CHARACTER_RESOURCE = "r3:character-dossiers"
    HR_RESOURCE = "r3:hr"

    _CHARACTER_ACTIONS = {
        "character.dossier.read": ("character.dossier.read", "read"),
        "character.history.read": ("character.history.read", "read"),
        "character.context.read": ("character.context.read", "read"),
        "character.propose": ("character.propose", "write"),
        "character.approve": ("character.approve", "write"),
        "character.publish": ("character.publish", "write"),
        "character.activate": ("character.activate", "write"),
        "character.rollback": ("character.rollback", "write"),
    }

    def __init__(self, authority: Any, *,
                 resolve_verified_principal: Callable[[GovernedActor], Any]):
        if not callable(getattr(authority, "authorize", None)) or not callable(
                getattr(authority, "audit", None)):
            raise TypeError("canonical R3Authority verifier and durable audit are required")
        if not callable(resolve_verified_principal):
            raise TypeError("server-side authenticated R3 session resolver is required")
        self._authority = authority
        self._resolve_principal = resolve_verified_principal

    def verified_principal(self, actor: GovernedActor) -> Any:
        """Resolve an actor only through the configured server-side session host."""
        if (not isinstance(actor, GovernedActor) or not actor.principal_id
                or not actor.authentication_ref):
            raise PermissionError("server-attested R3 actor required")
        principal = self._resolve_principal(actor)
        if (not getattr(principal, "principal_id", None)
                or not getattr(principal, "role", None)
                or principal.principal_id != actor.principal_id):
            raise PermissionError("authenticated R3 session did not resolve to the supplied actor")
        return principal

    def verify_actor(self, actor: GovernedActor) -> bool:
        try:
            self.verified_principal(actor)
            return True
        except PermissionError:
            return False

    def authorize_character(self, actor: GovernedActor, action: str, scope: str) -> bool:
        binding = self._CHARACTER_ACTIONS.get(action)
        if binding is None:
            return False
        principal = self.verified_principal(actor)
        grant_action, operation = binding
        return self._check(principal, self.CHARACTER_RESOURCE, grant_action,
                           operation, scope, capability=action)

    def authorize_hr(self, principal: Any, action: str, scope: str, *,
                    correlation_id: str | None = None) -> bool:
        """Authorization callback for existing HRCapability read/write operations."""
        if (not getattr(principal, "principal_id", None)
                or not getattr(principal, "role", None)
                or action not in {"hr.read", "hr.field.read", "hr.write"}):
            return False
        operation = "write" if action == "hr.write" else "read"
        return self._check(principal, self.HR_RESOURCE, action, operation, scope,
                           capability=("hr.identity.association" if action == "hr.write"
                                       else "hr.identity.resolve"),
                           correlation_id=correlation_id)

    def _check(self, principal: Any, resource_id: str, action: str,
               operation: str, scope: str, *, capability: str,
               correlation_id: str | None = None) -> bool:
        if not isinstance(scope, str) or not scope.strip():
            return False
        correlation_id = correlation_id or str(uuid.uuid4())
        grant_id = None
        outcome = "denied"
        try:
            grant = self._authority.authorize(
                principal=principal.principal_id, resource_id=resource_id,
                action=action, operation=operation, scope_ref=scope,
            )
            grant_id = grant.get("grant_id") if isinstance(grant, dict) else None
            if not isinstance(grant_id, str) or not grant_id:
                return False
            outcome = "allowed"
            return True
        except Exception:
            # Keep unavailable/denied distinct in the caller's error path only;
            # durable audit records the safe outcome and exact scope, not data.
            return False
        finally:
            self._authority.audit({
                "principal": principal.principal_id,
                "capability": capability,
                "action": action,
                "scope_ref": scope,
                "correlation_id": correlation_id,
                "grant_id": grant_id,
                "outcome": outcome,
                "resource_ref": resource_id,
                "operation": operation,
            })


def build_r3_character_workflow(repository: PostgresDossierRepository,
                                policy: GovernancePolicy, *, hr_capability: Any,
                                authority: Any,
                                resolve_verified_principal: Callable[[GovernedActor], Any]
                                ) -> tuple[CharacterWorkflowService, R3CapabilityGrantAdapter]:
    """Assemble the workflow from the existing R3 HR and exact-grant authorities.

    The host supplies an authenticated principal resolver and the HR capability
    created by its existing R3 factory. This function creates no identity,
    credential, grant, HR connection, or authority policy.
    """
    grants = R3CapabilityGrantAdapter(
        authority, resolve_verified_principal=resolve_verified_principal)
    identities = HRCapabilityIdentityResolver(
        hr_capability, resolve_verified_principal=grants.verified_principal)
    service = CharacterWorkflowService(
        repository, policy, verify_actor=grants.verify_actor,
        resolve_hr_identity=identities,
        authorize_capability=grants.authorize_character,
    )
    return service, grants
