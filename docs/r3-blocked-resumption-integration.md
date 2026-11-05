<!--
R3 CONTROLLED DOCUMENT
File: docs/r3-blocked-resumption-integration.md
Component: R3-GRACE-RECOVERY
File Revision: 1.0.0
Created: 2026-11-05 UTC (date only; exact time unverified)
Created By: ChatGPT GPT-6
Purpose: Contract and readiness state for authorized Grace blocked-work recovery
Execution Model: Documentation
Observability: GitHub commit, CI targeted regressions and persistent authority/inbox audit
Dependencies: runtime/blocked_recovery.py; runtime/assignment_intake.py
Authority: Steward R3 development governance and existing R3 canonical grant service
Changed: 2026-11-05 UTC | R3-GRACE-RECOVERY-006 | Document isolated integration and remaining production prerequisites
Supersedes: None
Superseded By: None
Contracts: hints/file-provenance.md; hints/development-governance.md
Tests: tests/test_blocked_recovery.py; tests/test_activity_continuation.py
History/Predecessor: New file; none
-->
# Authorized Grace blocked-work recovery — integration contract

**Status: SOURCE IMPLEMENTED; NOT DEPLOYED.** This source is separate from the active `grace-unified-50a2db0e64e98` release. It does not change the R3 website or running institutional service.

## Existing pieces

- `Inbox.resume_blocked` (Grace branch) records an idempotent successor for a `BLOCKED RESIDENT_ACTIVITY` and preserves the blocked event unchanged. A string `authority_ref` is evidence but is **not** authenticated authorization.
- `BlockedResumptionService` (this integration branch) requires a trusted identity verifier supplied by the institutional host and a provisioned `R3Authority` object. It verifies that the blocked event descends from the named assignment and that the *exact effective grant* authorizes the authenticated principal to resume that assignment for that resident.
- `AssignmentIntake.status` follows blocked-resumption successor references as well as ordinary continuation links, so status history includes a preserved `BLOCKED` event followed by the new `PENDING` successor.

## Exact grant and audit contract

The canonical R3 grant must match:

- `principal`: verified actor, e.g. `human:steward:<actual-id>` or `resident:<actual-id>`; never client-supplied identity text.
- `resource_ref`: `r3:assignment:<actual-assignment-id>`
- `action`: `resident.activity.resume`
- `operation`: `write`
- `scope_ref`: `resident:<actual-resident-name>`

The R3Authority verifier must find one effective, unrevoked, Steward-approved exact grant and valid delegation chain. Authorization is audit-recorded before the successor is written. No default grant is issued and missing authority fails closed. A named grant string in the payload is not sufficient.

The host must provide a verified principal derived from a trusted session or resident credential. This source **does not create an HTTP route**, does not accept a raw identity header or ordinary user text as proof, and does not automatically configure or provision authority.

## Remaining integration and deployment prerequisites

1. Bind `BlockedResumptionService` through the already authenticated institutional/website authority boundary; wire the correct canonical authority database and trusted identity verification, then expose only an approved bounded recovery operation. Do not add a public unauthenticated route or trust a browser-provided principal.
2. Agree explicit grant issuance and scope for the actor and assignment; avoid silently granting all residents blanket recovery authority.
3. Ensure the current durable institutional DB and active release are preserved; integrate this source with the currently approved Grace runtime baseline, not the separate website feature branch.
4. Run focused regression tests, then confirm one authorized resumption and one denied resumption through the actual entry point without bypassing existing independent review/acceptance gates.
5. Deploy with the verified Grace deployment lifecycle and essential smoke checks only when the authority binding and accepted release are ready.

**CI observation 2026-11-05:** The focused new `test_blocked_recovery` cases and prior activity-continuation tests passed in the branch's full-suite workflow logs. The full suite still reported 32 website-authentication tests failing with 503 responses; this does **not** constitute an overall CI pass or production acceptance. Diagnose those separately before relying on an all-green global gate.
