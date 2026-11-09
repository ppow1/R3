# Provenance

- Component: R3A AP3 native Steward authentication.
- Source: R3A Authentication Independence Plan approved by the Steward; Issue #49 implementation.
- Contract: `r3a.steward-access.config.v1`, `r3a.identity-provider.v1`.
- Purpose: Example only. It contains no credentials, identity record, session token, or database DSN.
- Deployment: Coordinator/Website must copy to external configuration, set the actual LAN origin, use the least-privilege local socket role, and preserve `public_exposure: false`.
