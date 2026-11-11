<!--
R3 CONTROLLED DOCUMENT
File: r3a_plugins/octominer_telemetry/manifest.v2.1.0.json.provenance.md
Component: R3A-PLUG-OCTOMINER-MANIFEST-PROVENANCE
File Revision: 1.0.0
Created: 2026-11-11T18:04:26Z
Created By: Codex GPT-6
Purpose: Record the immutable v2.1.0 telemetry manifest's artifact and target-scope contract provenance.
Execution Model: N/A; provenance record for JSON manifest.
Observability: SHA-256 pins in the adjacent manifest and source-control history.
Dependencies: manifest.v2.1.0.json; scope_provider.py; scoped_http_providers.py; existing read-only collectors.
Authority: AD-024; Modular Plugins #46 Planned Step 51; no runtime activation authorization.
Changed: 2026-11-11T18:04:26Z | R3A-MODULAR-PLUGINS-STEP-51 | Codex GPT-6 | Document the immutable source and compatible v2.0 predecessor.
Supersedes: None.
Contracts: r3a.capability-operation.v1; r3a.octominer-independent-telemetry.config.v3.
Tests: tests/test_r3a_telemetry_target_scope.py verifies every declared artifact pin.
History/Predecessor: New sidecar for manifest derived from manifest.json at approved source a224a6b30f1e96b95a65fde6a50d81775f5e5039.
-->
# Telemetry v2.1.0 manifest provenance

This manifest is an additional immutable provider version. It preserves `manifest.json` and provider v2.0.0 unchanged. Version 2.1.0 routes through `scope_provider.py`, pins all supporting collector files, requires the config v3 `request_host_id`, and accepts explicit `host_ids` / `source_ids` only when they resolve against the external provider configuration. The required `infrastructure.octominer.telemetry.read` capability grant remains unchanged; this metadata grants no authority.

The manifest's `allowed_residents` is empty so CME's existing capability grant remains the authorization boundary and no resident name is fixed into this module version. Configured model-server and ComfyUI sources need explicit `host_id` values before v2.1.0 activation; missing mappings fail provider construction. Host/source selection is enforced inside the provider before network/database reads.
