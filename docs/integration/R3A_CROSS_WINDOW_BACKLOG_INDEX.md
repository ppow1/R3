<!--
R3 CONTROLLED DOCUMENT
File: docs/integration/R3A_CROSS_WINDOW_BACKLOG_INDEX.md
Component: R3A-CROSS-WINDOW-BACKLOG-INDEX
File Revision: 1.0.2
Created: 2026-11-11T18:57:15Z
Created By: Codex GPT-6, R3A Coordinator
Purpose: Provide a durable, evidence-linked view of cross-window work, review disposition, integration readiness, deployment queue, ownership, and dispatch continuity.
Execution Model: N/A; evidence index only.
Observability: Exact source/artifact revisions, review states, runtime identities, dependencies, and owner actions are linked below.
Dependencies: Approved R3A Master Roadmap, Punch List, Architecture Charter, module/state contracts, and Issues #43/#46/#47/#48/#49/#50/#51/#56/#58/#61/#62/#63.
Authority: Subordinate to approved architecture and Steward decisions. It does not grant deployment authority or replace source workstream records.
Changed: 2026-11-11T18:57:15Z | STEP-77/86/92 | Codex GPT-6 | Establish canonical cross-window backlog evidence index and serial release queue.
Changed: 2026-11-11T19:04:05Z | STEP-92 | Codex GPT-6 | Record direct #58 assignment check confirming there is no named assignee for HR authority/composition dependencies.
Changed: 2026-11-11T19:33:42Z | STEP-93/99/101 | Codex GPT-6 | Map existing source owners, update exact review outcomes, and record read-only Website release preflight and rollback gates.
Supersedes: None; status-only predecessor is docs/integration/R3A_SIX_WORKSTREAM_LEDGER_20261110.md, retained as historical evidence.
Contracts: R3A Master Roadmap 1.0.3; Punch List 1.0.6; MOD-001–MOD-010; STM-001–STM-007; AD-024; AP0 specification; lifecycle and acceptance policy.
Tests: Documentation consistency review and git diff --check; no runtime behavior changed.
History/Predecessor: Git blob 2adb415c6fd01565899e695b10e973bd7d94ca75 in commit 200ac93867bfbcc2f08d1173f5cfa23fe0832ea8; source baseline 2cc3fe3aabad88c95a5e6489c633cb01472f7c7f.
-->

# R3A cross-window backlog and release index

