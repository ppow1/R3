# R3A Activity Handler Continuation v1.1

The `r3a.activity-handler` contract v1.1 adds an optional CME-mediated action
round trip while retaining v1.0's single `execute` call unchanged. A module
opts in by declaring an activity handler at v1.1 in module-manifest v1.2. The
registered module remains the only owner of workflow decisions.

## Wire sequence

1. CME dispatches the normal handler request with its activity, attempt,
   correlation, binding, authorization decision, and durable checkpoint.
2. The handler may return `completed`, `blocked`, or `action_required`. An
   action request uses `r3a.activity-handler.action@1.0.0`, includes a stable
   action ID, a registered operation ID/version, target, input, evidence
   purpose, and an optional opaque durable work record. An action must include
   the handler's next checkpoint. The `action_required` transport envelope is
   validated by the generic v1.1 socket schema; terminal results remain
   validated by the module's declared result schema.
3. CME validates that the operation is declared both by the handler and its
   registered module, validates target/input against the operation descriptor,
   and durably records the action intent before invoking it.
4. CME uses the canonical capability dispatcher, which rechecks authorization,
   writes the invocation ledger, dispatches the registered provider, and
   collects result/evidence. Handler isolated writes require an opaque bounded
   durable work record tied to the action ID; external writes remain subject to
   the existing budget-reservation contract and are not admitted by this
   extension alone.
5. CME persists the result as
   `r3a.activity-handler.continuation@1.0.0` before resuming the same registered
   module binding. The handler receives its own checkpoint, continuation, and
   action history and chooses the next workflow state.

## Authority and recovery

CME retains scheduling, authorization enforcement, durable activity and
invocation state, canonical invocation, audit, lease, and recovery ownership.
Registry membership and declared capabilities do not grant authority. Denials
are returned as explicit continuations after the canonical authorization audit
path. Execution failures carry an `UNKNOWN` effect disposition and
reconciliation reference; CME does not tell the handler that an uncertain
effect succeeded. Stable action IDs produce stable invocation IDs and
idempotency keys, so replay after a process loss uses the invocation ledger.
The pending action stores its exact digest, attempt, configuration revision,
and immutable registered handler binding. Changed configuration or binding
fails closed. CME bounds serialized handler action state to 512 KiB and limits
an activity to 100 actions.

No new scheduler, grant store, handler registry, cross-module database access,
or provider execution path is introduced. Existing v1.0 handlers continue to
use their original execute/result flow.
