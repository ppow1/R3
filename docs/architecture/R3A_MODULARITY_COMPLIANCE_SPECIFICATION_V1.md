<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_MODULARITY_COMPLIANCE_SPECIFICATION_V1.md
Component: R3A-MODULARITY-COMPLIANCE-SPEC
File Revision: 1.0.0
Created: 2026-11-10T00:17:40Z
Created By: Codex GPT-6, acting as Independent Auditor
Purpose: Govern enforceable modularity obligations for CME, Ring 0, capability providers, resident executors, durable workflow handlers, integrations, and Website surfaces.
Execution Model: N/A; architecture specification.
Observability: Module lifecycle, activity, handler, configuration and acceptance evidence remain in the existing CME registry/state/diagnostic mechanisms.
Dependencies: R3A Charter; Roadmap Baseline 1.0; AD-001–AD-024; MOD-001–MOD-014; capability, resident, activity, state, diagnostic, authorization and Website contracts.
Authority: Steward decision in “R3A Modularity Architecture Decisions,” 2026-11-09; recorded as AD-024. Governs architecture; does not itself authorize unrestricted runtime or production implementation.
Changed: 2026-11-10T00:17:40Z | R3A-MODULARITY-DECISIONS | Codex GPT-6 | Publish final Steward-authorized modularity compliance specification and bounded implementation backlog.
Supersedes: `docs/audits/R3A_MODULARITY_COMPLIANCE_SPEC_PROPOSAL_20261109.md` revision 1.1.0 as the governing modularity specification; the proposal remains historical audit evidence.
Contracts: MOD-001–MOD-010; `r3a.capability-operation.v1`; `r3a.module.v1`; `r3a.resident.execution-profile@1.0.0`; `r3a.activity-intake.v1`; proposed `r3a.resident.module-binding.v1` and `r3a.activity-handler.v1` extensions as specified here.
Tests: No implementation tests run; this is a normative architecture document. Implementation acceptance tests are assigned in section 9.
History/Predecessor: New controlled specification; decision basis and evidence at commit `87d868d7e2a64da1d58ca71eb9899d61b5a1d2b2`.
-->
# R3A Modularity Compliance Specification v1

**Status:** Steward-authorized governing architecture specification.
**Decision record:** AD-024 in [the R3A Architectural Decision Log](R3A_ARCHITECTURAL_DECISION_LOG.md).
**Evidence basis:** Auditor verification at commit `87d868d`, including provider lifecycle fixtures and the source-level limitations summarized in [the extensibility verification](../audits/R3A_EXISTING_EXTENSIBILITY_VERIFICATION_20261109.md).

## 1. Purpose and authority

R3A shall support independently developed, replaceable modules through stable, published interfaces. Normal module operations must not routinely require changes to CME or Ring 0 source. CME coordinates. Residents make resident and domain decisions. Modules implement declared responsibilities. The Website presents and controls the system through authoritative interfaces.

This specification incorporates the Steward’s 2026-11-09 decisions. It preserves approved A-01 through A-10 and existing Roadmap Baseline 1.0 requirements. It supersedes the auditor’s proposal as governing authority. It defines architecture and acceptance obligations, but does not authorize production changes or an unrestricted implementation campaign. Work remains subject to Roadmap governance and separately granted implementation authorization.

## 2. Governing principles

