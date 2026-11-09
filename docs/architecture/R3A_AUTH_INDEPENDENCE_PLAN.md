<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_AUTH_INDEPENDENCE_PLAN.md
Component: R3A-AP3-AUTH-INDEPENDENCE
File Revision: 1.0.1
Created: 2026-11-09T16:32:39Z
Created By: Codex GPT-6
Purpose: Define a bounded integration design for R3A-owned Steward authentication and governed initial identity provisioning.
Execution Model: Architecture and migration plan; no identity authority is deployed by this document.
Observability: Contract revision, provider health, session lifecycle events, and acceptance evidence.
Dependencies: R3A Master Roadmap Baseline 1.0; R3A Architecture Charter; AP3 Steward Access contract; Steward approval for identity provisioning policy.
Authority: Steward directive — R3A Authentication Independence; AP3/R3A-010; no phase exception.
Changed: 2026-11-09T16:32:39Z | R3A-AUTH-INDEPENDENCE-001 | Codex GPT-6 | Record target boundary, safe association plan, workstream contracts, and approval gates.
Changed: 2026-11-09T16:32:39Z | R3A-AUTH-INDEPENDENCE-001 | Codex GPT-6 | Specify the one-time non-secret R3 identity provenance read and prevent ongoing R3 synchronization dependencies.
Supersedes: None.
Contracts: r3a.identity-provider.v1; r3a.steward-principal.v1; r3a.steward-session.v1; r3a.capability-invocation.v1.
Tests: Documentation/design review only; implementation and operational acceptance pending.
History/Predecessor: New file; initial publication recorded in Git.
-->
# R3A Authentication Independence Plan

## Decision and roadmap traceability

R3A is an independent institutional system under the R3A Architecture Charter. Reusing reviewed R3 authentication source is allowed; depending on live R3 login, account/session services, cookies, database, or website is not. The current AP3 portal adapter is therefore a legacy prototype binding and cannot be the acceptance architecture.

This work maps to approved Master Roadmap Baseline 1.0, AP3, requirement R3A-010 (secure Steward operations and authentication). It does not change phase ownership, priority, scope, or acceptance criteria, so no roadmap exception is required under R3A-GOV-01. The addendum to R3A-010 records the independence condition. Initial identity association and enrollment policy are approval gates, not a phase exception. No identity records, credentials, grants, or live deployment are authorized by this plan.

## Target service boundary

Keep one AP3 `StewardAccess` session and CME authorization path. Add an R3A-owned identity provider behind the existing `r3a.identity-provider.v1` interface. The provider and its account data must operate with R3 services unavailable. The Website serves a same-origin R3A login experience and calls the AP3 session API; successful login returns to the R3A Steward interface. No R3 URL, cookie, session endpoint, database, or website participates at runtime.

The existing `R3AccountSessionIdentityProvider` may remain as a disabled compatibility adapter for controlled legacy tests, but the independent R3A deployment must reject that provider type. No fallback from a failed R3A login to an R3 authority is permitted.

Use the existing R3A PostgreSQL boundary and append-only event ledger, with explicit migrations and a least-privilege R3A service role. Reuse `r3a.steward_sessions` where its schema is sufficient. Add only the minimum R3A-owned principal/account, credential-verifier, enrollment-challenge, and revocation records required by the approved design. Store password verifiers using a reviewed password-hashing scheme; never store or log plaintext credentials. Session tokens remain random opaque values with only digests persisted. The login service must be independently configurable and restartable, and it must not query or proxy to R3.

Use an R3A-only host cookie named `r3a_steward_session`, host-only, `HttpOnly`, `SameSite=Strict`, and `Path=/api/v1`. Require `Secure` on HTTPS. The current LAN-only HTTP development mode may use `Secure=false` only for the explicitly configured LAN origin and with public exposure disabled. Do not widen network/firewall exposure. Logout revokes the AP3 session; account disablement/revocation invalidates active R3A sessions; expiry is enforced server-side.

