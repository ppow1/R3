"""PostgreSQL-backed governed workflow integration test for an isolated dev DB."""

from __future__ import annotations

import copy
import os
import unittest
import uuid
from pathlib import Path

import psycopg

from r3a_runtime.residents.governance import GovernedActor, GovernancePolicy
from r3a_runtime.residents.postgres_repository import PostgresDossierRepository
from r3a_runtime.residents.repository import RevisionConflict
from r3a_runtime.residents.workflow_service import CharacterWorkflowService


TEST_DSN = os.environ.get("R3A_CHARACTER_TEST_DSN")


@unittest.skipUnless(TEST_DSN, "set R3A_CHARACTER_TEST_DSN to an isolated, migrated test database")
class PostgresCharacterWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.resident_id = "r3:test-workflow-" + uuid.uuid4().hex
        source = json_read(Path(__file__).parents[1] / "data/residents/dossiers/grace.v1.0.0.json")
        self.dossier = copy.deepcopy(source)
        self.dossier["identity"].update({
            "resident_id": self.resident_id,
            "display_name": "Workflow Test Resident",
            "identity_status": "provisional_legacy_record_id",
            "source_ids": [{"source_id": "test.integration", "value": self.resident_id,
                             "link_status": "confirmed"}],
        })
        self.dossier["office"].update({"title": "Test Office", "department": "Test"})
        self.dossier["mission"].update({"summary": "Test-only mission", "responsibilities": ["Test workflow"]})
        self.dossier["governance"]["approval_status"] = "proposed"
        self.connection_factory = lambda: psycopg.connect(TEST_DSN)
        self.repository = PostgresDossierRepository(self.connection_factory)
        self.ids = {
            "architect": "principal:test-character-architect",
            "reviewer": "principal:test-independent-reviewer",
            "publisher": "principal:test-publisher",
            "activator": "principal:test-runtime-activator",
            "reader": "principal:test-reader",
        }
        self.policy = GovernancePolicy(
            frozenset(), frozenset({self.ids["architect"]}),
            frozenset({self.ids["reviewer"]}), frozenset({self.ids["publisher"]}),
            frozenset({self.ids["activator"]}), frozenset(), frozenset(),
            frozenset(self.ids.values()), "test://character-governance-policy/v1")

        def resolve(actor, resident_id):
            if resident_id != self.resident_id:
                return {"institutional_id": resident_id, "status": "unknown",
                        "classification": "RESIDENT", "revision": None}
            return {"institutional_id": resident_id, "status": "authoritative",
                    "classification": "RESIDENT", "revision": 1}

        def authorize(actor, action, scope):
            return scope == self.resident_id

        self.service = CharacterWorkflowService(
            self.repository, self.policy, verify_actor=lambda actor: actor.authentication_ref.startswith("test-authentication-reference:"),
            resolve_hr_identity=resolve,
            authorize_capability=authorize)

    def actor(self, role):
        return GovernedActor(self.ids[role], "test-authentication-reference:" + role)

    def test_durable_proposal_review_publish_activation_read_and_history(self):
        author = self.actor("architect")
        reviewer = self.actor("reviewer")
        publisher = self.actor("publisher")
        activator = self.actor("activator")

        self.dossier["revision"] = "1.0.0"
        first = self.service.propose(
            author, self.dossier, expected_active_revision=None,
            reason="Create isolated workflow test dossier",
            source_refs=("test://workflow-integration/source",), durable_canon_change=True)
        self.service.submit_for_review(author, self.resident_id, first,
                                       reason="Submit test revision for independent review")
        with self.assertRaises(PermissionError):
            self.service.approve(author, self.resident_id, first,
                                 reason="Self-approval must fail")
        self.service.approve(reviewer, self.resident_id, first,
                             reason="Independent reviewer approved test revision")
        self.service.publish(publisher, self.resident_id, first, reason="Publish test revision")
        self.service.activate(activator, self.resident_id, first, reason="Activate test revision")
        self.assertEqual(self.service.read(self.actor("reader"), self.resident_id)["revision"], first)
        first_digest = self.repository.revision_digest(self.resident_id, first)
        pin = self.repository.pin_context(
            resident_id=self.resident_id, revision=first, dossier_sha256=first_digest,
            execution_kind="conversation_boundary", execution_ref="conversation:test:turn:1",
            identity_revision="1", directory_resident_id="resident:test", binding_revision=1,
            directory_snapshot_sha256="b" * 64,
            directory_source_ref="directory://snapshot/test/1",
            hr_source_ref="hr://resident/test@1",
            hr_principal_association_ref="hr://association/test@1",
            office_id="office:test", office_role="Test role",
            provider_id="model:test", principal_ref=self.ids["reader"],
        )
        self.assertTrue(pin["created"])
        self.assertEqual(pin["directory_snapshot_sha256"], "b" * 64)
        self.assertEqual(pin["hr_principal_association_ref"], "hr://association/test@1")

        second_dossier = copy.deepcopy(self.dossier)
        second_dossier["revision"] = "1.0.1"
        second_dossier["character"]["development_goals"] = [
            "Test-only proposed character change; not canonical history."]
        second = self.service.propose(
            author, second_dossier, expected_active_revision=first,
            reason="Test a source-bound character development proposal",
            source_refs=("test://workflow-integration/proposal",), durable_canon_change=True)
        self.service.submit_for_review(author, self.resident_id, second,
                                       reason="Submit successor revision for review")
        self.service.approve(reviewer, self.resident_id, second,
                             reason="Independent reviewer approved successor")
        self.service.publish(publisher, self.resident_id, second, reason="Publish successor")
        self.service.activate(activator, self.resident_id, second, reason="Activate successor")

        # Existing executions keep their exact pin across a later safe-boundary activation.
        existing_pin = self.repository.pin_context(
            resident_id=self.resident_id, revision=first, dossier_sha256=first_digest,
            execution_kind="conversation_boundary", execution_ref="conversation:test:turn:1",
            identity_revision="1", directory_resident_id="resident:test", binding_revision=1,
            directory_snapshot_sha256="b" * 64,
            directory_source_ref="directory://snapshot/test/1",
            hr_source_ref="hr://resident/test@1",
            hr_principal_association_ref="hr://association/test@1",
            office_id="office:test", office_role="Test role",
            provider_id="model:test", principal_ref=self.ids["reader"],
        )
        self.assertFalse(existing_pin["created"])
        self.assertEqual(existing_pin["pin_id"], pin["pin_id"])
        with self.assertRaises(RevisionConflict):
            self.repository.pin_context(
                resident_id=self.resident_id, revision=second,
                dossier_sha256=self.repository.revision_digest(self.resident_id, second),
                execution_kind="conversation_boundary", execution_ref="conversation:test:turn:1",
                identity_revision="1", directory_resident_id="resident:test", binding_revision=1,
                directory_snapshot_sha256="b" * 64,
                directory_source_ref="directory://snapshot/test/1",
                hr_source_ref="hr://resident/test@1",
                hr_principal_association_ref="hr://association/test@1",
                office_id="office:test", office_role="Test role",
                provider_id="model:test", principal_ref=self.ids["reader"],
            )

        current = self.service.read(self.actor("reader"), self.resident_id)
        prior = self.service.read(self.actor("reader"), self.resident_id, revision=first)
        self.assertEqual(current["revision"], second)
        self.assertEqual(prior["revision"], first)
        history = self.service.history(self.actor("reader"), self.resident_id)
        self.assertEqual([event["event_type"] for event in history].count("approved"), 2)
        self.assertEqual([event["event_type"] for event in history].count("activated"), 2)
        self.assertEqual(len(self.repository.list_ids()) >= 1, True)
        with self.assertRaises(psycopg.Error):
            with self.connection_factory() as connection:
                connection.execute(
                    "UPDATE r3a.resident_dossier_revisions SET dossier_sha256=%s "
                    "WHERE resident_id=%s AND dossier_revision=%s",
                    ("0" * 64, self.resident_id, first),
                )

        with self.assertRaises(PermissionError):
            protected = copy.deepcopy(second_dossier)
            protected["revision"] = "1.0.2"
            protected_component = copy.deepcopy(protected["prompt_components"][0])
            protected_component.update({
                "component_id": "protected.test", "classification": "protected",
                "text": "test-only protected content",
            })
            protected["prompt_components"].append(protected_component)
            self.service.propose(author, protected, expected_active_revision=second,
                                 reason="Protected material must be withheld",
                                 source_refs=("test://protected-source",),
                                 durable_canon_change=True)

        self.service.rollback(activator, self.resident_id, first,
                              reason="Restore the prior activated version")
        self.assertEqual(self.service.read(self.actor("reader"), self.resident_id)["revision"], first)
        self.assertEqual(self.service.read(self.actor("reader"), self.resident_id,
                                           revision=second)["revision"], second)

        stranger = GovernedActor("principal:test-stranger", "test-authentication-reference:stranger")
        with self.assertRaises(PermissionError):
            self.service.read(stranger, self.resident_id)
        unverified = GovernedActor("principal:test-character-architect", "client-supplied-auth-ref")
        with self.assertRaises(PermissionError):
            self.service.read(unverified, self.resident_id)
        with self.assertRaises(PermissionError):
            self.service.propose(stranger, second_dossier, expected_active_revision=second,
                                 reason="Unauthorized proposal", source_refs=("test://source",),
                                 durable_canon_change=False)

        def steward_identity(actor, resident_id):
            return {"institutional_id": resident_id, "status": "authoritative",
                    "classification": "STEWARD", "revision": 1}
        steward_service = CharacterWorkflowService(
            self.repository, self.policy, verify_actor=lambda actor: True,
            resolve_hr_identity=steward_identity,
            authorize_capability=lambda actor, action, scope: True)
        with self.assertRaises(PermissionError):
            steward_service.read(self.actor("reader"), "institution:steward")


def json_read(path: Path):
    import json
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
