<!--
R3 CONTROLLED DOCUMENT
File: docs/integration/R3A_CROSS_WINDOW_BACKLOG_INDEX.md
Component: R3A-CROSS-WINDOW-BACKLOG-INDEX
File Revision: 1.0.0
Created: 2026-11-11T18:57:15Z
Created By: Codex GPT-6, R3A Coordinator
Purpose: Provide a durable, evidence-linked view of cross-window work, review disposition, integration readiness, deployment queue, ownership, and dispatch continuity.
Execution Model: N/A; evidence index only.
Observability: Exact source/artifact revisions, review states, runtime identities, dependencies, and owner actions are linked below.
Dependencies: Approved R3A Master Roadmap, Punch List, Architecture Charter, module/state contracts, and Issues #43/#46/#47/#48/#49/#50/#51/#56/#58/#61/#62/#63.
Authority: Subordinate to approved architecture and Steward decisions. It does not grant deployment authority or replace source workstream records.
Changed: 2026-11-11T18:57:15Z | STEP-77/86/92 | Codex GPT-6 | Establish canonical cross-window backlog evidence index and serial release queue.
Supersedes: None; status-only predecessor is docs/integration/R3A_SIX_WORKSTREAM_LEDGER_20261110.md, retained as historical evidence.
Contracts: R3A Master Roadmap 1.0.3; Punch List 1.0.6; MOD-001–MOD-010; STM-001–STM-007; AD-024; AP0 specification; lifecycle and acceptance policy.
Tests: Documentation consistency review and git diff --check; no runtime behavior changed.
History/Predecessor: New document at source baseline 2cc3fe3aabad88c95a5e6489c633cb01472f7c7f.
-->

# R3A cross-window backlog and release index

**Evidence snapshot:** 2026-11-11 18:57 UTC. This index tracks cross-window evidence and next actions; normative requirements remain in the approved documents linked below. Status can change as owners publish new commits and review results.

## Authority and status rules

- Normative sources: [Architecture Charter](../architecture/R3A_ARCHITECTURE_CHARTER.md), [Master Roadmap](../architecture/R3A_MASTER_ROADMAP_AP0_AP6.md), [Punch List and Parking Lot](../architecture/R3A_PUNCH_LIST_AND_PARKING_LOT.md), [AP0 specification](../architecture/R3A_AP0_TECHNICAL_SPECIFICATION.md), [Module Lifecycle and Contract Specification](../architecture/R3A_MODULE_LIFECYCLE_AND_CONTRACT_SPEC.md), [State Machine and Diagnostic Contract](../architecture/R3A_STATE_MACHINE_AND_DIAGNOSTIC_CONTRACT.md), [Bounded Testing and Acceptance Policy](../architecture/R3A_BOUNDED_TESTING_AND_ACCEPTANCE_POLICY.md), and the [Architectural Decision Log](../architecture/R3A_ARCHITECTURAL_DECISION_LOG.md).
- This file is an evidence index, not a second roadmap, authorization registry, issue tracker, or deployment approval. Issue/PR and module-owned handoff records remain authoritative for their own source evidence.
- Distinguish **source complete**, **independently reviewed**, **integrated**, **packaged**, **release-authorized**, **deployed**, and **live accepted**. Tests or a healthy endpoint alone do not establish deployment/live acceptance.
- `DONE` requires an exact reviewed source and immutable artifact, verified install/config/dependency/rollback information, Coordinator handoff, applicable release authorization, and operational acceptance. **No candidate in this snapshot meets the full `DONE` bar.**
- Queue progression is serial: audit exact package → compatibility preflight → stage → explicit release authorization → install/activate one candidate → live verify → rollback/readback if it fails → only then advance. No bridge, listener, parallel deployment, or competing tracker is introduced here.

## Baseline and runtime identity

