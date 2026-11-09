<!--
R3 CONTROLLED DOCUMENT
File: docs/runbooks/R3A_AP3_STEWARD_ENROLLMENT_AND_ACCEPTANCE.md
Component: R3A-AP3-AUTH-INDEPENDENCE
File Revision: 1.0.1
Created: 2026-11-09T17:04:07Z
Created By: Codex GPT-6
Purpose: Guide controlled first-Steward association, independent credential enrollment, deployment verification, and browser acceptance.
Execution Model: Operator-guided; Steward performs credential enrollment directly in the R3A Website.
Observability: Release SHA, service health, association operation reference, session/audit references, and acceptance results; never credentials or tokens.
Dependencies: Approved R3A Authentication Independence Plan; AP3/R3A-010; Remote Access #49 and Website #51 versioned contracts.
Authority: Steward approval — R3A Independent Authentication Approval, 2026-11-09; LAN-only operation.
Changed: 2026-11-09T17:04:07Z | R3A-AUTH-INDEPENDENCE-APPROVED | Codex GPT-6 | Prepare the Steward-controlled enrollment and deployment acceptance procedure.
Changed: 2026-11-09T17:54:09Z | R3A-AUTH-COOKIE-ISOLATION | Codex GPT-6 | Require a dedicated private-LAN hostname and browser-trusted TLS certificate before enrollment.
Supersedes: None.
Contracts: r3a.identity-provider.v1; r3a.steward-principal.v1; r3a.steward-session.v1; canonical HR/R3A association contract when published.
Tests: Procedure only; native authority and browser acceptance are pending implementation.
History/Predecessor: New file; initial publication recorded in Git.
-->
# AP3 first Steward enrollment and acceptance

This runbook is for the first independent R3A Steward account. It is not permission to create credentials without the Steward present. Use `https://192.168.1.155:8311` with the installed certificate whose IP SAN is `192.168.1.155`, trusted by the Steward's browser, and the existing private LAN route. No custom DNS is required. Cookies are host-scoped rather than port-scoped, so the R3A cookie is Secure, HttpOnly, SameSite=Strict, host-only, and restricted to `/api/v1/steward`. Do not use the legacy R3 login flow or its cookies.

## Preconditions

- A versioned R3A auth provider and Website release have passed focused and integration tests and are deployed through the controlled release process.
- The provider, Website, and CME use one canonical R3A principal/session contract. The R3 account adapter is disabled and configuration validation rejects it for this deployment.
- PostgreSQL migrations are additive, checksummed, backed up, and applied with the R3A migration identity. The account/session role has only the minimum table and column rights. No R3 database is queried by the R3A runtime.
- The R3A login origin is the browser-trusted private-LAN IP URL `https://192.168.1.155:8311`. The installed certificate has the matching IP SAN. The cookie is host-only, `r3a_steward_session`, `Secure`, `HttpOnly`, `SameSite=Strict`, and scoped to `/api/v1/steward`.
- An owner-authorized read interface is confirmed for the one-time R3 account metadata lookup. Its allowlisted fields are limited to stable subject ID, active/verified state, Steward eligibility, source revision, and provenance. Password hashes, sessions, factors, reset data, and recovery material are excluded.
- The HR authority has verified the canonical Steward identity, and CME grants are provisioned separately through the canonical R3A grant authority. Email match alone is insufficient.
- The Steward is present and controls the browser and chosen R3A credentials. Enrollment/recovery instructions are delivered through the approved channel; no credential or one-time token is placed in logs, issue comments, terminal history, or model context.

If any precondition is missing, stop account activation and record the specific owner/action. Continue unrelated R3A work.

## Private first-enrollment procedure

The Website login is one institutional entry point. When the approved association and pending R3A principal exist, the local identity operator issues one short-lived challenge and delivers it directly to the Steward. The challenge and new password must never be pasted into GitHub, chat, a ticket, a command argument, or an application log.

