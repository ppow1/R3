"""
R3 CONTROLLED SOURCE
File: tests/test_r3a_character_context.py
Component: R3A-CHARACTER-CONTEXT-CONSUMER-TESTS
File Revision: 1.0.0
Purpose: Verify the approved character-context v2 boundary, privacy-safe binding, and pin continuity.
Tests: tests for r3a_runtime.resident_character_context.
"""
import hashlib
import json
import unittest

from r3a_runtime.resident_character_context import (
    character_context_binding,
    require_character_context_pin,
    validate_resident_character_context,
)


def _context():
    prompt = "Calm, direct expression guidance."
    personality = {
        "warmth": 50, "humor": 20, "formality": 70, "assertiveness": 60,
        "curiosity": 65, "spontaneity": 25, "empathy": 70,
        "expressiveness": 45, "professional_directness": 75,
    }
    refs = [["dossier:revision-1", "voice"]]
    sources = ["hr-source:revision-1", "directory-snapshot:revision-9"]
    personality_sources = {key: "dossier:revision-1" for key in personality}
    context_digest = hashlib.sha256(json.dumps(
        {"prompt_text": prompt, "personality": personality,
         "prompt_component_refs": refs, "source_refs": sources,
         "personality_sources": personality_sources},
        ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
    return {
        "contract_id": "r3a.resident.approved-character-context",
        "contract_version": "2.0.0", "resident_id": "r3:grace",
        "directory_resident_id": "resident:grace", "identity_revision": "hr-revision-1",
        "directory_binding_revision": 9, "directory_snapshot_sha256": "a" * 64,
        "directory_source_ref": "directory-snapshot:revision-9",
        "hr_source_ref": "hr-source:revision-1",
        "hr_principal_association_ref": "hr-association:revision-1",
        "office_id": "office:grace", "office_role": "Director of Operations",
        "execution_kind": "inference_activity", "execution_ref": "activity-1",
        "pin_ref": "character-pin:activity-1", "provider_id": "character-context-provider",
        "dossier_revision": "1.0.0", "dossier_sha256": "b" * 64,
        "context_sha256": context_digest, "activation_status": "active",
        "classification_scope": ["public", "institutional"],
        "authorization_ref": "authorization-observation:1", "prompt_text": prompt,
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "prompt_component_refs": refs, "source_refs": sources,
        "personality": personality, "personality_sources": personality_sources,
        "authority_granted": False,
    }


class ApprovedCharacterContextTests(unittest.TestCase):
    def test_valid_context_is_activity_bound_and_binding_omits_character_content(self):
        context = validate_resident_character_context(
            _context(), execution_ref="activity-1", directory_resident_id="resident:grace")
        binding = character_context_binding(context)
        self.assertEqual(binding["contract_version"], "2.0.0")
        self.assertEqual(binding["pin_ref"], "character-pin:activity-1")
        self.assertNotIn("prompt_text", binding)
        self.assertNotIn("personality", binding)

    def test_rejects_activity_or_canonical_directory_identity_mismatch(self):
        with self.assertRaisesRegex(ValueError, "execution boundary"):
            validate_resident_character_context(_context(), execution_ref="different-activity")
        with self.assertRaisesRegex(ValueError, "directory identity"):
            validate_resident_character_context(
                _context(), execution_ref="activity-1", directory_resident_id="resident:vicky")

    def test_rejects_changed_content_digest_and_inactive_context(self):
        altered = _context()
        altered["prompt_text"] += " changed"
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            validate_resident_character_context(altered, execution_ref="activity-1")
        inactive = _context()
        inactive["activation_status"] = "in_review"
        with self.assertRaisesRegex(ValueError, "only approved active"):
            validate_resident_character_context(inactive, execution_ref="activity-1")

    def test_continuation_requires_the_same_context_pin(self):
        binding = character_context_binding(validate_resident_character_context(
            _context(), execution_ref="activity-1"))
        state = {"model_turns": [{"usage": {"resident_character_context": binding}}]}
        require_character_context_pin(binding, state)
        with self.assertRaisesRegex(ValueError, "differs from its pinned revision"):
            require_character_context_pin(None, state)


if __name__ == "__main__":
    unittest.main()
