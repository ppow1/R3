<!--
R3 CONTROLLED DOCUMENT
File: r3a_plugins/steward_access.config.example.json
Component: R3A-AP3-STEWARD-ACCESS
File Revision: 1.0.3
Created: 2026-11-07T21:37:42Z
Created By: Codex GPT-6
Purpose: Document externally owned configuration for optional Steward identity, session, CME, and remote transport wiring.
Execution Model: Loaded only when R3A_STEWARD_ACCESS_CONFIG points to an operator-owned copy.
Observability: Effective session and ingress states are exposed without secret values.
Dependencies: r3a.steward-access.config.v1; r3a.secrets.provider.v1 from Issue #50.
Authority: AP3-M1 Issue #49; no public exposure by default.
Changed: 2026-11-07T21:37:42Z | AP3-M1 | Codex GPT-6 | Add safe example with placeholders and remote ingress disabled.
Changed: 2026-11-07T22:00:10Z | AP3-M1 | Codex GPT-6 | Use Issue #50's Bitwarden SecretReference and explicit AP0 freshness threshold.
Changed: 2026-11-07T22:02:18Z | AP3-M1 | Codex GPT-6 | Document external database timeout behavior.
Supersedes: None.
Contracts: r3a.steward-access.config.v1; r3a.secrets.provider.v1; r3a.machine-principal.v1.
Tests: Config validation tests in tests/test_r3a_steward_access.py.
History/Predecessor: New file; initial publication recorded in Git.
-->
The example values are non-operational placeholders. Operators must configure the issuer and stable Steward principal from their existing identity authority, provision the referenced signing key in Bitwarden, place Issue #50's manifest/provider config at the configured paths, provision a least-privilege PostgreSQL role for the R3A session and event tables, and install a trusted ingress that strips client-supplied `X-R3-Identity-*` headers before adding a signed assertion. Set `health_stale_after_seconds` to the effective AP0 heartbeat freshness threshold. `connect_timeout_seconds` is an externally adjustable connection acquisition timeout; choose it to match the deployment's database/network behavior. Copy the example outside the repository and set `R3A_STEWARD_ACCESS_CONFIG` to that copy. Do not enable public exposure or set the transport state to configured until an authenticated encrypted ingress is actually configured and observed.
