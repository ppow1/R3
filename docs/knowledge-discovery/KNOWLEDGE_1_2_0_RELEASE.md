<!--
R3 CONTROLLED DOCUMENT
File: docs/knowledge-discovery/KNOWLEDGE_1_2_0_RELEASE.md
Component: R3A-KNOWLEDGE-1.2.0-RELEASE
File Revision: 1.0.0
Created: 2026-11-08 UTC (exact time recorded in Git commit)
Created By: Codex GPT-6
Purpose: Specify the independently staged Knowledge 1.2.0 module package and compatibility boundaries.
Execution Model: Deterministic package build and isolated module staging; no production activation.
Observability: Release manifest, per-file SHA-256 values, and archive checksum.
Dependencies: R3A module manifest v1; capability provider v1; generic Steward operation contract v1.1.0.
Authority: Issues #43/#46/#47/#56; module release does not itself authorize activation.
Changed: 2026-11-08 | AP1-K2 | Codex GPT-6 | Publish separately staged 1.2.0 release instructions.
Supersedes: None.
Contracts: institution.knowledge.read@1.1.0; proposal list/decide@1.0.0; capability contract v1.1.0.
Tests: tests/test_knowledge_module_package.py.
History/Predecessor: New file; initial publication recorded in Git.
-->
# Institutional Knowledge module 1.2.0

## Package identity

The build creates `artifacts/r3a.institutional-knowledge-1.2.0.tar.gz` and its `.sha256` sidecar. The archive carries plugin and review-store hashes pinned by three operation manifests, the governed Knowledge migration, the Website review API contract, and a release manifest with per-file digests. Its provider ID remains `r3a.institutional-knowledge` at version `1.2.0`.

The package uses the unique import root `r3a_plugins.institutional_knowledge_v1_2_0`. Its manifests point to that module path. This allows the host to stage the new source beside the existing `r3a_plugins.institutional_knowledge` 1.1.0 path without overwriting that directory. The bundle carries version/protocol identity in `RELEASE_MANIFEST.json` and uses canonical operation manifests without the optional `module_manifest` extension, which the current deployed Coordinator loader rejects. The host runtime supplies `r3a.capability-provider.v1` and psycopg 3.

## Build and verify

```sh
python3 scripts/package_knowledge_module.py
sha256sum -c artifacts/r3a.institutional-knowledge-1.2.0.tar.gz.sha256
tar -tzf artifacts/r3a.institutional-knowledge-1.2.0.tar.gz
```

For a non-managed isolated smoke test, extract into a disposable copy of the R3A runtime root, reference the bundled `manifest.read.json`, and confirm provider discovery/activation and one deterministic read. The proposal manifests use the agreed generic `steward_read` and `steward_write` effects at capability contract 1.1.0; their grants must be separately present in that isolated database. Verify the CME operation audit, source digest, citations, and returned provider identity. Test the 1.1 read package independently before the 1.2 test and verify its original manifest/artifact digest remains unchanged.

## Compatibility and activation boundary

Provider 1.2.0 retains `institution.knowledge.read`, operation revision 1.1.0, operation contract 1.0.0, existing input/output schemas, and the same Grace read grant. The two proposal operations are additive and use generic Steward contracts. Unit coverage already exercises provider 1.2.0 through the existing read contract and checks 1.1 read compatibility; package tests validate the versioned manifests, separate import path, contract effects, and package digests.

Packaging is not managed activation evidence. The latest Coordinator status reports its current config loader rejects manifests that include the optional `module_manifest` key; the bundle omits that extension and preserves the canonical operation descriptors, but this needs an isolated Coordinator-loader integration test before activation. Do not point the managed bootstrap at the package or select provider 1.2.0 until the Coordinator has performed the isolated module activation and compatibility exercise, the required schema is applied, and shared read behavior remains verified. Keep the managed 1.1.0 configuration and source path intact until that acceptance is recorded. This release contains no production configuration, credentials, grants, or automatic service restart.