1. **Preserve the verified provider architecture.** Use the external operation configuration, digest-pinned provider manifests, registry, CME lifecycle controls, capability contracts, and existing Website operation interface. Do not create a competing registry, installer, scheduler, grant store, state store, or orchestration service.
2. **Separate three module roles.** A package may implement one or more roles, but capability providers, resident executors, and durable workflow handlers have distinct contracts and must not be conflated.
3. **Use one generic CME boundary.** CME owns scheduling, lifecycle, authorization, durable routing/state, progress, diagnostics, and recovery coordination. It does not own module-specific workflow policy or resident reasoning.
4. **Keep registration distinct from authority.** Registry discovery and resident binding do not grant invocation or execution rights. Existing grants and authoritative identity/HR associations remain decisive.
5. **Make normal operations restart-free.** Register, configure, install, activate, deactivate, replace, and remove compatible modules without restarting CME or Ring 0. A safe activity boundary may delay a change. Incompatible infrastructure upgrades or exceptional maintenance may follow a separately governed maintenance procedure.
6. **Report the real process boundary.** Current module child processes are separate processes under the CME service UID. This provides process/protocol separation, not an independent OS security boundary or sandbox. Modules in the current baseline are trusted at that service identity level and may access resources readable by that UID; explicitly allowlisted environment references can expose configured credentials. Any stronger isolation requires a separate threat model and approval.
7. **Keep contracts small and evolvable.** Preserve current semantic-version schemas, dependency range evaluation, compatibility checks, and fail-closed activation. Breaking contract changes use a new major version; backward-compatible optional additions use a minor version; patch versions do not change the contract shape. A consumer accepts only versions/ranges it declares and validates the selected schema. Unknown or incompatible requirements fail closed. No universal deprecation framework is required.
8. **Do not infer completion.** Source tests, mocks, and isolated fixtures demonstrate the tested boundary only. Live service, durable store, authorization, and Website acceptance are separately evidenced when required.

### Preserved approved obligations A-01–A-10

| ID | Preserved obligation |
|---|---|
| A-01 | Ring 0 remains a minimal supervisor. CME coordinates lifecycle, scheduling, authorization, resource use, progress, recovery, and observability. Resident reasoning and domain decisions remain with residents/modules. |
| A-02 | Modules are independently identifiable, versioned implementations with declared contracts/dependencies and can be installed, activated, stopped, and replaced without restarting Ring 0. AD-024 clarifies normal compatible module operations also do not restart CME. |
| A-03 | CME uses the registry/loader boundary; module behavior is not a fixed CME/Ring 0 roster. Contract incompatibility blocks activation with a visible diagnostic. Lifecycle state is durable and observable. |
| A-04 | Discovery, registration, resident binding, and configuration do not grant invocation authority. CME enforces existing institutional authorization and audits invocations. |
| A-05 | Operational configuration is external, validated, revisioned, and uses protected secret references rather than plaintext secret values. |
| A-06 | Durable activities, events, ownership, recovery, and replacement preserve lineage. Uncertain work remains visibly blocked/degraded rather than falsely complete. |
| A-07 | Health and diagnostics use observed runtime state, identify freshness, and report unknown/unavailable honestly. |
| A-08 | A compatible disposable module fixture can be registered/discovered and lifecycle-managed without restarting Ring 0; discovery is distinct from authorization. |
| A-09 | Capability operations use versioned typed requests/results, declared effects, schemas, grants, evidence, retry/idempotency/reconciliation semantics; CME owns invocation authorization and audit. |
| A-10 | Acceptance requires evidence at the intended boundary. Source presence, isolated tests, mocks, and HTTP success alone do not establish operational completion. |

## 3. Module roles and conformance

### 3.1 Capability-provider modules — existing supported profile

A provider module publishes one or more typed capability operations and may declare dependencies, configuration, artifact digest, resource requirements, and lifecycle metadata. Existing configuration and module manifest code validate those declarations; CME discovers providers, checks grants, invokes the provider process, records outcomes, and performs lifecycle operations.

The implementation has verified provider configuration reload, discovery, install, activation, invocation, authorization denial, replacement, stop/disable, dependency validation, and coexistence without CME PID change. A provider artifact must already be staged, importable, declared, and digest-pinned; R3A does not claim a remote artifact distributor.

**Conformance:** use existing contracts. Do not add a parallel provider registration, invocation, or Website gateway. Preserve existing provider regression tests and add no module-specific CME branch to support a provider.

### 3.2 Resident-executor modules — generic binding required

A resident executor is a registered module version bound to one canonical, HR-associated resident identity. The existing resident execution profile carries identity, office role, directory evidence, route, and configuration revision, but does not bind a resident to an independently selected module artifact. Current configuration restricts the top-level module entrypoint to Observer/Grace; CME’s secondary resident launch path invokes the Grace entrypoint. These are the demonstrated limitations.

The minimum extension is a versioned resident-to-module binding that composes existing authorities and lifecycle mechanisms:

