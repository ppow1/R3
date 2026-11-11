# R3A Website conversation UI — backend handoff

**Date:** 2026-11-10
**Worktree:** `/home/admin1/r3a-workstreams/ap3-website`
**Branch:** `engineering/r3a-ap3-website-20261107`
**Authority:** Issue #51 conversation specification comment `6769718391`; Website continuation comment `6770760857`; modular architecture directive.

The Website increment implements the available presentation and client behavior. The following features need backend contracts before they can be enabled. This note does not change CME authorization, resident identity bindings, Grace autonomy, or shared services.

## Continuation from `ad9fd9a` — 2026-11-10

The resident roster is now refreshed through the existing same-origin, versioned `residents()` adapter every 15 seconds while healthy and every 5 seconds after a failed check. Only a `current` directory response may establish the green availability state or enable sending/creation; stale or unavailable evidence marks availability unconfirmed and pauses sends while preserving history and the last confirmed names. The indicator tooltip shows its last confirmed check time. In-flight directory responses are revision-checked and cannot repopulate the interface after session revocation. Message sender labels prefer the current authoritative directory display name over an identifier-shaped sender field. This adds no resident identity map, no client cache as source of truth, and no new backend or CME operation.

Python API tests are runnable without modifying the service environment by using the existing isolated interpreter: `/home/admin1/R3/.venv/bin/python -m unittest tests.test_r3a_website`. This passed 20 tests in this continuation. The venv was not changed. Client tests: `node --test tests/test_steward_workspace_api.mjs` (20 passed).

The server still has no persistent rename/archive/restore/delete routes and no authorized stream. These are actual interface dependencies, so the Website leaves those controls disabled and continues polling durable message snapshots. The Website must not create browser-only pretend conversation mutations or couple to the separate V2 account/database. The current messages API yields final durable messages/status; no genuine streaming transport is present.

## Prepared authenticated browser run

Run against the Coordinator-integrated deployed Website after that owner performs controlled deployment; this workstream must not deploy or restart shared services. Use the operator's normal authenticated Steward browser session, and do not export cookies or paste credentials into logs. Start with a clean browser tab on `/steward`; record the Website build revision, session state, date/time/timezone, browser and viewport. Capture the Network panel with response bodies redacted for message text and personal information, and capture console errors.

Execute and record these cases with API response/request correlation IDs, selected resident display name, conversation ID (in restricted evidence only), message/activity IDs and outcome:

1. **Roster and readiness:** load the resident directory; check names, availability dots, and last runtime/roster check. Keep the page open through at least one 15-second healthy refresh. If a dependency is starting or unreachable, verify visible retry state and no false ready claim.
2. **Durable conversation:** select Grace; create/open a conversation; send a short ordinary message using Enter; verify a completed reply appears without changing selection; reload and verify both messages remain.
3. **Resident isolation:** start reads for one resident, switch to another before responses finish, and verify the old response cannot replace the current list/history. Confirm unavailable residents remain readable but cannot send or create.
4. **Composer/accessibility:** verify Shift+Enter newline, IME composition, message toolbar keyboard operation, accessible labels/tooltips, Details and clipboard outcome; inspect narrow and desktop widths.
5. **Recovery:** exercise a real transient service/model start or outage approved by Coordinator, observe reconnect and final completed/blocked/failed message state, and verify an expired session is handled by the canonical Website login flow.
6. **Unsupported controls:** confirm lifecycle actions are clearly disabled while their APIs are absent. Do not test state-changing operations against guessed routes.

Keep this acceptance evidence separate from mocked test results. A feature is live-accepted only with the authenticated browser/API trace and durable reload check attached to Issue #51.

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
8. With browser site storage denied (or a test profile whose storage API throws), reload the workspace and verify navigation/chat initialization still completes, the UI reports tab-only preference persistence, layout controls remain usable for the session, and no auth/session credential is written to browser storage. Restore normal storage and verify ordinary preference persistence.

Source-level regression tests do not replace this authenticated browser acceptance. The Website branch must not independently deploy or restart shared services.
