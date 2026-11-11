"""Real PostgreSQL migration/repository checks, gated to a disposable test DB."""
from __future__ import annotations

import asyncio
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest
import uuid

import psycopg
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from r3a_runtime.capability_contracts import CapabilityContractError
from r3a_runtime.db import Store
from r3a_runtime.residents.onboarding import (
    DuplicateOnboarding,
    OnboardingActor,
    OnboardingRevisionConflict,
    REQUIRED_FIELDS,
    ResidentOnboardingService,
    new_onboarding_packet,
    public_packet_summary,
    transition_packet,
)
from r3a_runtime.residents.onboarding_repository import PostgresResidentOnboardingRepository


ROOT = Path(__file__).resolve().parents[1]
DOWN_MIGRATION = ROOT / "r3a_runtime/rollback/019_resident_onboarding.down.sql"
SYNTHETIC_FIXTURE = ROOT / "tests/fixtures/resident-onboarding-synthetic.json"
NOW = "2026-11-10T13:00:00Z"


def _identity_domain(resident_id: str) -> dict:
    approval = f"test://approval/hr/{resident_id}"
    evidence = f"test://evidence/hr/{resident_id}"
    return {
        "applicability": "mandatory", "owner": "HR",
        "authority_source": "riverview_authority.hr",
        "required_approval": "HR identity approval and source association", "approval_ref": approval,
        "status": "verified", "validation_contract": "r3a.resident.onboarding.identity.v1",
        "evidence_refs": [evidence], "revision_pins": {"hr_identity": "revision:1"},
        "blocker_ref": None,
        "fields": [{
            "field_id": field_id,
            "value_ref": f"test://value/{resident_id}/{field_id}",
            "classification": "institutional", "owner": "HR",
            "source_ref": f"test://source/{resident_id}/{field_id}",
            "approval_required": True, "approval_ref": approval,
            "validation_contract": "test://contract/hr-identity-field-v1",
            "evidence_refs": [evidence], "revision_pin": f"hr-identity:{resident_id}:1",
            "expires_at": None, "status": "verified",
        } for field_id in sorted(REQUIRED_FIELDS["identity"])],
    }