**Evidence snapshot:** 2026-11-11 19:33 UTC. This index tracks cross-window evidence and next actions; normative requirements remain in the approved documents linked below. Status can change as owners publish new commits and review results.

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
| Website live process | User unit `r3a-ap3-website.service`, PID 1997803; ExecStart `/home/admin1/R3/.venv/bin/python -m uvicorn r3_app:app --host 127.0.0.1 --port 18311`; cwd `/home/admin1/r3a-workstreams/ap3-website`; front door `https://192.168.1.155:8311` | Read-only API and process environment report build `3bbe100ed112eb8f24416243a1c798962ac5f083`, HTTP 200. Unit started 2026-11-10 20:34 EST; build commit timestamp is 20:24 EST. Current worktree is now **clean**, branch HEAD `8a46332435dbd38feac808a6fe15506fcc2e9718` (commit 2026-11-11 14:06 EST), so it advanced after the running process started. `PYTHONPATH=/home/admin1/.local/share/r3a-ap3-website/python` contains packaged dependencies; a same-cwd resolver check selects `/home/admin1/r3a-workstreams/ap3-website/r3_app.py`. The running process likely loaded the earlier 3bbe source, but no in-process source digest is exposed; exact loaded revision remains unverified. No restart/config change. |
| Website candidate artifact | Current source `6e5f3a6ceea723d0217367c57afd20d9b4c437bd`; `artifacts/releases/r3a-website-6e5f3a6.tar.gz`; SHA-256 `85322406cc44c1796af211176d7b6bd2d2abc17a92d3f511a1c85e534480914e`; 422 entries | Package/extracted verifier and focused 84 Python + 31 Node pass. Auditor exact re-audit requested #56 comment 6804840236, still pending in latest snapshot. Candidate source broad suite: 421 ran, 3 failures, 2 errors, 5 skipped. |

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
| Modular Plugins #46 | Candidate `399567d5d73b6bccb8f5d13dda5ab4c4fc6e3177`, branch `engineering/r3a-modular-plugins-20261109` | **FAIL** exact audit #56 comment 6804764189. Scope tests 12 passed; provider/registry/lifecycle tests 44 passed. Seven v2.1.1 pins verify in Git tree, but all seven change under `core.autocrlf=true`, causing standard loader failure. CME 2cc still passes `target:{}`; provider correctly rejects before collectors. | #46 source window corrects line-ending pin reproducibility and re-review. #51 Coordinator + #43 Autonomy define trusted host/source scope and pass it via approved invocation contract. No managed activation. |
| Knowledge #47 | Source `5b84e756cd18eb4110f3c3479620d25840e202bd` on `engineering/r3a-knowledge-governed-ingestion-20261108`; Coordinator fallback-removal `4e1acbef8dfa18b8b918e306378efcfb364d2b80` | Auditor BLOCKED pending current Coordinator provider/config/lifecycle and real CME authorized retrieval. Focused provider 27 pass; package tree 221 pass; fallback removal focused 42 pass and suite 490 passed/11 skipped/1 #48 digest failure. No live managed retrieval. | #47 Knowledge source window supplies exact current package/config and real evidence source; #51 Coordinator runs authorized retrieval through registered CME provider and records audit/provenance/recovery. |
| Notifications #48 | `artifacts/r3a-notification-delivery-1.0.0.tar.gz`; source `61b167bf4d55fd52767220828da6c0d6b418ed64`; archive SHA-256 `e3d38c9d32d4ac2ad96416cb16f3bc1d3cd8f55279fd40f6c75f3613cc312ab5` | **FAIL** exact audit #56 comment 6804764189. Linux focused 57 passed/5 skipped and package verifies. A `core.autocrlf=true` clone changes pinned `capability.py` hash from `f7409526…` to `60e29635…`; loader fails. No live activation. | #48 source window makes every pinned file line-ending stable, rebuilds, and requests exact review. #46/#51 own generic server-verified AP3 `steward_write` constraint; no wildcard/person-specific exception. |
| Website #51 | Source `6e5f3a6ceea723d0217367c57afd20d9b4c437bd`; package `artifacts/releases/r3a-website-6e5f3a6.tar.gz`; SHA-256 `85322406cc44c1796af211176d7b6bd2d2abc17a92d3f511a1c85e534480914e` | Current exact candidate re-audit pending #56 comment 6804840236. Previous 3207770 pair is superseded. Exact package verifier/extracted runtime and focused 84 Python + 31 Node passed; broad suite 421 ran, 3 fail/2 error/5 skipped. No authenticated live acceptance. | Website source window #51: give exact stage/install/rollback path. Auditor #56: same-SHA archive/source disposition. Coordinator: preflight below. Steward: authorize exact source/archive release if the prior 3bbe authorization does not cover it. |
| HR Development #58 | Current branch `engineering/r3a-hr-vicky-20261110`, HEAD `ac163ef3306522c9d2f0711a1d103ca6b514702f`; archive `artifacts/r3a-hr-onboarding-candidate-0d973cbea920.tar.gz`, SHA `418190d96090eb8c5b71084145fda6f5b62c47875ef6e2b98b1792e96d41a6ed`; wheel SHA `0886db886f360c44bceeec5cf1760e41c3357020cf100291b81bb6fa9b5d0860` | HR reports installable host-composition component, 114 passed/1 DSN skip/12 subtests and isolated PG reruns each 1 passed. Exact Auditor disposition for `ac163ef` not found. Prior `f3ead73` remains BLOCKED; #58 has no assignee. | HR source window: obtain named HR/directory authority and writer paths. #51 Coordinator: specify reviewed API/session/auth/DB-role/release composition. Do not claim Vicky onboarded or activated. |
| CME/Grace idempotency | `11a140b5a7de24752ab7639ba0e0cd3fc456c586` | Auditor PASS on frozen-base source + isolated PostgreSQL, 5 passed. Not reconciled onto active 2cc and not deployed. Live Grace activity currently fails before inference. | Coordinator: reconcile minimally onto 2cc, run combined regressions, exact same-SHA review and obtain controlled deployment approval; no grant expansion. |
| Live Modular / PR #59 | PR #59 head/integration baseline `2cc3fe3aabad88c95a5e6489c633cb01472f7c7`; OctoMiner artifact `r3a.octominer-telemetry@2.0.0`, digest `3c5441e1942d0a769ae5e299571cbf6267b3ac67363cecf6906fe9b6a9c7352b` | Open/unmerged; candidate source audit/managed acceptance pending; latest #46 scope FAIL means not deployment-ready. Reported isolated lifecycle tests; no managed activation. | Auditor review exact PR/source; owner correct target context and install evidence; Coordinator performs serial controlled integration only after gates. Runbook `docs/runbooks/R3A_LIVE_MODULAR_MODULE_LIFECYCLE.md`. |
| Independent Auditor #56 | Latest matrix/queue `45ff0b20fd6bbe5aa7e2d341773e98926effa9b2`; later update `2595e4a` | Step 87/91 review: Notifications `61b167` FAIL; Modular `399567` FAIL; HR prior `f3ead73` BLOCKED. Website exact `6e5f3a6` review pending; HR newer `ac163ef` exact review not found; Bridge `f35cb23` queued. | Auditor window/#56: review exact Website package, HR `ac163ef`, then Bridge per queue; publish exact disposition. Coordinator deploys only after review and release authority. |
| Remote Access #49 | Source `16b6230d5b48bb9bd1872f687f43678faeb296d7`, branch `engineering/r3a-ap3-remote-20261107` | Source PASS; browser CA trust and live Steward session acceptance remain pending; canonical identity association not inferred. | #49 Remote Access source window: complete approved browser trust/enrollment and authenticated session acceptance. HR supplies verified association; Coordinator verifies service integration. |
| Bitwarden #50 | Integrated provider `ce05b7307f203e0b37e5857228149c56e9353ae4` | Source PASS; managed retrieval BLOCKED by missing `bws`, authorized machine principal/credential, secret reference and configured #49 consumer. No secret fetched. | #50 Bitwarden + #49 AP3 windows: define non-secret consumer config and request authorized machine identity/reference; then test managed retrieval and lease closure. |
| Character Architecture #56 | Owner branch `engineering/r3a-character-architecture-20261107`, current remote head `da26e98d26ea2ef9bcb6f6755e4f8419e849b69d` | `R3A_CHARACTER_WORKFLOW_DEVELOPMENT_STATUS.md` last refreshed 2026-11-08; CA-01–11 current state is unverified. Historical isolated code/tests are not managed acceptance. | Character Architecture source window under #56: refresh per-ID CA source/review/package/deploy/live status and next owner; coordinate HR #58 and Autonomy #43. PR #57 remains excluded. |
| Bridge v3 #62 / PR #64 | Owner branch `engineering/r3a-bridge-v3-20261111`, candidate `f35cb23e77459f433ccfdb4b10daf2bdf0672626` | Exact review requested in #56 comment 6804974724 and queued; prior `10aa9d8` FAIL for cross-target idempotent receipt. No v3 runtime or Windows multiwindow acceptance. | Live Modular source window/#62: obtain exact audit, then Windows host acceptance and registry entry. Preserve working Bridge v2. |
| Artifact Registry #63 | Issue #63; no assignee; no implementation branch/candidate identified | **NOT COMPLETE; no accountable source window identified.** This index is not the machine-readable registry. | Issue #63 is the existing work item. Route implementation to an existing documentation/artifact-owner window and record owner/branch; do not assign registry feature code to the Coordinator deployment lane. |
| AP2 Engineering | Closest existing tracking is #43; handler candidate `30fd89c846559ad066035824a1e3f8482436427e` on `engineering/r3a-engineering-handler-freeze-20261110`; separate CME candidate `b259a09b3e5372717f455170e9414d82af2eff6f` on `engineering/r3a-step71-active-candidate-20261111` | No dedicated AP2 Engineering issue found. Handler source is on older lineage, not integrated into 2cc. CME `b259a09` is a deadline/idempotency fix, not the Engineering handler, and exact review is pending. | #43/Engineering source window: reconcile handler to active 2cc, exact review, combined durable-handler tests and live acceptance. #51 Coordinator integrates after same-SHA approval. Establish dedicated AP2 issue/owner through normal assignment; do not conflate candidates. |

