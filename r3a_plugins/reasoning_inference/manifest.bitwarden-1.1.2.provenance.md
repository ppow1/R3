<!--
R3 CONTROLLED DOCUMENT
File: r3a_plugins/reasoning_inference/manifest.bitwarden-1.1.2.provenance.md
Component: R3A-AP3-M2-VERSIONED-INFERENCE-MANIFEST
File Revision: 1.0.0
Created: 2026-11-09 UTC
Created By: R3A Coordinator
Purpose: Record the provenance and immutable artifact binding for optional Bitwarden-backed reasoning inference.
Execution Model: Side-by-side provider package; external configuration selects whether it is loaded.
Observability: Manifest artifact digest and focused synthetic integration tests.
Dependencies: r3a.secrets.provider.v1@1.1.0; CME authorization; versioned reasoning-inference provider.
Authority: AP3-M2 Issues #49/#50; no credentials or live activation included.
Changed: 2026-11-09 | R3A-UNIFIED-009 | Preserve existing reasoning-inference 1.0.0 while staging secret-reference consumer 1.1.2.
Supersedes: None.
Contracts: r3a.capability-operation.v1; r3a.module-manifest.v1; r3a.secrets.provider.v1@1.1.0.
Tests: tests/test_r3a_bitwarden_consumer_integration.py; tests/test_r3a_bitwarden_secrets.py.
History/Predecessor: Workstream source `engineering/r3a-ap3-bitwarden-20261107` commit `ce05b7307f203e0b37e5857228149c56e9353ae4`.
-->
# Optional Bitwarden-backed reasoning inference 1.1.2

The sidecar manifest pins `plugin_bitwarden_v1_1_2.py` at SHA-256
`cb4931e2e7b5c48cc764cecb2e4ff2096a47758cd55a3b516d07af97c237a0e4`.
It is separately configured and does not replace the existing
`reasoning_inference/manifest.json` 1.0.0 provider or the managed model route.

The provider resolves a configured secret reference only inside the CME-authorized
provider invocation, uses the lease value as an outbound HTTP authorization header,
closes the lease, and redacts echoed credential material before returning evidence.
The config example contains placeholders only. No `bws` credential, secret value,
secret reference, or external provider config is included in this repository.

This source has isolated synthetic tests only. Managed activation and live retrieval
require the authorized machine-account configuration and an explicit external
provider binding; this manifest is not selected by the managed bootstrap.
