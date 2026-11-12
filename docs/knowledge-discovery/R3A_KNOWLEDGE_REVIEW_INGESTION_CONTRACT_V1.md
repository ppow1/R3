<!--
R3 CONTROLLED DOCUMENT
File: docs/knowledge-discovery/R3A_KNOWLEDGE_REVIEW_INGESTION_CONTRACT_V1.md
Component: R3A-KNOWLEDGE-REVIEW-INGESTION-CONTRACT
File Revision: 1.0.1
Created: 2026-11-08 UTC
Created By: Codex GPT-6
Purpose: Define proposal listing, Steward review, durable decision, and approved institutional knowledge retrieval.
Execution Model: Generic CME capability invocation and one PostgreSQL transaction in the existing Knowledge provider.
Observability: Per-item decision records, CME authorization/invocation evidence, event lineage, source digests, and retrieval citations.
Dependencies: Issues #43/#46/#47/#51; canonical capability contracts; AP3 Steward Access.
Authority: Steward directive for governed institutional knowledge ingestion.
Changed: 2026-11-08 | AP1-K1 | Publish implemented provider/capability API and isolated acceptance limits.
Supersedes: 1.0.0 draft.
Contracts: r3a.knowledge-review-api.v1@1.0.0; capability-operation/invocation v1.1.0 Steward effects.
Tests: tests/test_governed_knowledge_contracts.py; scripts/knowledge_ingestion_acceptance.py.
History/Predecessor: Initial contract draft was not yet implementation-accurate.
-->
# R3A Knowledge review and ingestion API v1

This Knowledge-owned API uses the existing `r3a.institutional-knowledge@1.2.0` provider and PostgreSQL authority. It is published for Website integration through authenticated capability discovery and generic invocation. Coordination comments are posted to Issues #43, #46, #47, and #51. No Knowledge-specific CME route, registry, scheduler, or authority store is added.

## Registered operations

| Operation | Revision | Capability contract | Effect | Purpose |
|---|---:|---:|---|---|
| `institution.knowledge.read` | 1.1.0 | 1.0.0 | `read` | Existing Grace retrieval, extended to include active approved items |
| `institution.knowledge.proposals.list` | 1.0.0 | 1.1.0 | `steward_read` | Paginated proposal and decision-history listing |
| `institution.knowledge.proposals.decide` | 1.0.0 | 1.1.0 | `steward_write` | Per-item approval, rejection, or deferral; only approval publishes |

Steward effects are additive generic capability effects. Their invocations require a server-derived allowed Steward principal, a matching existing CME capability grant, and no activity, attempt, work order, or budget reservation. All existing operation effects retain their prior lineage rules. The provider receives principal and CME authorization references only after CME authorization. An operation registration does not create a grant. Current manifest principal is `steward:pat`, matching the AP3 prototype identity example; deployments must align the manifest with the authenticated AP3 principal.

Website uses `GET /api/v1/steward/capabilities` and `POST /api/v1/steward/operations/invoke`. AP3 must overwrite caller identity from its authenticated Steward session. Browser-local draft decisions are never sent or treated as institutional decisions.

## Proposal listing

Input fields are optional `batch_id`, `include_decided` (default true), `limit` (default 50, range 1–200), and `cursor` (proposal ID). The output is `r3a.knowledge-review-proposals.v1` with `batches`, `proposals`, and `next_cursor`. Each batch includes its title, description, project/category, source documents and revisions, summary, conflict/supersession notes, recommended disposition, digest, entry count, and decision-state counts. Each proposal contains its stable ID, proposal revision, aggregate proposal/source digest, batch ID, state, proposed text, flags/conflicts, exact source references, and ordered decision history. Source references preserve repository, path, source revision, commit, Git blob, SHA-256, location, and URL when present. Website groups results by `batch_id`; batch selection is expanded into explicit per-entry decisions.

## Decision request

```json
{
  "decisions": [
    {
      "proposal_id": "r3-knowledge-grounding",
      "proposal_revision": 1,
      "source_digest": "<digest returned by list>",
      "decision": "approve",
      "individual_review": false
    }
  ]
}
```

`decision` is `approve`, `reject`, or `defer`. Each item requires the current revision and digest from the list response. The canonical CME invocation has a stable idempotency key; the provider derives per-item keys from it. A whole submitted set is transactional and duplicate proposal IDs are rejected. Replaying an identical item key returns its original decision; reuse with changed content is rejected. Deferred entries may be reviewed again later, preserving every earlier decision. Approved/rejected entries require a successor proposal. A successor approval may include `supersedes_knowledge_item_id`; the prior active item is deactivated and its link retained.

Any proposal with flags or conflicts requires `individual_review: true` and a nonempty rationale, even when selected in a batch. Bulk selection never decides entries that were not explicitly included. Stale revisions/digests, missing proposals, unauthorized callers, and missing CME grants fail closed before publication.

## Durable records and retrieval

- `r3a.knowledge_proposals` stores imported source-grounded proposals as pending. Catalog import is idempotent and never records a decision.
- `r3a.knowledge_review_decisions` appends an individual decision with proposal revision, batch, source digest, reviewer principal, timestamp, per-item ID, CME authorization reference, invocation ID, and correlation ID.
- `r3a.institutional_knowledge_items` is the same institutional Knowledge authority used by the existing provider. Only an approve decision inserts an item. The item stores canonical content and digest, source references and digest, approval decision/reviewer/time, and supersession pointer.
- Decision event insertion and approved item publication occur in the same PostgreSQL transaction. Rejected/deferred entries stay in proposal history and never appear in retrieval.
- `institution.knowledge.read@1.1.0` searches active approved items alongside externally configured documents and cites the institutional item URI, item/content digest, proposal/source provenance, and approval identity/time.

## Isolated acceptance

`scripts/knowledge_ingestion_acceptance.py` applies the canonical migration and imports the actual seven-entry proposal catalog into a separate PostgreSQL database. It starts the generic provider child process and exercises proposal list, per-item approve/reject/defer, and existing Knowledge retrieval through `CME.invoke_capability`. For test repeatability it uses prefixed acceptance copies of three real catalog proposals and a local test grant for `steward:pat`. Those records prove the implementation path and are not Steward approvals of the seven real proposals. A live AP3 authenticated review remains a Website/Steward-session handoff.