## Ordered serial release queue (Step 86/92/99/101)

**Current result: NO RELEASE READY. No package may be installed or activated from this snapshot.** The next executable lane action is exact review/rework resolution, not deployment.

1. **Website (#51, Website source window → Auditor #56):** exact candidate `6e5f3a6` / archive `85322406…` is pending review; do not use superseded `3207770`. Complete path/install/rollback handoff; see read-only preflight below. On Auditor PASS, seek exact-SHA release authorization if not already covered, then run one Website-only deployment and acceptance. CME/Ring0 remain untouched.
2. **Notifications (#48, Auditor #56):** exact review of `61b167b` plus immutable archive. Any AP3 write route remains blocked on #46's generic caller contract. Do not deploy a write capability or broaden grants.
3. **Modular Plugins (#46, Auditor #56):** exact re-review of `399567d`; verify target fail-closed before collectors and versioned manifest/artifact. Then reconcile authoritative CME target construction on active source before any staged/live read.
4. **HR/Vicky (#58, HR/source authority):** blocked pending named authority and deployable service composition listed above. No Vicky onboarding or production migration is authorized by the source candidate.
5. **Grace executor and CME prerequisite (#43/#51/#56):** CME `11a140b` must first be reconciled to active baseline 2cc, combined-tested, independently reviewed, and separately deployment-authorized. Grace source PASS still lacks the generic resident-executor package/install/launch route and artifact; Autonomy must provide the reviewed package. No grant change is needed/authorized here.
6. **PR #59 / OctoMiner:** wait for exact source/contract review and target-scope fix; then compatibility preflight and stage under the lifecycle runbook. Keep old version for recovery and verify deactivation/config restoration before closing a release.

Per-candidate installer/config/rollback commands must be copied from the module's exact immutable handoff and the existing lifecycle/runbook. The Website candidate has no verified exact package install command yet; do not infer one from the R3 generic plan-only deploy script. No cross-window candidate is currently queued for release.

## Website read-only preflight and rollback plan (Steps 99/101)

**Exact candidate:** source `6e5f3a6ceea723d0217367c57afd20d9b4c437bd`; archive `artifacts/releases/r3a-website-6e5f3a6.tar.gz`; SHA-256 `85322406cc44c1796af211176d7b6bd2d2abc17a92d3f511a1c85e534480914e`; package contract `r3a.website-release-package.v1`, 422 entries. The exact re-audit request is #56 comment 6804840236; the latest Auditor comment is still that request, so review remains pending.

### Runtime identity evidence (read-only)

- `r3a-ap3-website.service` is active, PID `1997803`; it runs `/home/admin1/R3/.venv/bin/python -m uvicorn r3_app:app --host 127.0.0.1 --port 18311` from `/home/admin1/r3a-workstreams/ap3-website`, behind `https://192.168.1.155:8311`. Identity API returned HTTP 200 and build `3bbe100ed112eb8f24416243a1c798962ac5f083`.
- Unit start was 2026-11-10 20:34 EST; commit 3bbe timestamp is 20:24 EST. Current worktree is clean at `8a46332435dbd38feac808a6fe15506fcc2e9718`, committed 2026-11-11 14:06 EST, after the process start. Same-cwd import resolution selects `r3_app.py` from that worktree. `PYTHONPATH=/home/admin1/.local/share/r3a-ap3-website/python` supplies packages. This points to the process having loaded the earlier 3bbe checkout, but the running process exposes no source digest; exact in-memory revision is **not attested**. No service restart or config change was made.
- Service venv is Python 3.12.3. Compared with the candidate's 20-entry lock, observed differences include `anyio` 4.15.1 vs 4.16.0, `pydantic` 2.14.2 vs 2.14.3, and `typing-inspection` 0.4.4 vs 0.4.5. No packages were changed. A candidate-specific environment matching its lock or a reviewed compatibility/install plan is needed; do not mutate the running shared venv during preflight.
- The LAN deployment runbook covers Website-only systemd drop-in/restart and Nginx checks. Candidate handoff covers archive verification/staged tests but not a complete production install path or exact source rollback command. Website owner must publish those commands and a release path before deployment.

### Deployment and rollback sequence (not executed)

1. After exact Auditor PASS, verify the downloaded archive SHA and all 422 manifest entries against the reviewed handoff.
2. Before touching the unit, capture current unit/drop-in identities, non-secret config revisions, build/source metadata, venv package list, PID/cwd/start time, health/identity responses, and reproducible rollback source. Keep the native-auth environment file contents private.
3. Stage the exact archive at the Website owner's approved release path and install the locked 20 dependencies into a candidate-specific environment. Stage path/command remains an owner handoff dependency; do not invent it.
4. Confirm the candidate reports source `6e5f3a6…`, then switch/restart only the Website unit under applicable release authorization. Keep CME, Ring0, PostgreSQL, grants, Nginx and other services untouched.
5. Verify LAN TLS/login/health/background and anonymous protected-route denial. With a Steward-authenticated session, verify the actual roster and resident-neutral UI plus reload continuity. Current managed directory returns only Grace; a live second-resident exercise is unavailable until an authoritative second identity is onboarded. Do not present Vicky fixture tests as live onboarding or falsely claim missing CME views work.
6. If acceptance fails, restore the exact captured prior source/release path, unit/drop-in/config revision and dependency environment, restart Website only, then verify the prior build/health. **Rollback is not release-grade yet:** there is no immutable deployed Website release path/archive recorded and the exact process source is not attested. Keep the current process untouched until that gap is closed.

**Release authorization:** prior Website authorization named `3bbe100…`; it did not name `6e5f3a6…` or this archive. After Auditor PASS and complete install/rollback handoff, request Steward authorization for the exact source/archive if no standing procedure covers it. The candidate is not eligible now.

## Existing owner and source-window map (Step 93)

- **Artifact registry:** #63 is the existing governing issue, but it has no assignee or candidate source window. The next action is to route #63 to an existing documentation/artifact owner and record that branch; Coordinator's deployment lane will not absorb registry feature development. Until then the registry remains unowned/incomplete.
- **Character Architecture:** issue #56 and branch `engineering/r3a-character-architecture-20261107` at remote HEAD `da26e98d…`. Its CA status file is dated Nov 8; the Character Architecture window must refresh CA-01–11 line by line with current source/review/package/deploy/live evidence and next owners.
- **AP2 Engineering:** no dedicated AP2 issue or assignee found. Current source handoff is #43; Engineering handler `30fd89c…` remains on its old branch, while `b259a09…` is a separate CME digest fix. #43/Engineering must reconcile the handler to active 2cc and secure exact review; a dedicated AP2 issue/owner mapping remains missing.
- **Knowledge:** #47, branch `engineering/r3a-knowledge-governed-ingestion-20261108` at `5b84e75…`; owner supplies exact compatible package/config and evidence source, Coordinator verifies managed authorized retrieval.
- **Remote Access:** #49, branch `engineering/r3a-ap3-remote-20261107` at `16b6230…`; owner completes trusted-browser/Steward session acceptance and coordinates verified HR association.
- **Bitwarden:** #50 provider is already source-integrated at `ce05b73…`; #50/#49 owners must obtain the authorized machine identity, secret reference, and non-secret consumer config before managed retrieval.
- **Development Bridge v3:** #62, branch `engineering/r3a-bridge-v3-20261111` at `f35cb23…`; Live Modular owns the source correction, Auditor review and Windows host validation. Preserve Bridge v2.
- **Grace resident executor 1.2.15:** Autonomy #43 owns artifact `PR #66`, digest `e4e429fbb2929b9329e6816cae478e5390f3f146de9a4fe27bdaa45caba34fac`; this artifact is not deployable. #46 owns acceptance of the generic versioned package descriptor/installer contract; #63 owns the registry entry but has no assigned source window; Coordinator #51 owns CME launcher compatibility and end-to-end integration; Auditor #56 reviews the exact assembled package; Steward release authority and existing grants remain unchanged. Next executable sequence: #46 publishes/accepts package descriptor and install/rollback validation → Autonomy packages 1.2.15 to that contract → #63 records immutable source/artifact/path → Coordinator verifies generic launcher consumption without resident-specific routing and runs combined tests → #56 audits exact package → Steward authorizes controlled install → Coordinator performs managed acceptance. No new grant or installation is authorized by this status.

These issues have no GitHub assignee in the current issue snapshots. Named source branches/windows and the next actions above are observed; absence of a formal AP2/#63 assignment remains explicit rather than inferred.

## Ownership gaps and external dependencies

- **HR source authority:** accountable owner is still unnamed for authoritative HR principal association writer and approval/provenance record.
- **Directory office binding:** existing `institutional.directory.discover` is read-only; an accountable authorized binding writer/approval path has not been identified.
- **Production HR composition:** no deployable API composition, session/auth resolver wiring, least-privilege DB-role provisioning, or exact release/rollback procedure is included in the reviewed bundle.
- **AP3 session caller contract:** current static `allowed_principals` cannot represent a CME-verified per-request Steward session principal for generic `steward_write`. #46 owns generic contract; no wildcard or Website-supplied authority.
- **Resident executor packaging:** current Grace JSONL supervised entrypoint is not yet shown to load via the generic module package worker that expects provider `create_provider()/invoke()`. #46 must identify the existing contract; #43 owns package implementation.
- **Website source identity:** live build metadata reports 3bbe while the clean cwd is now 8a and the service predates that commit; external `PYTHONPATH` supplies dependencies. Exact in-memory source is not attested; release owner must make identity unambiguous.
- **Website command completeness:** exact artifact staging/install/rollback invocation for current candidate `6e5f3a6` is not present in the reviewed handoff; Website owner must publish and verify it before release queue eligibility.
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
| 92 | `6804629168` | wake-up `6804633057`; ACK `6804641037`; result #61 comment `6804780756` | Queue confirms no release ready; exact blockers retained. |
| 93 | `6804764182` | ACK #61 comment `6804949942`; result to be posted with this index update | Existing source windows/issues mapped; #63 and AP2 assignment gaps are explicit. |
| 99 | `6804920935` | ACK #61 comment `6804950329`; result to be posted with this index update | Read-only Website preflight/rollback sequence recorded; no install/deploy. |
| 101 | `6805112938` | ACK #61 comment `6805124515`; result to be posted with this index update | Website audit/release gate and Grace 1.2.15 dependency chain recorded. |

## Source locations and next executable actions

- **This index:** `docs/integration/R3A_CROSS_WINDOW_BACKLOG_INDEX.md` — complete queue, candidate ledger, ownership and `WHERE TO FIND IT` entry point.
- **Normative roadmap/contracts:** linked in Authority section; retain their requirement IDs and owners.
- **Previous six-workstream snapshot:** `docs/integration/R3A_SIX_WORKSTREAM_LEDGER_20261110.md` — historical as-of 2026-11-10 and superseded for current status only.
- **Website release process:** `docs/runbooks/R3A_LAN_HTTPS_DEPLOYMENT.md`; package handoff on #51 comment 6803968032. Exact source/package command and identity mismatch remain open.
- **Module install/rollback:** `docs/runbooks/R3A_LIVE_MODULAR_MODULE_LIFECYCLE.md`; use only after exact candidate review and authority gates.
- **Coordinator next action:** await exact Website Auditor disposition, obtain the approved install/rollback path and release authorization if needed; in parallel continue exact Notifications/Modular reviews and HR authority-owner requests. Do not deploy until one package clears review, install/rollback preflight, compatibility, and release authorization.

## Evidence boundaries

All test counts above are reported with their exact source/owner context; platform-specific Windows failures are not generalized as Linux failures or dismissed. PostgreSQL evidence is disposable isolated data where specified. No production database, grant, service restart, module activation, or shared deployment was changed while preparing this index. Live runtime details above came from read-only process/unit/API inspection; the Website source identity discrepancy remains unresolved.
