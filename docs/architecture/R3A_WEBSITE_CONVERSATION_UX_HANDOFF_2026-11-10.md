# R3A Website conversation UI — backend handoff

**Date:** 2026-11-10
**Worktree:** `/home/admin1/r3a-workstreams/ap3-website`
**Branch:** `engineering/r3a-ap3-website-20261107`
**Authority:** Issue #51, latest Website directive comment `6769718391`.

The Website increment implements the available presentation and client behavior. The following features need backend contracts before they can be enabled. This note does not change CME authorization, resident identity bindings, Grace autonomy, or shared services.

## Current boundary found in source

- `r3_app.py` provides authenticated conversation list, create, durable message read, and send routes. Conversation reads/sends use the scoped Steward principal and existing CME control request. No rename/archive/restore/delete route was found.
- `r3a_runtime/db.py` stores messages and projects durable activity outcomes into resident replies. The Website polls this durable history and does not invent response chunks.
- `GET /api/v1/steward/about` returns `r3a.website-about.v1`, observed time, freshness, Ring0, CME, Grace module and runtime revision. It does not expose inference model/provider startup or readiness.
- No authenticated SSE or WebSocket conversation stream route was found. Current durable snapshot polling is therefore retained.

## Conversation lifecycle API

Provide a versioned API that scopes every operation to the authenticated Steward principal and the existing resident binding. Required operations: rename/title update, archive, restore/unarchive, and delete if retention policy permits. Responses should return the canonical conversation ID, resident ID, title, lifecycle state, updated timestamp, revision, freshness, and request correlation. Require optimistic concurrency (revision/ETag) and idempotency for mutations; produce an auditable actor and outcome. A missing or cross-owner conversation must fail closed without revealing another resident's records. Once available, the Website can enable each action separately according to the route and policy exposed by the service.

## Genuine streaming API

If the managed service supports genuine response deltas, expose a same-origin authenticated stream scoped to one authorized conversation. The contract should define:

- server-authenticated session and origin policy; per-conversation owner/resident authorization;
- explicit accepted, queued, starting, streaming, completed, blocked, failed, and cancelled events;
- monotonically ordered event IDs/cursors, reconnect replay, heartbeats, and terminal status;
- durable message/activity references and timestamps on final events;
- cancellation semantics and reconciliation with the canonical durable messages route.

The Website should reconnect using the last event cursor, then reconcile the final state against durable messages. Until this exists, the Website uses real persisted snapshots with backoff and makes no streaming claim.

## Model and startup readiness

Extend `r3a.website-about.v1` (or add a separately versioned status contract) with source-attested model/provider health, readiness state, observed timestamp, freshness, and safe reason. Distinguish host/service startup, model loading, ready, unavailable, stale, and failed. Do not infer model readiness from Grace module lifecycle, a process being alive, or prior successful inference. A starting state should be polled automatically without a fabricated countdown. The Website must remain usable and show the latest check time while startup proceeds.

## Acceptance after Coordinator integration

1. Use a real authenticated Steward browser session against the Coordinator-controlled deployment.
2. Exercise list, create, select, send, and receive; verify a completed response appears without switching conversations and remains after reload.
3. Switch between two residents while reads are pending and confirm no conversation or message crosses the resident boundary.
4. Exercise startup, transient outage, session expiry, recovery, failure and blocked responses with server-reported state.
5. Test streamed events only after a real stream contract exists; otherwise verify accurate polling and no fake deltas.
6. Test enabled conversation mutations against the actual authorization and audit responses before enabling their UI controls.
7. Check keyboard/IME behavior, narrow viewport, focus order, accessible action names, and tooltip discoverability.

Source-level regression tests do not replace this authenticated browser acceptance. The Website branch must not independently deploy or restart shared services.
