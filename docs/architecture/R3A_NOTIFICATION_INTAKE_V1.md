<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_NOTIFICATION_INTAKE_V1.md
Component: R3A-AP1-NOTIFICATION-INTAKE
File Revision: 1.1.0
Created: 2026-11-07
Created By: Codex GPT-6
Purpose: Define AP1 notification intake through the existing CME event and activity records.
Execution Model: A registered source adapter produces a versioned generic activity-intake envelope; CME authorizes and persists it through the generic intake operation.
Observability: Versioned source envelope and append-only notification lifecycle events on the Grace activity lineage.
Dependencies: R3A AP0 event/activity contracts; Issue #43 Grace routing; Issue #46 capability registry.
Authority: Steward directive R3A-019, GitHub Issue #48; isolated R3A development prototype.
Changed: 2026-11-07 | R3A-AP1-N1 | Codex GPT-6 | Define institution-event adapter and notification lifecycle.
Changed: 2026-11-10 | R3A-FS01-GENERIC-INTAKE | R3A Coordinator | Retire the notification-specific CME ingest route and require source-cited terminal disposition before acknowledgment.
Supersedes: None.
Contracts: r3a.notification-intake.v1; r3a.activity.generic; r3a.authorization-decision.v1.
Tests: tests/test_r3a_notifications.py.
History/Predecessor: New document.
-->
# R3A Notification Intake v1

The registered `notification.activity-intake.prepare` adapter reads one selected row from the append-only `r3a.institution_events` ledger. It does not poll, schedule work, mutate the source, or acknowledge the source event upstream. CME invokes the registered source operation through `activity.intake.accept`, applies the operation's capability grant, validates its provider provenance and idempotency key, then persists the `r3a.activity-intake.v1` envelope through the generic activity ledger. The former `notification.ingest` CME control route and `notification-ingest` CLI command have been removed.

The source envelope is validated against `r3a.notification-intake` version `1.0.0` and persisted in the normal Grace activity input. The idempotency key is exactly `notification:<source_id>:<source_event_id>`. Correlation remains the source event's correlation UUID; the ledger event UUID is the source event ID and payload reference. Occurrence and receipt timestamps remain distinct. The envelope records severity, source event type, provenance and original event evidence.

Grace receives the envelope and a digest-checked notification evidence item through the existing configured `objective_reasoning` model role. The 0.6B autonomic role is rejected by the existing task-class routing contract. CME records `grace.notification.actionable` when the normal scheduler claims the activity. It records `grace.notification.acknowledged` only in the same PostgreSQL transaction that completes the activity, after validating a healthy terminal decision, non-empty assessment and recommended action, and an exact citation to the notification source. Intermediate, failed, timed-out, blocked, malformed or uncited results cannot acknowledge. CME then records `grace.notification.resolved` in that transaction after completion and acknowledgment, or `grace.notification.blocked` with the durable blocked activity outcome. These events share the original correlation ID and cite the source event UUID as causation.

The active source configuration belongs to the registered module's validated
configuration contract (`r3a.notification-source.config.v1` in
`manifest.activity-intake.json`). The old bootstrap `notification_intake`
field remains parse-compatible for prior configurations but no longer selects
or executes a CME source route.

Install and activate the registered `r3a.notification-activity-intake` source module and authorize its `notification.activity-intake.prepare` operation under the existing capability/grant policy. Intake command:

```sh
r3a --config <bootstrap.json> activity-intake-accept \
  --operation-id notification.activity-intake.prepare \
  --operation-contract-version 1.0.0 \
  --input-json '{"source_event_id":"<event UUID>"}' \
  --idempotency-key 'notification:r3a.institution-events:<event UUID>'
```

The source adapter enforces its registered event-type allowlist. CME validates the returned source-bound key and provider provenance before accepting the generic intake.
