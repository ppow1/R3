<!--
R3 CONTROLLED DOCUMENT
File: docs/audits/R3A_NEXT_INTEGRATION_QUEUE_20261109.md
Component: R3A-AUDIT-INTEGRATION-QUEUE
File Revision: 1.0.2
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
Supersedes: None
Contracts: R3A integration policy; AD-024; approved module, authorization, state and Website contracts.
Tests: N/A; queue record only. Candidate tests are in the linked compliance matrix.
History/Predecessor: New audit artifact; initial publication recorded in Git.
-->
# R3A Next Integration Queue — 2026-11-09

**Status:** Two source candidates have PASS review. Integration is dependency-gated; the rows below are queued for Coordinator sequencing, not deployment approval.

The audit found **2 PASS, 2 FAIL, and 13 ALREADY INTEGRATED** among 17 distinct delivered work items. Corrected #43 candidate `aeac6fcc3396b8f148b4b3c87754b6a2459f29a8` passed source review; see Q-02. The 13 integrated units are not queued for duplicate integration. The two failed candidates have been returned through their original issues. Five operational items remain blocked and are not source queue entries.

| Queue ID | Owner / issue | Reviewed SHA | Specifications/contracts | Integration order | Dependencies / conflict | Migration/config needs | Required acceptance | Risk / rollback |
|---|---|---|---|---|---|---|---|---|
| Q-01 Modular Plugins v1.1 role metadata and shared handler contracts | #46, branch `engineering/r3a-modular-plugins-20261109` | `a224a6b30f1e96b95a65fde6a50d81775f5e5039` | AD-024 §3.7; `r3a.module-manifest.v1@1.0.0` and `@1.1.0`; `r3a.resident.module-binding.v1`; `r3a.activity-handler.v1`. | Integrate as the contract producer before #43 consumer Q-02. Dry merge into Coordinator branch `90346ec` has no conflicts. | Corrected #43 candidate `aeac6fc` is Q-02, based on `90346ec`, includes #46 `a224a6b`, and dry-merges cleanly. Source review and an isolated PostgreSQL-backed checkpoint persistence/recovery regression pass. #48 must reconcile its pre-existing notification artifact digest pin for `r3a_runtime/capability_contracts.py` before the full suite can be clean. | No DB migration or managed configuration required for this contract-only step. Integrate before Q-02; do not activate resident/handler roles before the CME consumer is integrated and authorized. | The combined #43 candidate produced 191 focused passes (its opt-in PostgreSQL test skipped without DSN; Auditor separately ran it against a disposable PostgreSQL 16 database: 1 passed). Full suite: 474 passed, 10 skipped, 1 known #48 digest failure. Re-run combined full suite after the #48 pin correction. Live activation requires separate managed CME/PostgreSQL/HR authorization evidence. | Additive v1.1 declarations; v1.0 remains role-free. Revert #46 source before any v1.1 module registration if rollback is needed. No production or live acceptance claimed. |
| Q-02 CME generic resident/activity dispatch and checkpoint recovery | #43, branch `engineering/r3a-autonomy-reconcile-20261109` | `aeac6fcc3396b8f148b4b3c87754b6a2459f29a8` | AD-024; `r3a.resident.module-binding.v1`; `r3a.activity-handler.v1`; capability invocation/authorization; authoritative directory/HR identity; activity ledger and recovery. | After Q-01 #46 contract producer. Candidate is based on Coordinator `90346ec`; #46 `a224a6b` is an ancestor; dry merge is conflict-free. | Q-01 must be integrated first. #48's stale notification artifact digest remains the sole full-suite failure and should be reconciled before claiming green combined regression. No source-level #43 blocker remains. | No new DB migration. Managed configuration must separately bind approved resident/module versions and config digests; grants and HR association remain authoritative and are not created by registration. | Focused set 191 passed (opt-in PG test skipped); Auditor separately ran the persistence/recovery regression against a disposable PG16 DB: 1 passed. Full suite 474 passed/10 skipped/1 known #48 digest failure. Before operational acceptance, prove registered handler/executor activation in managed CME, HR-backed resident association, authorization decisions, durable retry/recovery, and Website path as applicable. | Candidate changes CME/store handling of generic activity checkpoints; retain existing Grace and provider regressions. Roll back candidate code as one release unit if integrated behavior regresses; no live deployment approved by this PASS. |

### Re-entry conditions

- **Coordinator roster/chat source:** resolve the v1 response-schema/version mismatch and generic executor-binding gap; report a corrected SHA on #43/#51 for review.
- **CME generic resident/activity dispatch:** #43 `aeac6fc` passed source review and is Q-02 after #46. Managed activation, HR-backed binding, authorization and live Website use remain separate acceptance gates.
- **Notification artifact pin:** #48 to correct the pre-existing stale hash for `r3a_runtime/capability_contracts.py` (baseline test expected `107ea3…`, actual `41cd92…`; #46 candidate actual `8f6584…`) and report a pushed SHA in #48.

Coordinator V2 retains integration/deployment authority. Q-01/Q-02 are source-review approvals with explicit sequence gates; they do not establish deployment, managed activation, handler use, or live acceptance.
