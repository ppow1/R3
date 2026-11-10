<!--
R3 CONTROLLED DOCUMENT
File: docs/audits/R3A_NEXT_INTEGRATION_QUEUE_20261109.md
Component: R3A-AUDIT-INTEGRATION-QUEUE
File Revision: 1.0.3
Created: 2026-11-10T01:26:06Z
Created By: Codex GPT-6, Independent Auditor V2
Purpose: Record independently approved source candidates and their integration gates for Coordinator V2.
Execution Model: Existing GitHub coordination and controlled integration workflow; no service.
Observability: Exact reviewed commit, owner issue, dependencies and acceptance checks for each queued candidate.
Dependencies: R3A Development Backlog Compliance Matrix; AD-024; integration branch and Coordinator acknowledgment.
Authority: Steward Directive — Development Backlog Compliance and Integration Readiness, 2026-11-09.
Changed: 2026-11-10T01:26:06Z | R3A-AUDIT-BACKLOG-V2 | Codex GPT-6 | Publish current evidence-backed integration queue.
Changed: 2026-11-10T02:35:00Z | R3A-AUDIT-BACKLOG-V2 | Codex GPT-6 | Queue #46 v1.1 manifest contract after independent PASS; record #43/#48 integration dependencies.
Changed: 2026-11-10T04:00:00Z | R3A-AUDIT-BACKLOG-V2 | Codex GPT-6 | Add #43 checkpoint-corrected PASS candidate as Q-02 with PostgreSQL regression and managed acceptance gates.
Changed: 2026-11-10T10:30:00Z | R3A-AUDIT-ACTIVE-PRIORITY | Codex GPT-6 | Refresh queue for #43 Grace identity correction and #59 latest runbook reconciliation.
Supersedes: None
Contracts: R3A integration policy; AD-024; approved module, authorization, state and Website contracts.
Tests: N/A; queue record only. Candidate tests are in the linked compliance matrix.
History/Predecessor: New audit artifact; initial publication recorded in Git.
-->
# R3A Next Integration Queue — 2026-11-09

**Status:** One current source candidate has PASS review. Integration is Coordinator-owned and live acceptance remains open.

Current review-ready dispositions: **1 PASS, 1 dependency-BLOCKED, 1 source PASS already included in the PASS candidate, and no current FAIL awaiting rework.** Historical matrix counts refer to earlier review snapshots. Candidate #43 `e0b872e079640e8930cb792ee4df13540a5a6037` is the only PASS queue item. It includes #46 `a224a6b30f1e96b95a65fde6a50d81775f5e5039`; do not queue #46 a second time. #59 `4ec7f542a282208a1ad370b0410e498e92d2f880` is blocked pending #43 integration/reconciliation and managed evidence, so is not a PASS queue item.

## Current integration queue

| Queue ID | Owner / issue | Reviewed SHA | Specifications/contracts | Integration order | Dependencies / conflict | Migration/config needs | Required acceptance | Risk / rollback |
|---|---|---|---|---|---|---|---|---|
| Q-01 Grace identity correction, resident executor and durable handler boundary | #43, branch `engineering/r3a-grace-capability-autonomy-20261110` | `e0b872e079640e8930cb792ee4df13540a5a6037` | AD-024; Modularity Specification v1; `r3a.resident.module-binding.v1`; `r3a.activity-handler.v1`; capability invocation/authorization; authoritative resident directory/HR association; activity ledger/recovery. | First and only current PASS candidate. Coordinator V2 owns integration; #46 v1.1 contract provider `a224a6b30f1e96b95a65fde6a50d81775f5e5039` and checkpoint correction `aeac6fcc3396b8f148b4b3c87754b6a2459f29a8` are ancestors/included. Candidate is based on Coordinator source baseline `d592d1d9e09e05dafb52fac4c598bcf92445fef6`; current Coordinator branch head is `8fed74539db211bdcb9a60a2939cf141ebaf57f5`, documentation-only over that baseline. | No source merge conflict against the stated Coordinator base was reported for this candidate. #59 latest candidate has four merge-tree conflicts with this candidate and must be reconciled after #43. #48 digest pin remains one known full-suite failure. | No new migration or grant. Preserve authoritative HR/directory association and current `resident.grace` executor grant. Registration/binding does not grant authority. | Independent tests: focused `pytest` 74 passed + 4 subtests. Full suite 483 passed, 10 skipped, 1 known #48 digest failure, 34 subtests. Checkpoint DB integration test skipped for absent DSN. Source review confirms public Website identity `resident:grace` is resolved against the authoritative directory/conversation and remains distinct from configured executor/grant subject `resident.grace`; discovery filters configured tools by current authorization and provider health; unsupported scope fails closed; authorization/invocation audit context carries both IDs. New Coordinator ledger records an actual 80B inference plus successful tool invocation/audit for executor `resident.grace`, but also confirms the existing Website principal `resident:grace` path is denied. This is pre-candidate runtime evidence, not post-fix acceptance. After integration, managed acceptance must demonstrate the authoritative Website-to-executor association, truthful authenticated inventory (including no-tools/fail-closed case), bounded resident-selected read, exact grant subject, CME authorization/audit event, provider result/evidence, persisted activity completion/retry, and current deployed SHA. | Identity split is high-impact authorization behavior. Roll back integrated source if a denied invocation is allowed, audit loses either identity, or directory/HR validation is bypassed. No live execution/grant change performed by Auditor. |

## Blocked and follow-up candidates (not integration queue entries)

- **Q-02 / PR #59 Live Modular Integration:** `4ec7f542a282208a1ad370b0410e498e92d2f880`, **BLOCKED** pending #43 integration and conflict reconciliation in `r3a_runtime/cme.py`, `r3a_runtime/db.py`, `tests/test_r3a_institutional_directory.py`, and `tests/test_r3a_telemetry_inbox_demo.py`; current package/runbook focused tests pass (6); full suite has 483 pass/10 skip/1 known #48 digest fail/34 subtests. Coordinator must also resolve host/resource-scope limits and collect managed install/invoke/authorization/rollback evidence.
- **Notification artifact pin:** #48 has no corrected pushed SHA. Reproduced expected `107ea3b45871477ab24038114d4f00b1bf92d4b78b2ca4882c859635800780c3` versus actual `8f6584602d6b6a9c2e8e3f01694c75da721b40a0f1b8f64b91ec9bf587da5480` on #59 `4ec7f54`; historical baseline also failed with then-source hash `41cd92f...`. Notifications #48 owner to correct the pin and report SHA.
- **Other active items:** HR #58 passed only its original transfer slice at `989945deae47979765c859852ce44faa654ed112`; universal onboarding packet work added afterward has no reviewable candidate. Website #51 `923a94bbcf9273e2726e5d3e9b0ad75261d64998` remains blocked on Python API suite dependencies/current baseline reconciliation and authenticated managed chat evidence. See the compliance matrix for evidence and owner actions.

Coordinator V2 retains integration/deployment authority. Q-01 is an independent source-review approval only; it does not establish integration, deployment, managed executor/handler activation, or live acceptance. Recheck active workstream issues after each review cycle under #56 comment `6769145175`.
