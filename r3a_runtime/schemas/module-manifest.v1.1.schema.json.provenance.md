<!--
R3 CONTROLLED DOCUMENT
File: r3a_runtime/schemas/module-manifest.v1.1.schema.json
Component: R3A-MODULE-MANIFEST-SCHEMA
File Revision: 1.0.0
Created: 2026-11-10T02:02:46Z
Created By: Codex GPT-6
Purpose: Define backward-compatible optional resident-executor and activity-handler declarations under manifest contract v1.1.0.
Execution Model: JSON Schema selected by capability_contracts.validate_module_manifest.
Observability: Strict validation fails closed for malformed or unknown role contracts.
Dependencies: r3a_runtime/capability_contracts.py; r3a_runtime/module_extensions.py.
Authority: AD-024 §§2.7–2.8 and 3.2–3.3; Modular Plugins #46.
Changed: 2026-11-10T02:02:46Z | R3A-MODULAR-PLUGINS-46 | Codex GPT-6 | Publish manifest v1.1.0 schema with optional role declarations.
Supersedes: None.
Contracts: r3a.module-manifest.v1@1.1.0; r3a.resident.executor@1.0.0; r3a.activity-handler@1.0.0.
Tests: tests/test_r3a_module_extensions.py; tests/test_r3a_activity_handler_interop.py.
History/Predecessor: New schema generated from the v1.0 envelope plus optional, separately versioned role metadata.
-->
