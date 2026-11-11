# R3 Control Record

- Component: R3A AP3 Steward Access
- Contract: `r3a.steward-access.config.v1`
- Purpose: Historical legacy prototype binding to the R3 account portal and AP3 session gateway; not the independent R3A deployment configuration.
- Authority: Issue #49; coordinated integration with Issue #51.
- Security: Contains no credential or session material. It trusts only the loopback R3 account-session endpoint, requires the portal's `steward` role, keeps AP3 sessions in the configured durable store, and never accepts browser-supplied principal claims. The HTTP/Secure-cookie exception is limited to the explicitly configured LAN development origin while `public_exposure` remains false.
- Activation: Historical only. Do not use for new deployment. Independent R3A authentication requires the approved design and provisioning gate in `docs/architecture/R3A_AUTH_INDEPENDENCE_PLAN.md`.
- Date: 2026-11-08
- Status: Legacy regression fixture only; the R3 account-session provider is prohibited for independent R3A deployment. Its presence does not authorize new runtime coupling.
