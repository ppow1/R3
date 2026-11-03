# R3 durable conversation API

**Status:** implementation candidate on `engineering/grace-conversation-api-20261103`; not deployed. The HTTP listener is opt-in and has no browser-facing route until the website backend adds its same-origin proxy.

OpenAPI: [openapi-r3-conversations.yaml](openapi-r3-conversations.yaml)

## Service boundary

This API stores conversations and messages in R3's existing SQLite database and queues each user message as a `CONVERSATION_MESSAGE` event for the existing resident scheduler. The resident inference handler loads prior delivered messages in sequence, persists the response, and records delivery failures against the originating message. The inbox remains the execution journal; it is not presented as the conversation transcript.

It is distinct from:

- Assignment intake: `POST /v1/assignments` and `GET /v1/assignments/{root_event_id}` submit and observe assigned work, including verification lineage.
- The model inference endpoint: OpenAI-compatible model completion only. It has no conversation storage or R3 authorization.

## Runtime configuration

The API binds only to `127.0.0.1` and is disabled unless the service starts with both:

- `--conversation-port 8770`
- `--conversation-token-file /home/admin1/.local/state/r3-runtime/credentials/conversation-api.token`

The token file must be service-readable and mode 0600 or stricter. The token must be at least 32 characters. The service reports `conversation_api_enabled` and `conversation_api_connected` in its health snapshot. The candidate default listener is `http://127.0.0.1:8770`; it is not reachable from a browser on another machine.

## Authentication and browser path

The website backend must authenticate the Steward using the website's established session and enforce that principal's authorization for the selected resident before proxying a request. It then sends the authenticated principal as `X-R3-Principal` and the server-held integration token as `Authorization: Bearer ...` to the loopback listener. The R3 service confines each conversation to its recorded owner principal and verifies that the resident is registered.

The principal header is a trusted server-to-server assertion. R3 cannot independently validate the website session from that header. Therefore only the website backend may hold the token or call this loopback endpoint; it must never accept a browser-supplied principal as proof of identity. Keep the token out of the browser, Settings, HTML, URLs, and client-visible logs.

The browser calls a same-origin website route such as `/api/r3/chat/v1/...`; the website server proxies to `127.0.0.1:8770`. CORS is not enabled or needed for this same-origin flow. Do not expose the runtime listener on LAN or Internet interfaces.

## Endpoints

All paths below are relative to `http://127.0.0.1:8770`. Every route requires the service bearer credential and the trusted `X-R3-Principal` header.

| Method | Path | Result |
|---|---|---|
| GET | `/v1/residents/{resident}/conversations` | Conversations owned by this principal for a registered resident |
| POST | `/v1/residents/{resident}/conversations` | Create an open conversation; optional JSON `{"title":"..."}` |
| GET | `/v1/conversations/{conversation_id}/messages?after=0&limit=100` | Stable sequence-ordered messages; `after` is an exclusive sequence cursor |
| POST | `/v1/conversations/{conversation_id}/messages` | Persist and enqueue one message |
| GET | `/v1/residents/{resident}/capabilities` | `message_actions` and configured `resident_tools` |

Send body:

```json
{"content":"Hello Grace","client_message_id":"stable-client-retry-id"}
```

A new message returns HTTP 202 with `message_id`, `sequence`, `delivery_status: "QUEUED"`, `event_id`, and `duplicate: false`. Retry with the same client message ID and same content returns HTTP 200 and the original receipt. Reusing the ID with different content returns 409. Read the messages endpoint to observe the Steward message's eventual `PROCESSING`, `DELIVERED`, or `FAILED` state and Grace's response as the next sequence entry. Message and conversation timestamps are Unix epoch seconds from the R3 service clock.

## Persistence verification

After deployment and listener configuration, the website team can verify:

1. Through its authenticated session, create a Grace conversation.
2. POST a message using a stable `client_message_id`; confirm HTTP 202 and a queued receipt.
3. Poll the conversation messages endpoint. Confirm the same message ID and content are present, then confirm either a Grace response or a recorded failure.
4. Refresh the website and reload the messages. Confirm the same sequence, sender, and service timestamps.
5. Restart the R3 service and reload the same conversation. Confirm the messages remain.
6. Repeat with another authenticated principal and confirm it cannot list or read the first principal's conversation.

The candidate includes permanent store/API contract tests in `tests/test_conversations.py`; they must pass in the project regression suite before deployment. Syntax compilation alone is not qualification.

## Capabilities and unsupported features

For Grace, `message_actions` currently reports `send_text`. `resident_tools` reports the configured tool allowlist (currently `r3.status` and `r3.host.uptime`); these are information for capability display and are not automatically executable message actions.

Conversation search, rename, archive, reopen, delete, conference rooms, editing, quoting, branching, image generation, saved references, and work-resource actions are not implemented by this service. The API currently creates open conversations and supports text exchange only. The website should label other controls unavailable or planned.
