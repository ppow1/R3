<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_NOTIFICATION_PHONE_DELIVERY_V1.md
Component: R3A-AP1-NOTIFICATIONS
File Revision: 1.1.0
Created: 2026-11-08 UTC (exact time unknown)
Created By: Unknown (legacy)
Purpose: Record ntfy integration, phone-message payload and Website action boundaries.
Execution Model: Documentation of separate legacy and R3 source paths.
Observability: Source references, tests, and dated operational observations.
Dependencies: R3A Notifications module and private ntfy transport.
Authority: Steward Issue #48 and R3A AP1/R3A-019; no production change authorization.
Changed: 2026-11-11 | STEP-128-FOLLOWUP | Codex GPT-6 | Reconcile current R3 source and clarify the age of R2 runtime evidence.
Supersedes: None.
Contracts: r3a.notification-service-manifest.v1; ntfy-publish.v1; Website view-only action boundary.
Tests: tests/test_r3a_notification_ntfy.py; tests/test_r3a_notification_service.py.
History/Predecessor: Git blob 3cc4d8371b9e4e546a1053c0ab013943fbe72883.
-->
# R3A notification phone delivery v1

## Existing R2/R3 path and preserved behavior

The latest recorded legacy-path observation is from 2026-11-08: the Riverview
notification dispatcher and private ntfy systemd services were reported active;
ntfy health on loopback port 2586 returned `healthy`, and the installed server
reported v2.32.0. The dispatcher was reported to load its token and topic from
systemd credentials. These are dated observations, not a current host check.
The R2 dispatcher source and protected configuration are not present in this
R3 checkout, so its present version, publisher code, topic and credentials are
not independently revalidated here. No protected value was read or changed.

The recorded legacy publisher sends a title, priority, tags, and fixed generic
body selected by event type. Its `view` action opens a V2 work/communications
URL; the recorded payload omits source reason, event time and correlation ID.
The dispatcher was documented as tracking pending/sending/failed/sent state,
attempt count, retry time, lease and ntfy message ID. Preserve that path until
the separately configured R3A path has a verified device test.

## R3 publisher and transport source inventory — 2026-11-11

The current R3 source is distinct from the legacy dispatcher described above:

| Source | Evidence in this checkout | Boundary |
|---|---|---|
| Module version | `r3a_plugins/notification_service/manifest.json` declares `r3a.notifications@1.2.2` and pins the service publisher dependencies. | Source metadata only; no managed service activation is evidenced. |
| Publish path | `server_v1_2_1.py` persists/routs the delivery, claims the notification phone outbox, calls `NtfyPublisher.publish()`, then records `phone_sent` or `phone_failed`. | Request handling is synchronous and retry uses the durable delivery/outbox state; no second scheduler is added. |
| Transport/presentation | `ntfy.py` sends a JSON POST with bearer authentication, bounded message fields and a message ID; accepts HTTPS or loopback HTTP only. | Topic and token come from configured runtime inputs, not package source. |
| Actions | The phone actions use ntfy `view` links into the Website; intent query parameters do not mutate state. | Acknowledge/resolve require the authenticated Website POST path and its CME grant; phone receipt is not acknowledgement. |
| Configuration example | `config.example.json` sets `ntfy.enabled` to `false`; topic and token-file settings are environment/configuration names. | Example unit uses loopback port 18480 and an environment file; it is not proof of the deployed unit or present host config. |
| Regression evidence | `tests/test_r3a_notification_ntfy.py` checks detailed message fields, safe view-only actions, no fabricated actions without a Website destination, bounded text and transport rejection. `tests/test_r3a_notification_service.py` checks outbox failure/retry, successful replay suppression and reuse of the delivery identity. | Tests use local capture/fake transports; they do not publish to a protected topic or prove phone display. |

No R2 repository/source checkout or live host inspection was available in this task. The R3 implementation improves the source detail and authenticated navigation contract, but it has no real-device acceptance. The recorded legacy path remains preserved until a separately authorized phone test proves R3 delivery and links.

## Adopted R2/R3 requirements and parking-lot classification

- **Adopted from R3-P006:** event allowlisting, duplicate safety, severity and
  routing policy; routine observer activity remains excluded.
- **Adapted from PL-NEW-028/029/031/032:** identify event/source/reason, action
  requirement, severity, correlation, timestamps, full authenticated detail,
  phone transport state, and separate delivery/acknowledgment/resolution. Phone
  receipt is never approval or acknowledgment.
- **Adapted from R3-L009:** notification tap leads to the exact notification
  in the Website inbox. Image/reply capability is deferred until a real source
  evidence object, media privacy/retention policy, and authenticated Website
  route exist.
- **AP3 / #49:** phone-on-LAN, VPN-on, and cellular/Wi-Fi-off checks require a
  real authenticated phone session. The service endpoint stays loopback unless
  an approved gateway is configured.
- **#56 directory boundary:** current reported managed directory snapshot
  contains Grace only and has no verified Steward recipient binding. A test
  recipient or old HR roster must not be substituted. Coordinator/HR must
  identify the authoritative Steward office/principal projection before
  managed routing is activated.

## ntfy message contract

## Coordinator release and generic intake handoff

