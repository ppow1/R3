# R3A native Steward identity deployment and enrollment

This runbook describes the independent `r3a.identity-provider.v1` implementation. It does not operate or change any R3 account service. AP3 remains the only session and CME authorization path.

## Components and configuration

- `r3a_runtime/steward_identity.py`: independent account verification, identity association, governed enrollment/recovery, and account disable/revocation.
- `r3a_runtime/migrations/010_steward_identity.sql`: ordered after `009_steward_sessions.sql`; creates no default account.
- `r3a_plugins/steward_access.r3a-native.config.example.json`: external AP3 config; set the local R3A origin and keep `public_exposure` false.
- AP3 serves `GET /api/v1/steward/health`; `503` means the native identity or durable session store is unavailable. A healthy empty database does not imply that an account exists.
- `r3a-steward-identity`: local operator CLI for association, one-time challenge issuance, and disabling/revoking. Runtime and operator use separate peer-authenticated database roles.

For LAN HTTP only, use a private LAN IP origin, `Secure=false`, and a LAN-bound Website listener/firewall already managed by the Website owner. For HTTPS, use `Secure=true`. The native configuration loader rejects non-private origins and public exposure. This change does not open a firewall or restart a service.

## Database order and least privilege

Apply AP0 migrations in their established order, including `009_steward_sessions.sql` followed by `010_steward_identity.sql`, through the AP0 migration runner. Do not run migration SQL manually against a managed database. The database owner then applies `deploy/postgres/r3a-steward-auth-grants.sql` and configures local peer mappings. `r3a_steward_auth` is the AP3 runtime identity; `r3a_steward_identity_operator` is only for explicit account lifecycle operations. Neither role owns the schema, creates roles, or receives CME grant-management privileges. Supply `R3A_STEWARD_DATABASE_DSN` only to the AP3 process and `R3A_STEWARD_ADMIN_DSN` only to the local operator command.

The runtime can read account verification fields, update failed-login counters, invoke a constrained database function to consume an enrollment challenge and install a fresh verifier, manage AP3 session rows, and append institutional events. It cannot create identity associations or change account state to disabled/revoked. The operator role can associate, issue challenges, and invoke a constrained disable/revoke function; state revocation updates every active session atomically. Keep both DSNs in local service configuration, not JSON, Git, shell history, or logs.

## Identity association and enrollment

The approved process accepts only non-secret metadata: stable R3 subject ID, active/verified state, Steward eligibility, source revision, plus the HR/Character Architecture subject reference and revision. Do not export password hashes, login cookies, session records, MFA seeds, reset tokens, or recovery material. No R3 account data has been imported by this implementation.

Before `associate`, the accountable R3 identity owner and HR/Character Architecture owner must provide the approved source evidence through their authorized read interfaces. The exact R3 read endpoint/export mechanism and named approval reference remain an operational handoff to the owners; the software does not guess an endpoint or read the R3 database. The Steward-approved record must bind the R3 source subject/revision, HR source/reference/revision, approval actor/reference, and a unique association operation ID. Conflicting, inactive, unverified, ineligible, duplicate, or stale records are rejected. The input file must be mode 0600 and is not copied into the website. The database retains the allowed provenance and emits an append-only association event.

After the association is reviewed, run `r3a-steward-identity associate --record /secure/path/association.json`. It creates only a `pending_enrollment` principal. Then issue a single-use challenge with `r3a-steward-identity challenge --principal-id <id> --actor <operator> --purpose initial_enrollment`. The challenge is displayed once and must be delivered directly through the approved Steward-controlled out-of-band channel; never put it in chat, an issue, or logs. The Steward opens the R3A Website, selects enrollment, and chooses a fresh password of at least 14 characters. The challenge expires after at most 60 minutes, is stored only as a digest, and is consumed atomically with credential enrollment. The resulting principal gets no CME grants.

For recovery, use `--purpose credential_recovery`; the challenge can be issued only for an active associated identity. The same browser flow sets a new credential, consumes the challenge, and revokes prior active challenges. For suspected account compromise, use the audited `disable` or `disable --revoke` command; all current sessions are revoked. Recovery or account state actions require the accountable operator and out-of-band human verification.

## Website contract

`POST /api/v1/steward/session` uses the existing exact Origin allowlist and accepts one bounded JSON request:

```json
{"intent":"login","login_name":"…","password":"…"}
```

or for the governed first enrollment/recovery flow:

```json
{"intent":"enroll","login_name":"…","password":"…","challenge":"…"}
```

Successful calls return the existing `r3a.steward-session.v1` projection and set `r3a_steward_session`; the cookie token is never returned in JSON. `GET /session`, `DELETE /session`, Website protected routes, and generic `/operations/invoke` all use the same AP3 session rows and CME authorization path. Do not create a second browser token, redirect to R3, trust client-supplied principal or grants, or add per-capability routes. On login success, remain on this R3A origin and return to `/steward`.

## Rollout and rollback

Coordinator #56 owns migration application, role/socket provisioning, and managed AP3/Website activation. Website #51 owns its process and login presentation. Verify the deployed source/config revision and `/health` before inviting the Steward. Do not restart or alter existing R3 authentication services. If rollback is needed, disable the R3A auth config/router and restore the prior R3A Website/AP3 revision; retain identity, session, and append-only audit records for controlled review. No R3 account/session state is changed by either rollout or rollback.

## Current evidence boundary

Source and simulated regression coverage do not prove deployment, an imported identity association, or browser authentication. Interactive enrollment remains a Steward-operated step after the source owners provide the exact permitted metadata interface and the Coordinator activates migration/roles/config. No credential or account is fabricated while waiting for those owner-operated actions.
