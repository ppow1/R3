<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_OCTOMINER_TELEMETRY_RELEASE_2_1_1.md
Component: R3A-OCTOMINER-TELEMETRY-V2.1.1-RELEASE-EVIDENCE
File Revision: 1.0.0
Created: 2026-11-11T19:28:00Z
Created By: Codex GPT-6
Purpose: Record exact deterministic v2.1.1 provider artifact, portability and isolated install/rollback evidence.
Execution Model: Source package builder, git autocrlf checkout regression and local disposable extraction.
Observability: SHA-256, release inventory, standard loader result, previous-version retention and fail-closed tamper rejection.
Dependencies: scripts/package_octominer_telemetry.py; OctoMiner v2.1 manifests and pinned provider files.
Authority: AD-024; #46 Planned Step 98. No runtime activation, authorization or production deployment.
Changed: 2026-11-11T19:28:00Z | R3A-MODULAR-PLUGINS-STEP-98 | Codex GPT-6 | Record immutable telemetry package evidence and limits.
Supersedes: None.
Contracts: r3a.module-release-package.v1; capability-provider.v1; infrastructure.octominer.telemetry.read.
Tests: tests/test_r3a_telemetry_target_scope.py; tests/test_r3a_octominer_release_package.py.
History/Predecessor: Supplements v2.1.0/v2.1.1 manifest provenance and Step 70 target-scope correction.
-->
# OctoMiner Telemetry v2.1.1 package evidence

## Immutable artifact

- Builder: `scripts/package_octominer_telemetry.py --version 2.1.1 --output artifacts/r3a-octominer-telemetry-2.1.1.tar.gz`
- Archive SHA-256: `d613e73c7d37350a7fc5baae850b6ab63e9acdad4b2f588949ac69293b10e25a`
- Checksum sidecar: `artifacts/r3a-octominer-telemetry-2.1.1.tar.gz.sha256`
- Package source parent: `b3af02882c6bf125d51a87e0c7a55f9ecff2653b`
- The package contains the immutable v2.1.1 operation manifest and all seven primary/supporting artifacts. Each payload's path, size and SHA-256 appears in `RELEASE_MANIFEST.json`.

The v2.1.1 operation still requires the existing `infrastructure.octominer.telemetry.read` grant and now requires nonempty `host_ids` and `source_ids`. Empty target, absent context and malformed scopes still fail closed before collectors. The v2.1.0 manifest and seven pinned files were not changed.

## Verification

- A disposable clone with Git `core.autocrlf=true` preserves every declared file hash in both v2.1 manifests. The test also feeds the v2.1.1 package through `r3a_runtime.config.load_settings` and the normal capability registry loader.
- The deterministic archive test rebuilds v2.1.0 and v2.1.1 twice and compares byte-for-byte output. It extracts and verifies inventories, loads both versions, corrupts the v2.1.1 candidate, confirms the standard loader rejects it, and confirms the previously staged v2.1.0 remains usable.
- Focused target/package/provider/module/lifecycle tests: **122 passed, 2 skipped**.
- Full repository suite: **482 passed, 10 skipped, 1 failed**. The one failure remains the unrelated, unchanged Notification Service artifact hash mismatch (`107ea3b458…` expected; `8f658460…` actual).

This evidence is from disposable local artifacts and source loaders. It does not establish a CME lifecycle transition, live authorization, host telemetry read, service restart, production installation, or activation. The empty target received from the current CME path remains denied until Coordinator supplies an authoritative validated scope.
