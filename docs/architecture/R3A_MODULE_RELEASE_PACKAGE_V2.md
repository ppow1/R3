<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_MODULE_RELEASE_PACKAGE_V2.md
Component: R3A-MODULE-RELEASE-PACKAGE-V2
File Revision: 1.0.2
Created: 2026-11-11T19:02:40Z
Created By: Codex GPT-6
Purpose: Specify a generic immutable resident executor package and process-binding contract for Autonomy integration.
Execution Model: Versioned JSON release descriptor, local artifact staging, CME-constructed child process.
Observability: External bundle digest, manifest digest, artifact-tree digest, immutable path, lifecycle evidence from CME.
Dependencies: Existing module manifest/binding/registry/lifecycle, capability contract validator, AP0-M1 module protocol.
Authority: AD-024; Roadmap Baseline 1.0 AP0-007/008/009; Modular Plugins #46 Step 70/84. No production or frozen-core edits.
Changed: 2026-11-11T19:02:40Z | R3A-MODULAR-PLUGINS-STEP-70 | Codex GPT-6 | Publish package v2 and JSON-lines process-binding interface.
Changed: 2026-11-11T19:11:23Z | R3A-MODULAR-PLUGINS-STEP-84 | Codex GPT-6 | Document link-safe immutable staging and lifecycle-guarded cleanup.
Changed: 2026-11-11T19:32:00Z | R3A-MODULAR-PLUGINS-STEP-84 | Codex GPT-6 | Clarify the package-only versioned metadata boundary.
Supersedes: None; provider package v1 remains unchanged.
Contracts: r3a.module-release-package.v2@2.0.0; r3a.module-release-metadata.v1@1.0.0; r3a.module-process-binding.v1@1.0.0; r3a.module.v1.
Tests: tests/test_r3a_module_release_v2.py; tests/fixtures/r3a_module_release_package_v2.json.
History/Predecessor: New contract note derived from R3A_MODULE_LIFECYCLE_AND_CONTRACT_SPEC.md AP0-M1 profile.
-->
# R3A Module Release Package v2

## Scope and ownership

Package v2 defines a generic immutable source artifact and process-launch descriptor for any module declaring `r3a.resident.executor@1.0.0`. The interop fixture uses the synthetic module ID `executor.orbit`; it contains no resident identity, directory record, grant, or approval.

This does not replace provider release-package v1 or change the capability-provider, module registry, lifecycle manager, scheduler, or authorization store. CME remains the lifecycle writer and builds the child command from the descriptor after checking the selected binding, module/artifact identity, declared protocol range, configuration, and current authority. The package tool only builds, verifies, and stages artifact bytes. It neither registers/activates a module nor changes the effective module version.

Staging rejects symlink and special-file traversal and verifies every staged byte before treating an existing content-addressed target as idempotent. The cleanup helper only removes a failed/unactivated candidate when CME lifecycle state is non-effective and the caller provides the effective version and digest as a paired pin. It will not infer either value.

## Versioned contracts

`r3a.module-release-package.v2@2.0.0` carries module ID/version/kind, the exact release-metadata path and digest, the payload artifact-tree digest, a complete per-file path/digest/size inventory, and the process-binding descriptor.

`r3a.module-release-metadata.v1@1.0.0` carries the module ID/version, resident-executor role contract/version and resident execution compatibility range. It is package metadata with its own schema; it does not extend or claim compatibility with `r3a.module-manifest.v1`.

`r3a.module-process-binding.v1@1.0.0` declares:

- process protocol `r3a.module.v1` over the existing private Unix-socket JSON-lines transport;
- compatible protocol major/minor range;
- runtime selector `python3`, resolved by CME to its configured interpreter;
- a Python module entrypoint under the installed artifact root; and
- the fixed argument sequence `--socket {socket_path} --module-id {module_id} --module-version {module_version} --config {configuration_path}`.

The host constructs `[configured_python, -m, entrypoint, ...arguments]`; package data cannot name a shell or arbitrary executable. The process receives its configuration by the existing external configuration reference. The module does not choose its resident identity or gain authority from the package.

## Digest and staging rules

The payload tree digest is SHA-256 over sorted normalized relative file paths, each file's SHA-256 and byte length, prefixed with `r3a-module-artifact-tree.v1`. The release metadata's `artifact_digest` must equal this tree digest. `metadata_sha256` pins the canonical versioned release-metadata JSON. The entire compressed bundle also needs an external SHA-256 pin supplied to verify/install; a checksum written beside the artifact is not a trust root.

The installer rejects unsafe/noncanonical paths, links and special tar members, duplicate or undeclared entries, file inventory drift, metadata mismatch, role mismatch, invalid protocol binding, and bundle/artifact digest mismatch before staging. It stages under a content-addressed path of module ID, immutable module version and artifact digest; it never overwrites another version or digest. Staging is atomic, read-only after completion, and idempotent only after rechecking all installed bytes.

`discard_unactivated_candidate` is limited to staged-artifact cleanup. Its caller must supply CME's durable effective module version/digest and lifecycle state. It refuses active or in-progress states and refuses removal of the exact effective version/digest. CME owns deactivation, replacement, rollback of the effective selection, and durable lifecycle/event state. A failed candidate can be discarded while its previous installed/effective artifact remains intact.

## Shared interoperability evidence

`tests/fixtures/r3a_module_release_package_v2.json` is the descriptor fixture; the accompanying `executor.orbit` release metadata, process binding and worker package provide its pinned payload. Tests build and verify an archive, install it into a temporary content-addressed root, launch the worker with the descriptor's standard arguments, perform a health request over `r3a.module.v1`, stop it, and discard a failed unactivated next-version candidate while retaining the prior artifact.

This is a source/temporary-filesystem interoperability fixture. Autonomy must consume the shared descriptor in its CME binding/lifecycle implementation and run its own integration tests. No shared service, live CME, Ring 0, grant or resident module was changed. Artifact signing/distribution trust is not defined by this contract.
