<!--
R3 CONTROLLED DOCUMENT
File: r3a_runtime/schemas/module-manifest.v1.schema.json
Component: R3A-MODULE-MANIFEST-SCHEMA
File Revision: 1.1.0
Created: 2026-11-10T01:09:23Z
Created By: Codex GPT-6
Purpose: Extend the module manifest with optional generic resident-executor and activity-handler roles.
Execution Model: JSON Schema consumed by R3A configuration and module validation.
Observability: Stable contract/schema identifier and fail-closed validation errors.
Dependencies: r3a_runtime/capability_contracts.py; r3a_runtime/module_extensions.py.
Authority: AD-024 and Modular Plugins #46; no identity creation or authority grant.
Changed: 2026-11-10T01:09:23Z | R3A-MODULAR-PLUGINS-46 | Codex GPT-6 | Publish versioned role metadata schema.
Supersedes: None
Contracts: module-manifest.v1.schema.json
Tests: tests/test_r3a_module_extensions.py
History/Predecessor: Previous schema at integration commit 9a41d7e9647d37c2b7dc6f2aca3be3f5f82ccfe9, blob 220c9b79134abab46cd6d25215fb17cd7dcf0cc8; this revision adds optional role declarations without changing provider fields.
-->
