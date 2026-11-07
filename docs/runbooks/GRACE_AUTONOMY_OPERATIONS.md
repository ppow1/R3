<!--
R3 CONTROLLED DOCUMENT
File: docs/runbooks/GRACE_AUTONOMY_OPERATIONS.md
Component: R3-GRACE-AUTONOMY-OPERATIONS
File Revision: 1.0.0
Created: Unknown (legacy)
Created By: Unknown (legacy)
Purpose: Operate and verify Grace's authenticated autonomy workflow.
Execution Model: Human/operator reference; no automatic grants or deployment.
Observability: Authority decisions, identity crosswalk, durable proposal receipts, and workflow state.
Dependencies: R3 broker; authoritative HR identity contract; institutional proposal registry.
Authority: Steward directives; proposal approval and Engineering execution remain institutional decisions.
Changed: 2026-11-06T23:06:45Z | GRACE-AUTHORITY-ARCH-001 | Codex GPT-6 | Remove duplicate seven-day R3 proposal grant prerequisites.
Supersedes: Git predecessor's temporary-grant operational assumption.
Contracts: docs/architecture/RESIDENT_AUTHORITY_AND_CAPABILITIES.md; docs/r3-native-tool-contract.md.
Tests: Documentation review.
History/Predecessor: Git blob e2f767425484cd24233db6c1587d8acda3c6ac2b at cb162499a5ae94b801cbdbf9e5aa2dcd4c75ebaf.
-->
# Grace Autonomy Operations

## Proposal authorization source

**Do not provision duplicate R/3 proposal grants.** The prior implementation required separate local `proposal.draft.submit` and `proposal.status.read` grants in addition to the institutional registry's decision. The architecture correction removes that extra gate. The R/3 broker authenticates the resident, resolves the exact HR identity association, and delegates proposal authorization to Riverview's existing internal proposal registry.

The registry may still require an exact grant, active resident policy, or time-bounded exception under its own currently commissioned policy. Preserve its decision. If it denies or reports an expired institutional grant, record the identifier and exact expiry supplied by that authority and follow its authenticated Steward renewal process. Do not silently renew, extend, or invent an R/3-side substitute. If policy state cannot be read, treat it as unverified and stop that operation.

No production identity association or proposal grant was verified during the latest read-only check. Do not infer an active permission from the tool descriptor or this runbook. Proposal approval, promotion, work-order creation, and Engineering execution remain separate institutional decisions.

## Deployment handoff

- The additive broker preserves the existing HR and operational tools and registers the two proposal tools.
- The proposal tools carry the named institutional-registry authority source; they do not create or extend grants.
- Before live Grace acceptance, verify the confidential HR identity crosswalk and obtain a current decision from the institutional registry.
- If the registry denies or is unavailable, leave the proposal unsubmitted and report its exact response; do not bypass the denial.
- Proposal approval and Engineering execution remain Steward-controlled.

## R3-to-institutional identity crosswalk

The R/3 resident credential principal and Riverview institutional principal are separate identities. The broker must not lowercase, case-fold, or infer one from the other. The exact crosswalk is stored as confidential `r3_principal` and `authority_principal` extensions on the authoritative HR record. Proposal submission resolves the institutional principal from that record at invocation time.

R/3 only reads this association. It must not expose a second resident-facing HR mutation or require a new R/3 grant for an operation owned by HR. Establish or correct the confidential crosswalk through the existing authenticated HR write mechanism, using its current revision checks and audit. Preserve other HR fields, credentials, and grants. R/3 never infers the mapping, lowercases a principal, or treats tool registration as authority.
