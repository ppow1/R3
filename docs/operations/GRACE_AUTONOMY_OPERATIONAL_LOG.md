<!--
R3 CONTROLLED DOCUMENT
File: docs/operations/GRACE_AUTONOMY_OPERATIONAL_LOG.md
Component: R3-GRACE-AUTONOMY-OPERATIONAL-LOG
File Revision: 1.0.1
Created: 2026-11-06 UTC (exact time unknown)
Created By: Unknown (legacy)
Purpose: Record verified Grace autonomy operation state and limitations.
Execution Model: Append-only operational record by dated entry.
Observability: Source revisions, authority status, tests, and live outcomes.
Dependencies: R3 broker and institutional proposal registry.
Authority: Steward-directed operational record; no grants or approvals created here.
Changed: 2026-11-06T23:06:45Z | GRACE-AUTHORITY-ARCH-001 | Codex GPT-6 | Supersede the duplicate R3 proposal grant assumption.
Changed: 2026-11-06T23:58:00Z | GRACE-AUTHORITY-ARCH-002 | Codex GPT-6 | Correct the identity association writer boundary and record current read-only denial evidence.
Supersedes: None; adds a correction to the preceding operational entry.
Contracts: docs/architecture/RESIDENT_AUTHORITY_AND_CAPABILITIES.md.
Tests: Documentation review.
History/Predecessor: Git blob c985198f34d8dd3be942befb9cce369409d66a97 at cb162499a5ae94b801cbdbf9e5aa2dcd4c75ebaf.
-->
# Grace Autonomy Operational Log

## 2026-11-06 — Authority architecture correction

**Current rule:** Do not require duplicate R/3 exact proposal grants or seven-day terms merely because the staged adapter previously checked for them. Proposal authorization is delegated to the existing institutional registry after the R/3 resident identity is resolved through the authoritative HR crosswalk. Any institutional grant, classification restriction, or temporary exception remains governed by that authority's current policy. Record its exact identifier, scope, issue/expiry timestamps, renewal authority, and expired behavior only after readback from the owning system. No grant may be silently renewed or extended.

**Previous implementation record, superseded by this correction:** Earlier staged R/3 code included a proposal-specific grant diagnostic and seven-day grant assumption, with a 50-hour expiry warning and an `AUTHORIZATION_EXPIRED` response. No production grant was issued or verified by that work. Those R/3-local proposal grants are no longer an operational prerequisite. The monitoring implementation remains relevant only if R/3's own authority policy independently requires a temporary grant for an R/3-owned action; it does not govern the institutional proposal endpoint.

**Current activation state:** Riverview proposal endpoint active; native broker with expiry safeguards staged but not activated; identity association and production grants not verified active; live model-driven Grace assignment not run.

The additive staged broker exposes `hr.associate_principal` with a scope bound to one HR record and both exact identities. Proposal submission and readback resolve the institutional principal from the confidential HR crosswalk; there is no alias or case-folding fallback. Prior isolated composed-broker evidence used temporary databases and test-only grants; it is not a live model run and did not change production identity, grants, or resident credentials. The current production identity association and institutional policy decision remain unverified.

**Superseding correction (2026-11-06):** R/3 no longer stages a resident-facing `hr.associate_principal` writer that would require a separate R/3 grant. HR owns identity writes; R/3 consumes only the exact confidential crosswalk. A live HR read found `r3:grace` at revision 1 with no association. Read-only calls to Riverview's proposal status route using both available resident-token sources returned HTTP 403 `resident_proposal_not_authorized`. No identity, credential, grant, proposal, or website record was changed.
