<!--
R3 CONTROLLED DOCUMENT
File: r3a_runtime/schemas/module-manifest.v1.schema.json
Component: R3A-MODULE-MANIFEST-SCHEMA
File Revision: 1.2.0
Created: 2026-11-10T01:09:23Z
Created By: Codex GPT-6
Purpose: Preserve the original r3a.module-manifest.v1@1.0.0 schema without resident or handler role fields.
Execution Model: JSON Schema selected by capability_contracts.validate_module_manifest.
Observability: Unsupported fields and contract versions fail validation.
Dependencies: r3a_runtime/capability_contracts.py.
Authority: AD-024 §2.7–2.8; #46 correction after Auditor finding. This schema remains v1.0.0.
Changed: 2026-11-10T02:02:46Z | R3A-MODULAR-PLUGINS-46 | Codex GPT-6 | Restore the baseline v1.0.0 schema and move optional role declarations to v1.1.0.
Supersedes: Prior sidecar revision 1.1.0, which incorrectly described role fields under v1.0.0; the v1.0 schema content itself is restored from integration baseline 9a41d7e9647d37c2b7dc6f2aca3be3f5f82ccfe9.
Contracts: r3a.module-manifest.v1@1.0.0.
Tests: tests/test_r3a_module_extensions.py; tests/test_r3a_module_contracts.py.
History/Predecessor: Prior sidecar blob b89d2e1fc9e40e1775da436e33f81cba7c610a64; schema restored from baseline blob 220c9b79134abab46cd6d25215fb17cd7dcf0cc8.
-->
