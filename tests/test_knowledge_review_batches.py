"""
R3 CONTROLLED SOURCE
File: tests/test_knowledge_review_batches.py
Component: R3A-KNOWLEDGE-REVIEW-BATCH-TESTS
File Revision: 1.0.1
Created: 2026-11-08 UTC (exact time recorded in Git commit)
Created By: Codex GPT-6
Purpose: Validate source-grounded batch proposal invariants and draft-only review UI boundaries.
Execution Model: unittest; local JSON and HTML inspection.
Observability: Assertion failures identify invalid catalog, batch, or UI semantics.
Dependencies: Python standard library; review catalog and temporary browser interface.
Authority: Tests only; recommendations never become decisions.
Changed: 2026-11-08 | R3A-KNOWLEDGE-DISCOVERY | Codex GPT-6 | Add focused proposal and batch review regressions.
Changed: 2026-11-08 | R3A-KNOWLEDGE-DISCOVERY | Codex GPT-6 | Assert decisions remain tied to source revisions.
Supersedes: None
Contracts: r3a.knowledge-review-proposals.v1.
Tests: This module.
History/Predecessor: None; new file.
"""
from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "docs/knowledge-discovery/knowledge_review_proposals.v1.json"
UI_PATH = ROOT / "web/knowledge-review.html"


class KnowledgeReviewBatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        cls.html = UI_PATH.read_text(encoding="utf-8")
        cls.entries = {entry["entry_id"]: entry for entry in cls.catalog["entries"]}

    def test_catalog_is_versioned_and_each_proposal_starts_undecided(self):
        self.assertEqual("r3a.knowledge-review-proposals.v1", self.catalog["schema_id"])
        self.assertEqual(1, self.catalog["schema_version"])
        self.assertEqual(7, len(self.entries))
        self.assertEqual(len(self.catalog["entries"]), len(self.entries))
        self.assertTrue(all(entry["decision"] is None for entry in self.entries.values()))
        self.assertIn("proposed", self.catalog["review_state"])

    def test_batches_cover_each_entry_once_and_show_review_summary_fields(self):
        batch_members = [entry_id for batch in self.catalog["batches"]
                         for entry_id in batch["entry_ids"]]
        self.assertEqual(set(self.entries), set(batch_members))
        self.assertEqual(len(batch_members), len(set(batch_members)))
        for batch in self.catalog["batches"]:
            self.assertTrue(batch["title"] and batch["description"])
            self.assertGreater(batch["source_count"], 0)
            self.assertTrue(batch["summary"])
            self.assertTrue(batch["conflicts_and_supersession"])
            self.assertTrue(batch["recommended_disposition"])
            self.assertEqual(len(batch["entry_ids"]), len(set(batch["entry_ids"])))

    def test_proposals_have_revisioned_source_lineage_and_individual_review_flags(self):
        flagged = []
        for entry in self.entries.values():
            self.assertEqual(1, entry["version"])
            self.assertTrue(entry["sources"])
            self.assertIn(entry["recommended_disposition"], {"approve", "reject", "defer"})
            self.assertTrue(entry["proposed_canonical_knowledge"])
            for source in entry["sources"]:
                self.assertTrue(source["repository"] and source["path"])
                self.assertTrue(source["commit"] and source["git_blob"])
                self.assertTrue(source["location"] and source["url"])
                if source.get("sha256"):
                    self.assertEqual(64, len(source["sha256"]))
            if "requires-individual-review" in entry["flags"]:
                flagged.append(entry["entry_id"])
        self.assertTrue(flagged)
        self.assertIn("conflict", self.entries["legacy-execution-first-conflict"]["flags"])
        self.assertIn("out-of-scope", self.entries["cuemastery-authority-is-project-specific"]["flags"])

    def test_local_r3_sources_match_cited_sha256(self):
        for entry in self.entries.values():
            for source in entry["sources"]:
                if source["repository"] != "ppow1/R3" or not source.get("sha256"):
                    continue
                path = ROOT / source["path"]
                self.assertTrue(path.is_file(), source["path"])
                self.assertEqual(source["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())

    def test_ui_supports_resumable_item_drafts_without_claiming_authority(self):
        for phrase in (
            "r3a.knowledge-review.draft.v1",
            "localStorage",
            "data-selected",
            "data-batch",
            "data-item",
            "requires-individual-review",
            "not Steward approvals",
            "promotion is not connected",
            "authority_status: \"local-unverified-draft\"",
            "source_refs: sourceRefs",
            "catalog_revision: catalog.catalog_revision",
            "old.catalog_revision === catalog.catalog_revision",
            "Download review draft",
        ):
            self.assertIn(phrase, self.html)
        self.assertNotIn("fetch(\"/api/v1/steward/operations/invoke\"", self.html)


if __name__ == "__main__":
    unittest.main()
