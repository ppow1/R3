# R3 CONTROLLED SOURCE
# File: r3a_runtime/residents/onboarding_host.py
# Component: R3A-RESIDENT-ONBOARDING-HOST
# File Revision: 1.0.0
# Created: 2026-11-11T18:43:21Z
# Created By: Codex GPT-6
# Purpose: Compose resident onboarding with host-authenticated identity, authorization, authority verification, and Coordinator persistence.
# Execution Model: Imported by the Coordinator-owned authenticated API host; no server is started here.
# Observability: Explicit composition and permission failures; workflow audit is delegated to the onboarding service/repository.
# Dependencies: R3A PostgreSQL pool; host actor resolver; R3A authorizer; domain and activation verifiers.
# Authority: Steward Steps 74/81; R3A modular architecture and universal onboarding contracts.
# Changed: 2026-11-11T18:43:21Z | HRD-STEP-74 | Codex GPT-6 | Add fail-closed versioned host-composition façade.
# Supersedes: None
# Contracts: r3a.resident.onboarding.host-composition.v1
# Tests: tests/test_r3a_resident_onboarding_host.py
# History/Predecessor: New file; publication recorded by Git commit.

"""Versioned host-composition boundary for the resident onboarding service.

This package composes the R3A workflow store with host-owned authentication,
authorization, and authority evidence verifiers. It never writes HR, directory,
credential, character, capability-grant, or runtime authority records.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from .onboarding import OnboardingActor, ResidentOnboardingService
from .onboarding_repository import PostgresResidentOnboardingRepository


COMPOSITION_CONTRACT = "r3a.resident.onboarding.host-composition.v1"


class OnboardingCompositionError(RuntimeError):
    """Required authenticated host capability is absent or malformed."""


ActorResolver = Callable[[Any], OnboardingActor | Awaitable[OnboardingActor]]


@dataclass(frozen=True)
class ResidentOnboardingHost:
    """Authenticated application façade for a Coordinator-owned host.

    The host injects the request's already-authenticated context. The resolver
    must derive the institutional actor from that context; packet fields and
    request JSON are never actor sources. Route registration and lifecycle
    supervision remain with the host/Coordinator.
    """

    _service: ResidentOnboardingService
    _actor_resolver: ActorResolver

    async def resolve_actor(self, authenticated_context: Any) -> OnboardingActor:
        try:
            actor = self._actor_resolver(authenticated_context)
            if hasattr(actor, "__await__"):
                actor = await actor
        except Exception as exc:
            raise PermissionError("authenticated onboarding actor resolution failed") from exc
        if not isinstance(actor, OnboardingActor):
            raise PermissionError("host identity resolver did not return an attested onboarding actor")
        return actor

    async def create(self, authenticated_context: Any, packet: dict[str, Any], **evidence: Any) -> dict[str, Any]:
        actor = await self.resolve_actor(authenticated_context)
        return await self._service.create(packet, actor=actor, **evidence)

    async def record_domain(self, authenticated_context: Any, packet_id: str, domain_id: str,
                            *, domain: dict[str, Any], **evidence: Any) -> dict[str, Any]:
        actor = await self.resolve_actor(authenticated_context)
        return await self._service.record_domain(
            packet_id, domain_id, domain=domain, actor=actor, **evidence)

    async def transition(self, authenticated_context: Any, packet_id: str, **evidence: Any) -> dict[str, Any]:
        actor = await self.resolve_actor(authenticated_context)
        return await self._service.transition(packet_id, actor=actor, **evidence)


def compose_resident_onboarding_host(*, pool: Any, actor_resolver: ActorResolver | None,
                                     authorize: Callable[..., bool] | None,
                                     verify_domain_evidence: Callable[..., Any] | None,
                                     verify_activation_evidence: Callable[..., bool] | None,
                                     ) -> ResidentOnboardingHost:
    """Compose the onboarding service only when all external gates are present.

    Missing HR/character/security/runtime/communications verifiers are not
    replaced with permissive defaults. The caller supplies one verifier that
    routes to the authoritative owner for the requested packet domain.
    """
    required = {
        "Coordinator PostgreSQL pool": pool,
        "authenticated actor resolver": actor_resolver,
        "R3A action/scope authorizer": authorize,
        "authority evidence verifier": verify_domain_evidence,
        "activation evidence verifier": verify_activation_evidence,
    }
    missing = [label for label, value in required.items() if value is None or
               (label != "Coordinator PostgreSQL pool" and not callable(value))]
    if missing:
        raise OnboardingCompositionError("missing required host capabilities: " + ", ".join(missing))
    if not callable(getattr(pool, "connection", None)):
        raise OnboardingCompositionError("Coordinator pool does not satisfy the R3A async pool contract")

    repository = PostgresResidentOnboardingRepository(pool)
    service = ResidentOnboardingService(
        repository,
        authorize=authorize,
        verify_domain_evidence=verify_domain_evidence,
        verify_activation_evidence=verify_activation_evidence,
    )
    return ResidentOnboardingHost(service, actor_resolver)
