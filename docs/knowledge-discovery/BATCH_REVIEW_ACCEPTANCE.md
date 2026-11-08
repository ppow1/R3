<!--
R3 CONTROLLED DOCUMENT
File: docs/knowledge-discovery/BATCH_REVIEW_ACCEPTANCE.md
Component: R3A-KNOWLEDGE-BATCH-REVIEW-ACCEPTANCE
File Revision: 1.0.0
Created: 2026-11-08 UTC (exact time recorded in Git commit)
Created By: Codex GPT-6
Purpose: Provide a runnable review-interface check and distinguish it from pending authorized institutional acceptance.
Execution Model: Local static web server and browser.
Observability: Rendered batches, per-entry draft records, localStorage resume, exported JSON.
Dependencies: Python 3; modern browser; proposal catalog and review UI in this repository.
Authority: Interface acceptance only. The local actions are not Steward approvals and do not ingest material.
Changed: 2026-11-08 | R3A-KNOWLEDGE-DISCOVERY | Codex GPT-6 | Document local acceptance procedure and limits.
Supersedes: None
Contracts: r3a.knowledge-review-proposals.v1; local draft schema r3a.knowledge-review-draft.v1.
Tests: Executed through Chrome DevTools against a local static server on 2026-11-08.
History/Predecessor: None; new file.
-->
# Batch knowledge review acceptance procedure

## Run the review surface

From the repository root:

```sh
python3 -m http.server 8765 --bind 127.0.0.1
```

Open `http://127.0.0.1:8765/web/knowledge-review.html`. The page loads the checked-in source-grounded proposal catalog and displays three batches and seven entries. Open each batch's “source documents and revisions” list and each entry's evidence details to review citations, excerpts, authority/freshness, conflicts, and proposed wording.

## Exercise batch decisions, overrides, flags, and resume

Use a clean browser profile or clear the page's local review draft first.

1. Apply “Approve batch” to **R3 source governance and authority boundaries**. Each of its three unflagged proposals receives its own draft entry with a version, timestamp, reason/batch ID, and `local-unverified-draft` marker.
2. Change **Residents should consult relevant existing institutional knowledge** to “Reject item.” Confirm the latest draft status changes to reject and its draft history retains the prior batch-derived approve decision.
3. Apply “Approve batch” to **External review and promotion practices**. Both entries carry `requires-individual-review`; confirm the action reports zero eligible entries and changes neither item's decision.
4. Individually set **Do not silently promote AI classifications into canonical knowledge** to defer and **Legacy execution-first instruction is not current R3A policy** to reject. The item decision controls override any earlier eligible batch decision without removing the earlier event from that local draft's history.
5. Reload the page. Confirm the decisions resume from browser localStorage. Use “Download review draft” to inspect/export the local draft JSON.

## Observed interface check (2026-11-08)

Using the local R3 repository served over HTTP and headless Chrome:

- Loaded **3 batches / 7 proposals** and successfully fetched the JSON catalog (HTTP 200).
- Batch approve set **3 per-item draft records** on the unflagged R3 batch.
- An item override retained **one prior decision** in that item's local history.
- Batch action on the fully flagged external-reference batch left the draft count unchanged at **3**.
- A following explicit individual reject and defer produced latest draft counts **2 approve, 2 reject, 1 defer**; page reload restored “Draft: approve” for the first item.

These are browser interaction observations only. They were run in an isolated local browser profile; no real Steward identity was authenticated and no institution decision or promotion was written.

## Pending institutional acceptance

The actual acceptance requirement—authenticated Steward decisions durably recorded per proposal, only approved items promoted idempotently through the authorized Knowledge path, and approved content retrieved with provenance—cannot run yet. At this revision the Knowledge provider exposes only `institution.knowledge.read@1.1.0`, and no durable Knowledge review/decision/ingestion operation was found. See [the integration handoff](KNOWLEDGE_BATCH_REVIEW_INTEGRATION.md). Do not treat the local draft steps above as approval evidence. Once the canonical authorized action and persistence contract are integrated, repeat these choices through the existing Steward Access session and verify durable decision and retrieval records.