- **Identity authority:** canonical resident identity and HR association come from the existing authoritative directory/HR source. The binding references that record and revision; it does not create or duplicate resident records or establish a new HR authority.
- **Binding:** declare resident principal ID, module ID/version, immutable artifact digest, resident execution contract range, binding revision, external configuration reference/revision, and authoritative identity/HR association reference. Display names, office labels, routes, and module names are not identity keys.
- **Configuration:** validate binding and executor-specific config against published schemas. Model route and office role are joined from existing authoritative/configured sources; neither the binding nor executor grants authority.
- **Lifecycle:** register, install, activate, health-check, stop, replace, disable, and remove through existing module registry/process lifecycle concepts. A binding update is loaded at a safe boundary without restarting CME or Ring 0. Failed replacement preserves the prior effective binding or leaves a visible recoverable blocked state.
- **Dispatch:** CME resolves the authoritative identity-to-binding relation, schedules through the existing activity path, and sends the existing resident execution envelope/profile. CME contains no per-resident entrypoint branch. The executor makes its own reasoning and domain decisions within CME-enforced authority.
- **Authorization:** CME uses existing principal/grant and capability invocation contracts. A binding is not a grant. Resident discovery does not authorize execution. Dispatch revalidates current binding and authorization.
- **State:** resident identity, module version, binding revision, activity lineage, and profile/config revisions remain attributable through replacement and recovery. Private resident state uses the module’s declared state boundary.

Target contract: `r3a.resident.module-binding.v1`, adjacent to (not a breaking replacement of) `r3a.resident.execution-profile@1.0.0`. Existing profile v1 remains valid for current compatible paths; generic executor registration requires a resolvable binding reference before activation/dispatch.

### 3.3 Durable workflow-handler modules — generic handler contract required

A durable workflow handler is a registered module capability that accepts CME-routed durable activities and advances the module-owned domain workflow. Existing `r3a.activity-intake.v1` defines source-to-CME evidence intake, but the implementation accepts only `grace.objective`; Store rejects other activity types at `r3a_runtime/db.py:1403-1413`. Existing CME code has task-specific routing and persistence branches. These are the demonstrated limitations. The intake contract remains useful and is preserved.

The minimum extension is `r3a.activity-handler.v1`, bound through the existing module registry and activity intake/scheduler/persistence/lifecycle mechanisms:

- A module manifest/config binding declares handler ID/version, supported activity-type namespace, request/result/progress/checkpoint schemas, compatible activity and handler contract ranges, concurrency/resource limits, required capabilities, and state ownership/migration metadata.
- The durable activity envelope carries an opaque, validated handler reference or resolves an activity type to one unique active registered handler. CME—not the provider—records the authoritative resolved module/version and binding revision. Ambiguous, missing, disabled, incompatible, or unauthorized handlers fail closed with durable diagnostics.
- CME creates and owns the institutional activity ID, idempotency/replay decision, scheduling lease, authorization decision, durable lifecycle/events, progress timestamps, and recovery/reconciliation state. It routes using the generic scheduler and declared binding; no per-domain `if activity_type` dispatch roster is added to CME.
- The handler owns domain-specific decisions, task behavior, evidence obligations, and its declared private state. It receives only validated activity input and authorized capability references. It cannot assign grants, forge CME lifecycle state, or claim external effects without evidence.
- The handler protocol reuses module `prepare/activate/health/execute/checkpoint/stop`, CME’s existing durable activity APIs, and the existing capability invocation envelope. Progress, typed outcomes, evidence references, and checkpoint/private-state references are versioned and correlated to activity and handler versions.
- Stop, replacement, failure, and restart preserve activity identity, event lineage, handler version, checkpoint and private-state ownership. CME records whether work resumed, reconciled, completed, or remains blocked. The handler’s declared recovery contract controls its private data; CME owns institutional lifecycle and recovery orchestration.
- Intake remains authorization-gated before handler execution. Retries are at-least-once with stable idempotency and explicit external-effect reconciliation; no exactly-once guarantee is implied.

The existing `r3a.activity-intake.v1` source envelope remains backward-compatible for existing providers. Its generic `activity_type` field may identify a module-owned workflow after the consumer and scheduler support a registered handler binding. Grace’s current `grace.objective` route remains a compatible handler during migration; no bulk domain migration is required.

