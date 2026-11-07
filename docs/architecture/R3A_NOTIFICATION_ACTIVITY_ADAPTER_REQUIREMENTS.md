<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_NOTIFICATION_ACTIVITY_ADAPTER_REQUIREMENTS.md
Component: R3A-AP1-NOTIFICATION-ACTIVITY-ADAPTER
File Revision: 1.0.0
Created: 2026-11-08
Purpose: Publish typed notification adapter requirements for the proposed generic activity-intake boundary.
Authority: Issue #48; R3A Baseline 1.0, AP1, R3A-019.
Dependencies: Existing r3a.notification-intake.v1 and r3a.capability-operation.v1; proposed r3a.activity-intake.v1 from the modularity audit.
Tests: tests/test_r3a_notification_source_plugin.py.
Status: Source operation implementation is ready; generic activity-intake contract is still proposed and must be agreed by the coordinator before core integration.
-->
# Notification Source Adapter Requirements

## Boundary ownership

The modularity audit proposes `r3a.activity-intake.v1` as a reusable CME boundary. It is not yet an agreed or merged contract. This branch does not define its schema, generic persistence methods, or another core dispatch path. The notification adapter is packaged as a standard configured `r3a.capability-operation.v1` provider and returns the already established `r3a.notification-intake` version `1.0.0` envelope. CME remains responsible for authorization, deduplication, generic activity/event persistence, and lifecycle. The existing N1 command/control behavior remains available until an agreed generic boundary is integrated.

## Typed notification operation

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

These are adapter conformance requirements, not a definition of `r3a.activity-intake.v1`. Fields such as generic parent activity, accepted activity ID, task envelope, and generic persistence call shape must come from the coordinator-approved shared contract. The adapter must not guess them.

The source event's `subject_id` must not be used as a generic parent activity ID unless it is confirmed to identify that activity type. The source adapter can state the event subject and correlation; CME/intake owns the meaning and assignment of parent activity lineage.

## Test separation

`tests/test_r3a_notification_source_plugin.py` verifies source-domain behavior without invoking CME scheduling: manifest/operation registration, exact output envelope, source allowlisting, read-only SQL, digest/provenance, source outage, malformed/unknown input, and stable replay identity. `tests/test_r3a_notifications.py` and `tests/test_r3a_notification_delivery.py` continue to verify N1 and N2 lifecycle behavior. Generic intake integration tests belong beside the agreed shared boundary and should exercise deduplication, parent/correlation lineage, restart, grant denial, and durable lifecycle using a real CME event when that boundary is available.

## Activation limit

The plugin is configured and tested locally against a synthetic event-ledger connection. No source DSN is configured for this worktree and no managed runtime or website was changed. A live source read and generic activity-intake invocation remain unverified. The coordinator should first agree the generic boundary and tell #48 which combined integration revision owns it; the source provider can then be bound through ordinary `capability_operations` configuration without a notification-specific CME branch.
