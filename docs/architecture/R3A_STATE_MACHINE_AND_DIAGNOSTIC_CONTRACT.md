<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_STATE_MACHINE_AND_DIAGNOSTIC_CONTRACT.md
Component: R3A-STATE-DIAGNOSTIC-CONTRACT
File Revision: 1.0.0
Created: 2026-11-06T03:39:05Z
Created By: Codex GPT-6
Purpose: Define the shared versioned state-machine and truthful diagnostic contract.
Execution Model: N/A; contract specification.
Observability: Structured state catalogs, durable transitions and diagnostic projections.
Dependencies: R3A Architecture Charter; AP0 Technical Specification; Module Lifecycle and Contract Specification.
Authority: Steward directive; encoding, retention and transport choices remain open where noted.
Changed: 2026-11-06T03:39:05Z | R3A-BASELINE-001 | Codex GPT-6 | Establish initial state and diagnostic contract.
Supersedes: None.
Contracts: AD-005, AD-006, AD-009, AD-010; AP0-004 through AP0-006/AP0-010.
Tests: Not run; documentation only.
History/Predecessor: New document; initial publication recorded in Git.
-->
# State Machine and Diagnostic Contract

**Status:** Planned. This specifies the required shape and semantics; the physical schema, serialization and API transport are open decisions.

## Normative requirements

| ID | Contract requirement | Depends on | Acceptance criteria |
|---|---|---|---|
| STM-001 | Every operational state machine has a stable `machine_id`, `machine_version`, named states, allowed transitions, transition guards, and terminal/recoverable classifications. | Definition schema and ownership/version policy. | A valid definition loads and exposes its complete state/transition/version catalog. |
| STM-002 | Runtime transition validation and diagnostic state/transition descriptions consume the same versioned machine definition. A separately maintained HMI list is invalid. | STM-001; diagnostic projection. | For a named machine/version, runtime-valid transitions and diagnostic descriptions agree exactly. |
| STM-003 | Every state transition is persisted with a unique event identity, entity identity, machine/version, prior and next state, event time, actor/component, correlation/causation lineage, reason/outcome and relevant diagnostic/evidence references. | Database event schema; clock/correlation source. | Query transition history and verify required identity, version, timestamp, causality and outcome fields are durable. |
| STM-004 | Invalid or unknown transitions are refused, recorded as an exception, and visible; the last valid state remains attributable. | STM-001/003; error classification. | Attempt an illegal/unknown transition; operation is rejected, exception is visible and last valid state unchanged. |
| STM-005 | Recoverable blockages preserve the active entity and continuation lineage. A terminal result requires a durable explicit transition and reason. No timeout, retry exhaustion or process exit silently converts an activity into completion. | Continuation/idempotency and recovery policy. | Interrupt/restart recoverable work and verify identity/lineage remains resumable or explicitly blocked; no false terminal completion. |
| STM-006 | Runtime state is the source of diagnostic truth. An HMI may project or cache it only with source revision and freshness; stale/unavailable/unknown are explicit states. | AP0 diagnostics transport/freshness choices. | Compare projection with durable current state, then stale/unavailable source and observe explicit status/freshness change. |
| STM-007 | Definitions and events are versioned and database-backed. Upgrades preserve historical interpretation of prior events. | Database schema/migrations; version compatibility policy. | Restart and upgrade definition version; prior events still resolve to their original machine version and current state reconciles. |

## Required state machine families

AP0 requires versioned definitions for at least:

- **Ring 0 process lifecycle:** starting, running, degraded, stopping, stopped, failed, restarting/recovery conditions.
- **CME process lifecycle:** the same operational conditions, independently tracked under Ring 0 supervision.
- **Module lifecycle:** the logical conditions in the [module contract](R3A_MODULE_LIFECYCLE_AND_CONTRACT_SPEC.md), including installed, activating, active, stopping, stopped, failed, replacing and incompatible.
- **Generic activity lifecycle:** accepted/registered, ready/queued, running, waiting/recovering, blocked, completed, failed and cancelled, with terminal/recoverable semantics. This is not an Engineering work-order schema.
- **Capability/resource observation:** registered, available, unavailable, degraded, stale and unknown. Authorization is a separate decision and is not a health state.

These are semantic labels, not final wire identifiers. Final identifiers and transition guards belong in the versioned machine definition after review.

## Event record minimum

Each transition/event record must provide:

| Attribute | Requirement |
|---|---|
| Event identity | Unique, stable ID; deduplicable on retry. |
| Event type and schema version | Stable type plus versioned payload schema. |
| Event time | UTC occurrence time and persisted/observed time where different. |
| Subject | Entity type/ID and owning module/process. |
| State transition | Machine ID/version, prior state, next state, transition/result. |
| Causality | Correlation ID; causation/parent event or activity ID when applicable. |
| Actor | Component/module/role and authenticated principal/authority reference when relevant. |
| Outcome | Severity, reason/error classification, retry/recovery disposition. |
| Evidence | Immutable artifact/diagnostic reference or classified payload reference, not fabricated status. |
| Configuration | Effective configuration revision/reference and implementation revision when available. |

Payload classification, content retention, encryption, replay and erasure rules must follow Steward privacy decisions; do not assume all payloads are globally visible.

## Diagnostic projection

For each process/module/activity/resource, diagnostics expose current state, state-machine version, health, last transition time, duration in state, last heartbeat, progress timestamp/value if emitted, active operation/correlation, retry/recovery phase, latest exception and evidence references, effective configuration/implementation revision, and freshness. Fields with no observation are `unknown`/`unavailable`, not inferred. A diagnostic request is read-only with respect to operational records.

The HMI MUST distinguish:

- **state** (what lifecycle state is recorded),
- **health** (whether a fresh component probe meets its contract),
- **progress** (timestamped work evidence, not an animation),
- **completion** (terminal result with deliverable/evidence), and
- **acceptance** (independent substantive evaluation where required).

## Acceptance checks

AP0 validation SHALL show that STM-001–STM-007 hold: a valid transition succeeds; an invalid transition is denied and diagnosed; process/activity restart yields durable lineage and honest recovery; diagnostic definitions match runtime definitions; stale observations are labeled stale/unknown; and no completed status exists without the required completion evidence. See AP0-004–AP0-010 and the testing policy.
