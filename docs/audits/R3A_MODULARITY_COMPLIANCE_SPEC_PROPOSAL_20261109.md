<!--
R3 CONTROLLED DOCUMENT
File: docs/audits/R3A_MODULARITY_COMPLIANCE_SPEC_PROPOSAL_20261109.md
Component: R3A-MODULARITY-COMPLIANCE-SPEC
File Revision: 1.2.0
Created: 2026-11-09T23:34:13Z
Created By: Codex GPT-6, acting as independent Auditor
Purpose: Propose an enforceable, cross-cutting definition of R3A modular compliance for Steward review.
Execution Model: N/A; specification proposal
Observability: Requirement IDs, contract matrix, and acceptance evidence are recorded in linked audit documents.
Dependencies: Approved R3 Charter Revision 2; R3A Charter and Roadmap Baseline 1.0; AP0/module/capability/state/acceptance contracts; cited shared interfaces.
Authority: Proposal only under Steward Directive — Auditor / Reviewer V2, 2026-11-09. Does not amend approved requirements or authorize implementation.
Changed: 2026-11-09T23:34:13Z | R3A-AUDIT-V2 | Codex GPT-6 | Initial modular compliance specification proposal.
Changed: 2026-11-09 | R3A-AUDIT-V2 | Codex GPT-6 | Recalibrated P-01–P-13 against executable provider, reload, dependency, authorization, and Website evidence; see existing extensibility verification.
Changed: 2026-11-10T00:17:40Z | R3A-MODULARITY-DECISIONS | Codex GPT-6 | Mark historical proposal superseded by Steward-authorized architecture specification v1.
Supersedes: None. Superseded By: `docs/architecture/R3A_MODULARITY_COMPLIANCE_SPECIFICATION_V1.md` revision 1.0.0, authorized under AD-024.
Contracts: MOD-001–MOD-010; AP0-004–010; AD-001–010; capability, lifecycle, state, and shared domain interfaces.
Tests: N/A; specification proposal.
History/Predecessor: Initial proposal revision in auditor branch; immediate predecessor commit 87d868d7e2a64da1d58ca71eb9899d61b5a1d2b2 (file blob bc98aca9bfe46fe18a403492e337d2c420bf5c16).
-->
# R3A Modularity Compliance Specification — proposal for Steward review

**Status:** Historical proposal, superseded. The governing specification is [R3A Modularity Compliance Specification v1](../architecture/R3A_MODULARITY_COMPLIANCE_SPECIFICATION_V1.md), authorized by Steward decision AD-024. The classifications and evidence below remain historical audit records; the final disposition is in the governing specification.
**Review baseline:** `9a41d7e9647d37c2b7dc6f2aca3be3f5f82ccfe9`; current extension verification and contract comparison are in [the existing extensibility report](R3A_EXISTING_EXTENSIBILITY_VERIFICATION_20261109.md) and [the interface gap analysis](R3A_INTERFACE_CONTRACT_GAP_ANALYSIS_20261109.md).
**Purpose:** Turn the approved modularity direction into an auditable definition across core, modules, residents, external integrations, and user interfaces.

This proposal preserves approved requirements and offers additional clarifications for Steward decision. Nothing in the proposed section below is an approved architectural requirement until the Steward accepts it and records the decision in the approved architecture/decision mechanism.

## 1. Authority and source hierarchy

The compliance hierarchy is:

1. Approved R3 Charter Revision 2 for inherited institutional authority, identity, persistence, privacy, and operational responsibilities.
2. Approved R3A Architecture Charter for component roles and modular direction.
3. Steward-approved R3A Master Roadmap Baseline 1.0 for scope, AP ownership, and acceptance evidence. Newer explicit Steward requirements apply prospectively to their stated scope.
4. AP0 technical, module lifecycle, state/diagnostic, capability, and testing/acceptance contracts for detailed obligations.
5. Versioned domain/API contracts and approved architectural decisions/exceptions.
6. Implementation documents, handoffs, issues, and tests as evidence of design, status, or behavior; these do not independently amend architecture.

