<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_NOTIFICATION_INTAKE_V1.md
Component: R3A-AP1-NOTIFICATION-INTAKE
File Revision: 1.0.0
Created: 2026-11-07
Created By: Codex GPT-6
Purpose: Define AP1 notification intake through the existing CME event and activity records.
Execution Model: CME imports one explicitly identified institution event under the existing authorization provider.
Observability: Versioned source envelope and append-only notification lifecycle events on the Grace activity lineage.
Dependencies: R3A AP0 event/activity contracts; Issue #43 Grace routing; Issue #46 capability registry.
Authority: Steward directive R3A-019, GitHub Issue #48; isolated R3A development prototype.
Changed: 2026-11-07 | R3A-AP1-N1 | Codex GPT-6 | Define institution-event adapter and notification lifecycle.
Supersedes: None.
Contracts: r3a.notification-intake.v1; r3a.activity.generic; r3a.authorization-decision.v1.
Tests: tests/test_r3a_notifications.py.
History/Predecessor: New document.
-->
# R3A Notification Intake v1

The configured `institution_events.v1` adapter imports one selected row from the append-only `r3a.institution_events` ledger. It does not poll, schedule work, mutate the source, or acknowledge the source event upstream. The import is an explicit CME control operation and uses the existing `notification.source.read` capability grant.

The source envelope is validated against `r3a.notification-intake` version `1.0.0` and persisted in the normal Grace activity input. The idempotency key is exactly `notification:<source_id>:<source_event_id>`. Correlation remains the source event's correlation UUID; the ledger event UUID is the source event ID and payload reference. Occurrence and receipt timestamps remain distinct. The envelope records severity, source event type, provenance and original event evidence.

Grace receives the envelope and a digest-checked notification evidence item through the existing configured `objective_reasoning` model role. The 0.6B autonomic role is rejected by the existing task-class routing contract. CME records `grace.notification.actionable` when the normal scheduler claims the activity and `grace.notification.acknowledged` only after Grace returns a reasoning response. CME then records `grace.notification.resolved` together with activity completion, or `grace.notification.blocked` with the durable blocked activity outcome. A model/provider/source failure remains a retry or blocked activity and is not marked acknowledged or resolved unless Grace actually returned a response. These events share the original correlation ID and cite the source event UUID as causation.

Example external configuration:

```json
{
  "notification_intake": {
    "contract_id": "r3a.notification-intake",
    "contract_version": "1.0.0",
    "sources": [
      {
        "source_id": "r3a.institution-events",
        "adapter": "institution_events.v1",
        "enabled": true,
        "event_types": ["process.state", "process.restarted", "process.failed"]
      }
    ]
  }
}
```

Grant `notification.source.read` to `resident.grace` through the existing CME capability grant operation before importing. Intake command: `r3a notification-ingest --config <bootstrap.json> --source-event-id <event UUID>`. The command selects only an event type allowlisted for the configured source.
