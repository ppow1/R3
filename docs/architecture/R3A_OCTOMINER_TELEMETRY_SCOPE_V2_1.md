<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_OCTOMINER_TELEMETRY_SCOPE_V2_1.md
Component: R3A-OCTOMINER-SCOPE-NOTE
File Revision: 1.0.0
Created: 2026-11-11T18:04:26Z
Created By: Codex GPT-6
Purpose: Specify the v2.1 telemetry provider's host/source selector behavior and evidence limits.
Execution Model: N/A; module release contract note.
Observability: Selected source IDs, fail-closed target errors, and source freshness evidence.
Dependencies: R3A capability operation contract; OctoMiner telemetry v2.1.0 manifest/config.
Authority: AD-024; Roadmap Baseline 1.0 AP0-007/008/009; Issue #46 Planned Step 51.
Changed: 2026-11-11T18:04:26Z | R3A-MODULAR-PLUGINS-STEP-51 | Codex GPT-6 | Document v2.1 provider scope and authorization boundary.
Supersedes: None.
Contracts: r3a.capability-operation.v1; r3a.octominer-independent-telemetry.config.v3.
Tests: tests/test_r3a_telemetry_target_scope.py.
History/Predecessor: New document; approved source a224a6b30f1e96b95a65fde6a50d81775f5e5039.
-->
# OctoMiner telemetry provider v2.1 scope behavior

Provider v2.1.0 is published beside the unchanged v2.0.0 manifest. Its operation continues to require `infrastructure.octominer.telemetry.read`; CME still performs grant checks and records invocation authorization. The v2.1 manifest leaves `allowed_residents` empty so the provider is not hardwired to one resident. Discovery, configuration, and module registration still grant no authority.

The provider consumes CME's `context.target`. `host_ids` must name configured source hosts. A host selector returns only the SSH, database, model-server, or ComfyUI sources whose external config maps them to the selected host. `source_ids` selects exact configured source IDs, and a combined selector is their intersection. Unknown IDs, malformed/empty selectors, and source/host mismatches are denied before collection. Model-server and ComfyUI endpoint configs must declare their owning `host_id`; missing mappings prevent v2.1.0 activation. A history-only request reads the existing SQLite journal in read-only mode and limits rows to the selected source IDs.

An empty target keeps the existing v2.0.0 default behavior of reading all sources declared by that module's external config. This is capability-level scope: the provider cannot access a second host unless a host/endpoint is configured. The module child shares CME's service UID, so this contract is application-level selection, not an operating-system sandbox. No CME or Ring 0 source is changed here.

The config v3 example contains placeholders only. It does not assert real host ownership or authorize live endpoint access. Integration must choose the v2.1 manifest/config explicitly, preserve the current release until that version is reviewed and tested, and separately verify existing grants and endpoint ownership before any activation.