Original approved obligations are listed separately below from proposed clarifications. Historical work must be assessed against the requirement and contract versions in effect when that work was authorized. Later Website and chat directives are additive from their issue/directive dates; they do not retroactively make a previous delivery noncompliant.

## 2. Approved requirements carried forward

The following are already directed or approved; this proposal does not create them:

| ID | Existing authority | Requirement carried forward |
|---|---|---|
| A-01 | Charter / AD-001–003 | Ring 0 is a minimal supervisor. CME coordinates lifecycle, scheduling, authorization, resource use, progress, and observability. Resident judgment and domain decisions remain with residents. |
| A-02 | Charter / AD-004 / MOD-001 | Modules are independently identifiable, versioned implementations with declared contracts and dependencies. Modules can be installed, activated, stopped, and replaced without restarting Ring 0. |
| A-03 | MOD-002–005 | Core consumes module metadata through a registry/loader boundary; private module behavior is not a fixed core roster. Contract incompatibility prevents activation with an explicit diagnostic. Lifecycle state is durable and visible. |
| A-04 | MOD-006 / AD-P03 | Discovery and registration do not grant invocation authority. CME enforces existing institutional authorization and audits invocation. |
| A-05 | MOD-007 / AP0-009 / AD-008 | Operational configuration is external, validated, revisioned, and contains protected secret references rather than plaintext secret values. |
| A-06 | MOD-008–009 / AP0-004–006 / STM-003–007 | Durable state, events, ownership, recovery, and replacement preserve lineage; uncertain work remains visibly blocked/degraded rather than falsely complete. |
| A-07 | MOD-010 / AP0-010 / STM-006 | Health and diagnostics use observed runtime state, identify freshness, and expose unknown/unavailable honestly. |
| A-08 | AP0-007–008 | A compatible module fixture can be registered/discovered and lifecycle-managed without restarting Ring 0; registry discovery is distinct from authorization. |
| A-09 | Capability Contract v1 / AP0 | Capability operations use versioned typed requests/results, declared effects, schemas, grants, evidence, retry/idempotency and reconciliation semantics; CME owns invocation authorization and audit. |
| A-10 | Charter / AP0 / TAP-001–006 | Operational acceptance requires evidence at the intended boundary. Tests, source presence, mocks, and an HTTP success alone do not establish operation or acceptance. |

The implementation evidence changes the initial assessment. Generic capability-provider packages already have a usable external configuration, registry, lifecycle, invocation, authorization, and replacement path; configuration can be reloaded by a running CME. This demonstrates replaceable provider behavior without modifying CME or Ring 0 source. It does not establish a generic resident-executor loader or arbitrary durable module-owned workflow handler. The exact limitation for durable intake is that `Store.submit_activity_intake` accepts only `grace.objective`. Domain-specific CME branches are concrete, but whether each branch violates the approved module boundary depends on which domain behavior the assigned module is required to own; a provider implementation can be replaced today without claiming the entire related workflow has been extracted. The prior foundation implementation note's statements that dependency ranges are unsolved and modules are startup-only are contradicted by current source and fixture tests and should be treated as stale evidence.

Two implementation observations conflict with existing contract text and need reconciliation even before proposed requirements are considered: the module lifecycle contract describes supervised **unprivileged** child processes, while the implementation record says provider children share the CME service UID; and the module manifest requires state/migration/recovery fields while that implementation record says current providers are assumed stateless. These are contract/implementation clarity or conformance issues; this proposal does not select a stronger sandbox or migration technology.

## 3. Proposed clarifications requiring Steward approval

These proposals make existing terms more testable or add requirements beyond current approved wording. Each should be accepted, edited, or rejected explicitly.

