# R3A Notifications service

This package is an independently deployable HTTP module. It owns subscription filtering, recipient-scoped delivery persistence, inbox retrieval, durable acknowledgment/resolution, replay handling, and its PostgreSQL schema. It does not schedule work, reason about institutional objectives, or acknowledge the upstream event source.

## Runtime configuration

Copy `config.example.json` outside the package and set environment variables named by its `*_env` fields. Secrets and the configured Steward principal are supplied by the environment, never stored in module config. `source_ids` and `subscriptions` are exact allowlists. The source caller supplies directory-resolved recipients plus the authoritative directory snapshot digest; the module retains that routing provenance.

The example covers the six requested event categories plus an optional informational service-start transition. A subscription only matches its exact event type and any configured evidence filter. `foundation.observe` events and activity subjects are suppressed before persistence. The shared CME source binding remains Coordinator-owned; the HTTP source endpoint is a module boundary for that binding and is protected by a separate service token.

## HTTP contracts

- `GET /healthz` — module version and storage state.
- `POST /internal/v1/notifications` — authenticated source intake with `{notification, directory_snapshot}`. The notification is the existing N1 envelope. The module resolves configured role selectors against a fresh measured directory snapshot using the existing N2 routing contract; caller-supplied recipient IDs are not trusted. Only configured source IDs and event subscriptions are accepted. Duplicate source/recipient events return the original delivery.
- `GET /api/v1/notifications?cursor=&limit=` — recipient-scoped `r3a.notification-inbox.v1`; principal comes from the module's authenticated gateway/dev credential, never from query/body data.
- `POST /api/v1/notifications/{delivery_id}/acknowledgment` — `{idempotency_key, note?}`; actor is derived from authentication and action is persisted once.
- `POST /api/v1/notifications/{delivery_id}/resolution` — `{idempotency_key, disposition, evidence_refs}`.

The standalone bearer adapter is for an isolated development gateway. Production Website requests must be authenticated by #49 and forwarded by the Website server with the authenticated principal; do not expose the service's internal source token to the browser. Website owns local-time display. The service includes a `created_at_local` companion formatted with the shared `presentation_timezone`; canonical delivery and event timestamps remain UTC.

## Lifecycle

Use the packaged console entry point or the example systemd unit. Stopping the process deactivates the HTTP module without stopping PostgreSQL or CME. Replacing the installed package and restarting it upgrades the module version; 1.1.0 applies an additive schema migration from v1 to v2 and records the active module/schema versions in `r3a_notification.module_state`. Existing deliveries and event lineage remain in place.

The Coordinator still owns managed CME source binding and is not changed by this service. The isolated activation evidence uses a separate local PostgreSQL instance and loopback HTTP listener.
