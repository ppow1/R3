<!--
R3 CONTROLLED DOCUMENT
File: docs/comms-incidents/R3-COMMS-002.md
Component: COMMS-INCIDENT
File Revision: 1.0.1
Created: 2026-10-31 UTC (time unverified)
Created By: ChatGPT GPT-6
Purpose: Record blocked Camrui deployment preflight and incorrect manual fallback
Execution Model: N/A
Observability: GitHub incident record
Dependencies: Riverview Comms 1.1, R3 visual prototype
Authority: Steward direction to capture every failed operation
Changed: 2026-10-31 UTC | R3-COMMS-002 | ChatGPT GPT-6 | Record bypassed SSH alias and password prompt
Supersedes: None
Contracts: hints/comms-failure-recovery.md; hints/file-provenance.md
Tests: Pending
History/Predecessor: Git blob dd3efc2b3c393c0cc96b438f24d9003705426911
-->
# R3-COMMS-002 — Camrui visual prototype preflight failed

**Objective:** inspect Camrui checkout, Python and port 8303 before deploying the R3 visual prototype.
**Observed:** On 2026-10-31, both Camrui caller grant `grant:6422d222eca74cb3b328bf3a80384a59` and execution grant `grant:8327c8d7a74b4bf78e5529e53057fe69` returned active via `comms5_get_delegation_grant_status`. Two calls to `comms5_command_task_submit` with standard privilege on `camrui` returned **"The tool failed internally."** No command result or Camrui execution was verified. This is not evidence of grant denial or server outage.

**Secondary assistant failure:** Manual fallback was provided as Bash (`clear; result=$(...)`) without ensuring the user was in a Camrui Bash shell. User pasted into Windows PowerShell 7, where it failed with `result=$(...)` not recognized. Script also omitted the user's mandated capture/display/copy-to-clipboard convention. The error was an assistant shell-targeting and formatting failure, not a Camrui diagnostic result.

**Impact:** Visual prototype deployment not verified; user intervention wasted.
**Recovery:** Provide a Windows PowerShell 7 command beginning with `Clear-Host`, collecting diagnostic output into a variable, displaying and copying it to clipboard; SSH to Camrui and run Bash there. Avoid unverified assumptions about host path. Retry authorized Comms when tool available; independently verify deployment and record result.
**Status:** OPEN. Neither command execution nor deployment verified.
**Related:** `hints/comms-failure-recovery.md`, `docs/PUNCH_LIST.md`, R3-P019, R3-P020.

## Subsequent manual fallback failure — SSH identity selection

The next PowerShell fallback invoked `ssh admin1@192.168.1.155` rather than the established `camrui` SSH alias. The user's screenshot shows a password prompt for `admin1@192.168.1.155`; the diagnostic command had not produced results. This is a separate assistant failure to discover/reuse the existing SSH identity and alias configuration. The screenshot does **not** prove aliases were modified or damaged. Recovery: cancel the prompt, inspect effective alias configuration with `ssh -G camrui` and use the existing alias if it resolves correctly; do not overwrite SSH config, generate keys, or prompt for credentials without necessity. **Status: unresolved.**


## 2026-11-02 follow-up — resident avatar deployment

**Objective:** deploy the merged resident avatar web module to Camrui and verify its served entry points.

**Authorization and preflight:** the Windows `desktop-ja3rpnq` standard command caller/execution grants were verified active. A Comms5 transport probe returned `available` with a healthy dashboard (180.948 ms). The fixed `comms5_command_submit` PowerShell identity operation returned `NOT_AUTHORIZED` and `executed:false`; the error stated that authenticated Steward identity or an exact grant was required. The bounded `comms5_command_task_submit` path was then used with the verified host-scoped grants. Q2, Queue, and Results were inspected; `4007.ps1.txt` was the prior numeric result, and 4008/4009/4010 were unused at their respective preflight checks.

**Failed first Q2 attempt:** script `4008.ps1` attempted to download the private repository's pinned deployment script through `raw.githubusercontent.com`. It returned HTTP 404 before SSH or remote deployment. Durable result: `A:\\AI\\Scripts\\Riverview\\Queue\\Results\\4008.ps1.txt`. No Camrui changes were made by this attempt.

**Recovered deployment:** script `4009.ps1` embedded the reviewed remote Bash payload from `scripts/Deploy-R3.ps1` and used the configured `ssh camrui` alias. Its Results file records SSH exit 0, previous commit `dafa352b7f850822c105042878fec8b900f691e4`, deployed commit `7ce2e0e49026c9f5bed4d302f22d6bf7ebb591fa`, healthy Uvicorn PID `3114772`, and successful health, root, and background checks (`200 image/png`, 3,605,170 bytes). Durable result: `A:\\AI\\Scripts\\Riverview\\Queue\\Results\\4009.ps1.txt`.

**Served frontend verification:** script `4010.ps1` confirmed the deployed page references `/web/resident-avatar.js`; that route returned HTTP 200 and the module source contained `window.r3Residents`, the `play-animation` command, and the configured Gobkit asset URL. Durable result: `A:\\AI\\Scripts\\Riverview\\Queue\\Results\\4010.ps1.txt`.

**Remaining acceptance gap:** the browser automation attempt to open `http://192.168.1.155:8303/` was rejected with `ERR_CERT_COMMON_NAME_INVALID`. No certificate warning was bypassed. Consequently the actual WebGL render, model fetch from the browser, and animation playback remain visually unverified. The deploy script correctly reports `VISUAL_ACCEPTANCE=PENDING`; do not mark Milestone 1 accepted until browser evidence confirms the avatar renders and responds to an API command.
