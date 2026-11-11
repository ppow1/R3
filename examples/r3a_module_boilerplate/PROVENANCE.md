<!--
R3 CONTROLLED DOCUMENT
File: examples/r3a_module_boilerplate/PROVENANCE.md
Component: R3A-MODULE-BOILERPLATE-PROVENANCE
File Revision: 1.0.4
Created: 2026-11-11T21:52:37Z
Created By: Codex GPT-6
Purpose: Provide file-level provenance for the JSON files in the boilerplate example.
Execution Model: N/A; provenance manifest.
Observability: Tracked file revisions and Git predecessor/content history.
Dependencies: hints/file-provenance.md; parent example README.
Authority: Steward assignment #68 comment 6807799874; Planned Step 126 comment 6807801282.
Changed: 2026-11-11T21:52:37Z | R3A-MODULE-BOILERPLATES-STEP-120 | Codex GPT-6 | Record provenance for JSON contract and fixture files.
Changed: 2026-11-11T21:59:39Z | R3A-MODULE-BOILERPLATES-STEP-120 | Codex GPT-6 | Record finalized content pins for metadata and resident-binding examples.
Changed: 2026-11-11T21:59:39Z | R3A-MODULE-BOILERPLATES-STEP-120 | Codex GPT-6 | Recompute content pins after adding the worker's provenance header.
Changed: 2026-11-11T22:04:26Z | R3A-MODULE-BOILERPLATES-STEP-120 | Codex GPT-6 | Restrict the artifact digest to the shared builder's explicit file list.
Changed: 2026-11-11T22:06:58Z | R3A-MODULE-BOILERPLATES-STEP-120 | Codex GPT-6 | Record the configuration example's exact revision digest.
Supersedes: None.
Contracts: Module release metadata v1; module process binding v1; resident module binding v1; configuration schema v1.
Tests: tests/test_module_boilerplate_example.py.
History/Predecessor: New sidecar manifest for commentless JSON files.
-->
# JSON file provenance

| File | Revision | Created | Purpose / execution / observability | Dependencies and authority | Changes / supersedes / contracts / tests / history |
|---|---|---|---|---|---|
| `MODULE_METADATA.json` | 1.0.3 | 2026-11-11T21:52:37Z; Codex GPT-6 | Package-only executor metadata; consumed by the shared package builder. The builder fills `artifact_digest` from the declared source tree. | Shared release metadata schema v1; #68 comment 6807799874; Step 126 comment 6807801282. | Final package tree digest `a10b8edb16cb38ddb72252be15be99f112ff0539fc7ec55137218f0cf262467c` pinned on 2026-11-11T22:04:26Z; supersedes 1.0.2 digest; release metadata v1; validated by focused test and shared builder at `2641bda993384d6f0a78d3798401a2a1585d39b8`; new file. |
| `process-binding.json` | 1.0.0 | 2026-11-11T21:52:37Z; Codex GPT-6 | Data-only child-process launch contract over the existing JSON-lines protocol. | Shared process-binding schema v1; AP0-M1; no shell or arbitrary executable. | Initial example; supersedes none; module process binding v1; focused test and shared builder; new file. |
| `configuration.schema.json` | 1.0.0 | 2026-11-11T21:52:37Z; Codex GPT-6 | External example configuration schema. | JSON Schema Draft 2020-12; no credentials or authority data. | Initial example; supersedes none; example configuration v1; focused test; new file. |
| `configuration.example.json` | 1.0.0 | 2026-11-11T21:52:37Z; Codex GPT-6 | Non-secret external config sample. | `configuration.schema.json`; fixture-only values. | Initial example; supersedes none; example configuration v1; focused test; new file. |
| `resident-module-binding.example.json` | 1.0.3 | 2026-11-11T21:52:37Z; Codex GPT-6 | Synthetic identity-association and config-binding fixture; not installed or authorized. | Existing `resident-module-binding.v1.schema.json`; fixture-only identity and revisions. | Artifact digest `a10b8edb16cb38ddb72252be15be99f112ff0539fc7ec55137218f0cf262467c`; configuration revision `8cd8b6e2e028773d9eb3232bcf097c30d414766b7ec5d590efd4aa59fcc8d229` pinned on 2026-11-11T22:06:58Z; supersedes 1.0.2 digest entry; resident module binding v1; focused test; new file. |