| Plane | Exact identity | Verified state |
|---|---|---|
| Frozen/deployed core | `89eda1331b96fe40918e4aa67de09c5ae3f45227`; runtime checkout `/home/admin1/r3a-workstreams/releases/r3a-89eda133` | Ring0, CME, Grace 1.2.14 and directory worker processes are observed on the frozen release checkout. This remains distinct from active development source. |
| Active development integration target | `2cc3fe3aabad88c95a5e6489c633cb01472f7c7f`, branch `integration/r3a-live-modular-integration-20261110`, PR #59 | Current source integration target per Auditor. It is not the frozen runtime and is not deployed. |
| Coordinator-only Step 72 candidate | `17d81e575b5e45ca85e5a35eb196f40eaef1fc62`, based on 89 | 514 Python passed, 13 skipped, 2 warnings, 42 subtests; Website suite 23 Python/25 Node. Not deployed; do not treat it as the 2cc integration target. |
| Website live process | User unit `r3a-ap3-website.service`, PID 1997803; cwd `/home/admin1/r3a-workstreams/ap3-website`; Uvicorn on 127.0.0.1:18311; front door `https://192.168.1.155:8311` | Read-only identity endpoint returned HTTP 200 and reports build `3bbe100ed112eb8f24416243a1c798962ac5f083`. The cwd worktree HEAD is `49bb68645568587d9564f27e56f6422a78a9e289` and is dirty; process environment also references `/home/admin1/.local/share/r3a-ap3-website/python`. Exact loaded source is therefore unresolved. Record this as a **release identity discrepancy**, not evidence that either SHA is live source. No restart/config change was made. |
| Website candidate artifact | Source `32077703603fba2a4595348d81b7d1b0ee2472e9`; tar SHA-256 `a23d6c1b961ff976bccbb168e077f31096b999388e64e1510a4b5e0bfcfd18da`; 414 manifest entries | Auditor package integrity PASS, source FAIL. Not deployable and not eligible. |

## Backlog inventory and current disposition

The following inventory counts normative IDs; a status is a snapshot, not a claim that every acceptance criterion is complete.

| Inventory | Scope/count | Current evidence state |
|---|---:|---|
| Master Roadmap | 21 requirements: R3A-001–019 plus R3A-021 and R3A-023. R3A-020 and R3A-022 do not exist in revision 1.0.3. | AP0/AP1/AP2/AP3/AP4/AP5/AP6 rows remain independently gated; R3A-010 has integrated auth/session work but identity association and fresh Steward enrollment remain pending. No phase is declared complete by this index. |
| Governance | R3A-GOV-01, GOV-01A, GOV-02; Punch List also carries GOV-01/02 | Traceability and workstream controls remain normative; issue status cannot override Steward authority. |
| Parking lot | R3A-L001–L015 (15 items) | L014 still says #42/Steward is integration authority until explicit reassignment; current Step 86 assigns Coordinator the serial deployment lane while Steward retains release authority. Reconcile this stale ownership text in the canonical punch list through its owner; do not silently rewrite authority. L015 is approved for implementation, not proof of enrollment. |
| AP0 technical specification | AP0-001–AP0-013 (13) | AP0 runtime/core evidence is in Auditor #56 and the frozen 89 baseline. Freeze/deployment status remains whatever Steward and Auditor have actually authorized; this index does not declare a freeze. |
| Module lifecycle | MOD-001–MOD-010 (10) | Candidate-specific results below; exact package install/recovery evidence is required per module. |
| State/diagnostic contract | STM-001–STM-007 (7) | Candidate-specific durable state/recovery tests exist; no generalized declaration of full conformance is made here. |
| Architecture decisions | AD-001–AD-023 (23) and AD-P01–AD-P09 (9 AP0-M1 planning selections) | Decisions remain normative. AD-P items are planning selections, not operational acceptance. |
| Character workflow | CA-01–CA-11 (11) | Status report last refreshed 2026-11-08 and is stale; see Character Architecture status file and owner for updates. CA-01/02/06–10 have live authority/context/activation dependencies; isolated code or tests do not equal managed acceptance. |

### Workstream and artifact ledger

