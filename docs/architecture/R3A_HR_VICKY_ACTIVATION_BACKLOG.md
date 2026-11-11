<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_HR_VICKY_ACTIVATION_BACKLOG.md
Component: R3A-HR-VICKY-ACTIVATION-BACKLOG
File Revision: 1.0.1
Created: 2026-11-11T18:43:21Z
Created By: Codex GPT-6
Purpose: Track the evidence-backed, authority-separated path from universal resident roster governance through Vicky's operational activation.
Execution Model: Durable workstream register; no authority writes or activation.
Observability: Step owner, status, evidence reference, and next action.
Dependencies: Issue #58, R3A roadmap/contracts, current Coordinator integration baseline.
Authority: Steward dispatch Steps 74 and 81; R3A modular architecture.
Changed: 2026-11-11T18:43:21Z | HRD-STEP-81 | Codex GPT-6 | Recover activation path and roster policy work into a proof-linked backlog.
Changed: 2026-11-11T18:54:31Z | HRD-STEP-74 | Codex GPT-6 | Record installable wheel verification and remaining deployment gates.
Supersedes: None
Contracts: Universal resident onboarding v1; HR/directory/dossier/grant/runtime/communications authority boundaries.
Tests: Documentation review against linked authoritative R3A contracts and issue evidence.
History/Predecessor: New file; publication recorded by Git commit.
-->

# R3A HR — Universal Roster and Vicky Activation Backlog

**Status:** Active evidence register; source work and operational approval are tracked separately.  
**Scope:** Issue #58, including dispatches #61 comments `6804154755` (Step 74) and `6804261392` (Step 81).  
**Baseline:** Coordinator source integration target `2cc3fe3aabad88c95a5e6489c633cb01472f7c7`; this is not deployment authority.  
**Current HR candidate at start of this register:** `f3ead73bc1ed3bc86bd64bcddd95fbe858e58f12`; Step 74 implementation commit `e247f3fba9c9affdbeac3293b77b91f904cbb27c` adds the host façade and activation register.

This register recovers the universal packet, HR privacy/dossier/grant boundaries, deployment work, and open dependencies from Issue #58 and the R3A roadmap/contracts. It is an ordered path to Vicky activation, not a claim that any blocked authority decision exists. A successful source operation or packet-state transition cannot establish an appointment, identity, grant, or activation by itself.

## Evidence-backed end-to-end path

