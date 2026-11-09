<!--
R3 CONTROLLED DOCUMENT
File: docs/audits/R3A_MODULAR_COMPLIANCE_REVIEW_20261109.md
Component: R3A-INDEPENDENT-MODULAR-AUDIT
File Revision: 1.0.0
Created: 2026-11-09T23:28:20Z
Created By: Codex GPT-6, acting as independent Auditor
Purpose: Record evidence-backed modular compliance and chat architecture review at the stated baseline.
Execution Model: N/A; source/specification and handoff review
Observability: Findings cite requirement, source, evidence boundary, status, and owner.
Dependencies: Approved R3A charter/roadmap/contracts; baseline commit 9a41d7e9647d37c2b7dc6f2aca3be3f5f82ccfe9; Coordinator handoff.
Authority: Steward directive — R3A Independent Auditor / Reviewer V2, 2026-11-09
Changed: 2026-11-09T23:28:20Z | R3A-AUDIT-V2 | Codex GPT-6 | Initial independent compliance review.
Supersedes: None
Contracts: MOD-001–MOD-010; STM-001–STM-007; capability and Website consumer contracts.
Tests: N/A; no tests or runtime operations performed.
History/Predecessor: New file; initial revision in this branch.
-->
# R3A modular compliance review — 2026-11-09

**Reviewer:** Independent Auditor
**Baseline:** `9a41d7e9647d37c2b7dc6f2aca3be3f5f82ccfe9`
**Review type:** Source, specification, and handoff review. No runtime changes or tests were performed.
**Status:** Initial review; operational claims are limited to evidence explicitly recorded in the handoff and integration inventory.

## A. Auditor scope

This review independently evaluates contracts, source boundaries, and reported operational evidence. It does not integrate, deploy, grant permissions, alter identities, or implement resident chat. Coordinator V2 owns integration; module owners own corrections; the Steward owns final acceptance and exceptions.

## B. Governing specifications

The source hierarchy used for this review is:

1. Approved R3 Charter Revision 2 for inherited institutional responsibilities and PostgreSQL direction.
2. `docs/architecture/R3A_ARCHITECTURE_CHARTER.md` for R3A responsibilities, status vocabulary, modular principles, and evidence standards.
3. Steward-approved `docs/architecture/R3A_MASTER_ROADMAP_AP0_AP6.md` Baseline 1.0 for AP ownership, scope, and acceptance; assignments and newer explicit Steward directives may add requirements prospectively.
4. `R3A_AP0_TECHNICAL_SPECIFICATION.md`, `R3A_MODULE_LIFECYCLE_AND_CONTRACT_SPEC.md`, `R3A_STATE_MACHINE_AND_DIAGNOSTIC_CONTRACT.md`, `R3A_CAPABILITY_CONTRACT_V1.md`, and `R3A_BOUNDED_TESTING_AND_ACCEPTANCE_POLICY.md` for module registration/lifecycle, invocation, state, diagnostics, and evidence.
5. Domain contracts where applicable: `R3A_INSTITUTIONAL_DIRECTORY_CAPABILITY.md`, `R3A_STEWARD_WORKSPACE_WEB_API_V1.md`, `R3A_STEWARD_WEBSITE_SESSION_CONTRACT.md`, `R3A_RESIDENT_EXECUTION_PROFILE.md`, and versioned provider manifests/schemas.
6. `R3A_ARCHITECTURAL_DECISION_LOG.md` and the versioned Roadmap Exception Register record decisions and approved deviations. The 2026-11-07 modularity audit is prior analysis, not itself an architectural authority.

The Website-wide functional requirements in GitHub Issue #51 were issued after the original roadmap baseline. They are assessed as later Steward requirements, not retroactively applied to earlier work. The 2026-11-09 Coordinator handoff and integration inventory are evidence, not specifications.

The previous-auditor branch requested by the Steward was inspected locally. Its ref resolves to `db9ba0e` (`Test Grace continuation from durable checkpoint`), shared with `engineering/r3a-phase0-20261105`; it contains no auditor-specific review or deliverables. No distinct prior audit report or GitHub auditor branch evidence was identified in the available local refs. The valid 2026-11-07 modularity audit and 2026-11-09 handoff were reused and checked against current source.

