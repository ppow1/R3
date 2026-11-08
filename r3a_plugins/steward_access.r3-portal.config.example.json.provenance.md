# R3 Control Record

- Component: R3A AP3 Steward Access
- Contract: `r3a.steward-access.config.v1`
- Purpose: Illustrate development binding to the already deployed R3 account portal and the shared AP3 session gateway.
- Authority: Issue #49; coordinated integration with Issue #51.
- Security: Contains no credential or session material. It trusts only the loopback R3 account-session endpoint, requires the portal's `steward` role, keeps AP3 sessions in the configured durable store, and never accepts browser-supplied principal claims. The HTTP/Secure-cookie exception is limited to the explicitly configured LAN development origin while `public_exposure` remains false.
- Activation: Copy outside Git, set an operator-owned `R3A_STEWARD_DATABASE_DSN`, replace the LAN origin and CME socket with approved runtime values, and set `R3A_STEWARD_ACCESS_CONFIG` to the copy. Do not activate until the AP0 session migration/least-privilege grant and Website-owned service configuration are in place.
- Date: 2026-11-08
