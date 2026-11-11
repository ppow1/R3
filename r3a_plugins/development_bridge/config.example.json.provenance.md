<!--
R3 CONTROLLED DOCUMENT
File: r3a_plugins/development_bridge/config.example.json.provenance.md
Component: R3A-DEVELOPMENT-BRIDGE-CONFIG-PROVENANCE
File Revision: 1.0.0
Created: 2026-11-11T14:20:00Z
Created By: Codex GPT-6
Purpose: Preserve provenance for the comment-free Bridge v3 example configuration
Execution Model: N/A; configuration metadata
Observability: Configuration schema validation by R3A capability loader
Dependencies: manifest.json; operator-provided absolute transport state path environment reference
Authority: Step 11 dispatch 6798229653; no transport activation authorization
Changed: 2026-11-11T14:20:00Z | R3-BRIDGE-V3-STEP11 | Codex GPT-6 | Add example configuration provenance sidecar
Supersedes: None
Contracts: r3a.development-bridge.config.v1; hints/file-provenance.md
Tests: tests/test_r3a_development_bridge.py
History/Predecessor: None; new file
-->
# Bridge example configuration provenance

The example deliberately sets transport to `unavailable`. A deployment must configure an approved absolute cache location via the named environment reference, then independently configure and authorize any host transport adapter. This file contains no credentials or host path.