## 4. Core and module responsibility boundary

| CME and Ring 0 own | Modules and residents own |
|---|---|
| Ring 0 supervision and CME lifecycle; generic module registry/lifecycle; safe-boundary configuration reload; dependency/contract compatibility; scheduler, leases, durable work routing and institutional activity/event state; authorization enforcement; capability invocation; generic progress, diagnostics, error reporting, and recovery coordination. | Capability behavior; resident reasoning and decisions; handler dispatch behavior after CME routes work; domain policy and workflow transitions; task-specific evidence obligations; module-declared private state, migration, and recovery behavior. |

The presence of domain-specific code in CME is evidence to review, not automatic authority for a wholesale extraction. Correct a specific branch when it prevents an assigned module from implementing its declared responsibility. Migrate incrementally, preserving operation IDs, data lineage, authorization, existing outcome semantics, and evidence. Keep generic scheduler and persistence primitives in CME.

### Specific domain branches for incremental correction

These branches are concrete current coupling points. They are not instructions to move all code at once. Keep CME’s authorization, institutional activity identity/state, leases, generic scheduling, audit, diagnostics, and recovery coordination. Module owners should first establish behavior-equivalence tests, then move only domain decisions/handlers that their assigned modules own.

| Current path | Specific shared-core behavior | Incremental module boundary and owner |
|---|---|---|
| `r3a_runtime/cme.py:1180-1207` and `r3a_runtime/db.py:1365-1401` | `notification.ingest` selects configured source adapters, enforces notification-specific idempotency/grant, parses and maps events into Grace objectives. | #48 Notification module produces validated `r3a.activity-intake.v1`; CME generic intake validates source invocation, persists and schedules. Preserve notification delivery/ack equivalence and existing source/event lineage. |
| `r3a_runtime/cme.py:1786-1813` | If no registered Knowledge provider resolves, CME validates `institution.knowledge.read` arguments, authorizes, reads configured knowledge paths, and creates evidence results. | #47 Knowledge provider/handler owns retrieval and grounding policy under its versioned operation/evidence contract; CME retains grant enforcement, invocation audit, and generic evidence reference persistence. Remove fallback only after provider equivalence and failure/denial tests pass. |
| `r3a_runtime/cme.py:1519-1537`, `2264-2268`, and `2364-2405` | CME validates Engineering assignment/proposal, creates the Engineering-specific work order, advances its states, and coordinates effectful operation plus verifier continuation. | AP2 Engineering handler owns proposal interpretation, workflow policy, task evidence and verifier coordination. CME retains generic durable activity/work routing, grants, leases, invocation audit, institutional state and recovery. Migrate only after authorization, work-order, verifier, and replay equivalence coverage is available. |

These paths are the first domain-specific correction candidates; their existence does not weaken the provider architecture or justify a CME rewrite. Each owner records the exact migrated behavior and retained generic CME responsibilities in its issue/acceptance evidence.

## 5. Configuration, versioning, state, and compatibility

- Module and binding configuration remains external, schema-validated, revisioned, and secret-free except for approved secret references.
- Existing semantic version parser and dependency graph evaluator remain authoritative for dependencies. All required contracts, protocol majors, operation schemas, and binding versions are declared and checked before activation.
- Configuration reload applies compatible module/binding changes at a safe boundary without restarting CME/Ring 0. Immutable bootstrap changes and incompatible infrastructure upgrades may require governed maintenance. Active-module removal requires deactivation/drain first.
- Stateless modules declare statelessness. Stateful modules name their owner, namespace, migration compatibility, checkpoint/recovery method, and data-retention relation. Metadata without executable migration/recovery evidence is not accepted as stateful upgrade support.
- Replacement preserves the prior effective binding/provider and durable state until the candidate passes compatibility, readiness, authorization-boundary, and recovery checks. Failure remains visible and recoverable.
- Existing process separation, filtered environment, digest pinning, and private socket remain. Because children share CME’s service UID, the module may access resources readable by that UID; explicitly allowlisted environment references can expose configured credentials. Do not report OS-level privilege separation. Stronger isolation is a separate approved threat-model decision.

