<!--
R3 CONTROLLED DOCUMENT
File: hints/deployment.md
Component: DEPLOYMENT
File Revision: 1.0.1 (provenance baseline; prior revisions untracked)
Created: Unknown (legacy; initial commit can establish earliest publication)
Created By: Unknown (legacy)
Purpose: R3 engineering reference and continuation guidance
Execution Model: N/A
Observability: N/A
Dependencies: R3 docs and hints index
Authority: R3 engineering guidance; approved charter prevails
Changed: 2026-10-31 UTC | R3-PROVENANCE-001 | ChatGPT GPT-6 | Add provenance baseline
Changed: 2026-11-01 UTC | R3-Q2-DOC-001 | ChatGPT GPT-6 | Index Q2 watched-folder runbook
Supersedes: None
Contracts: hints/file-provenance.md
Tests: Not run (metadata-only change)
History/Predecessor: Git blob 7e4420fa5c55aadeb4f96283919de0706c478ff3
-->
# Deployment and operations

Graceful runtime shutdown closes assignment and conversation write admission and drains active residents and reviewers. The user service drop-in must set `TimeoutStopSec=infinity`; verify the effective value with `systemctl --user show r3-institution.service -p TimeoutStopUSec`. A finite stop timeout can terminate the process before active work reaches its durable completion point.

For the first rollout from a runtime without an admission gate, an idle health snapshot is insufficient. Close new work at an existing upstream admission point before stopping the old process, then verify already-admitted work is drained or durably queued. If no such upstream gate is available, do not restart the old service during active work.

- [Current implementation handoff](../docs/IMPLEMENTATION_HANDOFF.md) — Camrui target, manual bootstrap and pending work.
- [R3 capability API](../r3_app.py) — current source; verify deployed behavior separately.
- [Q2 Windows script queue](q2-script-queue.md) — write PowerShell scripts into Q2, let the watcher dispatch them, and read Queue/Results.

Try Riverview Comms 1.1 before asking the Steward to run commands. Do not claim deployment or runtime behavior without observed evidence. Keep credentials out of browser-facing code.
