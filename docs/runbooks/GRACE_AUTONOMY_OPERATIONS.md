# Grace Autonomy Operations

## Temporary proposal grant expiration — action required

**The proposal permissions authorized for Grace are temporary seven-day grants. They expire seven days after the individual grant's issuance timestamp. Expiration can stop proposal submission or readback even when the broker and institutional registry are healthy. This is a temporary operational limitation, not a permanent architectural requirement.**

No grant identifiers or issue/expiry timestamps are recorded yet because no production grants have been issued in the verified authority stores. Do not fill these fields from estimates. Copy them from each authoritative grant record immediately after the authenticated Steward approval succeeds.

| Grant ID | Authorized principal | Resource | Action | Scope | Operation | Issued at (UTC) | Expires at (UTC) | Renewal authority |
|---|---|---|---|---|---|---|---|---|
| Pending issuance | `resident:Grace` (R/3 authority) | `riverview:institutional-proposals` | `proposal.draft.submit` | `institution:proposal-drafts` | `write` | Pending | Pending | Steward, through authenticated R/3 grant request/decision |
| Pending issuance | `resident:Grace` (R/3 authority) | `riverview:institutional-proposals` | `proposal.status.read` | `institution:proposal-drafts` | `read` | Pending | Pending | Steward, through authenticated R/3 grant request/decision |
| Pending issuance | `resident:grace` (institutional registry) | `riverview:institutional-proposals` | `proposal.draft.submit` | `institution:proposal-drafts` | `write` | Pending | Pending | Steward, through the registry's authenticated exact-grant approval |
| Pending issuance | `resident:grace` (institutional registry) | `riverview:institutional-proposals` | `proposal.status.read` | `institution:proposal-drafts` | `read` | Pending | Pending | Steward, through the registry's authenticated exact-grant approval |

All four grants must remain exact, non-delegable, and limited to seven days. Renewal requires a new exact request and authenticated Steward approval. **Never silently renew or extend a grant.** The broker's authorized resident diagnostic is `GET /v1/diagnostics/authorization` with Grace's existing bearer credential. It lists only the authenticated resident's two exact R/3 proposal grants and marks grants inside a 50-hour visibility window as `EXPIRING_SOON`. The monitor scans hourly and begins warning by the 50-hour threshold, so its normal polling delay still leaves at least 49 hours before expiration. It emits a warning with grant ID, principal, resource, action, scope, operation, issue time, expiration time, and renewal action.

After expiration, proposal calls must stop with `AUTHORIZATION_EXPIRED`, identify the expired grant, and instruct the operator to request a new exact grant through Steward approval. This is an authorization lifecycle event, not a generic autonomy or service-health failure. Do not retry indefinitely. Institutional-registry grants remain governed by the registry's own authority records; record their grant IDs and exact times in the table above as well.

## Deployment handoff

- The expiry monitor and authenticated diagnostic are included in the additive native broker release, alongside the existing HR and operational tools.
- These additions do not issue, extend, or approve grants.
- Before live Grace acceptance, confirm the four exact grants are active and record each grant's issue and expiry timestamps above and in the operational evidence log.
- If any required grant is missing or expired, leave the website-clock proposal unsubmitted and escalate the exact grant ID and renewal request to the Steward.
- Proposal approval and Engineering execution remain Steward-controlled.
