<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_ACTIVITY_HANDLER_OBJECTIVE_SUBMISSION_V1.md
Component: R3A-ACTIVITY-HANDLER-OBJECTIVE-CONTINUATION
File Revision: 1.0.0
Created: 2026-11-10T20:10:03Z
Created By: Codex GPT-6
Purpose: Specify generic resident objective submission and durable handler result continuation.
Execution Model: N/A; versioned contract documentation.
Observability: Activity state, checkpoint, action digest, correlation, audit and continuation result.
Dependencies: CME objective control operation; canonical directory and grant authority; resident execution; PostgreSQL activity ledger.
Authority: AD-024; Steward P0 directive, Issue #51 comment 6777543318.
Changed: 2026-11-10T20:10:03Z | R3A-GENERIC-OBJECTIVE-CONTINUATION | Codex GPT-6 | Publish the generic objective-submission socket contract.
Supersedes: None.
Contracts: r3a.activity-handler.objective-submission@1.0.0; r3a.activity-handler.continuation@1.0.0.
Tests: tests/test_r3a_activity_handler_interop.py.
History/Predecessor: New controlled document; implementation published with Coordinator candidate.
-->

# R3A Activity Handler Objective Submission v1

## Purpose

`r3a.activity-handler@1.1.0` may return an `action_required` envelope whose
`action` is either the existing `r3a.activity-handler.action@1.0.0` registered
capability action or the new `r3a.activity-handler.objective-submission@1.0.0`
control request. The latter is a separate, versioned shape because
`resident.objective.submit` is a CME control operation, not a registry
capability. Existing capability actions and v1.0 handlers retain their current
wire behavior.

## Objective submission action

The objective action contains a stable `action_id`, canonical
`target_resident_id`, objective, task class, event kind, required capabilities
and modalities, acceptance criteria, optional notification envelope, and a
bounded timeout (1–86,400 seconds). CME validates the shape and invokes its
existing `resident.objective.submit` control path. CME resolves and authorizes
the resident, checks the configured execution route and
`resident.objective.execute`, and requires `resident.delegate` when a resident
submits work for a different resident. Self-submission uses the existing
resident execution grant. An absent or denied authorization fails closed.

The handler request envelope includes the optional server-derived
`execution_principal` identity context for the parent activity. A handler may
use it to select a self-target; it is metadata only and carries no authority.
CME independently validates the requested target against the authoritative
directory and effective grants.

The action never invokes `reasoning.model.invoke`. The resulting objective is
scheduled on the ordinary CME activity ledger and resident execution path, so
the existing inference provider and per-activity budget reservation remain in
force.

## Durable continuation and recovery

CME derives a stable objective idempotency key from the parent activity, pinned
handler binding, and action ID. It persists the action intent and checkpoint
before dispatch. If the child objective remains active, CME persists its
activity ID and deadline, changes the parent handler activity to `WAITING`, and
releases its worker lease. The scheduler requeues the parent when the child
reaches `COMPLETED`, `BLOCKED`, or `CANCELLED`, or when the bounded timeout
expires.

On resume CME repeats the same authorized submission idempotently and verifies
that it resolves to the checkpointed child activity. A completed child result
is included in the v1.0 continuation receipt as `{activity_id, state, result,
exception, latest_event_id}`. A blocked/cancelled result is returned as an
explicit failed continuation with its terminal state and reconciliation
reference. A timeout is explicit and reports `KNOWN_PENDING`; it does not claim
the child failed or cancel it. The handler remains responsible for its
domain-level decision and may return `blocked` when no trustworthy result is
available.

The parent activity retains the exact handler/module/artifact binding,
configuration revision, action digest, and stable action ID. Lease recovery
replays the same action; process loss while waiting is recovered by the
scheduler from the durable parent checkpoint. A changed handler binding or
configuration revision fails closed. CME continues to own state, scheduling,
authorization audit, persistence, leases, retries, and recovery; the registered
handler owns workflow decisions.

## Contract artifact

Schema: `r3a_runtime/schemas/activity-handler-objective-submission.v1.schema.json`

Validator: `validate_activity_handler_objective_submission` in
`r3a_runtime/module_extensions.py`.

Focused regressions: `tests/test_r3a_activity_handler_interop.py`.
