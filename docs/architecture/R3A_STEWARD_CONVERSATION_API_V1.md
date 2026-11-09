# R3A Steward Conversation API v1

Status: coordinator implementation on `integration/r3a-unified-20261109`; managed activation pending. The API is a same-origin adapter over AP3 session verification and CME durable activities.

## Authority and flow

- AP3 validates the existing `rv_account_session` portal session, required Steward role, expiration/revocation, and same-origin mutation requests. It supplies the session's canonical `principal_id`; callers cannot choose an owner identity.
- CME reads residents only through the configured `institutional.directory.discover` capability invocation, using normal CME grant checks and the registered provider. The response is restricted to directory records with the primary resident execution path or an active `resident.objective.execute` grant.
- CME owns conversation records and messages in PostgreSQL schema `r3a`; each user turn is linked to one idempotent CME activity. CME resolves each selected resident through the authoritative directory and existing execution-profile/model-route contracts.
- The Website never invokes a model endpoint or stores institutional conversation data locally. Its browser client uses the existing `r3a.steward-workspace-web.v1` contract and same-origin opaque cookie.

## HTTP routes

All routes require an active authenticated AP3 session. Mutations require a configured allowed `Origin`. API responses set no-store security headers.

| Method and path | Behavior |
|---|---|
| `GET /api/v1/steward/residents` | Directory discovery with current provenance and only currently executable residents. |
| `GET /api/v1/steward/conversations?resident_id=…` | Lists the authenticated principal's conversations for one resident. |
| `POST /api/v1/steward/conversations` | Idempotently creates a conversation using `{resident_id, client_conversation_id}`. |
| `GET /api/v1/steward/conversations/{conversation_id}/messages` | Returns durable transcript, activity IDs and delivery state; a completed CME result is projected as the resident message. |
| `POST /api/v1/steward/conversations/{conversation_id}/messages` | Accepts `{client_message_id, text}` and enqueues one resident turn. Reuse the same client ID on retry. Returns `202` while CME works. |
| `GET /api/v1/steward/about` | Authenticated read-only Website/build/runtime/module health projection for Settings/About. |

The Website responds `401` for missing/expired sessions, `403` for denied identity/operation, `409` while a prior turn in that conversation is still processing, `422` for invalid input/current directory mismatch, and `503` when configured CME/DB/provider services are unavailable.

## Persistence and execution

Migration `017_steward_conversations.sql` adds `r3a.steward_conversations` and `r3a.steward_conversation_messages`. Conversation ownership is keyed by canonical session principal and resident ID. Creation pins the measured directory snapshot digest and invocation ID. Message IDs are client-supplied UUIDs; activity idempotency binds conversation and message IDs. The transcript is bounded before it is included in the activity input.

Each turn enters `grace.objective.submit` with `event_kind=conversation`; Grace uses the configured resident model role. Other residents require a fresh directory result, office route, Grace delegation grant, and target `resident.objective.execute` grant; CME starts the resident using the existing versioned execution profile. User and assistant messages both retain the CME activity reference. Database owner checks prevent one Steward principal from reading another principal's conversations.

`diagnostics.status` and `diagnostics.events` are read-only CME control operations used by the Website. The status result includes the managed process's captured implementation revision; the Website separately reports its own build revision. These operations use the configured AP3 CME control socket and do not require a second `R3A_CONFIG` file.

## Acceptance boundary

Unit/contract tests do not establish an authenticated browser session, actual model completion, refresh/restart persistence, or Vicky activation. Those require the real account portal session and a current measured directory record with the correct resident execution profile, route and grants. Missing identity, session, route or grant is returned as unavailable/denied; no identity or grant is synthesized.
