<!--
R3 CONTROLLED DOCUMENT
File: docs/integration/R3A_SIX_WORKSTREAM_LEDGER_20261110.md
Component: R3A-COORDINATOR-INTEGRATION-LEDGER
File Revision: 1.0.0
Created: 2026-11-10 UTC
Created By: R3A Coordinator
Purpose: Record source review, integration, deployment, live acceptance, blockers, and owners across six active R3A workstreams.
Execution Model: Evidence ledger updated from Git, GitHub issues/PRs, systemd, Website APIs, and PostgreSQL.
Observability: Exact source SHA, runtime/config revision, activity and request references, evidence boundaries, and owner actions.
Authority: Steward directive in ppow1/R3 Issue #51, 2026-11-10.
Changed: 2026-11-10 | #51 | Coordinator | Establish six-workstream source/integration/live status and controlled module installation lane.
Supersedes: None.
Contracts: AD-024; R3A module manifest v1.1; institutional directory v1; Steward workspace web v1.
Tests: Documentation/evidence only; verification commands recorded in Issue #51 and source workstream reports.
History/Predecessor: New ledger; generated from observed R3A worktrees and managed runtime on 2026-11-10.
-->

# R3A six-workstream integration ledger — 2026-11-10

**Coordinator baseline:** `integration/r3a-coordinator-v2-20261109` at `b1b38130e796adfe02c7343f71764e9ab0513f6b` (clean; matches origin at inspection).
**Scope:** R3A only. Source/test readiness, integrated source, managed deployment, and live functional acceptance are separate states.

## Live baseline

- The Website, CME/Ring0, and PostgreSQL user services are active. Website health and `/steward` returned HTTP 200; anonymous resident discovery returned HTTP 401.
- Website and Ring0 `WorkingDirectory` point to `/home/admin1/r3a-workstreams/coordinator-20261109-v2`. The Website process started 2026-11-10 04:55:57Z; Ring0/CME started 04:56:08Z. The external runtime configuration digest is `ddb8de5eb022d8e59982e70e50b5062fa0677e1bb71fb07cc5406dc4a3374f5e`.
- **Release metadata discrepancy:** the Website unit still advertises `R3_WEBSITE_BUILD_COMMIT=e2fe437d02dfef75f6d9d08a64c46e806bacebeb` and Ring0 advertises `R3A_IMPLEMENTATION_REVISION=1deaaaf735766d9ff1f53f033eeb58e41baa1794`; these do not identify the checked-out source at `b1b3813`. The source directory/branch and service restart times support that current code was loaded, but deployed build metadata is stale and must be corrected through the normal release procedure.
- The authenticated conversation owned by `steward:camrui` contains completed ordinary Grace turns and a persisted response from the earlier 80B acceptance. Conversation ID `635da82a-96eb-57da-a5e6-78cac6a5a00c` remains available in PostgreSQL. The tool-awareness turn below is separately blocked; do not describe capability-aware chat as accepted.

## Six-workstream status

