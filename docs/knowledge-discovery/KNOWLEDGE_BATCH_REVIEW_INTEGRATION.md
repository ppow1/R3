<!--
R3 CONTROLLED DOCUMENT
File: docs/knowledge-discovery/KNOWLEDGE_BATCH_REVIEW_INTEGRATION.md
Component: R3A-KNOWLEDGE-BATCH-REVIEW-INTEGRATION
File Revision: 1.0.0
Created: 2026-11-08 UTC (exact time recorded in Git commit)
Created By: Codex GPT-6
Purpose: Specify the boundary between proposal review drafts, authenticated Steward decisions, and Knowledge promotion.
Execution Model: Integration handoff; no runtime behavior.
Observability: Current operation inventory and required durable decision evidence.
Dependencies: Issue #43 coordinator; Issue #46 capability contracts; Website Steward Access contract; Knowledge provider 1.1.0.
Authority: Development integration note. Does not grant authority or define a new CME policy.
Changed: 2026-11-08 | R3A-KNOWLEDGE-DISCOVERY | Codex GPT-6 | Record the verified review/ingestion boundary.
Supersedes: None
Contracts: Existing institution.knowledge.read@1.1.0; generic capability invocation; Steward Access.
Tests: Repository search and provider manifest inspection; no runtime write attempted.
History/Predecessor: None; new file.
-->
# Batch knowledge review integration boundary

## What exists

- Knowledge provider `r3a.institutional-knowledge@1.1.0` exposes the existing read operation `institution.knowledge.read@1.1.0`, with capability contract 1.0.0 and `effect_class: read`. It returns source/document revisions, retrieval time, excerpt digests and evidence. Its manifest and provider expose no proposal decision or ingestion operation.
- The current R3A generic `capability.invoke` path owns invocation authorization and durable audits. It is not a knowledge-specific authorization branch.
- The Website Steward Access integration authenticates the Steward session and principal, then calls generic CME invocation at `POST /api/v1/steward/operations/invoke`. It does not currently expose knowledge-item review state or a knowledge promotion operation. Website owns future GUI work; no website worktree was modified.
- Discovery proposal data and `web/knowledge-review.html` can be served locally. The page supports batch and multi-select draft actions, per-item overrides, flag-aware batch exclusion, reload resumption, and export. Browser storage and reviewer labels are unverified local data. The page does not claim these are approvals.

## Precise integration blocker

No existing API or durable store was found for proposal revisions, item decisions, Steward identity, review timestamps, supersession, or idempotent knowledge ingestion. Therefore this branch cannot truthfully record a Steward approval or promote an item through the current read-only operation. Direct database/file mutation, a Knowledge-local identity system, or treating a browser draft as approval would bypass the required boundary and was not done.

## Contract needed from owners

Please coordinate through #43 and #46 and keep CME generic. The integration needs an established, versioned action contract reachable through the existing authenticated Steward Access invocation path, or an equally established Steward authority mechanism, that can:

1. Persist a proposal catalog revision and resumable review session without treating it as approved knowledge.
2. Record each entry disposition independently (`approve`, `reject`, or `defer`) with stable proposal ID/version, source digest(s), authenticated reviewer principal, server timestamp, and optional reason. A batch command must materialize item-level decisions, skip conflict/sensitive/uncertain items unless explicitly handled individually, and retain any per-item override.
3. Promote only explicitly approved entries through the existing Knowledge-owned authorized ingestion path, in an idempotent transaction or with a durable idempotency key. Replays must return the existing result rather than create duplicates.
4. Preserve source URL/path, exact repository commit/blob or content digest, source location, approved canonical text digest, and supersession linkage in retrievable evidence.
5. Emit normal canonical capability invocation/audit/evidence records through CME. No direct Knowledge-specific CME branch, second registry, scheduler, or authentication system is needed.

The operation identifier and schemas are intentionally not invented in this handoff. Knowledge can implement the adapter after #43/#46 establish the invocation shape and Steward Access grants the existing authenticated principal a suitable authority. If the established route uses operation IDs, Website can render this review catalog and send item-level payloads through the existing `POST /api/v1/steward/operations/invoke` contract.

## Batch semantics for the future durable operation

- A batch is a convenience over a versioned list of proposal IDs. It is never a new authority unit.
- The durable result stores an independent decision record per item; each includes batch ID for traceability.
- Batch approve/reject/defer applies only to eligible, explicitly selected items. An entry with conflict, sensitive-data, unclear-authority, or uncertain-source flags is excluded and shown to the Steward. It can receive a decision only through an explicit individual review action.
- A later individual override creates a new decision version; it does not erase the prior batch-derived decision.
- Review sessions can resume from the durable item decision records. Reopening a previously deferred item creates a new review event/version, retaining history.
- Ingestion uniqueness should be keyed on the approved canonical item identity/version plus source digest set, with supersession explicit. Duplicate submit returns the existing ingestion record and evidence references.