Service manifest `r3a.notification-service-manifest.v1` pins module
`r3a.notifications@1.2.2`, state schema 3, the inbox schema, the source
adapter manifest and adapter implementation, and the shared
`r3a.activity-intake.v1` schema. The source adapter manifest is
`r3a.capability-operation.v1` operation `notification.source.read@1.0.0`,
capability `notification.source.read`; its input is exactly
`{"source_event_id":"<UUID>"}` and its output is
`r3a.notification-intake@1.0.0`. Configured source is
`r3a.institution-events`, with event allowlist `process.state_transition`,
`process.restarted`, and `process.failed`. The external source DSN is named by
`R3A_NOTIFICATION_SOURCE_DSN`; connection and statement timeouts are 3s and
2000ms. Reads use a repeatable-read, read-only transaction against the existing
`r3a.institution_events` ledger. The adapter excludes events whose activity
subject is `foundation.observe`; that event type is not in the allowlist.

The typed envelope retains source/event/correlation IDs, UTC occurrence and
receipt times, severity, payload reference, source schema/config/implementation
provenance, subject/state/reason/outcome and persisted time. Evidence carries a
SHA-256 digest of canonical serialized source-row fields, a ledger payload
reference, and `read_only: true`. It does not copy arbitrary raw evidence files
or define an attachment payload. `to_activity_intake()` is a pure projection
that produces `r3a.activity-intake.v1` with the stable notification idempotency
key, evidence reference/hash, provider artifact and config revision, objective
task class, and mappings for all five notification lifecycle phases. Coordinator
must validate the shared schema and policy, apply the configured task class and
lifecycle mapping, and persist/replay through its one generic CME intake path.
The notification workstream does not register another bridge or scheduler.

Pinned digests are in `r3a_plugins/notification_service/manifest.json`; the
source plugin artifact is SHA-256
`19d080f806313c5cf33f48d34f19bef7a87ddcee71193f39a4ee98ad735f3239`, source
manifest `8288542a21d1ca8d407d5af005b289a087db00a5827009ea45f6c719f7b90ca7`,
and generic schema
`d98dcf249ebb61471ada6051bb9831bbedc1454e74e819e35a9755b18cc05b3c`.
Coordinator activation still requires authoritative directory binding for a
Steward recipient and its scoped grants; no identity is inferred from display
names or a test directory.

With optional `ntfy.enabled=true`, module v1.2.2 sends a JSON publish request
to the configured private ntfy origin and authenticated topic. The bearer is
read from a credential file whose path is supplied by environment; secrets,
topic names, and message text are not logged. HTTP is allowed only for loopback
ntfy; all other ntfy origins and the Website base must use HTTPS.

The title and body carry the categorized event, source and event type, source
reason, severity/urgency, affected subject/state transition, local timestamp
with canonical UTC, correlation ID, source-event ID, and delivery ID. The
phone payload contains no evidence image/file and does not include raw nested
source evidence. The complete notification and evidence references remain in
the authenticated inbox API.

The message offers at most three `view` actions: **Open details**,
**Acknowledge**, and **Resolve**. All three open the Website with
`view=notifications`, `notification_id=<delivery UUID>`, and optionally
`notification_intent=acknowledgment|resolution`. They do not mutate state.
The Website must authenticate the current Steward, ignore intent as authority,
show the exact record, and require its normal POST confirmation. Do not use
ntfy `http` actions for lifecycle changes: an action definition is distributed
in the message and cannot establish an authenticated AP3 session.

The new `phone_delivery` object has `state` (`disabled`, `pending`, `sending`,
`failed`, `sent`), attempts, optional ntfy message ID, last error class, and
attempt/sent times. `sent` means ntfy accepted the publish request; it does not
prove handset receipt, display, or human acknowledgment. A source retry after
phone failure replays the same delivery and retries the durable outbox. The
module adds no scheduler. A lost response after ntfy acceptance can still cause
an external duplicate on retry; the durable delivery ID and idempotency key
remain stable.

## Images, attachments and platform limits

The local ntfy server's current configuration was not readable to this account,
so attachment storage, expiry, quotas, and phone client versions are unverified.
ntfy supports local file uploads and external attachment URLs, but configured
server limits and retention vary. The default documented server attachment
expiry is three hours; default per-file size is 15 MB, while ntfy.sh uses a
different 2 MB limit. Current ntfy iOS release notes describe inline images
and downloadable files beginning with iOS app 1.7.0. Do not infer these limits
or features for this private server/device without testing it.

R3A will not upload raw event evidence or arbitrary external URLs. When an
authoritative event includes an image, link to its authenticated source record;
add an attachment only after the image is explicitly classified for the
recipient and a durable, access-controlled retention path is established.

## Website inbox contract

`r3a_plugins/notification_service/notification-inbox.v1.schema.json` describes
the additive `r3a.notification-inbox.v1` response. It retains the complete N1
notification and adds a presentation object with title, summary, details,
source, reason, UTC/local occurrence time, correlation, evidence references,
deep link, and safe navigation intents. It includes delivery and ntfy transport
state separately. The existing routes remain:

- `GET /api/v1/notifications?cursor=&limit=` — recipient-scoped history;
- `POST /api/v1/notifications/{delivery_id}/acknowledgment` — authenticated,
  idempotent receipt action;
- `POST /api/v1/notifications/{delivery_id}/resolution` — authenticated,
  idempotent disposition plus evidence references.

Website #51 should mount these behind the #49 session, add the documented
notification deep-link query behavior, and render only canonical API outcomes.
No browser should receive the internal source or ntfy publish token.

## Acceptance limits

Payload tests use a local HTTP capture server; they do not call the protected
phone topic. The existing legacy phone services remain active. R3A phone
delivery is not reported live until Coordinator activates the compatible
module, a real managed event maps to an authoritative Steward recipient, the
Website session/action routes work, and a real phone on the #49 network matrix
confirms receipt and link behavior.
