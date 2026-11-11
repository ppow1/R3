<!--
R3 CONTROLLED DOCUMENT
File: r3a_runtime/state_machines/process.json.provenance.md
Component: R3A-PROCESS-MACHINE-PROVENANCE
File Revision: 1.0.0
Created: 2026-11-06T15:15:00Z
Created By: Codex GPT-6
Purpose: Preserve provenance for the JSON process lifecycle definition.
Execution Model: N/A; sidecar metadata.
Observability: Git blob history and state-machine digest.
Dependencies: r3a_runtime/state_machines/process.json; hints/file-provenance.md.
Authority: AP0-M1 implementation authorized by Steward in GitHub Issue #42.
Changed: 2026-11-06T15:15:00Z | R3A-AP0-M1 | Codex GPT-6 | Add JSON provenance sidecar.
Supersedes: None.
Contracts: STM-001/002/007; AP0-005.
Tests: State-machine catalog validation.
History/Predecessor: New file; initial publication recorded in Git.
-->
# Process lifecycle JSON provenance

The sibling `process.json` is the versioned machine definition loaded into the isolated AP0 PostgreSQL catalog. Its exact bytes are identified by SHA-256 and historical versions are retained in the database.