## C. Architectural baseline

The required principle is independently developed and replaceable modules integrated through stable, published interfaces, without routine edits to shared core for each module. CME coordinates lifecycle, scheduling, authorization, and observability; module domain behavior and resident judgment remain outside orchestration. Registry discovery does not confer invocation authority. Website presentation consumes authoritative versioned APIs and must show actual freshness/state, not fabricate it.

## D. Chat review

### Findings

| ID | Result | Requirement and observed evidence | Owner / correction |
|---|---|---|---|
| CHAT-01 | **FAIL** | Website resident roster is not independent of chat execution eligibility. In `r3a_runtime/cme.py`, `steward.residents.discover` obtains a fresh directory snapshot, then adds a row only when directory `resident_id == self.module_id` or an office route plus CME `resident.delegate` and target `resident.objective.execute` checks pass (around lines 990–1030). `web/steward-workspace-api.mjs` additionally skips residents with `authorized === false` (around lines 262–283). Issue #51 requires a dynamic roster; the Workspace Web API v1 defines resident discovery from the institutional directory. Handoff section “Observed roster behavior and failure” records this as the current integrated behavior. | Coordinator V2 / Website #51. Return authorized directory rows independently from execution readiness; represent separate evidence-backed onboarding/readiness/authorization/chat-availability fields. Do not call directory measurement availability onboarding state. Keep create/send fail-closed in CME. |
| CHAT-02 | **FAIL** | Execution profile does not identify the registered runtime module or an authoritative directory-principal-to-module binding. Handoff’s source/registry inspection reports `_resolve_resident_execution_profile` includes directory principal, office, route, config revision and directory evidence, but no source module ID/binding reference; the active Grace module is `resident.grace`, while the directory principal is `resident:grace`. These strings are not authoritative proof of identity equivalence. | Coordinator / CME with authoritative identity/profile owner. Resolve through an existing approved source or procedure before deriving execution identity. No new HR operation is presumed necessary. No identity/grant changes by Auditor. |
| CHAT-03 | **PASS (boundary only)** | Website sends conversation requests through authenticated Website routes; `r3_app.py` forwards canonical CME control operations. The CME send path submits `resident.objective.submit` with `event_kind="conversation"`; no direct model invocation is present in the inspected Website path. | Keep this boundary and verify live request/activity/model lineage during acceptance. |
| CHAT-04 | **PASS (fail closed in source)** | Conversation creation re-reads a fresh, measured authoritative directory and rejects absent residents. For a target other than the configured primary resident it checks office routing and both delegation and target execution grants. Message sending is tied to CME persistence and activity submission. | Keep enforcement in CME after roster display is decoupled. The present checks do not establish correct generic identity binding or usable chat. |
| CHAT-05 | **NOT VERIFIED** | Durable conversation/message schema and idempotency implementation exist (`017_steward_conversations.sql`, CME store APIs, client-generated IDs). Handoff reports live PostgreSQL conversation/message counts are both zero. No real Website conversation, inference result, or persisted transcript was observed. | Coordinator / Website #51 and Autonomy #43: provide authenticated browser evidence, actual CME activity/model request and result references, and history after refresh/restart. |
| CHAT-06 | **BLOCKED** | Handoff records fresh directory discovery for one resident (`resident:grace`) and active module `resident.grace@1.2.12`, but no authoritative binding and no effective `resident.delegate` / `resident.objective.execute` grants. Conversation creation correctly fails closed; there are no messages. | Identity/authority owners supply or identify an existing authoritative binding and scoped authorization; Coordinator then performs live acceptance. No grants or identities issued by Auditor. |

### Independent R/3 reference

The handoff inspected existing R/3 release `r3-unified-8ab4b2ab1669`: configured dynamic roster, scheduler registration of enabled residents, conversation persistence, principal pinning, and scheduler/inference processing are useful implementation evidence. Its website proxy is configured for a resident ID and is not a generic dynamic roster interface. This establishes a reference for registered execution and durable conversation behavior, not R3A identity equivalence, authorization, or permission to reuse R/3 authority.

### Chat acceptance still required

