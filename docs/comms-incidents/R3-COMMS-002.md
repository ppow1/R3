<!--
R3 CONTROLLED DOCUMENT
File: docs/comms-incidents/R3-COMMS-002.md
Component: COMMS-INCIDENT
File Revision: 1.0.0
Created: 2026-10-31 UTC (time unverified)
Created By: ChatGPT GPT-6
Purpose: Record blocked Camrui deployment preflight and incorrect manual fallback
Execution Model: N/A
Observability: GitHub incident record
Dependencies: Riverview Comms 1.1, R3 visual prototype
Authority: Steward direction to capture every failed operation
Changed: 2026-10-31 UTC | R3-COMMS-002 | ChatGPT GPT-6 | Initial incident
Supersedes: None
Contracts: hints/comms-failure-recovery.md; hints/file-provenance.md
Tests: Pending
History/Predecessor: None
-->
# R3-COMMS-002 — Camrui visual prototype preflight failed

**Objective:** inspect Camrui checkout, Python and port 8303 before deploying the R3 visual prototype.
**Observed:** On 2026-10-31, both Camrui caller grant `grant:6422d222eca74cb3b328bf3a80384a59` and execution grant `grant:8327c8d7a74b4bf78e5529e53057fe69` returned active via `comms5_get_delegation_grant_status`. Two calls to `comms5_command_task_submit` with standard privilege on `camrui` returned **"The tool failed internally."** No command result or Camrui execution was verified. This is not evidence of grant denial or server outage.

**Secondary assistant failure:** Manual fallback was provided as Bash (`clear; result=$(...)`) without ensuring the user was in a Camrui Bash shell. User pasted into Windows PowerShell 7, where it failed with `result=$(...)` not recognized. Script also omitted the user's mandated capture/display/copy-to-clipboard convention. The error was an assistant shell-targeting and formatting failure, not a Camrui diagnostic result.

**Impact:** Visual prototype deployment not verified; user intervention wasted.
**Recovery:** Provide a Windows PowerShell 7 command beginning with `Clear-Host`, collecting diagnostic output into a variable, displaying and copying it to clipboard; SSH to Camrui and run Bash there. Avoid unverified assumptions about host path. Retry authorized Comms when tool available; independently verify deployment and record result.
**Status:** OPEN. Neither command execution nor deployment verified.
**Related:** `hints/comms-failure-recovery.md`, `docs/PUNCH_LIST.md`, R3-P019, R3-P020.
