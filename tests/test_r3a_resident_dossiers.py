"""Tests for source-grounded resident dossier contracts and integration adapters."""

# R3 CONTROLLED SOURCE
# File: tests/test_r3a_resident_dossiers.py
# Component: R3A-RESIDENT-DOSSIERS-TESTS
# File Revision: 1.0.0
# Created: 2026-11-08 UTC (exact creation time not captured)
# Created By: Codex GPT-6
# Purpose: Cover roster data shape, prompt/config composition, privacy, governance, memory and epistemics.
# Execution Model: unittest; local fixtures and temporary directories only.
# Observability: Assertions report contract failures without connecting to production or external services.
# Dependencies: Python standard library; r3a_runtime.residents; data/residents.
# Authority: Steward directive; tests cannot certify live authoritative roster or operational readiness.
# Changed: 2026-11-08 UTC | CHARACTER-ARCHITECTURE | Codex GPT-6 | Add dossier architecture regressions.
# Supersedes: None
# Contracts: r3a.resident.dossier.v1; r3a.resident.prompt-composition.v1; memory/relationship/epistemic v1
# Tests: python3 -m unittest tests.test_r3a_resident_dossiers
# History/Predecessor: New file.

from __future__ import annotations

import json
import sqlite3
import shutil
import tempfile
import unittest
from pathlib import Path

from r3a_runtime.residents import (
    DossierRepository, DossierError, DossierValidationError, compose_prompt, resolve_personality,
    runtime_binding, validate_dossier, validate_emotional_state,
    validate_memory_entry, validate_relationship, append_memory_correction,
    evolve_relationship, transition_emotional_state,
    reconcile_records, InstitutionalIdentity, ProtectedRelationship, validate_steward_record,
    CharacterRevision, CharacterGovernance, transition_revision, RuntimePrincipal, load_runtime_context,
    validate_runtime_character_context,
    GovernedActor, GovernancePolicy, authorize_workflow_action,
)
from r3a_runtime.residents.validation import validate_epistemic_span
from r3a_runtime.residents.legacy_import import extract_legacy_hr_candidates


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/residents"
DEFAULTS = json.loads((DATA / "global-config.v1.json").read_text())[
    "personality_defaults"
]


