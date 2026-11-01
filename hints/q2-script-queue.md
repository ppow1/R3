<!--
R3 CONTROLLED DOCUMENT
File: hints/q2-script-queue.md
Component: ENG-Q2-SCRIPT-QUEUE
File Revision: 1.0.0
Created: 2026-11-01 UTC (date verified; exact time not independently verified)
Created By: ChatGPT GPT-6
Purpose: Explain the existing Windows Q2 watcher submission and result retrieval workflow for R3 engineering.
Execution Model: Windows PowerShell script submission through a watched Q2 directory; external watcher handles dispatch.
Observability: Script moved to Queue; captured output written to Queue/Results.
Dependencies: Existing configured Q2 watcher on desktop-ja3rpnq, Riverview Comms 1.1 and Windows PowerShell.
Authority: Steward-described and previously observed workflow; no authority to modify R2.
Changed: 2026-11-01 UTC | R3-Q2-DOC-001 | ChatGPT GPT-6 | Document Q2 queue workflow and failure handling
Supersedes: None
Contracts: AI_HINTS.md; hints/deployment.md; hints/file-provenance.md
Tests: Previous Q2 submission/result round trips observed; watcher configuration and reboot persistence not independently inspected.
History/Predecessor: New document; Git history preserves revisions.
-->
# Q2 Windows script queue — submission and results

## Purpose and scope

This is the R3 engineering reference for the **existing** Q2 watched-folder workflow on Windows host `desktop-ja3rpnq`. Q2 is a command-submission transport, not a second R3 runtime, resident, or source-code location. This document describes observed behavior; it does not claim ownership of or changes to the watcher implementation.

## Canonical locations

- **Submit a complete PowerShell `.ps1` script to:** `A:\AI\Scripts\Riverview\Q2\<unique-script-name>.ps1`
- **Watcher execution queue:** `A:\AI\Scripts\Riverview\Queue\`
- **Captured output:** `A:\AI\Scripts\Riverview\Queue\Results\<unique-script-name>.ps1.txt`

The watcher normally picks up submitted scripts in approximately **5–7 seconds**, moves them from Q2 into Queue, executes them, and writes the corresponding result file. This is an observed typical delay, **not** a guaranteed completion deadline. **Do not manually move scripts from Q2 into Queue.**

## Agent procedure

1. Read root `AI_HINTS.md`, `hints/deployment.md`, `hints/comms-failure-recovery.md`, and this document. Check the relevant host authorization and existing work before submitting.
2. Construct a complete, uniquely named PowerShell script. Start with `Clear-Host`. For remote Bash, pass literal script content to `ssh.exe ... camrui bash -s`, normalize CRLF to LF, capture all output and `$LASTEXITCODE`, and print the SSH exit code.
3. Through authorized Riverview Comms 1.1, **write the `.ps1` file directly to Q2**. This is the submission action; do not also execute it manually or move it into Queue.
4. Read the matching `Queue\Results\<script>.ps1.txt` file after the watcher finishes. An empty or missing result is **not success**. Check again or investigate watcher state before resubmitting; prevent duplicate side effects.
5. Distinguish the Comms gateway's result (file submission), the Q2 watcher's execution result, and the remote command's `SSH_EXIT_CODE`. A successful file write does not establish that the remote command succeeded.
6. For failed, blocked, or uncertain execution, follow `hints/comms-failure-recovery.md` and preserve incident evidence. Do not claim deployment without actual runtime verification.

## Minimal PowerShell submission pattern

The following illustrates **writing** a script into Q2 from a PowerShell session on the Windows host. It does not manually dispatch the watcher:

```powershell
Clear-Host
$name = 'R3-Inspect-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.ps1'
$path = Join-Path 'A:\AI\Scripts\Riverview\Q2' $name
$script = @'
Clear-Host
Get-Date -Format o
'@
[IO.File]::WriteAllText($path, $script, [Text.UTF8Encoding]::new($false))
Write-Output "Q2_SUBMITTED=$path"
Write-Output "EXPECTED_RESULT=A:\AI\Scripts\Riverview\Queue\Results\$name.txt"
```

This example is documentation only; it is not a production runtime behavior, automated test, or standing job.

## Boundaries and evidence

- The Q2 watcher, its permissions, restart behavior, and exact implementation have **not** been inspected as part of this document. Consult the original watcher configuration/runbook when available; do not invent its path.
- This file is the **R3 entry-point reference** for the Q2 workflow. It does not claim to supersede an existing external authoritative Q2 runbook.
- Preserve R3 source in `ppow1/R3`. **R2 is frozen and read-only.**
