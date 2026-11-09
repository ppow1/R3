# Notification adapter to generic activity intake

Status: adapter projection and conformance tests implemented; CME binding not present in the coordinator integration branch. No managed-runtime activation is claimed.

## Boundary

`notification.source.read@1.0.0` remains the authorized, read-only `capability_operations` operation and continues to return the unchanged `r3a.notification-intake@1.0.0` envelope. The published `r3a.activity-intake.v1` schema is copied verbatim from Coordinator commit `7825e91` at `r3a_runtime/schemas/activity-intake.v1.schema.json`.

The coordinator-owned generic CME bridge should call `r3a_plugins.notification_source.plugin.to_activity_intake()` on the successful provider output. The pure projection takes the N1 output and provider evidence plus the registered provider identity/version/artifact digest, invocation configuration revision, externally configured lifecycle projection, permitted task class, and optional parent activity ID. It validates and returns the normative generic envelope. It performs no storage, scheduling, authorization, source acknowledgment, or lifecycle transition.

The envelope preserves N1 unchanged under `activity.input.notification`. Its stable intake ID and idempotency key are both `notification:<source_id>:<event_id>`. The source occurrence and receipt timestamps, correlation, payload reference, provider evidence digest, source provenance, and configured CME lifecycle names remain separately addressable. CME remains responsible for binding task class, rejecting conflicting replay, assigning activity identity, persisting, and recording observed lifecycle events.

## Source selection and subscriptions

`notification_source.config.event_types` remains an externally configured exact allowlist, not a wildcard subscription. The existing example includes only CME process lifecycle events. Generic activity notifications may be enabled only for explicitly listed source event types. The adapter query filters out events whose activity subject is `foundation.observe`, even if an administrator later enables shared event names such as `activity.completed` or `activity.blocked`; those routine observation records must never create Steward notifications.

The delivery policy is separately configured through `notification_delivery.rules`. It supplies directory role routing, urgency, and `requires_action`; recipient IDs are resolved from the canonical directory. Informational events use `requires_action: false`. Actionable events use `true`, and views never constitute acknowledgment.

The current event producer set supports process state changes/failures, generic `activity.completed` / `activity.blocked`, `engineering.verification.completed`, and `capability.invocation.finished`. The current sources do not yet emit unambiguous institution event types for Steward approval required or resident delegation completed. The coordinator must publish those event names/subject/evidence semantics before their subscriptions can be enabled safely. For completion/blockage/verification/invocation events, CME must include enough immutable subject details to classify resident activity and outcomes; generic lifecycle event names alone are insufficient for recipient policy.

## Website and time presentation

The Website client already expects `GET /api/v1/notifications`, acknowledgment, and resolution routes, but its branch documents those routes as not mounted. The API response should use the Website `r3a.notification-inbox.v1` fields and bind the session principal server-side; actions must invoke CME grants and reread durable state. The notification service returns UTC timestamps. Website renders `created_at` using configured `presentation_timezone` and `Intl.DateTimeFormat` with an explicit IANA zone, displays the zone label, and retains original UTC for copy/export. No fixed offset or local-time value is stored in the event ledger.

## CME integration requirements for Coordinator

1. In the existing generic capability invocation path, after grant authorization and provider success, validate the N1 result and provider evidence, then invoke the module-declared adapter projection above with descriptor provenance and CME config revision.
2. Validate its result with `r3a.activity-intake.v1`; validate `activity.task_class` against CME's configured permitted task class and bind lifecycle event names from external module config.
3. Persist through the generic durable activity/event intake. Same-key/same-envelope replay returns the original activity; conflicting source/content rejects. Retain original receipt timestamp and event lineage on replay/restart.
4. Preserve N1 behavior: received is not upstream acknowledgment; actionable follows claim; acknowledged follows the real Grace result; resolved/blocked follow durable terminal outcome. Do not run the provider again to replay already persisted identical activity.
5. Keep the N1 CME compatibility route until generic replay, authorization-before-provider, restart, lifecycle, observer coexistence, and 71-test N1 regression equivalence pass.

No new CME endpoint, scheduler, registry, notification-specific event store, or Website backend is required by this adapter.