The design can be completed without another architectural redesign: directory discovery returns the authorized dynamic directory roster; each row reports only evidence-supported availability dimensions; conversation create/send independently revalidates current directory membership, binding, route, and grants in CME. Grace is the first demonstration, while data flow and routing remain resident-generic. Accept only after an authenticated browser can display roster rows, create/send a durable conversation to authorized Grace, receive a real CME-governed inference response, and retrieve the transcript after refresh/restart, with denial evidence for unauthorized targets. HTTP status or passing isolated tests alone is insufficient.

## E. Module and workstream review

“Pass” below means only the stated property is supported by inspected contract/source or cited live evidence; it is not whole-workstream acceptance.

| Workstream | Result | Evidence and deviation | Owner / next evidence |
|---|---|---|---|
| Modular provider framework | **FAIL / partial** | `R3A_MODULAR_FOUNDATION_IMPLEMENTATION.md` says manifests discover from external config, but general dynamic binding is incomplete; unlisted modules cannot load into a running CME. Prior audit identifies in-process provider imports and startup registry; approved MOD-002–005 require registry boundary, independent lifecycle, and no Ring 0 restart. Integration inventory reports active directory, Knowledge, telemetry and resource-monitor providers, which proves configured presence, not hot replacement. | Coordinator / Modular Plugins: demonstrate independent register/configure/activate/stop/replace and compatible coexistence against a fixture, without capability-specific core edits or Ring 0 restart. Record exact live versions and diagnostics. |
| Capability invocation and authorization | **PASS (source contract), NOT VERIFIED (all live cases)** | `R3A_CAPABILITY_CONTRACT_V1.md` defines versioned discovery/invocation; CME explicitly returns `authorization_evaluated: false` for discovery and invocation uses grants. This follows AD-P03/MOD-006. Full per-module denial and authorized live invocation evidence is not provided for every module. | Module owners/Coordinator: retain invocation IDs, grant/decision evidence, provider version and result for representative allowed and denied cases. |
| Institutional directory | **PASS (live read reported), FAIL (chat projection)** | Handoff reports fresh measured directory snapshot: one binding/resident, `resident:grace`; CHAT-01 details the projection deviation. The directory contract defines source freshness, not onboarding status. | Coordinator: preserve source digest/invocation; provide independent roster/readiness fields. |
| Website and Steward access | **PASS (anonymous boundary only), NOT VERIFIED (authenticated workflows)** | Handoff reports `/login` served, anonymous session/resident APIs return 401, website unit active; Issue #51 comments report session-integrated shell and TLS checks. They do not establish authenticated resident chat or all class-I administration workflows. Website v1 is expressly a consumer contract proposal. | Website #51 / Coordinator: authenticated browser evidence for roster/chat, notifications, settings, telemetry, resident administration, and engineering workflow APIs; mark unimplemented features honestly. |
| Knowledge | **NOT VERIFIED operationally** | Handoff reports providers 1.1.0/1.2.1 active/healthy in PostgreSQL; authorized institutional retrieval acceptance was not exercised. Prior 2026-11-07 audit found knowledge-specific behavior remains in CME; recheck current integration before claiming modular replacement. | Knowledge owner / Coordinator: managed authorized retrieval with source citations, failure/freshness evidence, and demonstrate provider disable/replace independent of core behavior. |
| Notifications | **NOT VERIFIED operationally** | Handoff reports source has durable isolated work; generic intake, real delivery, inbox read and acknowledgment are outstanding. Current class-I Website requirements call for real notifications, not just UI. | Notifications #48 / Website: actual event intake, route, delivery, session-bound inbox, acknowledgment and durable audit evidence. |
| Engineering and autonomy | **PASS (prior demonstration cited), NOT VERIFIED for current release** | Handoff records prior Grace real objective execution and generic durable dispatch, but no new operation was executed in the handoff. The branch/release currentness and live operation are not established by source presence. | Coordinator / Autonomy #43 / Engineering: current revision, live authorized work, durable activity lineage, output artifact and independent verifier result. |
| Resident character / HR identity | **NOT VERIFIED** | Handoff reports provisional dossiers and unreconciled legacy IDs; no authoritative live Grace-to-module binding. | Character Architecture / authority owner: source-grounded identity and binding evidence with privacy-safe references. |
| Bitwarden / secrets | **BLOCKED** | Handoff says `bws` and machine-account credentials unavailable for live auth/retrieval; no secret contents inspected. | Bitwarden owner: managed secret-reference resolution and lease closure/status evidence without exposing values. |
| AP3 remote access | **PASS (partial), NOT VERIFIED for full operations** | Handoff reports native identity/session source integrated and website login serving; authenticated chat/browser acceptance was not completed. | Remote Access / Website: authenticated Steward workflow over trusted HTTPS with protected operations and audit evidence. |
| Telemetry and resource monitoring | **NOT VERIFIED operationally** | Integration inventory reports active providers; no current in-Website live value/freshness/source evidence in handoff. | Modular Plugins / Website: show real observed values and stale/unavailable transitions from provider contract. |