## 6. Website and external integration obligations

Capability operations continue through the existing generic authenticated discovery/invocation API and Website registry UI. Website identity is derived from the authenticated session; invocation is authorized by CME. New modules must not require a module-specific Website gateway route for generic discovery, lifecycle status, diagnostics, or compatible common operations.

An assignment may require a tailored panel for a domain workflow. It consumes versioned authoritative APIs, shows actual lifecycle/health/freshness/errors, and does not become a second scheduler, identity authority, grant store, or direct model route. A backend module is not operationally accepted for an assignment requiring a Website action until that authenticated user journey works. Unique panels are not a universal requirement.

External integrations remain adapters/providers with explicit source identity, freshness, provenance, authorization, and failure semantics. They do not become shadow CME registries or schedulers.

## 7. Acceptance criteria

Each module role is reviewed independently. PASS requires evidence for applicable criteria; untested live requirements remain NOT VERIFIED.

### Common module criteria

1. Identify governing roadmap requirement, module owner, contract versions, dependencies, configuration schema/revision, artifact digest, state profile, and role (provider, resident executor, handler).
2. Add/configure/discover/activate/stop/replace/disable using external metadata and existing interfaces, without module-specific CME/Ring 0 edits or CME/Ring 0 restart during normal operations.
3. Verify compatible and incompatible dependency/version cases, explicit diagnostics, schema rejection, digest mismatch, and fail-closed behavior.
4. Verify CME authorization allow and deny; discovery/registration/binding alone never grants access.
5. Verify health/availability/freshness and errors use observed state. Verify Website/API flow when the assignment requires one.
6. Verify unrelated providers/handlers continue to work after add, replace, disable, and configuration reload.
7. Verify stop/restart/replacement preserves activity, event, configuration, binding, and state lineage as applicable.

### Resident-executor criteria

- Add a previously unlisted disposable resident executor artifact plus authoritative fixture identity/HR association and external binding. No CME/Ring 0 source change and no name/ID special case.
- Registry resolves the binding to one digest-pinned executor and profile; bad identity, missing association, incompatible version, stale binding, and missing grant deny execution with distinct diagnostics.
- Register/activate/health-check/dispatch/stop/replace the executor while CME and Ring 0 process identities remain unchanged. A safe-boundary deferral is reported truthfully.
- Two authorized residents can bind distinct module versions/routes/config without cross-resident identity, state, or conversation leakage. Resident decisions remain in the resident process; capabilities flow through CME.
- Replacement/recovery preserves durable activity and binding history. Directory roster visibility remains independent of execution eligibility.

### Durable-handler criteria

- Add a previously unlisted handler module and external handler binding; intake a valid non-Grace activity type and route it through existing CME scheduler/persistence without a domain-specific CME branch.
- Prove missing/incompatible/disabled/ambiguous handler rejection; authorization denial occurs before handler invocation; allowed execution includes audit and provenance.
- Prove stable replay idempotency, conflicting replay rejection, lease/attempt progress, typed result/evidence validation, checkpoints, stop/restart recovery, and explicit blocked outcome for uncertain side effects.
- Replace/deactivate a handler while work exists; work remains attributable to original handler/version and resumes under compatible replacement only according to declared migration/recovery contract.
- Demonstrate coexistence with `grace.objective`, provider modules, and at least one unrelated handler; no second scheduler or state store.

### Operational evidence boundary

Fixture tests prove contracts and isolation behavior in the fixture environment. Operational acceptance additionally uses an isolated running Ring 0/CME, disposable PostgreSQL schema/database, actual configured authorization provider, and the Website/API path where assigned. Record exact revision, environment, durable state evidence, process identities before/after, and limitations. No production service/database is used for this evidence.

## 8. Minimum compatibility rules

