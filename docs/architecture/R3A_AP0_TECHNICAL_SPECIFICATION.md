<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_AP0_TECHNICAL_SPECIFICATION.md
Component: R3A-AP0-SPECIFICATION
File Revision: 1.0.0
Created: 2026-11-06T03:39:05Z
Created By: Codex GPT-6
Purpose: Bound the AP0 institutional foundation and state its functional acceptance requirements.
Execution Model: N/A; technical specification only.
Observability: Acceptance evidence linked to AP0 requirement IDs at a named revision/environment.
Dependencies: R3A Architecture Charter; Module Lifecycle and Contract Specification; State Machine and Diagnostic Contract; Bounded Testing and Acceptance Policy.
Authority: Steward directive authorizes AP0 specification only; implementation requires further Steward authorization.
Changed: 2026-11-06T03:39:05Z | R3A-BASELINE-001 | Codex GPT-6 | Establish initial AP0 specification.
Supersedes: None.
Contracts: R3A architectural decisions AD-001–AD-009, AD-021.
Tests: Not run; documentation only.
History/Predecessor: New document; initial publication recorded in Git.
-->
# AP0 Technical Specification

**Status:** PLANNED — specification only. The Steward has not authorized runtime implementation.
**Objective:** Establish the smallest functioning institutional foundation with independently supervised CME, durable truthful operation, and a viable module/capability lifecycle.

## Scope boundary

### Included

- Minimal persistent Ring 0 supervisor.
- CME as an independently supervised and restartable process/component.
- Database-backed operational state, events, applied configuration revisions/references and continuation state.
- Structured, versioned state-machine execution shared with diagnostics.
- Minimal module registry and capability/resource registry.
- Validated external configuration.
- Actual health, lifecycle, transition, timing, progress and exception diagnostics.
- Restart/recovery behavior for Ring 0/CME and in-flight generic activities.
- Bounded, risk-based validation with evidence.

### Excluded

Full Engineering work management/execution; Jessica or resident character development; 3D/Quest presentation; advanced security administration; general resident onboarding/HR; replacing R3 services; production data migration/deployment; implementation of future AP features. Bitwarden/TOTP/YubiKey and secure remote Steward operations are early roadmap requirements but not a reason to enlarge AP0's module/domain scope. AP0 must keep the secret-reference and authentication boundaries compatible with them.

## Components and responsibilities

| Component | AP0 responsibility | Explicit non-responsibility |
|---|---|---|
| **Ring 0** | Remain alive as the minimal core supervisor; load validated external configuration; supervise CME lifecycle; expose its own process and CME health; record/reconcile CME lifecycle. | Resident reasoning, Engineering decisions, capability policy, module-domain state, approval/grant decisions. |
| **CME** | Run independently under Ring 0 supervision; schedule registered work; coordinate configured resource claims; record progress and exceptions; maintain/reconcile its process lifecycle and module lifecycle. | Replace Grace's investigation/corrective direction; infer authority from registration; silently discard blocked work. |
| **Module registry** | Describe installed/active module identity, contract versions, dependencies, lifecycle state and health. | Supply module behavior or confer permissions. |
| **Capability/resource registry** | Describe institutional resource/capability identity, owner, contract/version, availability/health and invocation reference. | Replace authorization/grants or claim availability when unobserved. |
| **Persistence layer** | Store operational state, event lineage, config references, registry state and continuation/checkpoint references durably. | Keep secrets or unbounded external payloads without the approved data classification/retention decision. |
| **Diagnostic interface** | Read state-machine definitions and durable runtime state to expose actual status and history. | Write operational state or derive activity from presentation/mock values. |

## Functional requirements

