<!--
R3 CONTROLLED DOCUMENT
File: r3a_plugins/octominer_telemetry/config.v3.example.json.provenance.md
Component: R3A-PLUG-OCTOMINER-CONFIG-PROVENANCE
File Revision: 1.0.0
Created: 2026-11-11T18:04:26Z
Created By: Codex GPT-6
Purpose: Explain host ownership fields required by the v3 scoped telemetry provider configuration.
Execution Model: N/A; provenance record for JSON example.
Observability: Example is validated against manifest.v2.1.0.json in permanent tests.
Dependencies: config.v3.example.json; manifest.v2.1.0.json.
Authority: AD-024; Modular Plugins #46 Planned Step 51.
Changed: 2026-11-11T18:04:26Z | R3A-MODULAR-PLUGINS-STEP-51 | Codex GPT-6 | Record the purpose of explicit endpoint host identifiers.
Supersedes: None.
Contracts: r3a.octominer-independent-telemetry.config.v3; capability target host_ids.
Tests: tests/test_r3a_telemetry_target_scope.py.
History/Predecessor: New sidecar; example derived from config.example.json at approved source a224a6b30f1e96b95a65fde6a50d81775f5e5039.
-->
# Telemetry config v3 example

The host identifiers in this JSON file are placeholders. Replace each with the independently verified host owning that SSH, database, model-server, or ComfyUI source. The provider uses these values to enforce `target.host_ids`; it does not infer host ownership from endpoint names or URLs. Secret values remain external environment references.