| ID | Proposed clarification | Why needed / change status |
|---|---|---|
| P-01 | Define **module** as an installable/versioned artifact and ownership boundary; define **capability operation**, **provider**, **resident executor**, **activity intake**, and **activity handler** as distinct interfaces that a module may implement. One module may publish multiple operations; an operation/provider is not automatically a full module. | New precision. Current specs and implementation use “module,” “provider,” and “plug-in” across different process and lifecycle scopes. |
| P-02 | A module is not compliant if adding, configuring, replacing, disabling, or removing its behavior routinely requires adding/changing module-specific branches in CME, Ring 0, shared persistence, or Website gateway code. Generic lifecycle, authorization, event, and API adapters may change once to establish a reusable interface; an individual module plugs into that interface through metadata/configuration. | Clarifies the approved no-fixed-roster/core independence principle; formalizes a measurable core-edit test. Existing hardcoded behavior is assessed against when this clarification is approved, not retroactively. |
| P-03 | Module registration, configuration, activation, discovery, and use are separate observable operations. Each has an idempotency/correlation identity, actor/authority evidence, target module/version, compatibility outcome, and durable diagnostic. Installing an artifact never activates it or grants capabilities. | Adds enforceable operation semantics. The current lifecycle contract names states but does not fully define an end-to-end lifecycle API or registration trust boundary. |
| P-04 | State whether compatible external configuration can register a previously unlisted module into an already-running CME. If required, support it without restarting Ring 0 or CME; if runtime registration is not required, state the permitted safe reload boundary and prove it without source edits. | This is an open policy choice, not an assumption: approved MOD-004 explicitly protects Ring 0 availability, while current loader behavior is startup-configured. Steward should select the required CME availability guarantee. |
| P-05 | Define one module-level compatibility declaration that names supported protocol, operation, configuration, dependency, state/migration, and host-service contract versions. Specify dependency range grammar and evaluation. Unknown/missing compatibility is incompatible; ranges are not accepted as satisfied until the evaluator resolves them. | Clarifies MOD-001/005/008. Current module manifest fixes its own schema version but uses unconstrained strings for dependency ranges; current implementation documentation says ranges are not solved. |
| P-06 | For every stateful module, activation/upgrade requires a declared state owner/namespace, migration compatibility, backup/recovery behavior, and old-version retention. Stateless modules must declare that explicitly. State namespace and migration fields cannot be placeholders used to claim stateful compatibility. | Strengthens MOD-008/009; current implementation record says provider binding assumes stateless modules despite manifest fields. |
| P-07 | A module's required identity/authority mapping is explicit, source-grounded, versioned, and separate from module/display names, office roles, model routes, and grants. The module manifest may identify its owner, but may not assert resident identity or permissions. | Clarifies identity/config/authority separation; useful for generic resident binding. No new HR endpoint or identity authority is implied. |
| P-08 | The module protocol and provider-call API must define one normative transport/behavior contract and any adapters between them. The documented synchronous `CapabilityProvider.invoke` abstraction and AP0 child-process JSON-lines protocol must not leave call ordering, timeout, cancel, error, health, and evidence semantics ambiguous. | Resolves a contract-layer gap without prescribing a new transport. Existing API docs describe both Python call shape and process protocol at different layers. |
| P-09 | Isolation claims name the actual OS/process boundary and threat model. “Separate child process” does not imply a different UID or a security sandbox. A module that shares CME credentials/authority is explicitly trusted at that level; stronger unprivileged isolation is required only if the approved threat model selects it. | Clarifies AP0 wording: the lifecycle implementation record reports children share CME service UID, while the module contract says unprivileged child process. This proposal does not choose a stronger sandbox. |
| P-10 | Each contract version declares compatibility/evolution rules: required vs optional fields, unknown fields, deprecation period, major/minor behavior, and a conformance test fixture. A consumer that cannot safely interpret a version fails visibly. | Adds a reusable versioning rule; current schemas often use `additionalProperties: false` and major/minor support is inconsistent between manifest, operation, invocation, and adapter docs. |
| P-11 | Domain behavior that turns events into durable work, advances module-owned workflows, or imposes evidence obligations uses generic handler/intake/evidence interfaces. Domain-specific policy and judgment stay in the owner module/resident; generic CME persists, schedules, authorizes, and exposes lifecycle. | New extension-point requirement. Prior audit explicitly found notification intake, Engineering workflow, and Knowledge evidence semantics remain core-specific and the generic activity-handler/evidence contracts are missing. |
| P-12 | Website extensions consume discoverable, versioned service/API contracts and registry metadata. A module capability or Website panel is not accepted as institutionally usable solely from backend/API tests when the assignment requires a user-facing function. Website must not hold a second scheduler, identity source, authorization store, or direct model route. | Adds testable cross-cutting interpretation of approved HMI/registry boundaries and the later Class I Website directive, prospectively. |
| P-13 | Define extension conformance as both negative and positive: a generic fixture module can be added, configured, activated, invoked under grant, denied without grant, replaced/stopped, and removed/disabled without module-specific core edits; existing unrelated modules continue to work. | Makes independent replaceability measurable. Current MOD criteria cover parts but not a full add/use/remove/coexistence cycle. |

