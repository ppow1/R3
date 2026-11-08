<!--
R3A controlled handoff
File: docs/architecture/R3A_NOTIFICATION_PHONE_DELIVERY_V1.md
Component: R3A-AP1-NOTIFICATIONS
Revision: 1.0.0
Purpose: Record ntfy integration, phone-message payload and Website action boundaries.
Authority: Steward Issue #48 and R3A AP1/R3A-019.
Changed: 2026-11-08 | AP1-N2 | Inspect R2/R3 delivery, parking lots and ntfy contracts.
Tests: tests.test_r3a_notification_ntfy; tests.test_r3a_notification_service.
-->
# R3A notification phone delivery v1

## Existing R2/R3 path and preserved behavior

The currently active legacy path is the Riverview notification dispatcher plus
the private ntfy server. Read-only inspection on 2026-11-08 found both system
services active; ntfy health at loopback port 2586 returned `healthy`, and the
installed ntfy server reports v2.32.0. The dispatcher loads its ntfy token and
topic using systemd credentials. This work does not change or restart either
service or reuse its protected topic credentials.

The deployed publisher sends a title, priority, tags, and a fixed generic body
selected by event type. Its single `view` action opens a V2 work/communications
URL. It does not include the source reason, event timestamp, or correlation ID.
The durable legacy dispatcher tracks pending/sending/failed/sent delivery,
attempt count, retry time, lease, and ntfy message ID. Preserve that path until
the separately configured R3A path has a verified device test.

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
`r3a.notifications@1.2.0`, state schema 3, the inbox schema, the source
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

With optional `ntfy.enabled=true`, module v1.2.0 sends a JSON publish request
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
