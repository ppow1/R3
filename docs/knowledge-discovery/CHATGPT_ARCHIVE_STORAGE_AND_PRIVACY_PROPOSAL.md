<!--
R3 CONTROLLED DOCUMENT
File: docs/knowledge-discovery/CHATGPT_ARCHIVE_STORAGE_AND_PRIVACY_PROPOSAL.md
Component: R3A-KNOWLEDGE-ARCHIVE-STORAGE-PROPOSAL
File Revision: 1.0.0
Created: 2026-11-08 UTC (exact time recorded in Git commit)
Created By: Codex GPT-6
Purpose: Record archive-source discovery and propose a reviewable durable institutional storage path.
Execution Model: Read-only discovery; proposal only, no archive movement or ingestion.
Observability: Source-location checks and evidence level recorded below.
Dependencies: Approved R3 Charter Revision 2; R3A AP0/AP6 backup boundaries; Knowledge provider 1.2.0.
Authority: Issue #47; storage architecture remains a proposal pending infrastructure and privacy owners.
Changed: 2026-11-08 | AP1-K2 | Codex GPT-6 | Document source discovery and retention/indexing/privacy proposal.
Supersedes: None.
Contracts: r3a.knowledge-review-api.v1@1.0.0; institution.knowledge.read@1.1.0.
Tests: tests/test_chatgpt_archive_intake.py validates parser fixtures only.
History/Predecessor: New file; initial publication recorded in Git.
-->
# ChatGPT archive discovery and storage proposal

## Source inventory and observed state

The approved R3 Charter Revision 2, section 11 (“Data, history, and backups”), requires recovery of the historical three-seat ChatGPT business-account backup, including available conversations, images, and attachments. It requires preserving source, timestamps, original artifacts, and historical/current authority distinctions. Ongoing account backup must use verified supported export mechanisms; the charter explicitly does not assume a full-account conversation API. The charter identifies the required archive class but does not name a filesystem path, host, custodian, export revision, or current archive state.

The R3 and R3A punch lists and parking lots contain no more specific ChatGPT archive location or import batch. The R3 charter is therefore the documented source of the requirement, not evidence that the actual export has been found.

Read-only metadata searches were performed on 2026-11-08 in the current Knowledge checkout, `/home/admin1/R3`, `/home/admin1/backups`, `/home/admin1/.riverview-backups`, and `/home/admin1/riverview-audit-snapshots`, including filenames matching `conversations.json`, `chat.html`, `*chatgpt*`, `*conversation*`, and `*openai*export*`. No matching ChatGPT export was located in those searched locations. Generic Riverview code snapshot archives exist under `/home/admin1`; their names and metadata identify code worktrees/releases, not ChatGPT conversation exports. Their contents were not opened, moved, or changed. This search does not cover other users, Windows profiles, removable media, cloud accounts, or unmounted storage.

## Proposed durable model

Use the existing institutional PostgreSQL authority for conversation metadata, per-message searchable text, source/approval provenance, access policy, and index state. Keep original export archives byte-for-byte in a separate restricted archive/object store on the always-on R3 host; PostgreSQL stores immutable archive URI, export digest, object version, size, original timestamps, and backup/restore manifest references. Do not embed binary attachments in PostgreSQL; store them as separately addressed objects with per-object digests and conversation/message links.

The initial index should be PostgreSQL full-text search over normalized text, with stable conversation/message IDs and time ordering. Add semantic vectors only after retrieval quality, residency, access filtering, and operational cost are demonstrated. Search results must be permission-filtered before scoring and carry archive digest, conversation ID, message IDs, original timestamps, export/import revision, and an evidence digest. Archive text remains historical evidence; retrieval must never promote it to current policy by itself.

## Privacy, retention, and recovery controls

- Separate archive-original, normalized-index, and proposal/approved-knowledge access. Default to Steward and explicitly granted resident scopes; no public or general website exposure.
- Classify export contents as restricted personal/institutional data before parsing. Keep private HR, credentials, relationship material, and sensitive attachments out of general Knowledge. Detecting a sensitive pattern is a review aid, not proof that content is safe.
- Parse locally from a verified source without modifying it. Generate pending proposals only. Require an authenticated Steward decision through the existing CME `steward_write` path before any material becomes general searchable Knowledge. Conversation-derived material should be individually reviewable and labeled historical.
- Define retention, correction, deletion, legal hold, access review, encryption-key ownership/rotation, and cryptographic-erasure behavior with the Steward/privacy owner before retaining raw archives on a new service; these policy details are not yet resolved by this proposal.
- Keep an encrypted, independently restorable copy on a second failure domain, with manifest, source and object checksums, database backup, restore tests, and retention schedule. AP0 D9 supports operator-invoked isolated `pg_dump`; scheduled off-host retention and disaster recovery are AP6 work and must not be represented as already implemented.
- Never move or delete the development-machine originals as part of discovery. Before any copy, record exact path, owner, size, modification time, export format, checksum, and verified destination; keep a read-only source until a restore/readability check and Steward approval are recorded.

## Intake pipeline and acceptance boundary

[`scripts/propose_chatgpt_archive.py`](../../scripts/propose_chatgpt_archive.py) reads a supplied ChatGPT `conversations.json` file (bounded prototype limit: 256 MiB) and writes a separate `r3a.knowledge-review-proposals.v1` catalog. Example: `python3 scripts/propose_chatgpt_archive.py /verified/read-only/conversations.json /restricted/staging/archive-proposals.json --source-label historical-business-export-2020`. It computes a digest of the exact input bytes, preserves conversation/message identifiers and timestamps as source locations, excludes non-text attachment payloads, marks candidates historical and individually review-required, and never writes a decision or authoritative knowledge item. The catalog can be imported as pending proposals using the existing `scripts/import_knowledge_proposals.py`; all promotion remains subject to the existing generic CME authorization and Knowledge provider. Before production-scale intake, replace the bounded in-memory pilot parser with streaming ingestion and separately handle attachment objects under the same archive manifest.

The pipeline has synthetic fixtures only. It has not parsed an actual account export, and no actual ChatGPT archive was found during the scoped search above. The parser's pattern checks are not a substitute for human privacy review or a complete sensitive-data classifier.