## 3A. Evidence-based disposition of proposals (2026-11-09)

The classifications below supersede the initial “why needed” assumptions in P-01–P-13. They do not approve any proposal or add mandatory requirements. Evidence and limits are in [the existing extensibility verification](R3A_EXISTING_EXTENSIBILITY_VERIFICATION_20261109.md).

| Proposal | Classification | Verified disposition / smallest action |
|---|---|---|
| P-01 | DOCUMENTATION ONLY | Document capability-provider package, resident executor, and durable activity handler as distinct existing/possible roles. No new interface is needed for ordinary capability providers; resident execution and durable handler limitations are separately identified. |
| P-02 | IMPLEMENTATION CORRECTION | Approved MOD-002 already supplies the core-boundary obligation. Correct only specific behavior that an assigned module must own and that CME prevents replacing; no wholesale extraction. |
| P-03 | ALREADY SATISFIED | Provider install/status/activate/deactivate/replace and config revision are implemented and fixture-tested. Live production operation remains unverified. |
| P-04 | NEW POLICY DECISION | CME reload and provider registration without CME restart are implemented. Stronger guarantees for all package staging and arbitrary resident executors exceed the existing Ring 0 availability guarantee. |
| P-05 | ALREADY SATISFIED | Dependency range grammar, compatibility evaluation, missing/incompatible dependency and cycle validation run during config load; covered by module-contract tests. |
| P-06 | IMPLEMENTATION CORRECTION | Existing state contract applies. Provider fixture path is stateless; generic stateful migration/replacement recovery is not established. Smallest correction is enforce truthful stateless/stateful declarations and implement missing migration guarantees only for modules that own durable state. |
| P-07 | IMPLEMENTATION CORRECTION | Current resident executor configuration is limited to Observer/Grace and no generic resident-to-module artifact binding exists. Correct this only if generic independently developed resident executors are in approved scope; no new HR operation is implied. |
| P-08 | DOCUMENTATION ONLY | Provider adapter and worker protocol already connect typed invocation to isolated provider process lifecycle. Clarify mapping of errors/timeouts where the documents diverge; no new transport abstraction shown necessary. |
| P-09 | NEW POLICY DECISION | Runtime providers are separate processes with scrubbed environment and private socket but share CME's service UID. Resolve the meaning of “unprivileged” with a threat model before selecting stronger isolation. |
| P-10 | NEW POLICY DECISION | Existing interface versions and schema validation work; a universal deprecation/unknown-field evolution policy is additional policy, not a demonstrated extension blocker. |
| P-11 | CONTRACT GAP | Existing provider calls and Grace activity intake work, but durable intake rejects non-`grace.objective` activity. A generic handler extension is only needed if approved assignments require module-owned durable workflows; use the existing intake/scheduler boundary for the smallest extension. |
| P-12 | ALREADY SATISFIED | Generic capability discovery/invocation API and generic Website operation UI exist. Unique module panels are not required. Live authenticated Website operation is not verified. |
| P-13 | ALREADY SATISFIED | Existing isolated fixture tests cover external provider registration, discovery, lifecycle, authorized/denied invocation, replacement, stop/disable, and coexistence without core edits. They do not establish live Ring 0/PostgreSQL operation. |

## 4. Responsibility boundaries under this proposal

These boundaries reflect approved roles; proposed clarifications only make their interfaces explicit.