| # | Required step and completion evidence | Owner | Status / current proof | Next action |
|---|---|---|---|---|
| 1 | Identify the authoritative HR source owner, personnel decision-maker, and approval policy, including how Helen's HR management authority is represented | HR Steward / HR authority | **BLOCKED.** Existing host evidence in #33 comment `6767817621` lists `hr.directory`, `hr.read`, `hr.save`; it does not name a current accountable writer/approver. | Name the accountable principal and provide the approved appointment decision/read contract. |
| 2 | Record Vicky's approved appointment, title/responsibilities, office, reporting relationship, effective dates, status, source revision, and privacy classification in HR | HR authority | **BLOCKED.** No current approved R3A appointment evidence is in #33/#58; legacy `r3:vicky` onboarding row is not an appointment approval. | HR records or supplies the current authoritative appointment and revision. |
| 3 | Read and verify current HR person/appointment identity and source provenance | HR / host verifier | **BLOCKED.** Current authenticated HR read API/procedure is not evidenced here. | Provide authenticated, revision-pinned HR read and field-level evidence references. |
| 4 | Resolve/issue the canonical unique R3A resident principal and authoritative occupant record | Institutional directory authority; HR appointment prerequisite | **BLOCKED.** Latest documented authenticated directory snapshot was 2026-11-10 and returned Grace only; current read capability is `institutional.directory.discover`. | Directory owner names the approved occupant-provisioning operation; obtain a fresh authenticated snapshot before and after the authorized change. |
| 5 | Apply active Engineering Manager office binding with revision, effective period, and provenance | Institutional directory authority | **BLOCKED.** Discovery is read-only; no binding writer/owner/procedure has been evidenced. | Directory owner supplies authorized binding procedure and durable evidence response. |
| 6 | Associate HR authority principal to the canonical resident principal with provenance, revision/CAS, idempotency, correlation, conflict checks, and audit | HR authority/source maintainer | **BLOCKED.** `associate_authority_principal_with_provenance` is absent from the verified HR host interface. R3A adapter fails closed. | HR owner publishes/identifies the exact approved operation and accountable approver. Do not create a substitute writer. |
| 7 | Approve Vicky's character identity/canon revision; associate continuity and memory; apply protected relationship and privacy restrictions; reference approved artifacts | Character Architecture / Jessica's configured authority; HR for personnel privacy | **BLOCKED.** Vicky's dossier remains provisional; no approved canon or continuity association is evidenced. Contract references: `R3A_RESIDENT_CHARACTER_ARCHITECTURE.md`, `R3A_UNIVERSAL_RESIDENT_ONBOARDING_V1.md`. | Character Architecture records the required approval or the governed not-applicable decision; HR confirms allowed personnel projection. |
| 8 | Provision and verify resident credentials, ownership, expiry, rotation, and revocation path | Security | **BLOCKED.** No credential or approval is evidenced. | Security publishes its existing provisioning/verification interface and approves any exact credential. |
| 9 | Approve exact capabilities/resources/actions/scopes, expiry, renewal and revocation; verify effective CME authorization | Security / R3Authority; CME enforces | **BLOCKED.** No Vicky capability grants are evidenced. Packet grant-domain status alone cannot grant access. | Security issues separately approved exact grants; test allowed and denied operations through CME. |
| 10 | Register role-neutral resident module/configuration and model/inference route, dependencies, health and recovery | Autonomy #43 owns resident profile/logic; Coordinator #51 owns registration/deployment | **BLOCKED.** No Vicky execution profile, route, module registration, or live health evidence. | Owners provide the versioned registration/config and approve route; health checks must observe ACTIVE readiness. |
| 11 | Install the onboarding runtime library and compose its authenticated host route | HR Development supplies reusable boundary; Coordinator owns API composition | **SOURCE INTERFACE IMPLEMENTED; HOST DEPLOYMENT BLOCKED.** `r3a.resident.onboarding.host-composition.v1` resolves actors from host-authenticated context and requires auth/evidence ports. Production route, host registration, and DB-role contract remain Coordinator-owned and absent. | Auditor exact-SHA review, then Coordinator reviews route, actor resolver, authorization binding, verifiers, DB role, health and recovery. |
| 12 | Build and verify immutable installable package plus checksums, install config, prerequisites, rollback and recovery instructions | HR Development; Coordinator installs | **SOURCE ARTIFACT VERIFIED; DEPLOYMENT BLOCKED.** Runtime wheel from `e247f3f` installed into an isolated target and imported; migration 019, guarded rollback, packet schema and state-machine resources are present. Wheel SHA-256 `0886db886f360c44bceeec5cf1760e41c3357020cf100291b81bb6fa9b5d0860`; source archive SHA-256 `7402554f727298f8c3d8549ceb8a828f0b1d433c1e8190b50994362029ee8916`. | Auditor reviews exact candidate and both digests; Coordinator manages install only after release/authority approvals. |
| 13 | Independently review source, package contents/digests, migration, authorization, privacy, failure recovery, and test evidence | Independent Auditor #56 | **PENDING.** Exact review requested for `f3ead73` at #56 comment `6803905512`; no later exact-SHA disposition appears in the reviewed issue comments. | Request review for the new final exact SHA and package digests. |
| 14 | Approve release, backup/restore preflight, least-privilege DB grants, checksummed migration 019, and application rollback | Coordinator / release authority; Steward approval where required | **BLOCKED.** Migration 019 only ran in private disposable PostgreSQL; shared ledger remains 018; no production role/release approval. | Coordinator documents exact approved release procedure and authorizes maintenance window before any shared migration. |
| 15 | Deploy/activate onboarding API and verify health, auth, audit, privacy redaction, idempotency, revision conflict, resume and rollback using synthetic resident | Coordinator; Auditor reviews | **BLOCKED.** No API deployed; no shared DB change authorized. | After steps 11–14, execute controlled synthetic acceptance in approved staging/maintenance lane and record diagnostics. |
| 16 | Publish approved resident identity/title/status through authenticated directory and Website roster | Directory authority supplies binding; Website #51 integrates; Coordinator deploys | **BLOCKED for Vicky.** Website's current deployed roster does not establish Vicky's current R3A binding or readiness. Display name/title/status must come from canonical directory/profile contracts. | After verified steps 2–6 and approved runtime state, refresh authenticated roster and verify canonical principal/display/title/status. |
| 17 | Verify resident chat route, persistence, model inference, CME activity/audit, and post-restart continuity | Website, Autonomy, Coordinator | **BLOCKED.** No Vicky model route, execution authorization, module readiness, chat or inference evidence. Directory visibility does not imply execution readiness. | Run a bounded authorized synthetic-to-Vicky acceptance only after all approvals; verify an actual inference result and durable conversation/activity after reload/restart. |
| 18 | Independent operational review and explicit institutional activation decision | Independent Auditor; Steward | **BLOCKED.** No completed acceptance packet or activation decision. | Auditor reviews evidence from 1–17; Steward makes explicit activation decision; persist exact decision and scope. |
| 19 | Maintain Vicky after activation: renewal, reassignment, suspension/reactivation, credential rotation, grant revocation, offboarding, rollback/recovery | HR, Security, Coordinator, directory authority; packet state machine | **CONTRACT IMPLEMENTED; OPERATIONAL PROCEDURES PENDING.** Lifecycle states and event/revision guards exist; real authority adapters/operating procedures do not. | Owners publish periodic review and response SLAs; exercise synthetic suspension, resumption, revocation, offboarding, and rollback before active use. |