| Workstream / governing record | Exact source or artifact | Review / integration / live status | Next owner action and dependency |
|---|---|---|---|
| Grace Autonomy #43 | Source `29353c978ed9ea0e9991a264bc222a61fdca2f1c` | Auditor source PASS, 228 passed, 2 strict xfailed. Not installed as a generic resident-executor package. | Autonomy: supply generic installable executor artifact through the established/reviewed lifecycle. Coordinator: reconcile identity and run managed Website acceptance after package and review gates. #43 asks which generic executor install/launch contract exists (comment 6804233688); no replacement interface assumed. |
| Modular Plugins #46 | Original `132b748a311fc2ff717babb39735b19bbc2221fa` FAIL; corrected `399567d5d73b6bccb8f5d13dda5ab4c4fc6e3177` | Corrected candidate re-review requested in #56 comment 6804496324. Original failure: missing/empty target allowed reading all configured telemetry/history records. Corrected v2.1.1 requires host/source selectors and fails closed before collectors; v2.1.0 remains pinned. No managed activation. **Package path/digest for corrected candidate is not established in the reviewed handoff.** | Auditor: review exact 399567d and package location. Autonomy/CME: pass authoritative host+source target under approved contract. Coordinator: only then preflight and stage under lifecycle runbook. |
| Knowledge #47 | Package `5b84e756cd18eb4110f3c3479620d25840e202bd`; Coordinator fallback-removal `4e1acbef8dfa18b8b918e306378efcfb364d2b80` | Provider source review blocked pending current configuration/lifecycle and live authorized retrieval. Focused 27 pass; package tree 221 pass; fallback removal focused 42 pass and suite 490 passed/11 skipped/1 notification failure. No live managed retrieval accepted. | Knowledge owner + Coordinator: demonstrate exact current CME config, registered provider lifecycle and authorized retrieval; preserve generic audit/evidence behavior. |
| Notifications #48 | Current package `artifacts/r3a-notification-delivery-1.0.0.tar.gz`, source candidate `61b167bf4d55fd52767220828da6c0d6b418ed64`; archive SHA-256 `e3d38c9d32d4ac2ad96416cb16f3bc1d3cd8f55279fd40f6c75f3613cc312ab5` | Previous source `e2782c7` FAIL due `store.py` pin mismatch; correction fixes canonical LF hash `059a1ef…` and adds regression. Exact review request #56 comment 6804385074 is pending. Package tests 57 passed/5 skipped; cross-module Windows subset 61 passed/12 failed due pinned artifact digests with autocrlf. No read activation/live use; write path blocked by generic AP3 `steward_write` caller contract. | Auditor: review exact source+archive. #46/Coordinator: establish reviewed server-derived AP3 session-principal contract; Notifications: preserve exact grants/recipient checks, no wildcard/person-specific exception. |
| Website #51 | Package `artifacts/releases/r3a-website-32077703603fba2a4595348d81b7d1b0ee2472e9.tar.gz`, source `32077703603fba2a4595348d81b7d1b0ee2472e9`; package SHA above | Exact package integrity PASS, source FAIL at `web/steward-workspace-api.mjs:450`: hardcoded disabled “Assign work to Grace” button in generic conversation toolbar. Focused extracted package 26 Python + 28 Node passed; broad suite 3 failures, 2 errors, 5 skipped. | Website owner: remove placeholder or implement contract-backed resident-neutral capability UI; add non-Grace regression. Also correct health `repository_present:false` discrepancy while preserving all 414 entries and 20 locked dependencies; rebuild, exact re-audit, then Coordinator release preflight. |
| HR Development #58 | Source bundle `artifacts/r3a-hr-onboarding-candidate-e618dd75334b.tar.gz`, branch head `f3ead73bc1ed3bc86bd64bcddd95fbe858e58f12`; embedded source `e618dd75334b3b7d5ed8216a4d2ca5867d83c2c0`; archive SHA `47de58e08c453749a9e68a558c365f31beafa5b1c603fa0e578728e5b1938ea6`; manifest SHA `93903da39595acd0d9aeb4fa68cd10073f4531159007d1d90167a8abb4d2b19b` | Auditor source/archive checks PASS; **BLOCKED for production integration/activation**. 94 passed, 1 DSN-gated skip, separately 1 passed on disposable PG16. Migration 019 not shared. | HR/authoritative institutional owner must name (1) HR authority owner for provenance-bearing `associate_authority_principal_with_provenance`, (2) directory office-binding writer/owner, (3) production API composition/auth resolver/least-privilege DB role and release procedure; HR owner then publishes deployable exact artifact. Vicky remains not onboarded. Coordinator asked for named owners in #58 comment 6804702380; no authority record was fabricated. |
| CME/Grace idempotency | `11a140b5a7de24752ab7639ba0e0cd3fc456c586` | Auditor PASS on frozen-base source + isolated PostgreSQL, 5 passed. Not reconciled onto active 2cc and not deployed. Live Grace activity currently fails before inference. | Coordinator: reconcile minimally onto 2cc, run combined regressions, exact same-SHA review and obtain controlled deployment approval; no grant expansion. |
| Live Modular / PR #59 | PR #59 head/integration baseline `2cc3fe3aabad88c95a5e6489c633cb01472f7c7`; OctoMiner artifact `r3a.octominer-telemetry@2.0.0`, digest `3c5441e1942d0a769ae5e299571cbf6267b3ac67363cecf6906fe9b6a9c7352b` | Open/unmerged; candidate source audit/managed acceptance pending; latest #46 scope FAIL means not deployment-ready. Reported isolated lifecycle tests; no managed activation. | Auditor review exact PR/source; owner correct target context and install evidence; Coordinator performs serial controlled integration only after gates. Runbook `docs/runbooks/R3A_LIVE_MODULAR_MODULE_LIFECYCLE.md`. |
| Independent Auditor #56 | Latest published queue record commit `a782a5a01347aa2da9a006cdfc8172684b5579ec` | Autonomy `29353c9` PASS; CME `11a140b` PASS (source+isolated PG); HR `f3ead73` BLOCKED; Website `3207770` FAIL; Notifications `61b167` pending exact review; Modular Plugins `399567d` re-review pending; Bridge candidate below FAIL. | Auditor: continue ordered exact-SHA queue; publish outcomes and test/platform evidence. Coordinator does not deploy from PASS alone. |
| Remote Access #49 | Source candidate `16b6230d5b48bb9bd1872f687f43678faeb296d7` | Source PASS (historical #49 review); native auth/deployment partly integrated; live authenticated Steward acceptance, identity association and fresh enrollment pending. | HR/Website/Security owners resolve authoritative identity and enrollment; Coordinator only verifies integration/runtime. |
| Bitwarden #50 | Provider source `ce05b7307f203e0b37e5857228149c56e9353ae4` | Source review PASS; managed use BLOCKED: no `bws` executable, authorized machine token/principal, secret ref, or #49 consumer configuration. No secret fetched. | Security/Steward provides approved machine identity/config; provider owner validates secret reference without exposing values. |
| Character Architecture | Local owner branch `engineering/r3a-character-architecture-20261107` at `da26e98d26ea2ef9bcb6f6755e4f8419e849b69d` | Status doc dated 2026-11-08 is stale. CA-03/04/05/11 have isolated code/test evidence; managed context, canon, HR writer, Vicky/Helen bindings and host activation remain blocked/unverified. | Character owner refreshes exact source/review/deploy/live status against CA-01–11 and coordinates with HR/Website owners; no legacy PR #57 import. |
| Bridge v3 #62 / PR #64 | Candidate `10aa9d8425eb1ac8dd55b562c778401e3e80f9ca` | Auditor FAIL: idempotent replay can misattribute receipt at a different target. Bridge v2 remains rollback. No v3 live/multiwindow/QUEUE acceptance. | Live Modular owner repairs receipt-target correlation, re-review exact SHA and test on authorized Windows host; do not claim bridge acceptance from Linux source tests. |
| Artifact Registry #63 | No canonical registry candidate; issue has no comments in inspected snapshot | **NOT COMPLETE.** Current index is a backlog/evidence index only, not a machine-readable artifact registry or implementation of #63. | Registry owner: establish records, validator and README/AI_HINTS/roadmap/punch-list links; seed Bridge v2/v3 path entries; require `WHERE TO FIND IT` in handoffs. Coordinator supplies the live Website identity evidence above. |
| AP2 Engineering | Roadmap R3A-011/012 and existing handler work; no current accountable Engineering issue was found in this snapshot | Work is not proven live accepted; source/test evidence does not establish actual supervised Engineering workflow. | Coordinator/Steward governance owner: identify current issue/owner for AP2 follow-up and exact handler contract; Engineering executes its domain workflow, Coordinator integrates/accepts. |