- Every invocation, binding, handler, and module process names a contract ID and semantic version/range.
- Compatible means the implementation explicitly supports the host’s required major and declared minor range; unknown is incompatible.
- New optional fields are backward-compatible minor additions only when existing consumers safely ignore or validate them under the published schema. Required semantic changes require a new major contract.
- Producers and consumers validate against the selected versioned schema. No untyped “best effort” coercion of identity, activity type, authority, or state is allowed.
- Dependency resolution uses the existing tested grammar/evaluator. Missing, cyclic, incompatible, or ambiguous dependencies prevent activation and remain discoverable with a diagnostic.
- This specification does not add automatic deprecation schedules, negotiation services, or a universal compatibility framework.

## 9. Implementation backlog and roadmap mapping

This is the minimum assignment-ready backlog. It assigns work to existing ownership areas; it creates no new coordinator or integration authority. Implementation is still subject to the applicable roadmap authorization and issue assignment.

| ID / order | Work | Existing interface to reuse; exact limitation | Minimum correction and owner | Roadmap/dependencies | Acceptance and regression coverage |
|---|---|---|---|---|---|
| MOD-B0 / 0 | Preserve provider profile and close provider documentation correction | External `capability_operations`, registry, `config.reload`, lifecycle controls and dependency evaluator already work. The historical foundation implementation record now identifies its startup-only/range statements as superseded and records current evidence. | No provider runtime change. Documentation correction is complete in this specification revision. **Owner for future doc drift:** Modular Plugins #46 / CME documentation owner. | AP0; prerequisite for all. No roadmap exception. | Provider/dependency fixture evidence remains 24 passed; document artifact staging, safe reload, same-UID boundary and fixture/live limits. |
| MOD-B1 / 1 | Generic resident-to-module binding | Reuse module manifest/registry/lifecycle, external config reload, resident execution profile, directory/HR authority, and existing resident IPC. Exact limits: config entrypoint allowlist only Observer/Grace; `_ensure_resident_module` launches Grace entrypoint for all secondary profiles; profile has no authoritative module binding ID/version. | Add `r3a.resident.module-binding.v1`; resolve canonical resident+HR reference to module/version/artifact/config revision; replace hardcoded dispatch with registry binding lookup; preserve existing CME scheduler and grants. **Owners:** CME/Autonomy #43 (dispatch), Modular Plugins #46 (binding/registry), HR/directory owner (authoritative association). | AP0 contract/config/lifecycle foundation, then AP4 generic onboarding/resident rollout. Depends on MOD-B0 and existing directory/HR contract. | New fixture executor loads/reloads/activates/replaces without CME/Ring0 restart; two residents/version bindings; grant denial; identity/binding mismatch; route/config correctness; profile compatibility; existing Grace/Observer and chat roster regression. |
| MOD-B2 / 2 | Generic durable activity-handler contract and scheduler binding | Reuse `r3a.activity-intake.v1`, CME durable activity/event APIs, scheduler lease/checkpoint lifecycle, capability authorization, and module process protocol. Exact limit: `Store.submit_activity_intake` rejects non-`grace.objective`; scheduler/dispatch branches assume Grace task classes and domain paths. | Define `r3a.activity-handler.v1`, configured type-to-handler binding, generic lifecycle/result/progress/checkpoint protocol, CME-owned activity routing/state and module-owned workflow/state. Replace the type rejection with generic validated routing. **Owners:** CME/Autonomy #43 (scheduler/persistence), Modular Plugins #46 (registration/contract), assigned module owner (handler behavior). | AP0 contract and durable scheduling correction; AP1 Grace/notification adoption and AP2 Engineering adoption in existing phase order. Depends on MOD-B0 and MOD-B1 dispatch/lifecycle reuse where a resident is handler. | Non-Grace fixture activity reaches handler with no CME domain branch; replay/conflict, grants, lifecycle/restart, checkpoints, replacement, evidence/schema rejection; `grace.objective` regression; provider coexistence. |
| MOD-B3 / 3 | State and replacement conformance for stateful modules | Reuse module state namespace, durable activity state, checkpoint, migration/recovery metadata. Exact limit: tested provider profile is stateless; manifest fields do not demonstrate generic state migration/recovery. | Enforce truthful stateless declaration; require module-owned migration/checkpoint/recovery evidence only for modules with durable private state. **Owner:** Module owner with CME/Modular Plugins #46. | AP0 state contract; before any stateful handler/resident replacement. | State ownership isolation, migration success/failure, rollback/blocked outcome, no lineage loss, existing stateless provider replacement. |
| MOD-B4 / 4 | Website/API evidence for generic modules | Reuse authenticated capability discovery/invocation and existing diagnostics/registry API patterns. Existing generic operation UI is verified; live authenticated module-management and handler UX are not. | First verify available authoritative APIs. Add only the common status/control surface required by assigned Website functions; no per-module gateway branch for generic capabilities. **Owners:** Website #51 with CME/Coordinator #43 and module owner. | AP0 diagnostics/API; AP1/AP2/AP4 only where their assignment requires a Website flow. | Authenticated end-to-end Website/API journey; server-derived principal; CME grant allow/deny; truthful state; no direct model route; generic UI works for two unrelated modules. |
| MOD-B5 / 5 | Source, focused, then live acceptance | Existing tests cover provider path; no generic resident binding or handler fixture exists. | Add role-specific contract fixtures and execute isolated live acceptance after implementation is separately authorized. **Owner:** Independent Auditor verifies; implementation owners provide evidence. | Follows MOD-B1–B4; align to existing AP milestone/issue; no new gate service. | Common and role-specific criteria in section 7; operational results remain distinct from unit/fixture results. |