| ID | Requirement | Depends on | Acceptance evidence |
|---|---|---|---|
| AP0-001 | Ring 0 SHALL start from validated external configuration and remain available while CME restarts. | Config schema; process ownership. | In isolated environment, demonstrate core health before/after CME restart without Ring 0 restart; capture process IDs/revisions and lifecycle records. |
| AP0-002 | Ring 0 SHALL supervise CME startup, health, stop and restart using an explicit lifecycle contract. | AP0-001; lifecycle states; restart policy decision. | Inject CME exit/failure; observe durable detected state, restart action/outcome, and healthy return or explicit blocked condition. |
| AP0-003 | CME SHALL schedule registered eligible work and account for configured resources. | State catalog; resource definitions; unresolved policy limits. | Show an eligible item dispatched, progress recorded, and resource ownership/release represented in durable state. Test parameters must be justified/configured, not arbitrary policy. |
| AP0-004 | Activities, events, registry records, effective configuration revisions/secure references, and continuation state SHALL be database-backed and restart-reconcilable. | PostgreSQL deployment/schema/migrations; config ownership/retention decisions. | Create state/event and apply a config revision, restart CME, query the same lineage and effective revision; validate migration/transaction behavior on disposable data. |
| AP0-005 | Runtime transitions SHALL be accepted/rejected by versioned state-machine definitions also used for diagnostics. | State Machine and Diagnostic Contract. | Valid transition accepted; invalid transition refused and recorded; diagnostic catalog/transition agrees with execution definition. |
| AP0-006 | A recoverable interruption SHALL preserve the activity identity, prior event lineage and continuation reference; it SHALL NOT report success or silently terminate. | AP0-004/005; idempotency/side-effect decision. | Interrupt during a recoverable activity, restart, inspect transition/lineage, resume or identify a visible evidence-backed block. |
| AP0-007 | The module registry SHALL represent install, activate, stop and replace lifecycle without restarting Ring 0. | Module lifecycle contract; process/runtime binding choice. | In isolated environment, install/activate/stop/replace a contract fixture while Ring 0 remains available; status and version changes are recorded. |
| AP0-008 | The capability/resource registry SHALL provide discovery metadata independently of authorization. | Registry schema; existing authority/capability compatibility. | Enumerate registered capability and its contract/health; prove discoverability does not authorize invocation (authorization remains denied absent grant). |
| AP0-009 | Operational settings SHALL be external to executable source, validated, and represented by durable effective configuration records/revisions. | Config source-of-truth and reload decisions. | Change a disposable config value; startup validates it; the database records the effective revision and provenance/reference; diagnostics report it and invalid-config failure. Secret values are not emitted or persisted in plaintext. |
| AP0-010 | Diagnostics SHALL expose actual process, module, activity and resource lifecycle, timestamps/durations, progress, exceptions, freshness and evidence references. | AP0-004/005; interface/auth decision. | Compare diagnostic output to durable records through healthy, failed, restarting and stale/unavailable states; no synthetic status. |
| AP0-011 | AP0 SHALL preserve external process and data separation from production R/3. | Isolated Camrui worktree/dev deployment plan; credentials/data decision. | Evidence shows dev-only paths/service/process/database; no production service/config/database touched. |
| AP0-012 | AP0 validation SHALL be bounded, risk-based and proportional without relaxing substantive acceptance. | Testing and Acceptance Policy. | Evidence bundle includes named revision, scenarios, actual results, residual gaps and reviewer/acceptance status; no suite expansion unless separately authorized. |

## Persistence and configuration constraints

The approved R3 Charter Revision 2 specifies PostgreSQL as the institutional structured-record/history foundation; AP0 shall align with that direction. The audit and Phase 0A investigation describe the current R3 institutional runtime's SQLite prototype. Do not treat that prototype as an approved R3A backend decision or silently migrate its data. PostgreSQL host/topology, schema namespaces, migrations, pooling, backup, event retention and data classification remain open decisions.

Runtime behavior SHALL be configured outside executable source. R3 bootstrap currently calls for documented validated JSON configuration; AP0 should conform unless a Steward-approved R3A supplement selects otherwise. The database SHALL record each applied configuration revision, effective non-secret values or protected references, provenance and activation time; configuration transport/source-of-truth and reload semantics remain OPEN. Configuration identifies component versions, database/secret references, resource policy and diagnostic settings, but MUST NOT contain plaintext secrets or grant authority by listing a capability.

## Proposed AP0-M1 implementation sequence (not authorized)

This is a dependency-ordered proposal for subsequent review; no step may begin until the Steward authorizes implementation.

1. Resolve the AP0 blocking decisions (process owner, PostgreSQL topology/schema/migrations, config source and reload, CME restart policy, resource dimensions/limits, secret references, diagnostic transport/auth, and recovery/idempotency).
2. Implement isolated external configuration validation and database schema/migration foundations; capture effective config and schema revisions.
3. Implement Ring 0 health/lifecycle supervision and a separately startable/stoppable CME child component; prove CME restart leaves Ring 0 alive.
4. Implement durable versioned state-machine definitions, events and generic activity continuation/reconciliation; prove valid/invalid transitions and crash recovery.
5. Implement minimal module and capability/resource registries with discovery separated from authorization; exercise install/activate/stop/replace without Ring 0 restart.
6. Implement truthful diagnostic projections directly from state definitions and durable records; verify staleness and exceptions.
7. Run only the bounded acceptance scenarios in the policy on disposable isolated state; produce evidence and unresolved-gap report before any operational acceptance request.

## AP0 exit condition

AP0 is ready for independent acceptance only when every AP0 acceptance row has evidence for the same named integration revision in the isolated target, the failure/restart/recovery path is exercised, diagnostics match the authoritative state/event data, production remains untouched, and a reviewer can distinguish verified behavior from remaining limitations. AP0 does not prove Engineering completion, resident autonomy, remote production access, or production readiness.
