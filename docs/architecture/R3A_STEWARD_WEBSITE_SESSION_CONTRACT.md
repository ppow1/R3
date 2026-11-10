<!--
R3 CONTROLLED SOURCE
File: docs/architecture/R3A_STEWARD_WEBSITE_SESSION_CONTRACT.md
Component: R3A-AP3-STEWARD-ACCESS
File Revision: 1.0.7
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
Changed: 2026-11-09T16:32:39Z | R3A-AUTH-INDEPENDENCE-001 | Codex GPT-6 | Define R3A-owned authentication target, login routing, and session-cookie namespace; demote R3 adapter to legacy compatibility.
Changed: 2026-11-09T17:06:17Z | R3A-AUTH-INDEPENDENCE-SECURE-LAN | Codex GPT-6 | Require trusted HTTPS for login and authenticated Website traffic over LAN.
Changed: 2026-11-09T17:20:00Z | AP3-NATIVE-AUTH-INTEGRATION | Codex GPT-6 | Integrate native login/enrollment API contracts while requiring trusted HTTPS and R3A-origin return.
Changed: 2026-11-09T17:54:09Z | R3A-AUTH-COOKIE-ISOLATION | Codex GPT-6 | Require a dedicated R3A hostname to isolate cookies across R3 and R3A sites.
Changed: 2026-11-09T19:23:00Z | AP3-R3A-010-LAN-IP | Codex GPT-6 | Support the approved LAN IP origin with the existing IP-SAN certificate and restrict the session cookie path to the R3A Steward API.
Changed: 2026-11-09T19:23:00Z | AP3-R3A-010-LAN-IP | Codex GPT-6 | Support the approved LAN IP origin with the existing IP-SAN certificate and restrict the session cookie path to the R3A Steward API.
Supersedes: None.
Contracts: r3a.identity-provider.v1; r3a.steward-principal.v1; r3a.steward-session.v1.
Tests: tests/test_r3a_steward_access.py validates provider replacement and session responses.
History/Predecessor: New file; initial publication recorded in Git.
-->
# Steward session contract for website clients

The machine-readable schemas are [steward-session.v1.schema.json](../../r3a_runtime/schemas/steward-session.v1.schema.json), [steward-principal.v1.schema.json](../../r3a_runtime/schemas/steward-principal.v1.schema.json), [steward-login-request.v1.schema.json](../../r3a_runtime/schemas/steward-login-request.v1.schema.json), and [steward-auth-health.v1.schema.json](../../r3a_runtime/schemas/steward-auth-health.v1.schema.json). Contract IDs are stable and versioned independently:

- `r3a.identity-provider.v1` is the trusted server-side adapter boundary. Implementations expose `contract_id`, compatible `contract_version`, and synchronous `authenticate(request, correlation_id) -> IdentityAssertion`. The result contains verified `issuer`, stable `principal_id`, unique `assertion_id`, original authentication time, factor references, and non-secret credential provenance. Implementations raise `PermissionError` for invalid/unauthorized identity and `AccessUnavailable` when the upstream identity service cannot be reached. They do not create sessions, accept browser-supplied principal authority, or decide CME grants.
- `r3a.steward-principal.v1` is the server-derived identity projection: `contract`, `principal_id`, `issuer`, `authenticated_at`, and `factor_refs`. Only the server's authenticated session response is authoritative.
- `r3a.steward-session.v1` is the shared cookie/session lifecycle. Its opaque token is HttpOnly and is never returned in JSON or stored by website JavaScript. Session state is re-read from the authoritative store on each request; expiry and revocation take effect immediately.

## Browser operations

Base path: `/api/v1/steward`. Requests are same-origin only, use `credentials: "same-origin"` and `cache: "no-store"`; session responses set `Cache-Control: no-store`. Mutation requests must include the browser's `Origin`, which the server checks against configured origins. R3A sets the host-only `r3a_steward_session` cookie with `Path=/api/v1/steward`, `HttpOnly`, `SameSite=Strict`, and `Secure`. Credential submission and authenticated Website traffic require browser-trusted HTTPS, including on the private LAN. Browsers scope cookies by host, not port; the narrow path keeps this cookie off R3's `/api/v1/auth` and `/api/v1/chat` routes when both use the LAN IP. Cross-origin credentialed access is disabled. The approved LAN origin is `https://192.168.1.155:8311`, using a certificate with IP SAN `192.168.1.155`; no custom DNS is required.

The R3A Website owns the login presentation and post-login route. It starts authentication at its own same-origin login API and returns to the R3A Steward interface. It must never redirect to or require the R3 website or R3 account/session service. LAN-only means private routing with no public ingress; separate remote-access approval is still required.