## 10. Roadmap reconciliation and exceptions

The backlog fits the approved Roadmap Baseline 1.0. MOD-B0 and contract foundations for MOD-B1/MOD-B2 align with AP0’s registries, versioned contracts, external configuration, durable state, recovery, and lifecycle. Generic resident onboarding and authority composition align with AP4’s new residents/responsibilities joining through versioned contracts and authoritative HR ownership. Grace/continuity handlers align with AP1; Engineering handlers align with AP2. Website work remains tied to the existing AP0 diagnostics/API and the specific AP assignment requiring user-facing operation.

This specification does not reorder phases, change priorities, add a product feature to AP0, or authorize production/runtime implementation. **No roadmap exception is required for this architectural clarification.** If implementation scheduling, scope, or phase ownership later departs from Baseline 1.0, record and obtain approval for a specific exception before executing that deviation. The exception register remains unchanged; no exception is proposed by this document.

## 11. Disposition of proposals P-01–P-13

| Proposal | Final disposition under Steward decision |
|---|---|
| P-01 | Documentation clarification. Keep provider, resident-executor, and durable-handler roles distinct. |
| P-02 | Targeted corrections only when source evidence shows a module-assigned responsibility trapped in CME/Ring 0/Website core. No wholesale rewrite. |
| P-03 | Preserve existing provider lifecycle/config behavior; do not duplicate it. |
| P-04 | Normal compatible module registration/configuration/activation/deactivation/replacement/removal is restart-free for CME and Ring 0; maintenance/incompatible infrastructure changes are separately governed. |
| P-05 | Preserve current dependency grammar/evaluator and fail-closed checks; correct stale documentation. |
| P-06 | Target state migration/recovery corrections to stateful modules whose existing obligations require them. |
| P-07 | Required generic resident-executor binding using authoritative existing identity/HR association and module lifecycle. |
| P-08 | Document existing provider API-to-worker protocol mapping; no new transport abstraction. |
| P-09 | Accurately report current same-UID process boundary; stronger isolation deferred to an approved threat model. |
| P-10 | Apply the minimum compatibility rules in section 8; no universal deprecation framework. |
| P-11 | Required generic durable activity-handler contract extending existing intake/scheduler/persistence/lifecycle mechanisms. |
| P-12 | Preserve generic Website capability discovery/invocation; tailored panels only when assigned workflow requires them. |
| P-13 | Preserve existing provider fixture conformance and add resident/handler role-specific acceptance fixtures. |

## 12. Review and change control

Auditors assess each role against the applicable approved roadmap, this specification, and versioned interface contracts. Findings cite requirement, exact code/interface, revision, executable evidence, limitations, responsible workstream, and smallest correction. Statuses are PASS, FAIL, BLOCKED, NOT VERIFIED, or NOT APPLICABLE. Implementation owners correct findings; the Auditor independently verifies; the Steward retains acceptance and exception authority. No review service or runtime subsystem is created.
