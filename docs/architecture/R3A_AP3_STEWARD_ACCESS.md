<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_AP3_STEWARD_ACCESS.md
Component: R3A-AP3-STEWARD-ACCESS
File Revision: 1.0.9
Created: 2026-11-07T21:37:42Z
Created By: Codex GPT-6
Purpose: Specify the AP3-M1 identity/session boundary, portal endpoints, authority delegation, and freshness behavior.
Execution Model: Architecture/contract record for the optional R3 portal router.
Observability: Versioned contracts, correlation IDs, structured log metadata, PostgreSQL append-only audit evidence.
Dependencies: AP0 PostgreSQL event ledger and CME Unix control protocol; Bitwarden/machine identity provider coordination in Issue #50.
Authority: Roadmap Baseline 1.0, AP3-M1 Issue #49, R3A-010 and R3A-013; exception None.
Changed: 2026-11-07T21:37:42Z | AP3-M1 | Codex GPT-6 | Record the implemented ingress identity/session and CME delegation contracts.
Changed: 2026-11-07T21:44:36Z | AP3-M1 | Codex GPT-6 | Specify signed factor references and index the responsive portal prototype.
Changed: 2026-11-07T21:48:11Z | AP3-M1 | Codex GPT-6 | Document the live CME health read and unavailable-state behavior.
Changed: 2026-11-07T21:53:47Z | AP3-M1 | Codex GPT-6 | Align secret resolution and machine-principal evidence with Issue #50's published API.
Changed: 2026-11-07T22:00:10Z | AP3-M1 | Codex GPT-6 | Define minimum database privileges and session factor metadata.
Changed: 2026-11-07T22:02:18Z | AP3-M1 | Codex GPT-6 | Document configurable database acquisition timeout and durable invalid-session/origin denials.
Changed: 2026-11-07T22:03:19Z | AP3-M1 | Codex GPT-6 | Specify mandatory Secure session cookies for configured remote transport.
Changed: 2026-11-07T23:53:17Z | AP3-M1/AP3-M2 | Codex GPT-6 | Record Bitwarden 1.1.0 compatibility, safe reason codes, and complete contract provenance.
Changed: 2026-11-07T23:53:17Z | AP3-M1/#51 | Codex GPT-6 | Document the shared Website principal dependency and coordinated prototype demonstration.
Changed: 2026-11-07T23:57:23Z | AP3-M1/#51 | Codex GPT-6 | Share one /api/v1 cookie with Website APIs and expose generic CME operation discovery.
Supersedes: None.
Contracts: r3a.steward-identity.v1; r3a.steward-session.v1; r3a.steward-operation-result.v1; r3a.steward-access-status.v1.
Tests: tests/test_r3a_steward_access.py; live transport remains unconfigured.
History/Predecessor: New file; initial publication recorded in Git.
-->
# AP3-M1 Steward access prototype

## Assignment traceability

- Approved roadmap: Master Roadmap Baseline 1.0.
- Phase/milestone: AP3-M1.
- Requirements: R3A-010 and R3A-013.
- Authorized scope: Issue #49, secure Steward identity/session lifecycle, grant enforcement, portal operations, mobile-friendly same-origin routes, and explicit remote freshness/unavailability.
- Acceptance: authenticated authoritative read, CME-authorized operation, denied invalid access, session revocation, correlated durable audit; remote/mobile proof when an ingress is available.
- Approved exception: None.

## Existing authority boundaries

The existing `r3_app.py` had no login or session API. The R3A directory provider is read-only discovery and does not grant authority. CME's `r3a.capability-invocation.v1` path and configured authorization provider remain responsible for operation grants, denials, and capability audit. The portal does not create or modify grants.

## Contracts and flow

The ingress verifies the existing identity authority and sends an HMAC signed assertion using `X-R3-Identity-Issuer`, `X-R3-Identity-Subject`, `X-R3-Identity-ID`, `X-R3-Identity-Time`, `X-R3-Identity-Authenticated-At`, `X-R3-Identity-Factors`, and `X-R3-Identity-Signature`. The signature covers the six preceding values joined with newlines, in that order. Factor references and original authentication time are retained as versioned hooks for TOTP/YubiKey. The portal accepts only the configured issuer and exact Steward principal and validates signature and assertion age. The edge must remove any client-supplied assertion headers before inserting its own. Assertion key resolution uses Issue #50 `r3a.secrets.provider.v1@1.1.0` and its closeable `SecretLease`, with the configured SecretReference's provider version set to `1.1.0`. The machine account remains secret-fetch metadata and never becomes the Steward principal. Durable non-secret provenance includes the secret-provider and machine-principal contract IDs/versions, provider/secret reference, remote revision, fetch time, and machine assertion fields.

