<!--
R3 CONTROLLED DOCUMENT
File: r3a_plugins/steward_access.config.example.json
Component: R3A-AP3-STEWARD-ACCESS
File Revision: 1.0.5
Created: 2026-11-07T21:37:42Z
Created By: Codex GPT-6
Purpose: Document non-operational R3A-owned configuration placeholders for optional Steward identity, session, CME, and remote transport wiring.
Execution Model: Loaded only when R3A_STEWARD_ACCESS_CONFIG points to an operator-owned copy.
Observability: Effective session and ingress states are exposed without secret values.
Dependencies: r3a.steward-access.config.v1; r3a.secrets.provider.v1 from Issue #50.
Authority: AP3-M1 Issue #49; no public exposure by default.
Changed: 2026-11-07T21:37:42Z | AP3-M1 | Codex GPT-6 | Add safe example with placeholders and remote ingress disabled.
Changed: 2026-11-07T22:00:10Z | AP3-M1 | Codex GPT-6 | Use Issue #50's Bitwarden SecretReference and explicit AP0 freshness threshold.
Changed: 2026-11-07T22:02:18Z | AP3-M1 | Codex GPT-6 | Document external database timeout behavior.
Changed: 2026-11-07T23:53:17Z | AP3-M1 | Codex GPT-6 | Align assertion SecretReference with Bitwarden provider version 1.1.0.
Changed: 2026-11-09T16:32:39Z | R3A-AUTH-INDEPENDENCE-001 | Codex GPT-6 | Reserve the R3A session-cookie namespace in the external configuration example.
Supersedes: None.
Contracts: r3a.steward-access.config.v1; r3a.secrets.provider.v1; r3a.machine-principal.v1.
Tests: Config validation tests in tests/test_r3a_steward_access.py.
History/Predecessor: New file; initial publication recorded in Git.
-->
The example values are non-operational placeholders. The canonical principal must be established through the approved R3A identity-association procedure; do not copy an identity literal from this example. No R3 portal endpoint is used by this configuration. Before any activation, the R3A identity authority, enrollment procedure, principal association, and grants must be approved and provisioned. The ingress signing key must be provisioned through Issue #50's approved Bitwarden contract, and a trusted ingress must strip client-supplied `X-R3-Identity-*` headers before adding a signed assertion. Set `health_stale_after_seconds` to the effective AP0 heartbeat freshness threshold. `connect_timeout_seconds` is an externally adjustable connection acquisition timeout. Do not enable public exposure or configure remote transport until approved encrypted ingress is deployed and verified.
