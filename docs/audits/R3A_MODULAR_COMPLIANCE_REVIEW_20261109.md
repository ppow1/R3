<!--
R3 CONTROLLED DOCUMENT
File: docs/audits/R3A_MODULAR_COMPLIANCE_REVIEW_20261109.md
Component: R3A-INDEPENDENT-MODULAR-AUDIT
File Revision: 1.3.0
Created: 2026-11-09T23:28:20Z
Created By: Codex GPT-6, acting as independent Auditor
Purpose: Record evidence-backed modular compliance and chat architecture review at the stated baseline.
Execution Model: N/A; source/specification and handoff review
Observability: Findings cite requirement, source, evidence boundary, status, and owner.
Dependencies: Approved R3A charter/roadmap/contracts; baseline commit 9a41d7e9647d37c2b7dc6f2aca3be3f5f82ccfe9; Coordinator handoff.
Authority: Steward directive — R3A Independent Auditor / Reviewer V2, 2026-11-09
Changed: 2026-11-09T23:28:20Z | R3A-AUDIT-V2 | Codex GPT-6 | Initial independent compliance review.
Changed: 2026-11-09T23:37:38Z | R3A-AUDIT-V2 | Codex GPT-6 | Add Coordinator 722a102 source review and focused test results; preserve original baseline finding.
Changed: 2026-11-09 | R3A-AUDIT-V2 | Codex GPT-6 | Supersede startup-only provider-framework finding with executable extensibility evidence; defer broad implementation audit pending Steward approval.
Changed: 2026-11-10T00:17:40Z | R3A-MODULARITY-DECISIONS | Codex GPT-6 | Link final AD-024 specification and update resident/handler workstream status.
Supersedes: None
Contracts: MOD-001–MOD-010; STM-001–STM-007; capability and Website consumer contracts.
Tests: `node --test tests/test_steward_workspace_api.mjs` at 722a102: 14 passed. Python pytest blocked at collection because psycopg_pool is unavailable; existing venvs lack pytest. No runtime tests.
History/Predecessor: Revision 1.0.0 in commit cfbeca794a184dc2fbd2bcfb0827bf7677650fdf; immediate predecessor commit 87d868d7e2a64da1d58ca71eb9899d61b5a1d2b2 (file blob 893d4a5484af2eeaf0cd7f6397fd75647361f747).
-->
# R3A modular compliance review — 2026-11-09

**Reviewer:** Independent Auditor
**Baseline:** `9a41d7e9647d37c2b7dc6f2aca3be3f5f82ccfe9`
**Review type:** Source, specification, and handoff review, supplemented by isolated provider-extension tests in revision 1.2.0. No live runtime changes.
**Status:** Preliminary module-framework finding is superseded by the 2026-11-09 existing extensibility verification; broad module-by-module implementation acceptance has not been performed in this document; current corrections are tracked in the AD-024 gap analysis.

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

The Steward-authorized [Modularity Compliance Specification v1](../architecture/R3A_MODULARITY_COMPLIANCE_SPECIFICATION_V1.md) now governs module reviews under AD-024. The [Interface Contract Gap Analysis](R3A_INTERFACE_CONTRACT_GAP_ANALYSIS_20261109.md) records verified gaps and implementation ownership; the prior proposal remains historical.

The previous-auditor branch requested by the Steward was inspected locally. Its ref resolves to `db9ba0e` (`Test Grace continuation from durable checkpoint`), shared with `engineering/r3a-phase0-20261105`; it contains no auditor-specific review or deliverables. No distinct prior audit report or GitHub auditor branch evidence was identified in the available local refs. The valid 2026-11-07 modularity audit and 2026-11-09 handoff were reused and checked against current source.

## C. Architectural baseline

The required principle is independently developed and replaceable modules integrated through stable, published interfaces, without routine edits to shared core for each module. CME coordinates lifecycle, scheduling, authorization, and observability; module domain behavior and resident judgment remain outside orchestration. Registry discovery does not confer invocation authority. Website presentation consumes authoritative versioned APIs and must show actual freshness/state, not fabricate it.

## D. Chat review

### Findings

