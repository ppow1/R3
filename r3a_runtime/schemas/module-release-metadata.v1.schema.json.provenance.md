<!--
R3 CONTROLLED DOCUMENT
File: r3a_runtime/schemas/module-release-metadata.v1.schema.json.provenance.md
Component: R3A-MODULE-RELEASE-METADATA-V1-PROVENANCE
File Revision: 1.0.0
Created: 2026-11-11T19:32:00Z
Created By: Codex GPT-6
Purpose: Record a separately versioned package metadata contract for resident executors.
Execution Model: N/A; schema sidecar.
Observability: Schema version and role/execution compatibility range are pinned in every package.
Dependencies: module-release-metadata.v1.schema.json; module-release-package.v2.schema.json.
Authority: AD-024; Modular Plugins #46 Step 84. Does not extend r3a.module-manifest.v1.
Changed: 2026-11-11T19:32:00Z | R3A-MODULAR-PLUGINS-STEP-84 | Codex GPT-6 | Publish versioned release metadata schema.
Supersedes: None.
Contracts: r3a.module-release-metadata.v1@1.0.0; r3a.resident.executor@1.0.0; r3a.resident.execution.
Tests: tests/test_r3a_module_release_v2.py.
History/Predecessor: New package-only metadata schema introduced to retain the canonical module manifest contract unchanged.
-->
# Module release metadata v1 schema provenance

This schema contains package-level module identity, immutable artifact digest, executor role contract, and execution compatibility range. It grants no authority and creates no HR/directory resident association. It is deliberately distinct from the existing capability-provider module manifest contract.
