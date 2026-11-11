<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_OCTOMINER_TELEMETRY_SCOPE_V2_1.md
Component: R3A-OCTOMINER-SCOPE-NOTE
File Revision: 1.0.2
Created: 2026-11-11T18:04:26Z
Created By: Codex GPT-6
Purpose: Specify the v2.1 telemetry provider's host/source selector behavior and evidence limits.
Execution Model: N/A; module release contract note.
Observability: Selected source IDs, fail-closed target errors, and source freshness evidence.
Dependencies: R3A capability operation contract; OctoMiner telemetry v2.1.0 manifest/config.
Authority: AD-024; Roadmap Baseline 1.0 AP0-007/008/009; Issue #46 Planned Steps 51 and 70.
Changed: 2026-11-11T18:38:47Z | R3A-MODULAR-PLUGINS-STEP-70 | Codex GPT-6 | Record v2.1.0 finding and v2.1.1 immutable correction.
Changed: 2026-11-11T18:04:26Z | R3A-MODULAR-PLUGINS-STEP-51 | Codex GPT-6 | Document v2.1 provider scope and authorization boundary.
Supersedes: None.
Contracts: r3a.capability-operation.v1; r3a.octominer-independent-telemetry.config.v3.
Tests: tests/test_r3a_telemetry_target_scope.py.
History/Predecessor: New document; approved source a224a6b30f1e96b95a65fde6a50d81775f5e5039.
-->
# OctoMiner telemetry provider v2.1 scope behavior

Provider v2.1.0 was published as an additive candidate beside the unchanged v2.0.0 manifest. Auditor review found that v2.1.0 treated an empty target as all configured sources; that version and its files are retained unchanged for exact history. Corrected provider v2.1.1 is published under a new manifest and artifact path. Both versions require `infrastructure.octominer.telemetry.read`; CME still performs grant checks and records invocation authorization. The v2.1 manifests leave `allowed_residents` empty so the provider is not hardwired to one resident. Discovery, configuration, and module registration still grant no authority.

Provider v2.1.1 consumes CME's `context.target`. Its operation schema and provider both require nonempty `host_ids` and `source_ids`; missing target context or an empty target is denied before collection. `host_ids` must name configured source hosts. A host selector returns only the SSH, database, model-server, or ComfyUI sources whose external config maps them to the selected host. `source_ids` selects exact configured source IDs, and the two selectors are intersected. Unknown IDs, malformed/empty selectors, and source/host mismatches are denied before collection. Model-server and ComfyUI endpoint configs must declare their owning `host_id`; missing mappings prevent v2.1.1 activation. A history-only request reads the existing SQLite journal in read-only mode and limits rows to the selected source IDs.

An empty or absent target never expands to all sources. This is capability-level scope: the provider cannot access a second host unless a host/endpoint is configured. The module child shares CME's service UID, so this contract is application-level selection, not an operating-system sandbox. No CME or Ring 0 source is changed here.

The config v3 example contains placeholders only. It does not assert real host ownership or authorize live endpoint access. Integration must choose the v2.1.1 manifest/config explicitly, preserve the current release until that version is reviewed and tested, and separately verify existing grants and endpoint ownership before any activation.