## F. Website-facing status

Issue #51 added Class I, cross-cutting Website requirements after the original roadmap baseline. The integration inventory and handoff establish a running Website shell/login and protected anonymous routes. The handoff does not establish authenticated operational acceptance for the requested features. Current evidence summary:

| Feature | Review status |
|---|---|
| Resident directory/chat | **FAIL** roster projection; **BLOCKED** binding/grants; no live conversation. |
| Module status/diagnostics | **NOT VERIFIED** in the Website; module registry/source work exists, but no authenticated live Website walkthrough is evidenced. |
| Telemetry/resource monitoring | **NOT VERIFIED** in the Website; provider presence is reported, rendered operational evidence absent. |
| Knowledge retrieval/correction | **NOT VERIFIED** through Website; governed backend work does not prove user-facing workflow. |
| Notifications/acknowledgments | **NOT VERIFIED** live; backend and API handoff remain outstanding. |
| Resident character/HR administration | **NOT VERIFIED**; identity source/crosswalk is unresolved. |
| Secrets status/configuration | **BLOCKED** live provider credentials; protected operational status UI not evidenced. |
| Engineering workflow/evidence | **NOT VERIFIED** through current authenticated Website; prior backend demonstration does not prove Website operability. |
| Remote access/account administration | **PASS** for portions of login/session integration as reported; **NOT VERIFIED** complete authenticated operational workflows. |

## G. Previous work and evidence limits

- The previous auditor branch ref available locally contains no auditor report; it aliases a phase-0 test commit. The 2026-11-07 modularity audit is retained as prior analysis and was checked against the 2026-11-09 source/handoff.
- The Coordinator handoff names source files, database observations, managed process/routes and a directory digest. Those are credited as reported evidence; this review did not query the live host/database or authenticate to the Website.
- Prior focused test counts in the handoff and GitHub comments are not treated as runtime or feature acceptance.
- This review adds no code and ran no tests. Commit/push of these documents establishes documentation only.

## H. Recommended corrective actions

1. Coordinator V2 separates directory roster discovery from execution eligibility in response shape and UI; retain current CME authorization at create/send.
2. Resolve the directory-to-module binding through an already approved authority or source record. Do not infer it from names, roles, or dossier IDs; do not invent an HR endpoint by default.
3. Add the registered module identity and authoritative binding reference to the execution profile where the owning contract permits, with versioned evidence and authorization boundary.
4. Complete live browser chat evidence as specified in section D; keep Grace as first proof and implementation generic.
5. For general modularity, demonstrate module lifecycle/replaceability and remove per-capability core edits in new integration paths; retain explicit existing deviations until corrected, without retroactively misclassifying pre-requirement work.
6. For each Website feature in Issue #51, report code status separately from authenticated live acceptance.

## I. Independent review procedure

Use the concise [acceptance checklist](R3A_INDEPENDENT_ACCEPTANCE_CHECKLIST.md) on each module delivery. The governing spec and contract version are named before review; source/contract evidence and bounded tests establish conformance; a live check at the intended boundary establishes operation. Deviations identify requirement, observed source/revision, evidence, owner and correction. The issue/PR remains the coordination record; Coordinator owns integration, module owner owns correction, independent reviewer records recommendation, and Steward accepts or approves exceptions.
