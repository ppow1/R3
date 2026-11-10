<!--
R3 CONTROLLED DOCUMENT
File: docs/audits/R3A_NEXT_INTEGRATION_QUEUE_20261109.md
Component: R3A-AUDIT-INTEGRATION-QUEUE
File Revision: 1.0.6
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
Changed: 2026-11-10T16:30:00Z | R3A-AUDIT-ACTIVE-PRIORITY | Codex GPT-6 | Re-review #59 merged head 2cc3fe3; disposition Website/HR candidates; record missing #43 role-binding fix.
Changed: 2026-11-10T18:15:00Z | R3A-AUDIT-ACTIVE-PRIORITY | Codex GPT-6 | Add reviewed #43/#46 generic executor-role candidates; update current #51/#58 rework and #59 baseline gates.
Changed: 2026-11-10T18:45:00Z | R3A-AUDIT-ACTIVE-PRIORITY | Codex GPT-6 | Verify PR #59 combines cleanly with current Coordinator and passes combined-tree regression suites.
Supersedes: None
Contracts: R3A integration policy; AD-024; approved module, authorization, state and Website contracts.
Tests: N/A; queue record only. Candidate tests are in the linked compliance matrix.
History/Predecessor: New audit artifact; initial publication recorded in Git.
-->
# R3A Next Integration Queue — 2026-11-09

**Status:** One current-base candidate has PASS review. Coordinator owns integration; managed and live acceptance gates remain open.

Current active review dispositions: **#46 de60bc14 PASS and queued; #43 935515e PASS source but its role correction is represented on the newer current-base #46 candidate; PR #59 2cc3fe3 remains PASS source and combines cleanly with current Coordinator c62bb28 in a disposable tree; Website 134518a FAIL; HR 97d75c9 FAIL.** The full-suite #48 artifact digest mismatch remains. PostgreSQL role-promotion and onboarding tests were skipped locally due the absent isolated DB runtime.

## Current integration queue

| Queue ID | Owner / issue | Reviewed SHA | Specifications/contracts | Integration order | Dependencies / conflict | Migration/config needs | Required acceptance | Risk / rollback |
|---|---|---|---|---|---|---|---|---|
| Q-01 Generic primary resident-executor role and registration | #46, branch `engineering/r3a-modular-executor-role-20261110` | `de60bc14a9e25c0e5e11b65f1d5ed1cd4adc7881` | AD-024; module-manifest v1.1; `r3a.resident.executor@1.0.0`; resident binding v1; module lifecycle/registry; CME authorization and directory identity association. | First: direct child of Coordinator baseline `c62bb28d026e1c1cad99c90583f0debae067f2a1`. #43 candidate `935515e` independently passes on prior base and is functionally represented here; do not integrate duplicate role implementation. | Full suite has the known #48 failure. PostgreSQL registration/promotion test requires an isolated DSN and was skipped locally; run it in the controlled integration environment. Preserve provider manifest lifecycle and exact artifact digest. | Coordinator validates managed bootstrap declaration and resident binding against current HR/directory record and compatible active module version. No schema migration expected; existing registry promotion is audited in the existing event ledger. | Focused tests 66 passed/1 skipped; full suite 490 passed/10 skipped/1 #48 failure/34 subtests. Verify bootstrap load, registry role persistence, exact HR association, separately authorized executor invocation with audit IDs, live resident execution, disable/re-enable, and rollback. | Keep resident binding absent/disabled until HR association and grant are confirmed through existing authority paths. Roll back by reverting config/role metadata or module version, no identity/grant mutation by Auditor. |
| Q-02 Live Modular Integration package and lifecycle | #46 / PR #59, branch `integration/r3a-live-modular-integration-20261110` | `2cc3fe3aabad88c95a5e6489c633cb01472f7c7f` | AD-024; module-manifest v1.1; capability/provider lifecycle; CME authorization and module registration; activity and evidence contracts. | Second, after Q-01. Disposable merge with current Coordinator `c62bb28` is clean; tested combined tree ID `c2e2d8b27ee1947f9065d0e0aea850d6d9ed4058`. Coordinator owns producing the real integration commit from this tree; if source differs, Auditor re-reviews the exact resulting SHA. | Four earlier PR conflicts were resolved on 2cc. Host/resource scope remains unenforced and needs Coordinator disposition or target enforcement before activation. #48 digest mismatch remains the sole full-suite failure. | Coordinator-owned managed capability config, exact resident binding, activity-scoped grant, host `octo1` verification and activation. No grant or deployment authorized by source PASS. | Auditor combined-tree focused tests 73 passed; full combined tree 489 passed/10 skipped/1 #48 failure/34 subtests. Verify package digest/install, current-base registration/config reload, provider ACTIVE health, authorized invocation/audit/evidence, measurements, deactivation and rollback. | Keep module disabled until role binding and host/resource scope gate are completed. Roll back through existing lifecycle and package version restore. No managed operation performed by Auditor. |

## Blocked and failed follow-up candidates (not integration queue entries)

- **#43 executor-role binding P0 / SHA `935515e1fe0de9f9b26e9d43cac182045db56526`: PASS source.** Issue #43 comment 6771679125. Use the current-base #46 Q-01 SHA for integration rather than duplicate stale-base replay. Managed HR/directory and authorization acceptance remain Coordinator-owned.
- **Website #51 / SHA `134518a4308bc767f5dbc7ea7a25418d1f51b5d1`: FAIL.** Generic toolbar still hardcodes “Assign work to Grace” at `web/steward-workspace-api.mjs:450`. Website owner must neutralize/remove and add non-Grace mounted-client regression. Comment 6771679555.
- **HR #58 / SHA `97d75c92a6925d8b8efb63cf9d45f0c186288c6f`: FAIL.** Mutable packet owner/authority metadata permits reassignment of Security-owned grants; cyclic local `$ref` raises `RecursionError`. HR owner to fix service and shared validator with regressions. Focused tests 51 passed/1 disposable-PostgreSQL skip; comment 6771680557.
- **Notification artifact pin:** #48 has no corrected pushed SHA. Reproduced expected `107ea3b45871477ab24038114d4f00b1bf92d4b78b2ca4882c859635800780c3` versus actual `8f6584602d6b6a9c2e8e3f01694c75da721b40a0f1b8f64b91ec9bf587da5480` on current PR head `2cc3fe3`; historical baseline also failed with then-source hash `41cd92f...`. Notifications #48 owner to correct the pin and report SHA.
- **Website live acceptance:** source rejection above does not replace the separate authenticated browser gate; browser send/receive, resident isolation, refresh persistence, and real service startup/outage behavior remain Coordinator/Website acceptance work after correction/integration.

Coordinator V2 retains integration/deployment authority. Q-01 is source-review approval only. The OctoMiner module remains disabled; no activation, grant, shared migration, or host operation is approved by this queue. Recheck active issues under #56 comment `6770759266` after each review cycle.