Authentication establishes a verified canonical R3A principal only. It does not imply CME capability grants. CME continues to authorize each invocation against its canonical grants. Directory discovery remains separate from login and authorization. Login, failed login, logout, expiry, revocation, and account state changes produce privacy-safe structured audit events without password, token, recovery code, or secret values.

## Existing identity association and credential plan

1. Character Architecture/HR authority identifies the authoritative existing Steward HR record through its authenticated read interface. Separately, the R3 identity owner provides a one-time authorized read of the existing account's stable subject identifier, active/verified state, Steward eligibility, source revision, and provenance reference. The exact R3 read interface and allowed fields must be confirmed with its owner before use. Never read or copy password hashes, sessions, reset tokens, factor seeds, or recovery material. Do not copy protected HR fields into Website or authentication records.
2. The Steward approves the canonical association across the HR identity, existing R3 account subject, and R3A principal. Record the source authorities, source revisions, actor, time, and idempotent association operation ID. Reject ambiguous, stale-revision, inactive, or duplicate associations. The R3 metadata read is a migration input only; R3A performs no ongoing runtime lookup or synchronization against R3.
3. Do not copy R3 password hashes, sessions, reset tokens, MFA seeds, or recovery material. Preferred enrollment is a fresh R3A credential set through a short-lived single-use enrollment challenge delivered by an already approved out-of-band procedure. The challenge conveys no capability grants.
4. Provision CME grants separately through the canonical R3A grant authority after identity association. Authentication roles or HR office bindings never synthesize grants.
5. Until the Steward approves the identity association and enrollment/recovery policy, do not create the R3A account, enroll a credential, issue a real session, or activate the independent authority. No fabricated principal, credential, or grant may be used for acceptance.

Credential-hash migration is excluded from this plan. If later requested, it requires a separate security and compatibility review plus explicit Steward approval; fresh enrollment is preferred. Any approval must specify accountable operator, out-of-band delivery, recovery/revocation, audit retention, and rollback before provisioning begins.

## Workstream contracts and sequence

| Owner | Deliverable | Acceptance boundary |
|---|---|---|
| Remote Access #49 | R3A-native identity provider/account store, independent service and migrations, namespaced cookie, login/logout/expiry/revocation behavior, origin/CSRF checks, no-R3-dependency regression tests, operator provisioning procedure. | Provider runs with R3 endpoints unavailable; no password/session material in logs; canonical principal assertion does not grant CME capabilities. |
| Website #51 | R3A same-origin login UI, authenticated state, correct R3A post-login route, logout/expiry handling, no R3 redirect or portal cookie dependency. | Browser stays on R3A and receives only the opaque R3A cookie; anonymous/protected routes fail closed. |
| Coordinator #56 | Integrate versioned provider/website contracts, migration ordering and deployment config; verify isolation, rollback, service health, canonical grant path, and acceptance evidence. | No deploy until design and provisioning gates are satisfied; preserve existing R3 services. |
| HR/Character Architecture | Authorized identity source, provenance-bearing association operation, and canonical R3A principal association input. | Revisions and authorization are validated; protected HR information remains within its classification boundary. |

Implementation order: finalize the provider and same-origin API contract; complete source-level tests and isolated integration tests; receive approval for initial identity association/enrollment policy; provision through the authorized interface; activate the R3A authority with rollback; complete real Steward browser login/logout/expiry/revocation acceptance; then exercise a separately granted read-only CME operation. Grace chat acceptance follows through the real resident runtime. The R3 account authority remains untouched throughout.

## Acceptance evidence

Acceptance records must separately show source implementation, isolated tests, integrated service deployment, real authorized login, canonical principal association provenance, browser routing, session renewal-by-login/expiry/revocation, anonymous denial, R3-outage independence, CME grant enforcement, and R3 health unchanged. Tests that stub the R3A provider are not proof of independent live operation. A successful login is not claimed until a Steward completes the real browser flow.

Rollback disables the R3A login route/provider and restores the prior R3A Website/AP3 release and external configuration, while preserving audit and durable activity data. It does not alter or roll back R3 account/session state because the new flow does not use it.