class ResidentOnboardingPostgresIntegrationTests(unittest.IsolatedAsyncioTestCase):
    """Run only with R3A_TEST_ONBOARDING_DSN targeting a disposable local DB."""

    @classmethod
    def setUpClass(cls):
        dsn = os.environ.get("R3A_TEST_ONBOARDING_DSN")
        if not dsn:
            raise unittest.SkipTest("R3A_TEST_ONBOARDING_DSN is not configured")
        settings = conninfo_to_dict(dsn)
        dbname = settings.get("dbname", "")
        host = settings.get("host", "")
        if not dbname.startswith("r3a_onboarding_test_"):
            raise RuntimeError("refusing PostgreSQL test DB without r3a_onboarding_test_ name prefix")
        if host not in {"", "localhost", "127.0.0.1", "::1"} and not host.startswith("/tmp/"):
            raise RuntimeError("refusing PostgreSQL test DB outside localhost or a private /tmp socket")
        cls.dsn = dsn

    async def asyncSetUp(self):
        self.pool = AsyncConnectionPool(self.dsn, min_size=1, max_size=4,
                                        kwargs={"row_factory": dict_row}, open=False)
        await self.pool.open()
        async with self.pool.connection() as conn, conn.transaction():
            await conn.execute("DROP SCHEMA IF EXISTS r3a CASCADE")
            await conn.execute("""DO $$ BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='r3a_runtime') THEN
                    CREATE ROLE r3a_runtime NOLOGIN;
                END IF;
            END $$""")
        store = object.__new__(Store)
        store.conninfo = self.dsn
        applied = await store.migrate()
        self.assertIn("019_resident_onboarding.sql", applied)
        self.assertEqual([], await store.migrate(), "re-running migrations must be a no-op")
        self.repository = PostgresResidentOnboardingRepository(self.pool)
        self.store = store

    async def asyncTearDown(self):
        if getattr(self, "pool", None):
            async with self.pool.connection() as conn, conn.transaction():
                await conn.execute("DROP SCHEMA IF EXISTS r3a CASCADE")
            await self.pool.close()

    async def test_real_upgrade_rollback_repository_transactions_and_privacy(self):
        # Migration runner has applied the full current stack through 019. Exercise
        # the guarded down migration only while both workflow tables are empty.
        down_sql = DOWN_MIGRATION.read_text(encoding="utf-8")
        async with self.pool.connection() as conn, conn.transaction():
            await conn.execute(down_sql)
            row = await (await conn.execute(
                "SELECT to_regclass('r3a.resident_onboarding_packets') AS packets, "
                "to_regclass('r3a.resident_onboarding_events') AS events")).fetchone()
            self.assertIsNone(row["packets"])
            self.assertIsNone(row["events"])
            ledger = await (await conn.execute(
                "SELECT 1 FROM r3a.schema_migrations WHERE version='019_resident_onboarding.sql'"
            )).fetchone()
            self.assertIsNone(ledger)

        # Upgrade after rollback must reapply exactly 019 and then remain idempotent.
        self.assertEqual(["019_resident_onboarding.sql"], await self.store.migrate())
        self.assertEqual([], await self.store.migrate())

        actor = OnboardingActor("principal:test-hr", "HR", "session:test-hr")
        identities = {
            "test://evidence/hr/r3:synthetic-analyst": "r3:synthetic-analyst",
            "test://evidence/hr/r3:synthetic-designer": "r3:synthetic-designer",
        }
        service = ResidentOnboardingService(
            self.repository,
            authorize=lambda _actor, _action, _packet: True,
            verify_domain_evidence=lambda _actor, domain_id, domain: (
                {"resident_id": identities[domain["evidence_refs"][0]]}
                if domain_id == "identity" and domain["evidence_refs"][0] in identities else False),
            verify_activation_evidence=lambda _actor, _packet: False,
        )

        synthetic_template = json.loads(SYNTHETIC_FIXTURE.read_text(encoding="utf-8"))
        created_packets = []
        for slug, title in (("analyst", "Research Analyst"), ("designer", "Product Designer")):
            packet_id = str(uuid.uuid4())
            packet = new_onboarding_packet(
                packet_id=packet_id, create_idempotency_key=f"request-{slug}-{packet_id}",
                resident_id=None, display_label=f"Synthetic {title}", requested_role=title,
                request_source_ref=f"test://request/{slug}", created_at=NOW)
            # The versioned general fixture demonstrates the same request shape.
            self.assertEqual(synthetic_template["schema_id"], packet["schema_id"])
            created = await service.create(
                packet, actor=actor, correlation_id=str(uuid.uuid4()),
                reason_ref="test://reason/request", evidence_refs=[f"test://request/{slug}"])
            replay = await self.repository.create_packet(created, created["audit"][-1])
            self.assertEqual(created["packet_id"], replay["packet_id"])
            created_packets.append((packet, created))
            associated = await service.record_domain(
                packet_id, "identity", domain=_identity_domain(f"r3:synthetic-{slug}"),
                actor=actor, expected_revision=1, idempotency_key=f"identity-{slug}-{packet_id}",
                correlation_id=str(uuid.uuid4()), reason_ref="test://reason/identity",
                event_id=str(uuid.uuid4()))
            self.assertEqual(f"r3:synthetic-{slug}", associated["resident_id"])

        # Different canonical residents can use the same schema/workflow without
        # source changes, and a create retry remains idempotent after identity bind.
        replay_after_identity = await self.repository.create_packet(
            created_packets[0][1], created_packets[0][1]["audit"][-1])
        self.assertEqual("r3:synthetic-analyst", replay_after_identity["resident_id"])
        self.assertNotEqual(created_packets[0][1]["resident_id"],
                            (await self.repository.get_packet(created_packets[1][1]["packet_id"]))["resident_id"])

        # A different packet cannot claim an already-associated canonical identity.
        duplicate_id = str(uuid.uuid4())
        duplicate_request = new_onboarding_packet(
            packet_id=duplicate_id, create_idempotency_key=f"request-duplicate-{duplicate_id}",
            resident_id=None, display_label="Synthetic duplicate", requested_role="Analyst",
            request_source_ref="test://request/duplicate", created_at=NOW)
        await service.create(duplicate_request, actor=actor, correlation_id=str(uuid.uuid4()),
            reason_ref="test://reason/request", evidence_refs=["test://request/duplicate"])
        with self.assertRaises(DuplicateOnboarding):
            await service.record_domain(
                duplicate_id, "identity", domain=_identity_domain("r3:synthetic-analyst"),
                actor=actor, expected_revision=1, idempotency_key=f"identity-duplicate-{duplicate_id}",
                correlation_id=str(uuid.uuid4()), reason_ref="test://reason/identity",
                event_id=str(uuid.uuid4()))
        self.assertIsNone((await self.repository.get_packet(duplicate_id))["resident_id"])

        first = await self.repository.get_packet(created_packets[0][1]["packet_id"])
        summary = public_packet_summary(first)
        self.assertNotIn("evidence_refs", json.dumps(summary))
        self.assertNotIn("test://source/", json.dumps(summary))

        # An event PK collision after a packet INSERT must roll the packet back.
        collision_packet_id = str(uuid.uuid4())
        collision_packet = new_onboarding_packet(
            packet_id=collision_packet_id, create_idempotency_key=f"request-collision-{collision_packet_id}",
            resident_id=None, display_label="Synthetic collision", requested_role="Analyst",
            request_source_ref="test://request/collision", created_at=NOW)
        collision_event = {
            "event_id": first["audit"][0]["event_id"],
            "idempotency_key": collision_packet["create_idempotency_key"],
            "correlation_id": str(uuid.uuid4()), "actor_ref": actor.principal_ref,
            "actor_role": actor.role, "action": "resident.onboarding.request",
            "from_state": None, "to_state": "REQUESTED", "expected_revision": 0,
            "occurred_at": NOW, "reason_ref": "test://reason/request",
            "approval_ref": None, "evidence_refs": ["test://request/collision"],
            "domain_id": None, "payload_digest": None,
        }
        collision_packet["audit"].append(collision_event)
        with self.assertRaises(psycopg.errors.UniqueViolation):
            await self.repository.create_packet(collision_packet, collision_event)
        self.assertIsNone(await self.repository.get_packet(collision_packet_id))

        # A transition event collision must roll the current-state UPDATE back.
        first = await self.repository.get_packet(first["packet_id"])
        colliding_successor = transition_packet(
            first, target_state="IDENTITY_PENDING", actor=actor,
            expected_revision=first["packet_revision"], idempotency_key="collision-transition",
            correlation_id=str(uuid.uuid4()), reason_ref="test://reason/transition",
            evidence_refs=["test://evidence/transition"], event_id=first["audit"][0]["event_id"])
        with self.assertRaises(psycopg.errors.UniqueViolation):
            await self.repository.transition_packet(colliding_successor,
                expected_revision=first["packet_revision"], event=colliding_successor["audit"][-1])
        unchanged = await self.repository.get_packet(first["packet_id"])
        self.assertEqual("REQUESTED", unchanged["state"])
        self.assertEqual(first["packet_revision"], unchanged["packet_revision"])

        stale_successor = transition_packet(
            created_packets[0][1], target_state="IDENTITY_PENDING", actor=actor,
            expected_revision=1, idempotency_key="stale-transition",
            correlation_id=str(uuid.uuid4()), reason_ref="test://reason/stale",
            evidence_refs=["test://evidence/stale"], event_id=str(uuid.uuid4()))
        with self.assertRaises(OnboardingRevisionConflict):
            await self.repository.transition_packet(stale_successor, expected_revision=1,
                event=stale_successor["audit"][-1])

        # Competing valid writes at the same revision serialize through SELECT FOR
        # UPDATE/CAS: one commits and the other observes a revision conflict.
        first = await self.repository.get_packet(first["packet_id"])
        concurrent_expected_revision = first["packet_revision"]
        concurrent = [transition_packet(
            first, target_state="IDENTITY_PENDING", actor=actor,
            expected_revision=concurrent_expected_revision, idempotency_key=f"concurrent-{index}",
            correlation_id=str(uuid.uuid4()), reason_ref="test://reason/concurrent",
            evidence_refs=[f"test://evidence/concurrent/{index}"], event_id=str(uuid.uuid4()))
            for index in range(2)]
        results = await asyncio.gather(*(
            self.repository.transition_packet(candidate,
                expected_revision=concurrent_expected_revision, event=candidate["audit"][-1])
            for candidate in concurrent), return_exceptions=True)
        self.assertEqual(1, sum(isinstance(item, dict) for item in results))
        self.assertEqual(1, sum(isinstance(item, OnboardingRevisionConflict) for item in results))
        first = await self.repository.get_packet(first["packet_id"])
        self.assertEqual(concurrent_expected_revision + 1, first["packet_revision"])

        # Secrets are not packet fields or table values; attempts to serialize an
        # unknown credential payload are excluded by the packet schema.
        stored_text = json.dumps(unchanged, sort_keys=True)
        self.assertNotIn("credential_secret", stored_text)
        self.assertNotIn("access_token", stored_text)
        secret_payload = deepcopy(unchanged)
        secret_payload["credential_secret"] = "synthetic-secret-must-never-persist"
        with self.assertRaises(CapabilityContractError):
            await self.repository.create_packet(secret_payload, secret_payload["audit"][-1])

        # The database trigger also protects event history if an adapter regresses.
        with self.assertRaises(psycopg.errors.RaiseException):
            async with self.pool.connection() as conn, conn.transaction():
                await conn.execute(
                    "UPDATE r3a.resident_onboarding_events SET action='tampered' WHERE packet_id=%s",
                    (unchanged["packet_id"],))

        # The down migration must protect durable packets/events from accidental loss.
        with self.assertRaises(psycopg.Error):
            async with self.pool.connection() as conn, conn.transaction():
                await conn.execute(down_sql)
        async with self.pool.connection() as conn:
            row = await (await conn.execute(
                "SELECT count(*) AS n FROM r3a.resident_onboarding_packets")).fetchone()
            self.assertGreater(row["n"], 0)


if __name__ == "__main__":
    unittest.main()
