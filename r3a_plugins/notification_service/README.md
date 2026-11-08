# R3A Notifications service

This package is an independently deployable HTTP module. It owns subscription filtering, recipient-scoped delivery persistence, inbox retrieval, durable acknowledgment/resolution, replay handling, optional ntfy outbox state, and its PostgreSQL schema. It does not schedule work, reason about institutional objectives, or acknowledge the upstream event source.

## Runtime configuration

Copy `config.example.json` outside the package and set environment variables named by its `*_env` fields. Secrets and the configured Steward principal are supplied by the environment, never stored in module config. `source_ids` and `subscriptions` are exact allowlists. The source caller supplies the authoritative directory snapshot; the module resolves a configured office role and retains the snapshot digest.

The example covers the six requested event categories plus an optional informational service-start transition. A subscription only matches its exact event type and any configured evidence filter. `foundation.observe` events and activity subjects are suppressed before persistence. The shared CME source binding remains Coordinator-owned; the HTTP source endpoint is a module boundary for that binding and is protected by a separate service token.

Optional `ntfy.enabled=true` turns on the durable phone outbox. Set its topic and credential-file path through the named environment variables; `website_base_url_env` separately names the HTTPS Website origin used by inbox deep links. A failed publish leaves the inbox delivery durable and returns a retryable 503; replaying the same N1 event retries the outbox without creating another delivery. The module has no phone scheduler. A successful response means ntfy accepted the publish, not that a phone displayed it. Leave ntfy disabled until a Coordinator-owned deployment supplies credentials and an authoritative Website origin.

## HTTP contracts

- `GET /healthz` — module version and storage state.
- `POST /internal/v1/notifications` — authenticated source intake with `{notification, directory_snapshot}`. The notification is the existing N1 envelope. The module resolves configured role selectors against a fresh measured directory snapshot using the existing N2 routing contract; caller-supplied recipient IDs are not trusted. Only configured source IDs and event subscriptions are accepted. Duplicate source/recipient events return the original delivery.
- `GET /api/v1/notifications?cursor=&limit=` — recipient-scoped `r3a.notification-inbox.v1`; principal comes from the module's authenticated gateway/dev credential, never from query/body data. Each record retains the complete N1 envelope and includes a `message` object with human-readable title/summary/details, source/reason/severity, UTC/local time, correlation, evidence references, deep link, and safe Website navigation intents.
- `POST /api/v1/notifications/{delivery_id}/acknowledgment` — `{idempotency_key, note?}`; actor is derived from authentication and action is persisted once.
- `POST /api/v1/notifications/{delivery_id}/resolution` — `{idempotency_key, disposition, evidence_refs}`.

The standalone bearer adapter is for an isolated development gateway. Production Website requests must be authenticated by #49 and forwarded by the Website server with the authenticated principal; do not expose the service's internal source token to the browser. The service includes local-time companions formatted with the shared `presentation_timezone`; canonical delivery and event timestamps remain UTC.

ntfy buttons are `view` actions only. Acknowledge and resolve buttons open the Website with an intent query; the Website must authenticate and require its normal POST confirmation. The module does not publish raw source images or external attachment URLs. See `docs/architecture/R3A_NOTIFICATION_PHONE_DELIVERY_V1.md` for the R2/R3 audit, platform limits, Website handoff, and test boundary.

## Lifecycle

Use the packaged console entry point or the example systemd unit. Stopping the process deactivates the HTTP module without stopping PostgreSQL or CME. Replacing the installed package and restarting it upgrades the module version; 1.2.0 applies an additive migration from schema v2 to v3 for phone outbox status and preserves existing deliveries and event lineage.

The Coordinator still owns managed CME source binding and is not changed by this service. The isolated activation evidence uses a separate local PostgreSQL instance and loopback HTTP listener.
