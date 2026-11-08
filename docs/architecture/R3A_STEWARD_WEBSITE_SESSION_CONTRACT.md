<!--
R3 CONTROLLED SOURCE
File: docs/architecture/R3A_STEWARD_WEBSITE_SESSION_CONTRACT.md
Component: R3A-AP3-STEWARD-ACCESS
File Revision: 1.0.2
Created: 2026-11-07T23:43:25Z
Created By: Codex GPT-6
Purpose: Publish the versioned Steward principal/session contract and integration instructions for website clients.
Execution Model: Same-origin browser client over the shared AP3 session and CME control boundary.
Observability: Each operation returns a correlation ID; authoritative mutations return durable audit references.
Dependencies: r3a.identity-provider.v1; r3a.steward-principal.v1; r3a.steward-session.v1; r3a.capability-invocation.v1.
Authority: AP3-M1 Issue #49; coordinated with #50 and #51.
Changed: 2026-11-07T23:43:25Z | AP3-M1 | Codex GPT-6 | Publish website session contract and integration instructions.
Changed: 2026-11-07T23:43:25Z | AP3-M1 | Codex GPT-6 | Publish standalone principal schema alongside the session schema.
Changed: 2026-11-07T23:55:00Z | AP3-M1/#51 | Codex GPT-6 | Document shared cookie scope and generic registry discovery for same-origin workspace clients.
Supersedes: None.
Contracts: r3a.identity-provider.v1; r3a.steward-principal.v1; r3a.steward-session.v1.
Tests: tests/test_r3a_steward_access.py validates provider replacement and session responses.
History/Predecessor: New file; initial publication recorded in Git.
-->
# Steward session contract for website clients

The machine-readable schemas are [steward-session.v1.schema.json](../../r3a_runtime/schemas/steward-session.v1.schema.json) and [steward-principal.v1.schema.json](../../r3a_runtime/schemas/steward-principal.v1.schema.json). Contract IDs are stable and versioned independently:

- `r3a.identity-provider.v1` is the trusted server-side adapter boundary. Implementations expose `contract_id`, compatible `contract_version`, and synchronous `authenticate(request, correlation_id) -> IdentityAssertion`. The result contains verified `issuer`, stable `principal_id`, unique `assertion_id`, original authentication time, factor references, and non-secret credential provenance. Implementations raise `PermissionError` for invalid/unauthorized identity and `AccessUnavailable` when the upstream identity service cannot be reached. They do not create sessions, accept browser-supplied principal authority, or decide CME grants.
- `r3a.steward-principal.v1` is the server-derived identity projection: `contract`, `principal_id`, `issuer`, `authenticated_at`, and `factor_refs`. Only the server's authenticated session response is authoritative.
- `r3a.steward-session.v1` is the shared cookie/session lifecycle. Its opaque token is HttpOnly and is never returned in JSON or stored by website JavaScript. Session state is re-read from the authoritative store on each request; expiry and revocation take effect immediately.

## Browser operations

Base path: `/api/v1/steward`. Requests are same-origin only, use `credentials: "same-origin"` and `cache: "no-store"`. Mutation requests must include the browser's `Origin`; the server checks it against configured origins. SameSite=Strict and HttpOnly cookies are set by the server. The shared cookie uses `Path=/api/v1` so authorized sibling APIs such as the recipient notification endpoints can validate the same opaque session; the session token is never returned in JSON or exposed to browser JavaScript. The API does not enable cross-origin credentialed access.

| Operation | Request | Success | Common outcomes |
| --- | --- | --- | --- |
| `POST /session` | Empty body; the trusted ingress supplies its signed assertion to the server. Website must not send identity or principal fields. | 200 `r3a.steward-session.v1` with authoritative `principal`, `expires_at`, `freshness`, `correlation_id`; sets cookie. | 401 unauthenticated/invalid identity; 403 origin denied; 503 identity or session store unavailable. |
| `GET /session` | Cookie only. | 200 `r3a.steward-session.v1` with server-derived principal and expiry. | 401 missing, expired, or revoked session; 503 session store unavailable. |
| `DELETE /session` | Cookie and `Origin`. | 200 `{contract, state:"revoked", revoked:true, principal_id, correlation_id}`; clears cookie. | 401 invalid session; 403 origin denied; 503 session/audit state unavailable. |
| `GET /status` | Cookie only. | 200 `r3a.steward-access-status.v1` with session principal, CME health/freshness, audit event ID, correlation. | 401 no valid session; 503 session state unavailable. CME unavailable/stale is represented in the 200 status body, not as healthy. |
| `GET /capabilities` | Cookie only. | 200 `r3a.steward-capability-discovery.v1` from CME registry discovery; explicitly reports `authorization_evaluated: false`. | 401 no valid session; 503 CME registry unavailable. Discovery does not authorize invocation. |
| `POST /operations/invoke` | Cookie, `Origin`, `{request: <r3a.capability-invocation.v1>}`. | 200 `r3a.steward-operation-result.v1`, authoritative result, audit event ID, correlation. | 401 unauthenticated; 403 CME grant denied; 422 malformed invocation; 503 CME/session/audit unavailable. |

Do not add a route per capability. Submit canonical versioned invocations through `/operations/invoke`; CME resolves the operation and remains authoritative for grants, execution, and its audit. The website must not set `caller.principal_id`, resident/service identity, or grants as authority. The gateway overwrites caller identity from the validated session and clears resident/service self-claims.

The current contract has no refresh endpoint. When a session expires, check `GET /session` and restart the identity authority's flow with `POST /session`; do not silently refresh from browser-held credentials. On non-2xx responses, inspect the HTTP status and treat the body as diagnostic only; never infer authentication from local UI state. Keep the correlation ID and returned audit event ID with operation evidence.

## Identity-provider replacement

`StewardAccess` receives one `IdentityProvider` implementation through dependency injection. The default `HmacIngressIdentityProvider` validates short-lived ingress assertions and resolves its verification key through Issue #50's `r3a.secrets.provider.v1` lease. A replacement OIDC/portal adapter must implement `r3a.identity-provider.v1` and normalize its trusted result into `IdentityAssertion`; the session router, durable store, CSRF/origin enforcement, status/operation endpoints, and CME grant path remain shared. The adapter must never emit credential material, create a parallel session authority, or treat #50's `r3a.machine-principal.v1` as the Steward principal.

For #51: consume the paths and JSON contract above from the same origin. Replace any website-local bearer-token behavior with this cookie session. Keep capability controls schema/discovery-driven where available and send operations through the generic invocation endpoint. This contract does not claim a live identity-provider, database, or CME connection; integration testing must distinguish mocked contract tests from an authenticated institutional runtime trace.
