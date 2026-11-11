<!--
R3 CONTROLLED DOCUMENT
File: docs/comms-incidents/R3-COMMS-006.md
Component: R3A-GRACE-CHAT-FROZEN-CME-INCIDENT
File Revision: 1.0.0
Created: 2026-11-11T21:28:31Z
Created By: Codex GPT-6
Purpose: Record the evidence-backed blocker to live authenticated Grace chat recovery at the frozen CME idempotency boundary.
Execution Model: Read-only frozen-source inspection and focused candidate regression; no frozen-core modification or deployment.
Observability: GitHub dispatch/governing issue comments, exact source SHA, focused test result, and punch-list status.
Dependencies: R3A CME, Website authenticated conversation path, Steward exception decision, Coordinator controlled integration/deployment, and Website owner live acceptance.
Authority: Planned Step 119 comment 6807252111; frozen-core changes/deployment are explicitly prohibited without approval.
Changed: 2026-11-11T21:28:31Z | R3-COMMS-006 | Codex GPT-6 | Create evidence-backed incident and record the preflight block.
Supersedes: None.
Contracts: R3A capability invocation idempotency; R3A Website durable conversation; hints/comms-failure-recovery.md.
Tests: Candidate focused suite: 22 passed, 2 skipped, 2 existing xfailed; PostgreSQL restart/replay is DSN-gated and skipped.
History/Predecessor: New file; created on engineering/grace-chat-recovery-20261111.
-->
# R3-COMMS-006 — Grace chat blocked before inference by frozen CME idempotency digest

**Status:** `OBJECTIVE_BLOCKED` pending explicit Steward decision and controlled core integration/deployment. The investigation and proposed exception are recorded; live chat recovery is not complete.

## Incident

- **Reported:** 2026-11-11; exact investigation time 21:28:31 UTC.
- **Objective:** Restore an authenticated Website Grace turn that invokes the configured real model, persists a visible reply, and retains it after refresh/reopen.
- **Dispatch:** Planned Step 119, GitHub comment [6807252111](https://github.com/ppow1/R3/issues/61#issuecomment-6807252111).
- **Host/source:** Linux engineering workspace `/home/admin1/r3a-workstreams/grace-chat-recovery`; frozen deployed/audited release tree `/home/admin1/r3a-workstreams/releases/r3a-89eda133`.
- **Operation attempted:** Read-only source, Git history, and trace inspection; focused tests on the exact reviewed candidate. These completed.
- **Core-change operation:** **Not submitted** because the dispatch expressly prohibits modifying or deploying frozen CME without Steward approval. No service, grant, configuration, module socket, or frozen source was changed.
- **Required permission:** Explicit Steward decision on the narrow exception proposal. No Riverview Comms command or grant operation was attempted; this is a core-freeze governance gate, not an authorization denial.
- **Retries:** No core mutation/deployment retry. The focused test command was rerun using the available shared Python environment after the default system interpreter lacked `psycopg_pool`; the focused suite completed successfully with database-gated cases skipped.

## Verified evidence and diagnosis

- Step 111 trace: authenticated Website submission returned 202 and created activity `89fa0d63-e52d-5ffa-bd33-ed1e3cd8ad42`; CME retried the already-successful directory invocation using the same idempotency key and a newly generated deadline. Durable Store rejected the changed canonical digest with `idempotency key already belongs to a different canonical request` before inference. Trace: [#51 comment 6805697745](https://github.com/ppow1/R3/issues/51#issuecomment-6805697745) and [#61 comment 6805707983](https://github.com/ppow1/R3/issues/61#issuecomment-6805707983).
- Exact frozen source is `89eda1331b96fe40918e4aa67de09c5ae3f45227`. Its `r3a_runtime/cme.py` generates a fresh deadline for the stable-key directory invocation and hashes the full validated request; `r3a_runtime/db.py` rejects an existing key with a changed digest.
- Narrow source candidate `b259a09b3e5372717f455170e9414d82af2eff6f` excludes only per-attempt `deadline` from the digest. Deadline validation remains per attempt and other semantic fields remain bound. Independent Auditor source review: [#51 comment 6805687557](https://github.com/ppow1/R3/issues/51#issuecomment-6805687557).
- Focused exact-candidate suite rerun: **22 passed, 2 skipped, 2 existing xfailed**. The PostgreSQL restart/replay regression was skipped because this environment has no disposable test DSN. It remains required before an approved integration is deployed.
- No fresh authenticated Website turn, real model inference, visible persisted reply, or refresh/reopen result was available. The Website polling improvement does not resolve or prove the CME first-hop recovery.

## Proposed recovery and ownership

A narrow exception proposal is posted at [#67 comment 6807435948](https://github.com/ppow1/R3/issues/67#issuecomment-6807435948). It limits scope to the reviewed digest correction and its regressions, requires the PostgreSQL restart/replay regression on a disposable database and the controlled integration/release path, and retains exact frozen `89eda1331b96fe40918e4aa67de09c5ae3f45227` as rollback. The proposal is not approval.

- **Next decision owner:** Steward, to explicitly approve or reject the exception and supply/confirm its roadmap mapping and formal ID.
- **After approval:** Coordinator/core owner to integrate and deploy the exact approved candidate through the controlled release path.
- **Live acceptance owner:** Website owner and Steward, using a fresh authenticated browser session to verify real inference, visible persisted reply, and refresh/reopen.
- **Impact:** Grace Website chat remains unable to complete turns that hit this retry path; no successful model call is claimed.
- **Closure evidence:** Approved exception reference; isolated PostgreSQL replay regression; exact integrated/deployed SHA and health; authenticated Website/model activity references; visible transcript and refresh/reopen result. If rejected, record the decision and next authorized path without changing frozen core.

See [R3-P020](../PUNCH_LIST.md) and the Step 119 blocker report on [#61 comment 6807435305](https://github.com/ppow1/R3/issues/61#issuecomment-6807435305).