## Universal roster and privacy policy work

The universal onboarding packet and institutional directory read contract are reusable across residents; no resident-specific mapping or source-code addition is permitted. The source design separates HR personnel identity/appointment, directory principal/office binding, character/canon, Security credentials/grants, Coordinator runtime, and Website communications. The resident dossier architecture says HR-sensitive fields remain in governed HR storage and only an authorized projection enters runtime context; directory/profile facts and a model route do not imply capability grants.

The institution still needs an HR-owned universal resident roster policy package defining: canonical source of truth and owner; eligibility/lifecycle statuses and appointment authority; required and optional fields by role; privacy classifications and minimization; disclosure audiences and redaction rules; retention/correction/access logging; revision/CAS and provenance; crosswalk/alias resolution; status and office-binding refresh; correction, suspension, reassignment and offboarding; and an authorized read/export contract usable by directory, dossier, Website and onboarding consumers. This policy cannot be approved by HR Development source code. **Owner:** HR authority/Steward. **Status:** BLOCKED on named authority and policy approval. **HR Development deliverable:** versioned consumer schema/adapter and privacy tests after policy owner supplies approved classifications and projections.

## HR Development-owned backlog

| Item | Status | Evidence / next work |
|---|---|---|
| Universal packet schema, authority metadata, state machine, revision/idempotency and PostgreSQL event repository | Source implemented; prior focused independent suite passed 79 tests at `82261c8`; reconciled-tree suite passed 143 with one separate DSN-gated test | Preserve; add Step 74 host-composition tests and re-run focused/DB suite on the new exact SHA. |
| Host integration seam, fail-closed authenticated actor resolution | **Step 74 in progress** | `r3a_runtime/residents/onboarding_host.py`, contract `r3a.resident.onboarding.host-composition.v1`; missing ports fail closed; host registers routes/deploys. |
| Installable package and production handoff | **Step 74 in progress** | Produce runtime wheel, verify package data and isolated install/import; source archive remains reproducible; document install/rollback/owner gates. |
| Vicky packet and evidence blockers | Existing packet is request-only; Vicky not activated | Keep identity/appointment/binding/character/credentials/grants/runtime/comms/acceptance pending or blocked; update only from cited authoritative evidence. |
| HR roster policy/schema | **BLOCKED** | Await HR authority's approved universal policy and named owner; then add versioned projection contract and multi-resident privacy tests. |
| HR provenance association interface | **BLOCKED** | Await source owner and authority operation; keep current adapter fail-closed and test missing/wrong-owner/conflict/replay. |
| Directory occupant/binding interface | **BLOCKED** | Await directory owner and authorized procedure; HR service must not write directory tables. |

## Authority references

- Roadmap and phase governance: `R3A_MASTER_ROADMAP_AP0_AP6.md` (AP0/identity foundation and AP4 institutional expansion; roadmap approval alone does not authorize production deployment).
- Universal packet/approval boundaries: `R3A_UNIVERSAL_RESIDENT_ONBOARDING_V1.md`.
- HR privacy, dossier, character and provenance: `R3A_RESIDENT_CHARACTER_ARCHITECTURE.md`.
- Capability profile and grant separation: `R3A_RESIDENT_EXECUTION_PROFILE.md`, `R3A_CAPABILITY_CONTRACT_V1.md`.
- Directory discovery contract: `R3A_INSTITUTIONAL_DIRECTORY_CAPABILITY.md`.
- Release/migration/composition and recovery: `R3A_HR_ONBOARDING_DEPLOYMENT_PLAN.md`.

**Truthful terminal status:** source development may be complete for an increment while Vicky remains not onboarded. Do not mark ACTIVE, READY FOR COORDINATOR, or chat-ready until the exact operational evidence and authorities above are present.