On success, the portal creates a cryptographically random bearer token, stores only its SHA-256 digest plus principal/issuer/authentication-time/factor/expiry/revocation metadata in `r3a.steward_sessions`, and sets an HttpOnly, Secure (configurable for local testing), SameSite=Strict cookie. A unique assertion ID prevents replay. Logout revokes the durable session and expires the browser cookie. Session lookup reads the durable database each time, so revocation and unavailable state are visible immediately.

`GET /api/v1/steward/status` reads live CME health through its private control socket and records a correlated state-read event. If CME cannot be reached, health and freshness report `unavailable`; no configured endpoint is presented as live. `POST /api/v1/steward/operations/invoke` takes one canonical capability invocation. The portal overwrites caller principal with the authenticated session subject, clears resident/service self-claims, supplies a server correlation ID, and passes the request through the existing CME local control socket. CME evaluates the configured grant and operation/effect contract. The browser cannot make a caller-supplied grant authoritative. The CME authorization audit and portal correlation are returned with successful results; a denial remains a refusal and is audited.

Endpoints are opt-in via `R3A_STEWARD_ACCESS_CONFIG`; no auth route or listener is added by default. The configured `StewardAccess` instance is retained on `app.state.steward_access`; Website route adapters under `/api/v1/steward/` can use `Depends(require_steward_principal)` so desktop and mobile clients share the same cookie, durable session, and revocation authority. The generic `/operations/invoke` endpoint remains the capability gateway and CME remains the grant authority. The configuration requires a session DSN and explicitly records `public_exposure: false`. Remote transport status remains `unavailable` until a real encrypted ingress is provisioned. The current repository does not contain a deployed identity ingress, Bitwarden credentials, or configured R3A DSN; therefore the prototype is not yet operational for remote use.

## Security and freshness

- No password database, duplicate resident roster, hardcoded grant, credential, or public endpoint is introduced.
- Secret values and raw assertions/tokens are not logged, returned, or stored; assertion IDs are only used for replay prevention.
- Authentication state, session lifecycle, operation outcome, and failure correlation are stored in PostgreSQL. CME remains authoritative for capability grant decisions.
- Invalid origin, invalid session, and operation denial paths append correlated denial events. A valid request with unavailable CME or session persistence reports unavailable instead of using cached state.
- Remote transport configuration requires `Secure` session cookies; same-origin and request-origin checks protect browser mutations.
- The portal database role needs `USAGE` on schema `r3a`; `SELECT`, `INSERT`, and column-level `UPDATE(revoked_at)` on `r3a.steward_sessions`; and `INSERT` on `r3a.institution_events`. Migrations remain owned by the existing migration identity. The portal role does not need event update/delete, session delete, grant, or schema ownership privileges.
- The session and operation endpoints fail closed on missing or stale identity, session, database, or CME state. They do not serve cached authentication or fabricate operation success.
- The reverse proxy/identity ingress remains an externally configured replaceable component. Bitwarden secret retrieval uses Issue #50's versioned provider contract; live retrieval still requires configured machine credentials and a secret reference.
- `SecretProviderError.reason_code` is retained as a finite internal audit/status reason; the HTTP response remains generic and the exception message/CLI output is discarded. Provider outcomes such as credential unavailable, access denied, reference not found, and provider failure remain distinct internally.
- Development E2E sequence, once the coordinator provides a configured identity ingress, Bitwarden machine account, AP3 database, CME socket, and test window: authenticate through ingress; verify durable current session; submit a known authorized generic CME invocation and retain its activity/correlation/audit references; delete the session; repeat the invocation and verify denial plus durable denial audit. Synthetic tests cover the sequence shape; no live run is claimed until that coordinated window is available.
- TOTP and YubiKey have no current implementation; the assertion contract preserves issuer and authentication-factor provenance hooks for the next adapter revision.
