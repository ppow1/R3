# Provenance

- Component: R3A AP3 native Steward authentication.
- Source: R3A Authentication Independence Plan approved by the Steward; Issue #49 implementation.
- Contract: `r3a.steward-access.config.v1`, `r3a.identity-provider.v1`.
- Purpose: Example only. It contains no credentials, identity record, session token, or database DSN.
- Deployment: approved LAN target is `https://192.168.1.155:8311`, using the existing certificate with IP SAN `192.168.1.155`; no custom DNS is required. Coordinator/Website copy to external configuration, use the least-privilege local socket role, and preserve `public_exposure: false`.
