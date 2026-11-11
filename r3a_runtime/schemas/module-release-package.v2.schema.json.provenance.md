<!--
R3 CONTROLLED DOCUMENT
File: r3a_runtime/schemas/module-release-package.v2.schema.json.provenance.md
Component: R3A-MODULE-RELEASE-PACKAGE-V2-PROVENANCE
File Revision: 1.0.1
Created: 2026-11-11T18:53:35Z
Created By: Codex GPT-6
Purpose: Record the generic immutable module package descriptor contract.
Execution Model: N/A; schema sidecar.
Observability: Exact package manifest and artifact file digests.
Dependencies: module-release-package.v2.schema.json; module-process-binding.v1.schema.json.
Authority: AD-024; Roadmap Baseline 1.0 AP0-007/008/009; Step 70/84 cross-workstream contract.
Changed: 2026-11-11T18:53:35Z | R3A-MODULAR-PLUGINS-STEP-70 | Codex GPT-6 | Publish versioned generic package descriptor for staged module artifacts.
Changed: 2026-11-11T19:04:46Z | R3A-MODULAR-PLUGINS-STEP-70 | Codex GPT-6 | Limit this release contract revision to resident-executor process packages.
Supersedes: None.
Contracts: r3a.module-release-package.v2@2.0.0; r3a.module-process-binding.v1@1.0.0.
Tests: tests/test_r3a_module_release_v2.py.
History/Predecessor: New schema; v1 provider-specific bundle remains compatible.
-->
# Module release-package v2 schema provenance

This descriptor is a versioned extension for general immutable module artifacts. It does not replace provider package v1, alter module activation, or assign invocation authority. The process binding uses the AP0-M1 module JSON-lines protocol and a declarative Python module entrypoint.
