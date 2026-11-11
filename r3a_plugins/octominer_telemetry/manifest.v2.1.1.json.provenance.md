<!--
R3 CONTROLLED DOCUMENT
File: r3a_plugins/octominer_telemetry/manifest.v2.1.1.json.provenance.md
Component: R3A-PLUG-OCTOMINER-MANIFEST-PROVENANCE
File Revision: 1.0.0
Created: 2026-11-11T18:38:47Z
Created By: Codex GPT-6
Purpose: Record the immutable v2.1.1 manifest's fail-closed target scope and artifact provenance.
Execution Model: N/A; provenance record for JSON manifest.
Observability: SHA-256 pins in the adjacent manifest and source-control history.
Dependencies: manifest.v2.1.1.json; scope_provider_v2_1_1.py; scoped_http_providers.py; existing read-only collectors.
Authority: AD-024; Modular Plugins #46 Planned Steps 51 and 70; no runtime activation authorization.
Changed: 2026-11-11T18:38:47Z | R3A-MODULAR-PLUGINS-STEP-70 | Codex GPT-6 | Publish a new immutable version correcting the audited v2.1.0 target defect.
Supersedes: None.
Contracts: r3a.capability-operation.v1; r3a.octominer-independent-telemetry.config.v3; required nonempty host_ids and source_ids.
Tests: tests/test_r3a_telemetry_target_scope.py verifies target semantics and every declared artifact pin.
History/Predecessor: v2.1.0 remains unchanged at prior commit 132b748a311fc2ff717babb39735b19bbc2221fa.
-->
# Telemetry v2.1.1 manifest provenance

This new immutable provider version corrects the v2.1.0 empty-target scope defect without rewriting that previously published version. Its operation schema requires nonempty `host_ids` and `source_ids`; the provider also rejects absent/empty target context before invoking SSH, HTTP, process, database, or history readers. The exact `infrastructure.octominer.telemetry.read` grant is unchanged. The manifest pins the new provider artifact and all shared collector files; it grants no authority.