## Ordered serial release queue (Step 86/92)

**Current result: NO RELEASE READY. No package may be installed or activated from this snapshot.** The next executable lane action is exact review/rework resolution, not deployment.

1. **Website (#51, Website owner → Auditor #56):** rework `3207770` hardcoded Grace label and health discrepancy; preserve package integrity; produce a new immutable package and exact source/package re-review. On PASS, publish a complete install/rollback command sequence and reconcile live build identity. Website-only restart is permitted only under the established procedure and applicable release authority.
2. **Notifications (#48, Auditor #56):** exact review of `61b167b` plus immutable archive. Any AP3 write route remains blocked on #46's generic caller contract. Do not deploy a write capability or broaden grants.
3. **Modular Plugins (#46, Auditor #56):** exact re-review of `399567d`; verify target fail-closed before collectors and versioned manifest/artifact. Then reconcile authoritative CME target construction on active source before any staged/live read.
4. **HR/Vicky (#58, HR/source authority):** blocked pending named authority and deployable service composition listed above. No Vicky onboarding or production migration is authorized by the source candidate.
5. **Grace executor and CME prerequisite (#43/#51/#56):** CME `11a140b` must first be reconciled to active baseline 2cc, combined-tested, independently reviewed, and separately deployment-authorized. Grace source PASS still lacks the generic resident-executor package/install/launch route and artifact; Autonomy must provide the reviewed package. No grant change is needed/authorized here.
6. **PR #59 / OctoMiner:** wait for exact source/contract review and target-scope fix; then compatibility preflight and stage under the lifecycle runbook. Keep old version for recovery and verify deactivation/config restoration before closing a release.

Per-candidate installer/config/rollback commands must be copied from the module's exact immutable handoff and the existing lifecycle/runbook. The Website candidate has no verified exact package install command yet; do not infer one from the R3 generic plan-only deploy script. No cross-window candidate is currently queued for release.

## Ownership gaps and external dependencies

- **HR source authority:** accountable owner is still unnamed for authoritative HR principal association writer and approval/provenance record.
- **Directory office binding:** existing `institutional.directory.discover` is read-only; an accountable authorized binding writer/approval path has not been identified.
- **Production HR composition:** no deployable API composition, session/auth resolver wiring, least-privilege DB-role provisioning, or exact release/rollback procedure is included in the reviewed bundle.
- **AP3 session caller contract:** current static `allowed_principals` cannot represent a CME-verified per-request Steward session principal for generic `steward_write`. #46 owns generic contract; no wildcard or Website-supplied authority.
- **Resident executor packaging:** current Grace JSONL supervised entrypoint is not yet shown to load via the generic module package worker that expects provider `create_provider()/invoke()`. #46 must identify the existing contract; #43 owns package implementation.
- **Website source identity:** the live build endpoint, dirty cwd revision, and external `PYTHONPATH` disagree; deployment owner must make release identity unambiguous before/after a Website release.
- **Website command completeness:** exact artifact staging/install/rollback invocation for `3207770` was not present in reviewed handoff; publish and verify it before release queue eligibility.
- **Artifact registry:** #63 implementation and machine-readable records remain absent; this index does not close the requirement.
- **Bridge host validation:** Windows v2 script/active-session behavior is not host-verified from the current Linux Coordinator runtime.
- **Authority staleness:** Punch List L014 still names Steward/#42 as integration authority until reassigned, whereas Step 86 assigns Coordinator the serial deployment lane. Steward release authorization remains required. Record governance clarification through the Punch List owner.

## Dispatch receipt ledger

| Step | Source #61 comment | Wake-up / receipt | Status |
|---:|---:|---|---|
| 72 | `6804153294` | wake-up `6804158002`; ACK `6804165272`; progress `6804234118` | Queue evidence published; no deployment/shared change. |
| 77 | `6804258688` | ACK `6804268014`; result/index preparation continues here | Backlog index required; no second tracker. |
| 82 Autonomy | `6804262244` | wake-up `6804270914`; no target ACK observed; follow-up #43 comment `6804410599`; status #61 comment `6804410999` | **Delivery unconfirmed.** Do not infer that Autonomy received or started. |
| 86 | `6804328525` | wake-up `6804331398`; ACK `6804337814`; follow-up in this snapshot | Serial deployment-lane controls incorporated; no release-ready package. |
| 92 | `6804629168` | wake-up `6804633057`; ACK `6804641037`; result to be posted with this index commit | Queue confirms no release ready; exact blockers retained. |

## Source locations and next executable actions

- **This index:** `docs/integration/R3A_CROSS_WINDOW_BACKLOG_INDEX.md` — complete queue, candidate ledger, ownership and `WHERE TO FIND IT` entry point.
- **Normative roadmap/contracts:** linked in Authority section; retain their requirement IDs and owners.
- **Previous six-workstream snapshot:** `docs/integration/R3A_SIX_WORKSTREAM_LEDGER_20261110.md` — historical as-of 2026-11-10 and superseded for current status only.
- **Website release process:** `docs/runbooks/R3A_LAN_HTTPS_DEPLOYMENT.md`; package handoff on #51 comment 6803968032. Exact source/package command and identity mismatch remain open.
- **Module install/rollback:** `docs/runbooks/R3A_LIVE_MODULAR_MODULE_LIFECYCLE.md`; use only after exact candidate review and authority gates.
- **Coordinator next action:** obtain Website candidate rework/new exact package and Auditor result; in parallel continue exact Notifications/Modular reviews and request named HR source/composition authorities. Do not deploy until one package clears review, install/rollback preflight, compatibility, and release authorization.

## Evidence boundaries

All test counts above are reported with their exact source/owner context; platform-specific Windows failures are not generalized as Linux failures or dismissed. PostgreSQL evidence is disposable isolated data where specified. No production database, grant, service restart, module activation, or shared deployment was changed while preparing this index. Live runtime details above came from read-only process/unit/API inspection; the Website source identity discrepancy remains unresolved.
