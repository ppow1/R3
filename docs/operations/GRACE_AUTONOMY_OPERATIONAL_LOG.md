# Grace Autonomy Operational Log

## 2026-11-06 — Proposal grant expiration safeguard

**Operational warning:** Grace's proposal-draft submission and status-read permissions are authorized as temporary seven-day, non-delegable grants. Expiration can disable proposal operations while the rest of the autonomy runtime remains healthy. This is a temporary operational limitation, not a permanent architectural requirement.

No grant was issued by this work session. Grant IDs, issuance timestamps, and exact expiration timestamps therefore remain **pending authenticated Steward approval**; none are inferred or fabricated. When issued, record each R/3 and institutional-registry grant in [the Grace Autonomy runbook](../runbooks/GRACE_AUTONOMY_OPERATIONS.md), including principal, resource, action, scope, operation, grant ID, issue time, exact expiration time, and Steward renewal path.

The additive R/3 broker change provides a resident-authenticated `/v1/diagnostics/authorization` response, an hourly read-only warning beginning by the 50-hour threshold (normally at least 49 hours before expiration), and an `AUTHORIZATION_EXPIRED` response with the grant identifier and explicit renewal action. The monitor does not change grants. A new exact seven-day request and Steward approval are required for renewal. Expired proposal permissions stop submission/read operations; they do not represent completion or a generic service failure.

**Current activation state:** Riverview proposal endpoint active; native broker with expiry safeguards staged but not activated; identity association and production grants not verified active; live model-driven Grace assignment not run.

The additive staged broker now also exposes `hr.associate_principal` with a scope bound to HR record `r3:grace`, the authenticated R/3 principal, and the exact institutional principal. Proposal submission resolves the institutional principal from the confidential HR crosswalk; there is no alias or case-folding fallback. The isolated composed-broker acceptance wrote HR revision 1 to revision 2, retried idempotently, then durably submitted and read back a DRAFT proposal under `resident:grace`. This used temporary test databases and test-only grants; production identity, grants, and resident credentials were not changed.
