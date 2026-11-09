# Provenance

- Component: R3A AP3 native Steward authentication.
- Source: R3A Authentication Independence Plan approved by the Steward; Issue #49 implementation.
- Contract: `r3a.steward-access.config.v1`, `r3a.identity-provider.v1`.
- Purpose: Example only. It contains no credentials, identity record, session token, or database DSN.
- Deployment: non-operational target uses dedicated `https://r3a.riverview.home.arpa`; provision private DNS/route and a browser-trusted certificate before use. Coordinator/Website must copy to external configuration, use the least-privilege local socket role, and preserve `public_exposure: false`.
