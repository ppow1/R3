<!--
R3 CONTROLLED DOCUMENT
File: r3a_runtime/schemas/module-release-package.v2.schema.json.provenance.md
Component: R3A-MODULE-RELEASE-PACKAGE-V2-SCHEMA
File Revision: 1.0.0
Created: 2026-11-11T18:20:00Z
Created By: Codex GPT-6
Purpose: Record provenance for the generic immutable process-module package descriptor schema
Execution Model: JSON Schema validation by the generic package builder/installer
Observability: Archive inventory and per-file SHA-256 records
Dependencies: AP0-M1 module lifecycle contract; Issue #46 Step 78 and package interface proposal comment 6804221672
Authority: Step 78 dispatch 6804259280; no CME launch, grant, or deployment authority
Changed: 2026-11-11T18:20:00Z | R3A-MODULE-PACKAGE-V2 | Codex GPT-6 | Add process-module package descriptor schema
Supersedes: None
Contracts: r3a.module-release-package.v2@2.0.0; r3a.module-manifest.v1; r3a.resident.executor@1.0.0; AP0-M1
Tests: tests/test_r3a_generic_module_package.py
History/Predecessor: New schema
-->
# Package v2 schema provenance

This descriptor packages immutable module artifacts and a constrained process launch profile. It is not a runtime registry, grant, installer authority, or CME lifecycle record. Install only stages verified files; CME remains the lifecycle and authorization authority.