| Actor | Owns | Must not own |
|---|---|---|
| Ring 0 | CME process supervision and minimal core availability. | Per-module domain behavior, resident choices, module roster logic. |
| CME | Generic scheduling, lifecycle coordination, durable activity/event plumbing, invocation authorization enforcement, resource coordination, and diagnostics. | Resident intelligence/decisions, module-specific workflow policy, identity invention, grants from registry presence. |
| Module/provider | Declared operation behavior, module-owned domain state and migration, schema-valid output/evidence, readiness/health according to declared contracts. | Grant decisions, CME lifecycle writes, cross-module private state, authority outside its declared scope. |
| Resident executor | Reasoning, domain decisions, work proposals, and action selection within its identity, profile, assigned authority, and available capabilities. | Bypassing CME or self-assigning grants/module identity. |
| External integration | Source-of-truth data/service under its declared ownership, authenticated contract and availability/freshness evidence. | Becoming a shadow CME registry or silently supplying stale/unverified authority. |
| Website/HMI | Authenticated presentation and user actions through authoritative versioned APIs; truthful status and errors. | Institutional truth, identity/grant authority, scheduling, direct model execution, fabricated status. |

## 5. Proposed module conformance profile

This profile is proposed for approval and subsequent contract revision. It is not an implementation instruction by itself.

### Identity and declaration

- Stable `module_id`; immutable `module_version`; owner and supported contract/version ranges.
- Immutable artifact identity/digest and explicit binding/entrypoint.
- External config schema/reference and configuration revision; declared dependencies with an evaluable grammar; capability/resource references.
- Explicit stateful/stateless declaration, namespace, migration and recovery compatibility.
- Explicit authority/identity references where needed, never embedded grant authority.

### Lifecycle and discovery

- Separate installed, configured, compatible, activating, active, stopping, stopped, failed, replacing, incompatible, and blocked states; availability/health/authorization remain separate dimensions.
- Registration and each lifecycle mutation are authorized, idempotent, correlated, auditable and durably diagnosable.
- Discovery returns declared identity/version/contracts, lifecycle/health/freshness, owner, dependencies and interface metadata. Discovery alone does not invoke or authorize.
- A failed update preserves prior effective version and durable data or leaves an explicit recoverable blocked state.

### Invocation and domain work

- Operations declare typed input/output/evidence, effect, caller/target scope, grants, timeout, idempotency/replay/reconciliation behavior, and contract version.
- CME validates request and authority before execution and records the canonical decision, provider/module version, outcome/effects, evidence, and correlation lineage.
- A module cannot write CME-owned state directly. Stateful module data crosses its declared persistence/migration boundary; generic state and lifecycle events are CME-owned.
- Event-to-activity and activity-handler extension points preserve domain ownership while CME supplies durable scheduling and recovery.

### Operational acceptance

- Source review checks no module-specific core branches, no duplicated identity/registry/scheduler, complete version/config/state declarations, and authority isolation.
- Contract checks cover valid/invalid compatibility, schemas, authorized/denied calls, stale/unavailable providers, retries/idempotency, health, error/evidence shape, lifecycle/replacement and data preservation as applicable.
- Integration check uses actual Ring 0/CME and a disposable database, proves install/configure/activate/discover/invoke/stop or replace while Ring 0 stays available, and demonstrates coexistence with an existing module.
- User-facing module check exercises the actual authenticated Website entry point if required by its assignment. Tests and a live service check are separately recorded.
- Report PASS/FAIL/BLOCKED/NOT VERIFIED/NOT APPLICABLE per requirement, with exact revision, evidence, deviation and owner. Reviewer recommends; Steward decides acceptance or exception.

## 6. Approval and change control

Steward review questions:

1. Approve, revise, or reject P-01–P-13 individually or as a grouped proposal.
2. In particular, decide P-04's CME runtime-registration/reload availability boundary and P-09's required process-isolation threat model.
3. If accepted, designate the approved version and change-control record. Then update affected versioned contracts and Roadmap/exception records as necessary before using proposed clauses as mandatory criteria for new work.

Until that decision is recorded, auditors may cite P-items as **proposed gaps**, but must not issue a FAIL solely for violating a proposal. Approved A-items remain enforceable against the versions and scope that governed the work.
