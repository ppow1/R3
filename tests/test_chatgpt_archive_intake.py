"""Fixture-only tests for source-read-only archive proposal conversion."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.propose_chatgpt_archive import build_catalog, main
from r3a_plugins.institutional_knowledge.review_store import validate_item_decision


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/knowledge/chatgpt_conversations.sample.json"
WEBSITE_CONTRACT = ROOT / "docs/knowledge-discovery/r3a-knowledge-review-api.v1.json"


class ChatGPTArchiveIntakeTests(unittest.TestCase):
    def setUp(self):
        self.raw = FIXTURE.read_bytes()

    def test_converts_text_messages_to_pending_historical_proposals_with_provenance(self):
        catalog = build_catalog(self.raw, source_label="verified-export-2026-01", source_path="/private/export.json")
        self.assertEqual("r3a.knowledge-review-proposals.v1", catalog["schema_id"])
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(), catalog["intake"]["source_sha256"])
        self.assertFalse(catalog["intake"]["original_modified"])
        self.assertEqual(2, len(catalog["entries"]))
        first = catalog["entries"][0]
        self.assertIn("Historical conversation transcript", first["proposed_canonical_knowledge"])
        self.assertIn("message-u1", first["sources"][0]["location"])
        self.assertIn("message-a1", first["sources"][0]["location"])
        self.assertIn("1760000001.0", first["proposed_canonical_knowledge"])
        self.assertNotIn("hidden metadata", first["proposed_canonical_knowledge"])
        self.assertEqual("defer", first["recommended_disposition"])
        self.assertIsNone(first["decision"])
        self.assertIn("individual-review-required", first["flags"])

    def test_sensitive_markers_are_flagged_and_catalog_is_deterministic(self):
        first = build_catalog(self.raw, source_label="archive-A", source_path="/tmp/archive.json")
        second = build_catalog(self.raw, source_label="archive-A", source_path="/tmp/archive.json")
        self.assertEqual(first, second)
        flagged = next(item for item in first["entries"] if item["title"].endswith("Contact details review"))
        self.assertIn("personal-data-review", flagged["flags"])
        self.assertIn("credential", flagged["flags"])

    def test_charter_protected_relationship_content_cannot_be_promoted(self):
        raw = json.dumps([{"id":"private","title":"Private notes","mapping":{"n":{
            "message":{"id":"m","author":{"role":"user"},
                       "content":{"parts":["Evelyn relationship history is confidential."]}}}}}]).encode()
        entry = build_catalog(raw, source_label="archive-fixture", source_path="/tmp/source.json")["entries"][0]
        self.assertIn("protected-relationship", entry["flags"])
        with self.assertRaisesRegex(PermissionError, "cannot be promoted"):
            validate_item_decision(entry, {"decision":"approve", "individual_review":True, "rationale":"reviewed"})

    def test_rejects_invalid_root_and_empty_provenance_label(self):
        with self.assertRaisesRegex(ValueError, "conversations array"):
            build_catalog(b'{"not":"array"}', source_label="archive", source_path="/x")
        with self.assertRaisesRegex(ValueError, "source_label"):
            build_catalog(self.raw, source_label=" ", source_path="/x")

    def test_cli_writes_separate_catalog_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "conversations.json"
            output = Path(temp) / "pending.json"
            source.write_bytes(self.raw)
            self.assertEqual(0, main([str(source), str(output), "--source-label", "archive-fixture"]))
            self.assertEqual(self.raw, source.read_bytes())
            catalog = json.loads(output.read_text())
            self.assertEqual(2, len(catalog["entries"]))
            with self.assertRaises(SystemExit):
                main([str(source), str(output), "--source-label", "archive-fixture"])

    def test_website_contract_matches_current_provider_and_generic_authority_path(self):
        contract = json.loads(WEBSITE_CONTRACT.read_text())
        self.assertEqual("1.0.0", contract["contract_version"])
        self.assertEqual("1.2.0", contract["provider_version"])
        self.assertEqual("steward_write", contract["operations"]["decide"]["effect_class"])
        self.assertIn("CME", contract["website_binding"]["authorization"])
        self.assertIn("approval", contract["$defs"]["citation"]["required"])
        self.assertIn("source_sha256", contract["$defs"]["citation"]["required"])


if __name__ == "__main__":
    unittest.main()
