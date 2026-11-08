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

    def test_all_recovered_public_roster_records_have_valid_unique_dossiers(self):
        resident_ids = self.repo.list_ids()
        self.assertEqual(len(resident_ids), 11)
        self.assertEqual(len(set(resident_ids)), len(resident_ids))
        for resident_id in resident_ids:
            dossier = self.repo.get(resident_id)
            validate_dossier(dossier)
            self.assertEqual(dossier["identity"]["resident_id"], resident_id)
            self.assertEqual(dossier["governance"]["approval_status"], "in_review")
            self.assertEqual(dossier["character"]["bible_status"], "not_recovered")

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
            with self.assertRaises(DossierError):
                repo.set_approval("r3:grace", "1.0.1", expected_revision="1.0.0",
                                  actor="Helen", owner="character_architecture", approved=True,
                                  reason="wrong owner")
            repo.set_approval("r3:grace", "1.0.1", expected_revision="1.0.0",
                              actor="Jessica", owner="character_architecture", approved=True,
                              reason="character review recorded")
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
