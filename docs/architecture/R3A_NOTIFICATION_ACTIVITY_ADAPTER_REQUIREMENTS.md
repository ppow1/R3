<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_NOTIFICATION_ACTIVITY_ADAPTER_REQUIREMENTS.md
Component: R3A-AP1-NOTIFICATION-ACTIVITY-ADAPTER
File Revision: 1.0.1
Created: 2026-11-08
Purpose: Document the notification module binding to the reusable generic activity-intake boundary.
Authority: Issue #48; R3A Baseline 1.0, AP1, R3A-019.
Dependencies: Existing r3a.notification-intake.v1 and r3a.capability-operation.v1; r3a.activity-intake.v1 and the CME activity-intake consumer.
Tests: tests/test_r3a_notification_source_plugin.py; tests/test_r3a_activity_intake_consumer.py.
Status: Source adapter and generic CME consumer are integrated in the unified candidate; managed source configuration, grant, invocation and restart recovery remain unverified.
Changed: 2026-11-10T18:53:48Z | R3A-CORE-FREEZE-CORRECTION | Codex GPT-6 | Document notification-owned handler metadata and N1 compatibility binding.
-->
# Notification Source Adapter Requirements

## Boundary ownership

`r3a.activity-intake.v1` is the shared CME boundary. `notification.source.read` remains the domain source operation and returns the established N1 envelope. A side-by-side `notification.activity-intake.prepare` read operation uses the notification module's pure adapter projection and returns the shared activity-intake envelope with activity type `notification.event.review`. Its module manifest declares the corresponding registered `r3a.activity-handler.v1` handler. CME's `activity.intake.accept` control operation invokes only registered read-only operations, uses the configured resident principal for the canonical grant check, validates operation and source-provider provenance, checks the source-bound idempotency key, and persists the envelope through the generic activity/event ledger. CME does not branch on notification-specific source or objective fields. Legacy N1 ingestion remains available during rollout and deduplicates a prior activity for the same source event.

## Typed notification operation

The new handler-bearing adapter is published as `r3a.notification-activity-intake@1.1.0` using `r3a.module-manifest.v1@1.1.0`; its handler is `r3a.notification.event-review@1.0.0` for `notification.event.review`. Register `manifest.activity-intake.json` as a separate `capability_operations` entry using the existing notification source configuration. Keep `manifest.json` / `notification.source.read@1.0.0` registered for legacy N1 ingestion during rollout. Both operations still require the normal `notification.source.read` grant; registration does not grant it.

| Direction | Type and fields | Owner/behavior |
| --- | --- | --- |
| Provider input | `notification.source.read@1.0.0`; object with exactly `source_event_id: UUID`. | CME validates the canonical capability invocation and grant. Source ID and event-type allowlist come from external provider configuration. |
| Provider output | Existing `r3a.notification-intake@1.0.0`: `source_id`, `source_event_id`, `event_id`, `event_type`, `correlation_id`, `occurred_at`, `received_at`, `severity`, `payload_ref`, `provenance`, and `evidence`. | Adapter reads one immutable `r3a.institution_events` row from a repeatable-read, read-only transaction. It filters event types from config and never acknowledges or mutates the source. |
| Provider evidence | `source_id`, `source_event_id`, `payload_sha256`, `payload_ref`, `read_only`, `queried_at`. | Adapter binds returned data to source identity and a canonical payload digest; CME records normal invocation authorization/provenance. |
| Failure | Not-found, source unavailable, malformed source data, or disallowed source type remains a provider failure/denial. | The adapter does not return an empty successful intake or invent a lifecycle outcome. CME’s existing invocation and activity recovery paths own durable failure handling. |

The package is registered through `capability_operations`; the provider declares `notification.source.read` as its required grant. It does not create a new registry, scheduler, authorization provider, or activity table. The external DSN is named by `dsn_env`; no DSN value is included in code, manifest, result, or evidence.

The bootstrap binding adds `notification.source.read` to the module's declared capabilities and points to the provider manifest and external config:

```json
{
  "module": {"capabilities": ["notification.source.read"]},
  "capability_operations": [
    {
      "manifest": "/configured/r3a_plugins/notification_source/manifest.json",
      "configuration": "/configured/notification-source.json"
    }
  ]
}
```

The named capability still requires a normal CME grant. Configuring an operation or selecting an event does not grant access.

## Requirements for mapping into the proposed generic intake

When the coordinator agrees the generic contract, its adapter binding must accept the typed operation result above and preserve these domain facts:

1. Stable source id and immutable source event id. Deduplication key remains `notification:<source_id>:<source_event_id>`.
2. Source correlation and event causation; occurrence and receipt timestamps remain distinct.
3. Payload reference, original source evidence, source configuration revision, implementation provenance, and payload digest.
4. Declared Grace task class is `objective_reasoning`; the 0.6B autonomic role cannot perform notification disposition.
5. The generic intake owns the durable Grace activity and generic event transitions. It records the existing notification lifecycle names and keeps N1 semantics: intake does not acknowledge upstream; Grace response/action and outcome are recorded only when supported by evidence.
6. Replay of the same source event resolves to the same durable activity and delivery identities. A different source event under the same key is rejected.
7. The adapter remains input/evidence only. It cannot decide whether the event needs follow-up or acknowledge it on Grace’s behalf.

These are adapter conformance requirements around the published shared schema and callable CME boundary. The adapter remains read-only and does not choose execution authority. The legacy N1 path continues to submit `grace.objective` with `objective_reasoning` and routes through configured Grace roles. The generic intake path emits `notification.event.review`; its registered notification handler contract owns the domain workflow declaration while CME continues to own authorization, scheduling, durable progress/checkpoints, lifecycle and outcome persistence. A missing or unavailable handler remains a fail-closed core integration condition.

The source event's `subject_id` must not be used as a generic parent activity ID unless it is confirmed to identify that activity type. The source adapter can state the event subject and correlation; CME/intake owns the meaning and assignment of parent activity lineage.

## Test separation

`tests/test_r3a_notification_source_plugin.py` verifies source-domain behavior without scheduling: registration, source allowlisting, read-only SQL, digest/provenance and source outage. `tests/test_r3a_activity_intake_consumer.py` verifies the versioned module manifest, generic CME authorization/invocation handoff, provider provenance, source-bound idempotency, bounded persistence, duplicate replay and authorization rejection. The activity-intake contract, existing N1 and N2 tests continue to validate schema and lifecycle behavior. These are fixture/unit checks; managed source access and restart recovery still require configured source access and grant.

## Generic boundary status

The schema is `r3a_runtime/schemas/activity-intake.v1.schema.json`; CME invokes it through `activity.intake.accept` using a registered read operation, version, typed input, and source-bound idempotency key. Provider output must declare the schema ID `r3a.activity-intake.v1`. The existing N1 source operation and new `notification.activity-intake.prepare` adapter operation are side by side; no notification-specific CME dispatch was added to the generic consumer.

## Activation limit

The provider, generic handler declaration and consumer are source-integrated and fixture-tested. No source DSN or live read grant is available in managed bootstrap, so no real event has been submitted through `activity.intake.accept` and notification activation is not claimed. The operation can be installed through ordinary `capability_operations` configuration; CME still requires the actual `notification.source.read` grant before invoking it. Coordinator-owned CME changes are required to route the new activity type through the generic registered-handler socket and remove the legacy special case after compatibility acceptance.