1. The accountable HR and R3 identity owners complete the approved non-secret, revision-checked association through their authorized interfaces. The operator writes the association evidence to a local access-controlled file with permissions `0600`; it contains no credentials or protected HR fields.
2. In a private local operator terminal, record the association with `r3a-steward-identity associate --record /secure/path/association.json`. Confirm only the returned state and association operation reference. Remove the local evidence file according to the source owners' retention rule.
3. Issue the single-use challenge with `r3a-steward-identity challenge --principal-id <verified-r3a-principal> --actor <verified-operator> --purpose initial_enrollment`. The token appears once in that private terminal. Deliver it directly through the approved Steward-controlled out-of-band channel; do not capture terminal output in logs or shell history.
4. The Steward opens `https://192.168.1.155:8311/login`, selects the first-enrollment option, enters the challenge and a fresh R3A password directly in the browser, and submits. The page remains on the R3A origin and opens the complete Website after the native session is established.
5. The Steward confirms navigation among Website modules, resident chat inheritance of the same session, and the single Website sign-out. The operator verifies only non-secret principal/session state and safe audit references. Login creates no CME grants.

The association input and challenge must not be created until source identity, revision, eligibility, and actor provenance are verified. At the current checkpoint those authoritative association inputs are still missing, so there is no pending principal or challenge to deliver. Once they are supplied through the authorized HR/R3 path, the steps above are directly executable without another architecture decision.

## Association and enrollment

1. Record the pre-deployment source/runtime SHAs, service identities, health results, and rollback target. Confirm existing R3/R2/V2 health without changing them.
2. Through the authorized, audited source interface, read only the approved non-secret R3 account metadata. Capture the source identifier and revision in the access-controlled association audit record. Do not put the identifier itself in general logs or GitHub; reference the association operation ID in coordination reports.
3. Resolve the same person through the authenticated HR read interface and verify the canonical identity and Steward eligibility. Do not use email equality as proof.
4. Have the authorized Steward/operator invoke the versioned, revision-checked association operation linking HR identity and prior R3 subject provenance to the new R3A principal. Require uniqueness, active source state, idempotency, and a durable audit reference. No ongoing R3 synchronization is created.
5. Start enrollment from the R3A login page. The R3A authority issues a short-lived, single-use enrollment challenge through the approved channel. The Steward sets a fresh R3A credential directly in the R3A browser flow. The service stores only a reviewed password verifier and audit metadata.
6. Activate privileged login only after association verification and completed Steward-controlled enrollment. Login establishes identity, not grants. Independently verify the approved read-only CME grants for that principal.

## Live acceptance

Record pass/fail and non-secret references for each step:

1. **R3A login and routing:** open the trusted LAN HTTPS R3A origin, complete sign-in, and remain on R3A after redirect. No R3 portal navigation or cookie is involved.
2. **Canonical identity:** session response returns the expected R3A principal and approved issuer. Never record the credential, session cookie value, challenge token, or recovery secret.
3. **Cookie isolation:** browser shows only the R3A host cookie `r3a_steward_session` for R3A; attributes are `Secure`, `HttpOnly`, `SameSite=Strict`, and `Path=/api/v1`. R3 cookies and behavior remain unchanged.
4. **Persistence:** reload the browser page and verify the session and session-backed conversations/status persist. Restart only the R3A auth/Website unit under the release procedure and verify the session state matches durable PostgreSQL records.
5. **Logout/revocation/expiry:** log out, verify the cookie is cleared and the server-side session is revoked; test expiry and administrative revocation using isolated test accounts/short TTLs. Subsequent requests must return 401 and produce safe audit evidence.
6. **Authorization:** invoke one separately granted, read-only CME operation. Verify caller identity is derived server-side and CME enforces its existing grant. Test an ungranted operation and require 403; login must not grant it.
7. **Independence:** automated integration test runs the R3A auth provider with R3 endpoints unavailable or outbound access denied and verifies successful R3A account/session validation. Do not stop production R3 services for this test. Inspect test egress and service dependencies to confirm no R3 endpoint is configured.
8. **Isolation and continuity:** verify anonymous Website/API requests return 401, invalid origins are rejected, session tokens are absent from logs/events, and existing R3/R2/V2 health and behavior remain unchanged.

Browser acceptance must be performed by the Steward. Automated tests and service health do not substitute for the real enrollment and login.

## Rollback

Retain the previously verified R3A Website/AP3 release, external configuration revision, and database backup. On failed health, isolation, or security checks, disable only the new R3A auth/login route and restore the prior R3A service release/configuration. Preserve audit and session records for investigation; do not remove identity evidence or reset R3/R2/V2 data. Verify the old R3A service state and all existing R3/R2/V2 services. Document rollback SHA and outcome.
