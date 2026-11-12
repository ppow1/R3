<!--
R3 CONTROLLED DOCUMENT
File: docs/knowledge-discovery/knowledge_review_proposals.v1.json.provenance.md
Component: R3A-KNOWLEDGE-REVIEW-CATALOG-PROVENANCE
File Revision: 1.0.0
Created: 2026-11-08 UTC (exact time recorded in Git commit)
Created By: Codex GPT-6
Purpose: Record origin and review constraints for the adjacent JSON proposal catalog.
Execution Model: N/A
Observability: JSON schema ID/version, source commit/blob/digests, per-entry source locations.
Dependencies: Adjacent knowledge_review_proposals.v1.json and R3A_AI_GUIDANCE_INVENTORY.md.
Authority: Proposal catalog only; every decision is null and recommendations are non-authoritative.
Changed: 2026-11-08 | R3A-KNOWLEDGE-DISCOVERY | Codex GPT-6 | Add JSON sidecar provenance.
Supersedes: None
Contracts: r3a.knowledge-review-proposals.v1.
Tests: tests/test_knowledge_review_batches.py.
History/Predecessor: None; new file.
-->
The adjacent JSON file is a source-grounded proposal snapshot created from the exact repository revisions cited inside each source record. For sources with a retained Git blob SHA but no captured raw SHA-256, the GitHub commit and blob reference are preserved. `decision` is null for every item. `recommended_disposition` is a review recommendation only; the catalog itself cannot authorize approval, rejection, deferral, or ingestion. Before any future approval or ingest, re-fetch the cited source revision and confirm its digest, current authority, and source location.
