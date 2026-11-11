<!--
R3 CONTROLLED DOCUMENT
File: r3a_runtime/schemas/module-process-binding.v1.schema.json.provenance.md
Component: R3A-MODULE-PROCESS-BINDING-PROVENANCE
File Revision: 1.0.0
Created: 2026-11-11T18:53:35Z
Created By: Codex GPT-6
Purpose: Record version and authority of the JSON-lines process binding schema.
Execution Model: N/A; schema sidecar.
Observability: Schema digest and fixtures are verified by module package contract tests.
Dependencies: module-process-binding.v1.schema.json; R3A module protocol v1.
Authority: AD-024; Roadmap Baseline 1.0 AP0-007/008/009; Step 70/84 cross-workstream contract.
Changed: 2026-11-11T18:53:35Z | R3A-MODULAR-PLUGINS-STEP-70 | Codex GPT-6 | Publish generic data-only process launch descriptor.
Changed: 2026-11-11T19:04:46Z | R3A-MODULAR-PLUGINS-STEP-70 | Codex GPT-6 | Correct schema provenance timestamp.
Supersedes: None.
Contracts: r3a.module-process-binding.v1@1.0.0; r3a.module.v1 JSON-lines protocol.
Tests: tests/test_r3a_module_release_v2.py.
History/Predecessor: New schema derived from AP0-M1 module lifecycle protocol profile.
-->
# Module process-binding schema provenance

The schema declares process transport and entrypoint data. It does not declare a shell command, resident identity, grant, or effective lifecycle state. CME constructs the child process using its configured Python runtime and the installed artifact root.
