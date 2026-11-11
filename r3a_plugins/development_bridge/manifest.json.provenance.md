<!--
R3 CONTROLLED DOCUMENT
File: r3a_plugins/development_bridge/manifest.json.provenance.md
Component: R3A-DEVELOPMENT-BRIDGE-MANIFEST-PROVENANCE
File Revision: 1.0.0
Created: 2026-11-11T14:20:00Z
Created By: Codex GPT-6
Purpose: Preserve provenance for the comment-free Bridge v3 manifest JSON
Execution Model: N/A; metadata sidecar
Observability: Git revision and referenced artifact digest
Dependencies: manifest.json; R3A module-manifest.v1@1.2.0 and capability-operation.v1
Authority: Step 11 dispatch 6798229653 and Step 10 correction 6797993717
Changed: 2026-11-11T14:20:00Z | R3-BRIDGE-V3-STEP11 | Codex GPT-6 | Add manifest provenance sidecar
Supersedes: None
Contracts: hints/file-provenance.md
Tests: tests/test_r3a_development_bridge.py
History/Predecessor: None; new file
-->
# Bridge manifest provenance

The manifest declares a disabled-by-default, digest-pinned Bridge v3 capability provider. CME owns registration, module lifecycle, authorization, activity/event persistence, and diagnostics. The SQLite transport attempt cache is subordinate deduplication/reconciliation state only; it is not a module/session registry or event log. The Windows transport is not configured by this manifest.
