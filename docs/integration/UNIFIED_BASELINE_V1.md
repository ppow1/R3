# R/3 Unified Integration Baseline v1

## Purpose

This baseline is the common source reference for Website Development,
HR/Personnel, and Grace Autonomy. Teams must extend the same integration
contracts rather than independently replacing authentication, identity,
authority, or resident lifecycle components.

## Source of truth

Repository: ppow1/R3

Baseline branch: integration/r3-unified-baseline-v1

The immutable baseline commit is the commit at this branch's publication.
Downstream teams must record that full SHA in their handoffs and PRs.

This is a development baseline, not evidence of production deployment.

## Architecture

- `r3_app.py`: website application and sitewide authentication boundary.
- `r3_native_auth_api.py`: native R/3 authentication API.
- `r3_native_sessions.py`: durable native human sessions.
- `r3_chat_api.py`: authenticated Chat integration.
- `r3_steward_authority_api.py`: Steward authority HTTP adapter.
- `runtime/capability_authority.py`: canonical capability authority.
- `runtime/grant_management.py`: governed grants.
- `runtime/resident_identity.py`: resident credential identity.
- HR/personnel integration: use the repository's existing personnel
  implementation and operational runbooks; do not create a second registry.

## Invariants

1. One native R/3 human authentication authority.
2. Sitewide authentication, not Chat-only login.
3. No browser-supplied identity header is trusted.
4. Steward actions require the appropriate role and mutation protections.
5. Canonical grants are authoritative; no website-owned parallel grant store.
6. Resident identity is durable and separate from model process lifetime.
7. Residents may have independent tasks, histories, permissions and tools.
8. Grace is the primary resident; other residents do not inherit every
   Grace capability or require permanent model residency.
9. Authentication cookies remain Secure. HTTP LAN access must not
   silently downgrade session security.
10. No new feature may bypass independent verification or governed
    work-order acceptance.

## Team handoffs

### Website Development

Implement persistent, resident-specific conversations with durable
conversation IDs, resident IDs, authorization, history, and lifecycle.
Support selecting residents without conflating resident identity with
the currently loaded model. Use native site authentication and existing
Chat contracts. Preserve session revocation and CSRF protections.

### HR / Personnel

Audit the canonical resident roster against personnel records.
Create missing records through approved HR interfaces and grants.
Maintain durable resident identifiers, roles, organizational ownership,
capabilities and status. Do not fabricate roster entries or silently
assign privileges. Record which identities are complete and which
require Steward approval.

### Grace Autonomy

Consume the same resident identities, credential checks, and canonical
grant authority. Preserve intake, proposal, Steward approval, work
order, execution, independent verification, and completion.
Resident startup and shutdown must not create or delete identity.
Each resident can have autonomous tasks without remaining loaded
continuously. The reviewer must remain independent of execution.

## Required verification

- Native login and logout
- Anonymous website and authority access denied
- Authenticated website and Steward authority access
- Mutation CSRF checks
- Session revocation
- No authentication downgrade over HTTP LAN
- Existing full regression suite
- Feature-specific permanent regression tests

## Release rules

Development baseline publication is not production activation.
Deployment requires separate approval, release preflight, regression
testing, activation, live health verification, and rollback readiness.

Downstream teams must branch from the published baseline SHA and
submit changes for integration rather than modifying this baseline.