| Workstream | Exact source/worktree | Independent review | In Coordinator baseline | Deployed/live evidence | Blocker and next owner action |
|---|---|---|---|---|---|
| **Coordinator #51** | `/home/admin1/r3a-workstreams/coordinator-20261109-v2`; `integration/r3a-coordinator-v2-20261109` @ `b1b38130e796adfe02c7343f71764e9ab0513f6b`; clean | Coordinator tests/evidence; no independent review asserted for `b1` | Yes; authoritative baseline | Same checkout serves Website/CME. Ordinary authenticated Grace turns completed and persisted. Tool-awareness turn `80fb105c-2f3a-548c-bdc1-e81da96ad960` is BLOCKED. | Coordinator owns integration, service/release metadata accuracy, and live acceptance after #43 submits its reasoning correction and #56 review gate clears. |
| **Grace Autonomy #43** | Active in-progress worktree `/tmp/r3a-autonomy-reconcile`; branch `engineering/r3a-grace-capability-autonomy-20261110`, HEAD `b1b3813`; working tree has staged, unstaged, and untracked changes. Reviewed checkpoint candidate `aeac6fcc3396b8f148b4b3c87754b6a2459f29a8`; separate earlier candidate `3b636a2ce5883e0e6602c891661d511ec1be6ade`. | Auditor #56 marked `aeac6fc` PASS / READY FOR INTEGRATION (checkpoint behavior only). No review of current uncommitted changes. | `aeac6fc` is not an ancestor of `b1`; not integrated. | The 12:49Z tool question reached configured 80B inference but Grace chose a blocked final. | Autonomy owns an accurate response for empty/available tool inventories and tests. For actual tool invocation, identify an existing read-only operation and request its exact grant via governance; no such effective read-tool grant was found for `resident:grace`. Coordinator integrates/retests only after a pushed, reviewed candidate. |
| **Modular Plugins #46** | `/home/admin1/r3a-modularity-impl-20261109`; `engineering/r3a-modular-plugins-20261109` @ `a224a6b30f1e96b95a65fde6a50d81775f5e5039`; clean | Auditor #56 source PASS; queue records it as Q-01 | `a224a6b` is not an ancestor of `b1`; not integrated | No managed registration/activation demonstrated. | Source contract candidate is ready; its owner can support PR #59 review/compatibility questions. Shared activation remains Coordinator-controlled after independent review and authorization. |
| **Live Modular Integration (#46, separate workstream)** | `/home/admin1/r3a-workstreams/live-modular-integration-20261110`; `integration/r3a-live-modular-integration-20261110` @ `990f90449d460178febed8105f431af24d50a300`; clean; PR #59 based on `b1` | PR #59 has no independent review yet. | No; open, unmerged PR. It carries #46 `a224a6b`, #43 `aeac6fc`, and package/staging work. | Package verification and isolated staged lifecycle passed using fixture SSH data; managed runtime/OctoMiner not contacted. Reported full suite: 481 passed, 10 skipped, 1 known #48 stale-digest failure. | Auditor #56 review is pending and its active window is paused by Steward scheduling. Once resumed/reviewed, Coordinator validates exact managed config/grant scope and runs controlled activation/rollback. |
| **Independent Auditor #56** | `/home/admin1/r3a-workstreams/modularity-auditor-v2-20261109`; `engineering/r3a-modularity-auditor-v2-20261109` @ `5c4b494462da8a826ceb2a1ad710c3ff3517daa9`; clean | Completed PASS for #46 `a224a6b` and #43 `aeac6fc`; audit matrix/queue committed. | Documentation/queue only; no product code integrated. | No runtime activation performed by Auditor. | Per latest Steward scheduling comment, Auditor is paused as an execution slot; review backlog retained. PR #59 review and any new #43/#58 candidates await Auditor resumption. |
| **HR Development #58** | `/home/admin1/r3a-workstreams/hr-development`; `engineering/r3a-hr-development-20261110` @ `65d33c4a22e05393fce6ec985c947e2ec5fceef0`; clean, still at phase-zero baseline. | No R3A #58 candidate reviewed. | No HR-specific change integrated. | Live R3A directory returned Grace only; no Vicky binding verified. Quarantined legacy PR #57 commit `cff4bba7502ed4ad31ebcad97e4b83d056d198db` is not an R3A candidate and was not imported. | HR Development owns the #58 transfer matrix and an R3A-only implementation/path for approved occupant association/onboarding. Do not fabricate Vicky identity, binding, route, credential, or grant. |

## Tool-awareness trace and ownership

Authenticated Steward message `09e2496e-72f2-48bd-9dea-c0bc096f2a5c`, created `2026-11-10T12:49:04.936940Z`, belongs to conversation `635da82a-96eb-57da-a5e6-78cac6a5a00c` and activity `80fb105c-2f3a-548c-bdc1-e81da96ad960`. The activity reached route `octominer1-primary-80b`; model request `f5ba0787-bef8-4500-8cfe-9d6e0f87a05c`, result `chatcmpl-O0ZiVnfbNXtUKCXhtzhxlbNknkxMpQlI`, measured 5.58 seconds. No capability invocation was recorded. Grace returned a blocked decision stating it had no tools available; CME then persisted the correct explicit `BLOCKED` result under `r3a.steward-conversation-response.v1`.

CME constructs resident tools from the canonical capability registry and filters them by `resident:grace` effective grants before inference. Live `Store.require_capability` checks denied all nine configured read/tool operation IDs. The separate `resident.objective.execute` grant permits the resident turn; it does not authorize tool invocation. Thus the concrete boundary is an empty authorization-filtered tool set plus Grace's blocked handling of a tools-availability question, not model transport, directory discovery, or conversation persistence. Coordinator supplied this trace to #43; Autonomy owns the decision behavior. No grant or enforcement change was made.

## Existing HR/directory interfaces

- The Website endpoint is `GET /api/v1/steward/residents` in `r3_app.py`; it derives the caller from the shared AP3 session and forwards `steward.residents.discover` to CME.
- CME resolves the canonical `institutional.directory.discover` operation through the registered capability provider. The provider reads `riverview_authority.institutional_offices`, then joins `office_bindings` to non-retired `resident_occupants`; returned bindings include canonical `principal_id` and `binding_revision`. Its response includes a measured/fresh snapshot digest. This is a read interface; no R3A occupant-association or office-binding write interface was found in the integrated source.
- The fresh roster snapshot at the failed tool turn had one binding: Grace. Absence of Vicky from that result does not distinguish missing/retired occupant from missing office binding. HR's reported `onboarding` row is legacy-source evidence from quarantined PR #57, not active R3A authority. Coordinator posted the interface/blocker details to #58.

## Controlled installation and rollback lane

PR #59's runbook is the current proposed handoff. After required independent review and scoped authorization:

1. Verify the reviewed module bundle and its digest; install the versioned artifact into the selected R3A application root with the existing package installer.
2. Validate the manifest, operation contract, dependency list, and configuration schema. Register the manifest/configuration and declared module capability through the existing managed `capability_operations` / `module.capabilities` configuration; verify the exact read-only grant for the intended principal and resource scope using CME's existing grant controls. Registration/discovery alone grants no authority.
3. Apply the existing CME `config.reload`, install the exact provider version, inspect module status/health, activate through CME's provider lifecycle, then invoke once through normal CME authorization and retain provider, audit, invocation, source/freshness, and evidence-digest records.
4. Roll back by deactivating the candidate version, restoring the prior capability operation/configuration, applying `config.reload`, and reactivating/verifying the retained prior provider version. Keep the previous artifact until readback succeeds.

Staging measured package build 0.42 s, verify 0.39 s, and four lifecycle tests 2.04 s. **Managed install/activation elapsed time, restart need, live invocation, and rollback readback are not measured.** No managed config/grant/provider was changed because PR #59 is unreviewed and its live grant scope/window are not approved. This lane uses CME's existing lifecycle; it does not add a Website/CME registry or scheduler.

## Integration queue

| Queue item | Candidate | Disposition |
|---|---|---|
| Q-01 | #46 manifest v1.1 contract `a224a6b30f1e96b95a65fde6a50d81775f5e5039` | Source review PASS; not in `b1`; carried by PR #59 for exact integration review. |
| Q-02 | #43 checkpoint recovery candidate `aeac6fcc3396b8f148b4b3c87754b6a2459f29a8` | Source review PASS; not in `b1`; carried by PR #59. New tool-awareness correction is separate and not yet a candidate. |
| Q-03 | Live Modular package/staging PR #59 @ `990f90449d460178febed8105f431af24d50a300` | Awaiting Auditor review; no managed activation. Requires exact scoped-grant/config review and Coordinator-run live smoke/rollback after review. |
| Q-04 | HR R3A transfer/onboarding work under #58 | Not integration-ready; HR must inventory PR #57 work product and produce R3A-only source/tests. |
| Parked | Notifications #48 stale artifact digest; source branch reported at `471c2cf836a0ac3ff5f73f46a1aeae5290b9d7bf` | Auditor reports blocked pending corrected digest/source from #48 owner. Separate from chat and module install. |

**No candidate is merged or deployed solely because fixture tests pass.** The authoritative integration baseline remains `b1b3813` until an eligible candidate clears the independent-review gate and is integrated in dependency order.

## P0 Grace tool execution update — 2026-11-10

The original November 8 success was not evidence that `resident:grace` had a tool grant. It was a successful CME invocation by `resident.grace`: activity `bc420253-49cf-4200-82bd-5752035139af`, invocation `44665a22-7b2c-412b-b273-754878c036a9`, audit event `758301bd-b231-4704-a4eb-59c61ad8615c`, provider `r3a.institutional-knowledge@1.1.0`. Its active `institution.knowledge.read` grant is `7c0671cb-9f88-465c-87ea-f28ad009814b`, scope `{}`. The live Website activity `80fb105c-2f3a-548c-bdc1-e81da96ad960` used directory principal `resident:grace`. The live CME authorization checker allows the dotted principal and denies the colon principal; no approved identity crosswalk was found in the inspected directory/execution-profile contracts. Equal names do not establish principal equivalence.

At Ring 0 startup `2026-11-10T04:56:10Z`, configured knowledge providers were durably `FAILED`, causing the capability projection to withhold the operation. Their sanitized lifecycle diagnostic records only `RuntimeError`, so the original startup exception is not recoverable from that record. The pinned artifact/config and a direct worker protocol probe (hello, prepare, activate, health) passed. The Coordinator activated the already configured `r3a.institutional-knowledge@1.2.1` through the existing CME operator lifecycle path; status readback at `14:00:38Z` showed `ACTIVE/healthy`, PID `1523159`. The activation CLI timed out while waiting for its response, but the subsequent CME readback and live invocation confirmed activation. No source deployment or grant change was made.

Managed live objective `5dc8d9e3-d255-41c7-9044-dc72e07b76f9` reached `COMPLETED` at `2026-11-10T14:06:41Z` under configuration revision `ddb8de5eb022d8e59982e70e50b5062fa0677e1bb71fb07cc5406dc4a3374f5e`. Configured route `octominer1-primary-80b` used the actual model `/root/Qwen3-Next-80B-A3B-Instruct-Q4_K_M.gguf`, request `686f3d70-ad99-4133-9445-a7e51ffb27f9`, result `chatcmpl-kC5xt159RDJwI8bPkAtqgi7fuwgWU69L`, measured inference `17204.782 ms`. During this activity Grace invoked `institution.knowledge.read` via CME: invocation `0531c10c-5859-4e17-a52e-97287d2d77c1`, outcome `SUCCEEDED`, provider `r3a.institutional-knowledge@1.2.1`, artifact digest `7b38742249858740850a963c012f8773e66bb07a021744da0c07318ae4c770db`, authorization audit `6155a8b7-f9ef-4e69-b856-9dfad009a279` (allowed). Evidence sources were `knowledge.r3a.module-lifecycle-state-machine` and `knowledge.r3a.process-state-machine`.

This proves authorized tool execution works for `resident.grace` through managed CME and the actual 80B runtime. It does **not** prove the Website chat tool path works: its distinct principal `resident:grace` still has no matching tool grant and CME correctly fails closed. The previous activity `effd8ee7-e3b2-4945-bc08-8c96879a3787` also completed real inference and a successful tool invocation but was blocked by an acceptance-format gap; it is not the accepted demonstration. The final accepted activity above is the evidence of completed execution.

Coordinator posted the exact current-principal/execution-principal reconciliation request to HR Development through #33 (comment `6769485321`) and requested Autonomy's owner determination for generic Website-turn execution/tool awareness in #43 (comment `6769314637`). No alias, grant, authorization enforcement, or source code was changed. Remaining live acceptance is a tool-aware authenticated Website turn after an authoritative existing identity/profile binding or other owner-approved execution identity is established. Ordinary authenticated Website chat remains previously demonstrated and preserved.