| Operation | Request | Success | Common outcomes |
| --- | --- | --- | --- |
| `POST /session` | With `r3a.native`, same-origin JSON `{ "intent":"login", "login_name":"…", "password":"…" }`. For an operator-issued one-time enrollment/recovery challenge, `{ "intent":"enroll"|"recover", "login_name":"…", "password":"…", "challenge":"…" }`. Legacy adapters may use an empty body. The Website must never send principal IDs, roles, or grants. | 200 `r3a.steward-session.v1` with authoritative `principal`, `expires_at`, `freshness`, `correlation_id`; sets cookie. Credentials are used only for this request and are neither returned nor persisted by Website JavaScript. | 401 generic authentication denied; 403 origin denied; 503 identity or session store unavailable. |
| `GET /health` | No cookie. | 200 `r3a.steward-auth-health.v1` when identity and session stores are reachable. | 503 with explicit `unavailable` state. A healthy empty account table does not mean a Steward is enrolled. |
| `GET /session` | Cookie only. | 200 `r3a.steward-session.v1` with server-derived principal and expiry. | 401 missing, expired, or revoked session; 503 session store unavailable. |
| `DELETE /session` | Cookie and `Origin`. | 200 `{contract, state:"revoked", revoked:true, principal_id, correlation_id}`; clears cookie. | 401 invalid session; 403 origin denied; 503 session/audit state unavailable. |
| `GET /status` | Cookie only. | 200 `r3a.steward-access-status.v1` with session principal, CME health/freshness, audit event ID, correlation. | 401 no valid session; 503 session state unavailable. CME unavailable/stale is represented in the 200 status body, not as healthy. |
| `GET /capabilities` | Cookie only. | 200 `r3a.steward-capability-discovery.v1` from CME registry discovery; explicitly reports `authorization_evaluated: false`. | 401 no valid session; 503 CME registry unavailable. Discovery does not authorize invocation. |
| `POST /operations/invoke` | Cookie, `Origin`, `{request: <r3a.capability-invocation.v1>}`. | 200 `r3a.steward-operation-result.v1`, authoritative result, audit event ID, correlation. | 401 unauthenticated; 403 CME grant denied; 422 malformed invocation; 503 CME/session/audit unavailable. |

Do not add a route per capability. Submit canonical versioned invocations through `/operations/invoke`; CME resolves the operation and remains authoritative for grants, execution, and its audit. The website must not set `caller.principal_id`, resident/service identity, or grants as authority. The gateway overwrites caller identity from the validated session and clears resident/service self-claims.

The current contract has no refresh endpoint. When a session expires, check `GET /session` and restart the identity authority's flow with `POST /session`; do not silently refresh from browser-held credentials. On non-2xx responses, inspect the HTTP status and treat the body as diagnostic only; never infer authentication from local UI state. Keep the correlation ID and returned audit event ID with operation evidence.

## Identity-provider replacement

`StewardAccess` receives one `IdentityProvider` implementation through dependency injection. The independent deployment uses `R3aNativeIdentityProvider` (`r3a.identity-provider.v1`), verifies an R3A-owned scrypt password verifier against `r3a.steward_accounts`, and has no runtime R3 URL, cookie, database, or login dependency. Credentials appear only in the same-origin login POST and are excluded from logging. First enrollment and recovery require a single-use challenge issued by the local operator procedure after the identity association is approved. The provider normalizes identity into `IdentityAssertion`; AP3 alone creates the shared durable session. `HmacIngressIdentityProvider` and `R3AccountSessionIdentityProvider` remain compatibility adapters for legacy tests and are not permitted in the independent deployment. The adapter must never create CME grants or treat #50's `r3a.machine-principal.v1` as the Steward principal.

Identity association, enrollment, and recovery follow the approved [R3A Authentication Independence Plan](R3A_AUTH_INDEPENDENCE_PLAN.md). Do not import R3 password hashes, sessions, reset tokens, factors, or recovery secrets. Do not create identity records from unverified claims. No credential is created until the accountable Steward completes fresh enrollment after authoritative association.

For #51, render a same-origin login form that submits credentials directly to `POST /api/v1/steward/session` with `credentials: "same-origin"`, `cache: "no-store"`, JSON content type, and the browser's exact `Origin`. Do not put passwords or challenges in local/session storage, URL parameters, logs, analytics, or response UI. Clear the fields after submission; on success remain on the dedicated R3A host at `/steward`, then fetch `GET /session`. Enrollment/recovery use the same endpoint and do not redirect to R3. Use the shared cookie for protected Website routes and generic CME invocation. Migration 018 adds account/verifier/challenge state after the current managed baseline through 017. It is uniquely named because 010 is already used by governed knowledge; source-level tests are not a live authenticated runtime trace.

The integration branch serves `/login` and `/web/steward-login.js`. The deployment must set `R3_WEBSITE_AUTH_MODE=r3a-native`, mount the independent AP3 config, and expose the site only on its dedicated browser-trusted HTTPS hostname before inviting credential entry. The client refuses to submit over HTTP. `/login` is a public authentication surface; all resident, conversation, and institutional routes remain protected by the shared AP3 session.
