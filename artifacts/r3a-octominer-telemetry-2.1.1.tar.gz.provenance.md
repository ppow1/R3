<!--
R3 CONTROLLED DOCUMENT
File: artifacts/r3a-octominer-telemetry-2.1.1.tar.gz.provenance.md
Component: ARTIFACT-R3A-OCTOMINER-TELEMETRY-2.1.1
File Revision: 1.0.0
Created: 2026-11-11T19:28:00Z
Created By: Codex GPT-6
Purpose: Bind the immutable telemetry package artifact to its builder, manifest and exact SHA-256.
Execution Model: Deterministic tar.gz package; inactive source candidate.
Observability: SHA-256 sidecar and release manifest inventory.
Dependencies: scripts/package_octominer_telemetry.py; v2.1.1 manifest and seven pinned payload files.
Authority: AD-024; Modular Plugins #46 Step 98. No grant, authorization or activation.
Changed: 2026-11-11T19:28:00Z | R3A-MODULAR-PLUGINS-STEP-98 | Codex GPT-6 | Publish package artifact provenance.
Supersedes: None.
Contracts: r3a.module-release-package.v1; infrastructure.octominer.telemetry.read.
Tests: tests/test_r3a_octominer_release_package.py.
History/Predecessor: Deterministic package built from the pinned source candidate.
-->
# Telemetry v2.1.1 archive provenance

Archive: `r3a-octominer-telemetry-2.1.1.tar.gz`

SHA-256: `d613e73c7d37350a7fc5baae850b6ab63e9acdad4b2f588949ac69293b10e25a`

Builder: `scripts/package_octominer_telemetry.py`

Release evidence: `docs/architecture/R3A_OCTOMINER_TELEMETRY_RELEASE_2_1_1.md`

The archive is deterministic, externally digest-pinned in its `.sha256` sidecar, and is not installed into or activated by a shared CME service.