class ResidentDossierTests(unittest.TestCase):
    def setUp(self):
        self.repo = DossierRepository(DATA)

    def test_every_materialized_hr_identity_has_a_valid_unique_dossier(self):
        resident_ids = self.repo.list_ids()
        self.assertEqual(len(set(resident_ids)), len(resident_ids))
        self.assertIn("r3:evelyn", resident_ids)
        self.assertIn("r3:gm", resident_ids)
        self.assertNotIn("institution:steward", resident_ids)
        for resident_id in resident_ids:
            dossier = self.repo.get(resident_id)
            validate_dossier(dossier)
            self.assertEqual(dossier["identity"]["resident_id"], resident_id)
            self.assertEqual(dossier["governance"]["approval_status"], "in_review")
            self.assertEqual(dossier["character"]["bible_status"], "not_recovered")

    def test_new_governance_schemas_are_well_formed_json_and_versioned(self):
        expected = {
            "institutional-identity.v1.schema.json": "r3a.institutional.identity.v1",
            "protected-relationship.v1.schema.json": "r3a.resident.protected-relationship.v1",
            "runtime-character-context.v1.schema.json": "r3a.resident.runtime-character-context.v1",
        }
        for filename, contract_id in expected.items():
            schema = json.loads((ROOT / "r3a_runtime/schemas" / filename).read_text())
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            self.assertEqual(schema["$id"], contract_id)

    def test_private_hr_office_and_protected_relationship_facts_are_not_in_git_dossiers(self):
        for resident_id in ("r3:evelyn", "r3:gm"):
            dossier = self.repo.get(resident_id)
            self.assertEqual(dossier["identity"]["display_name"], "Evelyn" if resident_id.endswith("evelyn") else "GM")
            self.assertIn("withheld", dossier["office"]["title"])
            self.assertEqual(dossier["relationships"], [])
            combined = json.dumps(dossier).casefold()
            self.assertNotIn("evelyn and gm", combined)
            self.assertNotIn("relationship milestone", combined)
            self.assertNotIn("onboarding", combined)

    def test_roster_index_is_data_driven_and_not_a_python_name_map(self):
        source = (ROOT / "r3a_runtime/residents/repository.py").read_text()
        for name in ("Grace", "Vicky", "Helen", "Jessica", "Chloe"):
            self.assertNotIn(f'"{name}"', source)
        self.assertEqual(self.repo.list_ids(), tuple(sorted(self.repo._index()["residents"])))

    def test_prompt_composition_is_stable_and_inspectable(self):
        dossier = self.repo.get("r3:grace")
        one = compose_prompt(dossier)
        two = compose_prompt(dossier)
        self.assertEqual(one, two)
        self.assertEqual(one.sha256, compose_prompt(dossier, provider_id="unmatched").sha256)
        self.assertTrue(one.component_refs)
        self.assertIn("VERIFIED", one.text)
        self.assertIn("no operational authority", one.text)

    def test_residents_are_differentiated_by_sourced_office_context(self):
        grace = compose_prompt(self.repo.get("r3:grace")).text
        vicky = compose_prompt(self.repo.get("r3:vicky")).text
        jessica = compose_prompt(self.repo.get("r3:jessica")).text
        self.assertIn("Director of Operations", grace)
        self.assertIn("Engineering Foundry", vicky)
        self.assertIn("Chief Character Architect", jessica)
        self.assertNotEqual(grace, vicky)

    def test_personality_override_precedence_and_validation(self):
        resident = {key: 40 for key in DEFAULTS}
        result, sources = resolve_personality(DEFAULTS, resident, [
            {"dimension": "warmth", "value": 80, "scope": "approved_experiment", "status": "approved"},
            {"dimension": "warmth", "value": 65, "scope": "resident", "scope_ref": "r3:grace", "status": "approved"},
            {"dimension": "humor", "value": 90, "scope": "approved_experiment", "status": "proposed"},
            {"dimension": "formality", "value": 70, "scope": "approved_experiment", "status": "approved"},
        ], resident_id="r3:grace")
        self.assertEqual(result["warmth"], 80)
        self.assertEqual(sources["warmth"], "approved_experiment")
        self.assertEqual(result["humor"], 40)
        self.assertEqual(result["formality"], 70)
        with self.assertRaises(DossierValidationError):
            resolve_personality(DEFAULTS, resident, [
                {"dimension": "warmth", "value": 200, "scope": "resident", "status": "approved"}
            ], resident_id="r3:grace")

    def test_repository_accepts_new_residents_without_runtime_roster_code_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "residents"
            shutil.copytree(DATA, root)
            repo = DossierRepository(root)
            new_dossier = repo.get("r3:vicky")
            new_dossier["identity"]["resident_id"] = "resident:fixture-new"
            new_dossier["identity"]["display_name"] = "Fixture"
            new_dossier["identity"]["source_ids"] = []
            repo.create(new_dossier, actor="test", reason="exercise data-driven extensibility")
            self.assertIn("resident:fixture-new", repo.list_ids())
            self.assertEqual(repo.get("resident:fixture-new")["governance"]["approval_status"], "proposed")

    def test_provider_replacement_preserves_identity_and_continuity(self):
        dossier = self.repo.get("r3:grace")
        dossier["implementation"]["continuity_state_ref"] = "state://resident/r3:grace"
        local = runtime_binding(dossier, "local-provider-a", configuration_revision="config-a")
        cloud = runtime_binding(dossier, "chatgpt-provider-b", configuration_revision="config-b")
        self.assertEqual(local["resident_id"], cloud["resident_id"])
        self.assertEqual(local["continuity_state_ref"], cloud["continuity_state_ref"])
        self.assertNotEqual(local["provider_id"], cloud["provider_id"])
        self.assertEqual(cloud["capabilities"], [])
        self.assertIsNone(cloud["authority_ref"])

    def test_unconfirmed_directory_crosswalk_fails_closed(self):
        with self.assertRaises(KeyError):
            self.repo.resolve_source_id("r3a.execution-profile", "resident.grace")
        self.assertEqual(self.repo.resolve_source_id("r3a.execution-profile", "resident.grace",
                                                     confirmed_only=False), "r3:grace")

    def test_unverified_legacy_test_fixtures_are_not_treated_as_hr_crosswalk(self):
        for value in ("resident:Grace", "resident:Vicky", "resident:Helen",
                      "resident:Evelyn", "resident:GM"):
            with self.assertRaises(KeyError):
                self.repo.resolve_source_id("r3.legacy.hr-principal-map", value)

    def test_personnel_sensitive_and_protected_components_never_enter_prompt(self):
        dossier = self.repo.get("r3:grace")
        private = dict(dossier["prompt_components"][0])
        private.update({"component_id": "private-source", "version": "1.0.0",
                        "classification": "protected", "approval_status": "approved",
                        "text": "SHOULD NEVER APPEAR"})
        sensitive = dict(private)
        sensitive.update({"component_id": "sensitive-source", "classification": "personnel_sensitive",
                          "text": "ALSO PRIVATE"})
        dossier["prompt_components"].extend([private, sensitive])
        text = compose_prompt(dossier).text
        self.assertNotIn("SHOULD NEVER APPEAR", text)
        self.assertNotIn("ALSO PRIVATE", text)

    def test_epistemic_spans_require_provenance_for_verified_and_canon(self):
        base = {"span_id": "span-1", "start": 0, "end": 31,
                "text": "Grace is Director of Operations.", "sources": [],
                "classified_by": "test-fixture", "classified_at": "2026-11-08T00:00:00Z",
                "audit_status": "pending"}
        with self.assertRaises(DossierValidationError):
            validate_epistemic_span({**base, "classification": "VERIFIED"})
        with self.assertRaises(DossierValidationError):
            validate_epistemic_span({**base, "classification": "CANON"})
        validate_epistemic_span({**base, "classification": "UNKNOWN"})
        validate_epistemic_span({**base, "classification": "CANON", "sources": [
            {"source_id": "charter", "locator": "section 2"}
        ]})

    def test_memory_relationship_and_emotion_are_separate_provenance_contracts(self):
        memory = {"memory_id": "m1", "category": "episodic", "content_ref": "mem://1",
                               "source_refs": ["conversation://1"], "occurred_at": "2026-11-08T00:00:00Z",
                               "recorded_at": "2026-11-08T00:01:00Z", "classification": "institutional",
                               "retention_rule_ref": "policy://memory/default", "status": "active"}
        validate_memory_entry(memory)
        correction = append_memory_correction(memory, {"memory_id": "m2", "category": "episodic",
            "content_ref": "mem://2", "source_refs": ["correction://1"],
            "occurred_at": "2026-11-08T00:00:00Z", "recorded_at": "2026-11-08T00:02:00Z",
            "classification": "institutional", "retention_rule_ref": "policy://memory/default",
            "status": "corrected"})
        self.assertEqual(correction["supersedes_memory_id"], "m1")
        self.assertEqual(memory["memory_id"], "m1")
        relationship = {"relationship_id": "r1", "from_resident_id": "r3:grace",
                               "to_resident_id": "r3:vicky", "affinity": 0.1, "trust": 50,
                               "respect": 70, "professional_rapport": 60,
                               "basis_refs": ["experience://shared-work"], "history": []}
        validate_relationship(relationship)
        grown = evolve_relationship(relationship, affinity=0.2, trust=55, respect=70,
                                    professional_rapport=65, experience_ref="experience://delivery",
                                    occurred_at="2026-11-08T01:00:00Z")
        self.assertEqual(grown["history"][0]["trust"], 50)
        self.assertEqual(grown["trust"], 55)
        initial_emotion = {"state_id": "e1", "resident_id": "r3:grace",
                                  "captured_at": "2026-11-08T00:00:00Z", "expires_at": None,
                                  "source_ref": "interaction://1", "values": {"dominant_emotion": "calm", "intensity": 40}}
        validate_emotional_state(initial_emotion)
        next_emotion = transition_emotional_state(initial_emotion, {"state_id": "e2", "resident_id": "r3:grace",
            "captured_at": "2026-11-08T00:02:00Z", "expires_at": None,
            "source_ref": "interaction://2", "values": {"dominant_emotion": "amused", "intensity": 45}})
        self.assertEqual(next_emotion["supersedes_state_id"], "e1")
        with self.assertRaises(ValueError):
            validate_relationship({"relationship_id": "r2", "from_resident_id": "r3:grace",
                                  "to_resident_id": "r3:vicky", "affinity": 0.1, "trust": 50,
                                  "respect": 70, "professional_rapport": 60, "basis_refs": [], "history": []})

    def test_hr_and_character_approval_ownership_and_rollback(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "residents"
            shutil.copytree(DATA, root)
            repo = DossierRepository(root)
            repo.set_approval("r3:grace", "1.0.1", expected_revision="1.0.0",
                              actor="principal:character-architect", owner="character_architecture", approved=True,
                              reason="decision claim recorded; repository is not the authenticating authority")
            character_approved = repo.get("r3:grace")
            self.assertEqual(character_approved["governance"]["approval_status"], "in_review")
            self.assertNotIn("hr", character_approved["governance"]["owner_approvals"])
            repo.set_approval("r3:grace", "1.0.2", expected_revision="1.0.1",
                              actor="Helen", owner="hr", approved=True,
                              reason="personnel review recorded")
            self.assertEqual(repo.get("r3:grace")["governance"]["approval_status"], "in_review")
            repo.rollback("r3:grace", to_revision="1.0.0", expected_revision="1.0.2",
                          actor="Steward", reason="restore prior approved source")
            self.assertEqual(repo.get("r3:grace")["revision"], "1.0.0")
            audit = (root / "audit.jsonl").read_text()
            self.assertIn("revision_added", audit)

    def test_reconciliation_fails_closed_and_distinguishes_projection_conditions(self):
        unavailable = {"source": {"availability": "unavailable", "freshness": "unavailable",
                                   "error": "directory_source_not_configured"}, "residents": []}
        self.assertEqual(reconcile_records(unavailable, ["r3:grace"], [],)[0].state,
                         "authoritative_source_unavailable")
        measured_empty = {"source": {"availability": "measured", "freshness": "fresh"}, "residents": []}
        self.assertEqual(reconcile_records(measured_empty, [], [], hr_access_state="insufficient")[0].state,
                         "hr_access_insufficient")
        self.assertEqual(reconcile_records(measured_empty, [], [], synchronization_state="failed")[0].state,
                         "directory_synchronization_unhealthy")
        snapshot = {"source": {"availability": "measured", "freshness": "fresh"},
                    "residents": [{"resident_id": "directory:grace"}]}
        unresolved = reconcile_records(snapshot, ["r3:grace"], ["r3:grace"])
        self.assertEqual({item.state for item in unresolved}, {
            "hr_identity_crosswalk_missing", "directory_identity_crosswalk_missing"})
        result = reconcile_records(snapshot, ["r3:grace"], [],
                                   confirmed_crosswalk={"directory:grace": "r3:grace"})
        self.assertEqual([(item.institutional_id, item.state) for item in result],
                         [("r3:grace", "dossier_missing")])
        result2 = reconcile_records(snapshot, ["r3:grace"], ["r3:grace"],
                                    confirmed_crosswalk={"directory:grace": "r3:grace"})
        self.assertEqual(result2[0].state, "resident_credential_missing_or_unverified")
        result3 = reconcile_records(snapshot, ["r3:grace"], ["r3:grace"],
                                    confirmed_crosswalk={"directory:grace": "r3:grace"},
                                    credential_ids=["r3:grace"])
        self.assertEqual(result3[0].state, "matched_observed_records")
        duplicates = {"source": {"availability": "measured", "freshness": "fresh"},
                      "residents": [{"resident_id": "x"}, {"resident_id": "x"}]}
        self.assertEqual(reconcile_records(duplicates, ["x"], ["x"],
                                           confirmed_crosswalk={"x": "x"})[0].state,
                         "directory_binding_ambiguous")
        truncated = {"source": {"availability": "measured", "freshness": "fresh",
                                "potentially_truncated": True}, "residents": []}
        self.assertEqual(reconcile_records(truncated, ["r3:grace"], ["r3:grace"],
                                           confirmed_crosswalk={"directory:grace": "r3:grace"})[0].state,
                         "directory_projection_incomplete")

    def test_steward_classification_excludes_resident_lifecycle(self):
        identity = InstitutionalIdentity("configured-authority-id", "Steward", "STEWARD", "governance://steward")
        self.assertEqual(identity.classification, "STEWARD")
        valid = {"classification": "STEWARD", "institutional_id": identity.institutional_id,
                 "authority_ref": identity.authority_ref, "identity_write_policy": "steward_governed_only",
                 "preferences_ref": "governance://steward/preferences"}
        validate_steward_record(valid)
        with self.assertRaises(ValueError):
            validate_steward_record({**valid, "employment_status": "active"})
        resident = InstitutionalIdentity("resident:id", "Resident", "RESIDENT", "hr://resident")
        self.assertEqual(resident.classification, "RESIDENT")
        with self.assertRaises(ValueError):
            validate_steward_record({**valid, "classification": "RESIDENT"})

    def test_protected_relationship_acl_is_separate_from_directory_discovery(self):
        relation = ProtectedRelationship(
            "relationship://protected/record", ("r3:evelyn", "r3:gm"), "protected",
            frozenset({"principal:steward-fixture", "principal:hr-fixture", "principal:character-fixture"}),
            frozenset({"principal:steward-fixture", "principal:hr-fixture"}),
            ("steward.character-architecture-directive",), "1.0.0",
            {"character_development": ("approved_interaction_context",)}, ())
        with self.assertRaises(PermissionError):
            relation.project("principal:resident-fixture", purpose="character_development")
        self.assertEqual(relation.project("principal:character-fixture", purpose="character_development")["facts"], [])
        with self.assertRaises(PermissionError):
            relation.require_edit("principal:character-fixture")
        relation.require_edit("principal:hr-fixture")

    def test_character_revision_requires_configured_independent_self_review_and_activation(self):
        policy = CharacterGovernance(frozenset({"reviewer-7"}), "governance://reviewer-policy",
                                     frozenset({"reviewer-7", "character-editor"}),
                                     frozenset({"character-editor"}), frozenset({"runtime-operator"}))
        own = CharacterRevision("r3:jessica", "1.0.1", "jessica", "in_review",
                                ("source://evidence",), True, True)
        with self.assertRaises(PermissionError):
            transition_revision(own, target_state="approved", actor_id="jessica", governance=policy)
        with self.assertRaises(PermissionError):
            transition_revision(own, target_state="approved", actor_id="character-editor", governance=policy)
        approved = transition_revision(own, target_state="approved", actor_id="reviewer-7", governance=policy)
        published = transition_revision(approved, target_state="published", actor_id="character-editor", governance=policy)
        active = transition_revision(published, target_state="active", actor_id="runtime-operator", governance=policy)
        self.assertEqual(active.status, "active")
        with self.assertRaises(ValueError):
            transition_revision(own, target_state="active", actor_id="runtime-operator", governance=policy)

    def test_hr_character_and_steward_ownership_uses_configured_attested_principals(self):
        policy = GovernancePolicy(
            frozenset({"principal:hr"}), frozenset({"principal:character"}),
            frozenset({"principal:reviewer"}), frozenset({"principal:publisher"}),
            frozenset({"principal:runtime"}), frozenset({"principal:steward"}),
            frozenset({"principal:character"}), "governance://policy/revision-4")
        authorize_workflow_action(GovernedActor("principal:hr", "auth-ref:hr"), policy, "hr.office.assign")
        authorize_workflow_action(GovernedActor("principal:character", "auth-ref:char"), policy,
                                  "character.propose")
        authorize_workflow_action(GovernedActor("principal:character", "auth-ref:char"), policy,
                                  "character.interaction_context.read", target_classification="STEWARD")
        with self.assertRaises(PermissionError):
            authorize_workflow_action(GovernedActor("principal:character", "auth-ref:char"), policy,
                                      "hr.office.assign")
        with self.assertRaises(PermissionError):
            authorize_workflow_action(GovernedActor("principal:character", "auth-ref:char"), policy,
                                      "character.approve", revision_author_id="principal:character",
                                      durable_canon_change=True)
        authorize_workflow_action(GovernedActor("principal:reviewer", "auth-ref:review"), policy,
                                  "character.approve", revision_author_id="principal:character",
                                  durable_canon_change=True)
        with self.assertRaises(PermissionError):
            authorize_workflow_action(GovernedActor("principal:character", "auth-ref:char"), policy,
                                      "character.propose", target_classification="STEWARD")
        with self.assertRaises(PermissionError):
            authorize_workflow_action(GovernedActor("principal:character", "auth-ref:char"), policy,
                                      "steward.identity.update", target_classification="STEWARD")

    def test_runtime_context_resolves_hr_identity_before_applying_prompt(self):
        dossier = self.repo.get("r3:grace")
        dossier["governance"]["approval_status"] = "approved"
        identity = {"institutional_id": "r3:grace", "status": "authoritative", "revision": 7}
        context = load_runtime_context(institutional_id="r3:grace",
            principal=RuntimePrincipal("resident.grace", "conversation", frozenset({"public", "institutional"}), "hr-authz:1"),
            resolve_identity=lambda value: {**identity, "directory_resident_id": "resident.grace"}, load_dossier=lambda value: dossier,
            defaults=DEFAULTS, overrides=[], provider_id="provider:test")
        self.assertEqual(context["resident_id"], "r3:grace")
        self.assertEqual(context["dossier_revision"], "1.0.0")
        self.assertFalse(context["authority_granted"])
        validated = validate_runtime_character_context(context, directory_resident_id="resident.grace")
        self.assertEqual(validated["classification_scope"], ["institutional", "public"])
        with self.assertRaises(PermissionError):
            load_runtime_context(institutional_id="missing", principal=RuntimePrincipal("p", "conversation", frozenset(), "hr-authz:2"),
                resolve_identity=lambda value: {"status": "unavailable"}, load_dossier=lambda value: dossier,
                defaults=DEFAULTS, overrides=[], provider_id="provider:test")
            self.assertIn("revision_rollback", audit)

    def test_vicky_minimum_configuration_is_available_without_fabricated_biography(self):
        vicky = self.repo.get("r3:vicky")
        prompt = compose_prompt(vicky).text
        self.assertIn("Engineering Foundry", prompt)
        self.assertEqual(vicky["character"]["backstory"]["status"], "not_recovered")
        self.assertTrue(vicky["open_questions"])
        self.assertEqual(vicky["relationships"], [])

    def test_grace_casual_social_exchange_is_not_forced_into_work_tracking(self):
        prompt = compose_prompt(self.repo.get("r3:grace")).text
        self.assertIn("may remain social", prompt)
        self.assertIn("do not redirect an invitation to coffee", prompt)

    def test_legacy_hr_import_is_explicit_allowlist_read_only_and_omits_classified_fields(self):
        with tempfile.TemporaryDirectory() as temp:
            db = Path(temp) / "hr.sqlite3"
            connection = sqlite3.connect(db)
            connection.execute("CREATE TABLE hr_records (resident_id TEXT PRIMARY KEY, revision INTEGER, payload TEXT)")
            connection.execute("INSERT INTO hr_records VALUES (?, ?, ?)", (
                "r3:sample", 7, json.dumps({"display_name": "Sample", "office": "Office",
                                            "status": "onboarding", "fields": {
                                                "private": {"value": "never-export", "classification": "confidential"}}})
            ))
            connection.commit()
            connection.close()
            candidates = extract_legacy_hr_candidates(db, ["r3:sample"])
            self.assertEqual(len(candidates), 1)
            self.assertEqual(candidates[0]["approval_status"], "proposed")
            self.assertTrue(candidates[0]["sensitive_fields_present"])
            self.assertNotIn("office", candidates[0])
            self.assertNotIn("lifecycle_status", candidates[0])
            self.assertNotIn("never-export", json.dumps(candidates))
            with self.assertRaises(ValueError):
                extract_legacy_hr_candidates(db, [])
            with self.assertRaises(KeyError):
                extract_legacy_hr_candidates(db, ["r3:absent"])
            reopened = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            self.assertEqual(reopened.execute("SELECT revision FROM hr_records").fetchone()[0], 7)
            reopened.close()


if __name__ == "__main__":
    unittest.main()
