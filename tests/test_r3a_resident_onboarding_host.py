# R3 CONTROLLED TEST
# File: tests/test_r3a_resident_onboarding_host.py
# Component: R3A-RESIDENT-ONBOARDING-HOST-TESTS
# File Revision: 1.0.0
# Created: 2026-11-11T18:43:21Z
# Created By: Codex GPT-6
# Purpose: Verify composition gates and authenticated actor derivation without starting a service.
# Execution Model: Pytest/unittest; fake pool and local synthetic actor only.
# Observability: Assertion failures identify missing port, spoofed actor, or resolver outage.
# Dependencies: onboarding_host contract.
# Authority: Steward Steps 74/81; R3A modular architecture requirements.
# Changed: 2026-11-11T18:43:21Z | HRD-STEP-74 | Codex GPT-6 | Add permanent host boundary regressions.
# Supersedes: None
# Contracts: r3a.resident.onboarding.host-composition.v1
# Tests: This test module.
# History/Predecessor: New file; publication recorded by Git commit.

"""Host-composition boundary regressions; no shared service is started."""
from __future__ import annotations

import unittest

from r3a_runtime.residents.onboarding import OnboardingActor
from r3a_runtime.residents.onboarding_host import (
    COMPOSITION_CONTRACT,
    OnboardingCompositionError,
    ResidentOnboardingHost,
    compose_resident_onboarding_host,
)


class _Pool:
    def connection(self):
        raise AssertionError("composition must not open a connection")


class _CapturingService:
    def __init__(self):
        self.actor = None
        self.kwargs = None

    async def create(self, packet, *, actor, **kwargs):
        self.actor, self.kwargs = actor, kwargs
        return {"packet_id": packet["packet_id"]}

    async def record_domain(self, packet_id, domain_id, *, domain, actor, **kwargs):
        self.actor, self.kwargs = actor, kwargs
        return {"packet_id": packet_id, "domain_id": domain_id}

    async def transition(self, packet_id, *, actor, **kwargs):
        self.actor, self.kwargs = actor, kwargs
        return {"packet_id": packet_id}


class ResidentOnboardingHostTests(unittest.IsolatedAsyncioTestCase):
    def test_composition_contract_requires_every_trusted_host_port(self):
        values = dict(
            pool=_Pool(), actor_resolver=lambda context: OnboardingActor("hr:1", "HR", "session:1"),
            authorize=lambda *args: True, verify_domain_evidence=lambda *args: True,
            verify_activation_evidence=lambda *args: True,
        )
        host = compose_resident_onboarding_host(**values)
        self.assertEqual(COMPOSITION_CONTRACT, "r3a.resident.onboarding.host-composition.v1")
        self.assertEqual(type(host), ResidentOnboardingHost)
        for name in ("actor_resolver", "authorize", "verify_domain_evidence", "verify_activation_evidence"):
            broken = {**values, name: None}
            with self.subTest(missing=name), self.assertRaises(OnboardingCompositionError):
                compose_resident_onboarding_host(**broken)

    async def test_request_actor_is_resolved_from_host_context_not_packet(self):
        service = _CapturingService()
        actor = OnboardingActor("principal:hr", "HR", "session:server")
        host = ResidentOnboardingHost(service, lambda context: actor)
        result = await host.create(
            {"server_session": "verified"}, {"packet_id": "packet:1", "actor": "forged"},
            correlation_id="correlation:1", reason_ref="reason:1", evidence_refs=["source:1"],
        )
        self.assertEqual({"packet_id": "packet:1"}, result)
        self.assertIs(actor, service.actor)
        self.assertEqual("correlation:1", service.kwargs["correlation_id"])

    async def test_invalid_or_unavailable_actor_resolution_fails_closed(self):
        for resolver in (lambda context: None, lambda context: "HR"):
            host = ResidentOnboardingHost(_CapturingService(), resolver)
            with self.subTest(resolver=resolver), self.assertRaises(PermissionError):
                await host.resolve_actor({"user_role": "HR"})

        async def unavailable(context):
            raise RuntimeError("session authority unavailable")

        host = ResidentOnboardingHost(_CapturingService(), unavailable)
        with self.assertRaisesRegex(PermissionError, "resolution failed"):
            await host.resolve_actor({})


if __name__ == "__main__":
    unittest.main()
