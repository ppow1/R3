<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_STEWARD_WORKSPACE_WEB_API_V1.md
Component: R3A-STEWARD-WORKSPACE-WEB-CONTRACT
File Revision: 1.0.0
Created: 2026-11-07 UTC
Created By: Codex GPT-6
Purpose: Define the website consumer contract for persistent chat and notification inbox APIs
Execution Model: Same-origin HTTP API, authenticated by the shared AP3 Steward session
Observability: Service timestamps, freshness, correlation identifiers, idempotency, audit outcomes
Dependencies: Issue #49 session integration; authoritative resident/conversation service; Issue #48 notification actions
Authority: Website consumer contract proposal; requires confirmation by the owning backend workstreams
Changed: 2026-11-07 | R3A-007/R3A-010 | Define versioned website interfaces without adding an identity or data authority
Supersedes: None.
Contracts: r3a.steward-workspace-web.v1; r3a.steward-session.v1; r3a.notification-delivery.v1; r3a.notification-inbox.v1.
Tests: tests/test_steward_workspace_api.mjs covers the client transport with development-only mocked fetch
History/Predecessor: New contract proposal; initial publication recorded in Git.
-->
# R3A Steward workspace web API v1

**Status:** Website consumer contract proposal. It is not evidence that resident chat is live. Notification paths follow the #48 AP1-N2 handoff proposal; #48/#43 still need to confirm principal binding and response schemas.

## Shared transport and authentication

Chat operations use same-origin paths below `/api/v1/steward`; notification delivery uses the `/api/v1/notifications` paths proposed by #48. The browser sends:

- `Accept: application/vnd.r3a.steward-workspace-web.v1+json`
- `X-R3A-Contract: r3a.steward-workspace-web.v1`
- `credentials: same-origin`

The browser does not send bearer tokens. The endpoint boundary must use the opaque Steward session cookie and origin validation established by #49. The shared cookie scope is `/api/v1` so it reaches both session-prefixed APIs and #48's proposed `/api/v1/notifications` routes. `401` means no valid session, `403` means a policy denial, `404` means the contract/service is not mounted, and `503` means an authoritative dependency is unavailable. Responses may include `X-Correlation-ID` or `X-Request-ID`; clients retain it for display and support. Every successful chat response includes `contract: "r3a.steward-workspace-web.v1"` and `freshness` (`current`, `stale`, or `unavailable`). The service, not the website, owns timestamps and durability.

The API must preserve authorization by the authenticated Steward and resident-specific membership/capability grants. A client supplied identifier never grants access. Reads must not fabricate empty data when the service is unavailable; an authorized empty result is `200` with an empty list.

## Resident directory and conversations

| Method and path | Purpose | Success shape |
| --- | --- | --- |
| `GET /residents` | Authorized resident discovery from the institutional directory | `{contract, freshness, residents:[{resident_id,display_name,authorized}]}` |
| `GET /conversations?resident_id=…&cursor=…` | Caller-accessible conversations for a directory resident | `{contract, freshness, conversations:[{conversation_id,resident_id,title,updated_at}], next_cursor}` |
| `POST /conversations` | Start or resume a durable conversation with the selected resident | Request `{resident_id, client_conversation_id}`; response `{contract, freshness, conversation:{conversation_id,resident_id,title}}` |
| `GET /conversations/{id}/messages?cursor=…` | Ordered durable history | `{contract, freshness, messages:[{message_id,conversation_id,sender:{id,kind,display_name},text,created_at,delivery_state}], next_cursor}` |
| `POST /conversations/{id}/messages` | Send text to the resident selected by the authoritative conversation record | Request `{client_message_id,text}`; response `{contract, freshness, message:{message_id,conversation_id,delivery_state,created_at}, correlation_id}` |

Message retries use `client_message_id` as the idempotency identity. `delivery_state` is service supplied; the UI calls a message accepted only after a durable message identifier is returned. Conversation messages are distinct from objectives and formal work orders. Conversation creation or send may be denied by the current resident membership/capability policy. No client-side roster, transcript, or message cache is an institutional source.

## Notification inbox

| Method and path | Purpose | Success shape |
| --- | --- | --- |
| `GET /api/v1/notifications?cursor=…` | Recipient-specific durable inbox and history; recipient derives from authenticated caller | `contract: "r3a.notification-inbox.v1"`, freshness, `deliveries` using `r3a.notification-delivery@1.0.0` fields (`delivery_id`, recipient scope, source/correlation, severity/urgency/requires_action/status, timestamps, `evidence_refs`) and next cursor |
| `POST /api/v1/notifications/{delivery_id}/acknowledgment` | Durable acknowledged transition | Request `{idempotency_key,note?}`; result includes durable state, actor, authorization/audit reference, timestamp and correlation |
| `POST /api/v1/notifications/{delivery_id}/resolution` | Durable resolved transition | Request `{idempotency_key,disposition,evidence_refs}`; result includes durable state or explicit rejection/blockage, actor, authorization/audit reference, timestamp and correlation |

Notification actions follow the #48 proposal and must enter CME under existing `notification.delivery.read`, `.acknowledge`, and `.resolve` capability grants. The site does not synthesize acknowledgement, resolution, or completion results. After an action, it rereads the record and renders the returned durable state. In particular, this endpoint does not equate a Grace notification receipt with Steward acknowledgement.

## Current integration boundary

The website consumes these routes but the current #51 branch does not host them. #49 currently owns `/api/v1/steward/session` and the shared access boundary; routes must use that opaque session and preserve origin validation. #48's branch documents the notification handoff paths above but reports principal binding and endpoint integration pending #43 coordination. The resident directory, conversation persistence, and message service must be identified as authoritative before routes are enabled. Until then the UI reports unavailable/unauthenticated states and displays no sample records.