| ID | Result | Requirement and observed evidence | Owner / correction |
|---|---|---|---|
| CHAT-01 | **FAIL at baseline; PASS for correction in source commit `722a102`** | At baseline `9a41d7e`, `steward.residents.discover` filtered directory rows through execution identity/route/grants and the Website hid unauthorized rows. In `722a102`, CME appends each well-formed row from its measured/fresh directory snapshot without grant checks or module-ID comparison; the Website renders each row and disables it if `chat_available` is false. The changed code introduces no hardcoded resident identity. This resolves the specific roster visibility coupling. | Coordinator V2 delivered the roster correction. Keep roster membership distinct from chat authorization. |
| CHAT-02 | **FAIL remains** | Execution profile still lacks an authoritative registered-module binding reference. The API's new static `chat_status` reports the binding unavailable, but `_resolve_resident_execution_profile` still carries resident principal, office, route, config revision and directory evidence without module ID/binding reference. Handoff distinguishes `resident:grace` from `resident.grace@1.2.12`. `steward.conversation.create` also exempts `resident_id == self.module_id` from delegation/target grant checks; no source evidence establishes this equality as the authoritative primary-resident binding. | Coordinator/CME and identity authority: resolve the binding through an existing authoritative source and define the primary-resident authorization path. Do not infer from display names or IDs; do not create grants. |
| CHAT-03 | **PASS (boundary only)** | Website sends conversation requests through authenticated Website routes; `r3_app.py` forwards canonical CME control operations. The CME send path submits `resident.objective.submit` with `event_kind="conversation"`; no direct model invocation is present in the inspected Website path. | Keep this boundary and verify live request/activity/model lineage during acceptance. |
| CHAT-04 | **PASS (fail closed in source)** | Conversation creation re-reads a fresh, measured authoritative directory and rejects absent residents. For a target other than the configured primary resident it checks office routing and both delegation and target execution grants. Message sending is tied to CME persistence and activity submission. | Keep enforcement in CME after roster display is decoupled. The present checks do not establish correct generic identity binding or usable chat. |
| CHAT-05 | **NOT VERIFIED** | Durable conversation/message schema and idempotency implementation exist (`017_steward_conversations.sql`, CME store APIs, client-generated IDs). Handoff reports live PostgreSQL conversation/message counts are both zero. No real Website conversation, inference result, or persisted transcript was observed. | Coordinator / Website #51 and Autonomy #43: provide authenticated browser evidence, actual CME activity/model request and result references, and history after refresh/restart. |
| CHAT-06 | **BLOCKED** | Handoff records fresh directory discovery for one resident (`resident:grace`) and active module `resident.grace@1.2.12`, but no authoritative binding and no effective `resident.delegate` / `resident.objective.execute` grants. Conversation creation correctly fails closed; there are no messages. | Identity/authority owners supply or identify an existing authoritative binding and scoped authorization; Coordinator then performs live acceptance. No grants or identities issued by Auditor. |
| CHAT-07 | **PARTIAL** | In `722a102`, `onboarding_status="unknown"`, `authorization_status="not_evaluated"`, `execution_status="unavailable"`, `chat_available=false`, and `chat_status="governed_execution_binding_unavailable"` are assigned to every row. The values avoid inferring onboarding or granting authority, but are constants rather than per-resident current observations. The Website therefore cannot enable an authorized generic resident through this path. | Coordinator V2/CME: expose evidence-backed readiness dimensions or explicit unknown/unavailable reason; only show chat selectable after governed readiness, without granting from discovery. |

### Independent R/3 reference

The handoff inspected existing R/3 release `r3-unified-8ab4b2ab1669`: configured dynamic roster, scheduler registration of enabled residents, conversation persistence, principal pinning, and scheduler/inference processing are useful implementation evidence. Its website proxy is configured for a resident ID and is not a generic dynamic roster interface. This establishes a reference for registered execution and durable conversation behavior, not R3A identity equivalence, authorization, or permission to reuse R/3 authority.

### Chat acceptance still required

The roster separation itself is source-level compliant at `722a102`. End-to-end readiness remains incomplete: discovery reports all residents unavailable, execution-profile binding is unresolved, and the primary equality authorization exemption needs an authoritative justification. Focused Node workspace tests passed 14/14 at `722a102`. Python conversation tests could not collect because `psycopg_pool` is absent from system Python; available local virtual environments lack pytest. The tests that ran do not exercise DOM roster rendering. No authenticated browser, live inference, database persistence, or restart acceptance was performed. Grace remains first demonstration and data flow/routing must remain generic. Acceptance requires the authenticated Website roster, authorized create/send through CME, real inference and transcript recovery, plus denial evidence for unauthorized targets.

## E. Module and workstream review

“Pass” below means only the stated property is supported by inspected contract/source or cited live evidence; it is not whole-workstream acceptance.

| Workstream | Result | Evidence and deviation | Owner / next evidence |
|---|---|---|---|
| Modular provider framework | **PASS for capability providers at source/fixture level; resident/workflow limits remain** | Focused existing fixtures demonstrate external provider registration, discovery, lifecycle, authorization, invocation, replacement, stop/disable, dependency checks and unrelated-provider coexistence. A disposable config reload harness adds an already staged provider to a running CME process without changing its PID. This disproves the earlier claim that providers can only load at startup. It does not establish arbitrary resident executor loading, remote package staging, live PostgreSQL/Ring 0 operation, or generic durable module-owned handlers. | See [existing extensibility verification](R3A_EXISTING_EXTENSIBILITY_VERIFICATION_20261109.md). Correct stale foundation documentation. AD-024 requires generic resident binding and durable handlers; see the approved specification and gap-analysis backlog for the minimal extension. |
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
