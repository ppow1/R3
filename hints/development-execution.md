<!--
R3 CONTROLLED DOCUMENT
File: hints/development-execution.md
Component: ENG-EXECUTION
File Revision: 1.0.0
Created: 2026-11-05 UTC (date only; exact time not independently verified)
Created By: ChatGPT GPT-6
Purpose: Mandatory evidence-first command execution and PowerShell fallback for R3 development
Execution Model: Development guidance
Observability: Captured command output, exit status, source evidence and development summary
Dependencies: hints/development-bootstrap.md; hints/comms-failure-recovery.md
Authority: Steward direction; authorized grants and applicable runbooks
Changed: 2026-11-05 UTC | R3-DEV-BOOTSTRAP-002 | ChatGPT GPT-6 | Establish local-first, gateway-first, clipboard fallback workflow
Supersedes: None
Superseded By: None
Contracts: hints/file-provenance.md; hints/comms-failure-recovery.md
Tests: Documentation inspection; no remote execution
History/Predecessor: New file; none
-->
# R/3 Development Execution — Required Workflow

This is a mandatory companion to [R3 Bootstrap](development-bootstrap.md). Use the least expensive authorized path that produces adequate evidence; do not turn routine feature work into a lengthy testing or infrastructure investigation.

## 1. Existing information first

Before executing new discovery commands, writing new diagnostics, or running tests, inspect **available local and already-retrieved evidence**: the active repository/worktree, configuration files, source, existing tests, prior command outputs, logs, health snapshots, institutional capability/authority registry, linked runbooks, punch lists and parking lots. Check evidence freshness and relevance. Do not assume old observations describe the live machine. Avoid repeating tests when existing trustworthy results already answer the question.

Use [AI_HINTS](../AI_HINTS.md) and its [hints index](README.md) as the current **miniature institutional knowledge base**. Search and follow existing topic pointers, punch lists, parking lots, issue records and historical R/2 references when relevant; do not claim these have already been consolidated. Prefer one authoritative current document per topic and link rather than duplicate. Future knowledge-base consolidation is planned, not implemented.

## 2. Authorized command gateway first

When live host inspection, code writing, execution, deployment or testing is required, **attempt the available authorized Riverview Comms 1.1 / command gateway first**, after discovering current capabilities and checking grants. Use it to query machines, read files, write code, run bounded commands and tests when the actual interface and authorization permit. Never infer a grant from historical status; do not bypass denied authorization or tool safety decisions. Prefer source/repository tools for repository operations when they are the direct appropriate interface. Record meaningful gateway failure or preflight block using [Comms recovery](comms-failure-recovery.md); bounded recovery only.

## 3. Manual fallback: Windows PowerShell 7

If gateway execution is unavailable, blocked, unsuitable, or cannot complete the objective, provide a **single complete, copy/paste-ready PowerShell 7 block** for the Steward. Start the block with `Clear-Host`. Capture command stdout, stderr, exceptions and exit codes in variables; build a consolidated human-readable `$result`; display `$result` and copy it with `Set-Clipboard -Value $result`. The user should not have to manually select terminal text. Use the actual verified host/SSH alias and paths; mark unknown values as inputs rather than inventing them. If SSH is used, invoke it from PowerShell and run Linux shell syntax remotely, never paste raw Bash into PowerShell.

### Reference pattern (adapt to the actual authorized task)

```powershell
Clear-Host
$ErrorActionPreference = 'Stop'
$target = 'camrui' # Verify the configured SSH alias before use
$lines = @()
try {
    $output = & ssh $target 'hostname; uptime' 2>&1 | Out-String
    $exitCode = $LASTEXITCODE
    $lines += "TARGET=$target"
    $lines += "SSH_EXIT_CODE=$exitCode"
    $lines += $output.TrimEnd()
} catch {
    $lines += "TARGET=$target"
    $lines += "ERROR=$($_ | Out-String)"
    $lines += "SSH_EXIT_CODE=NOT_EXECUTED"
}
$result = ($lines -join [Environment]::NewLine)
Write-Output $result
Set-Clipboard -Value $result
```

For longer commands, capture all relevant outputs in `$result`, including failure paths, and preserve a meaningful exit status. Do not hide stderr or falsely label a failed command as successful. Do not include credentials in captured clipboard output. The example is illustrative and does not authorize execution on its own.

## 4. Testing and delivery discipline

Prefer targeted tests and the smallest essential smoke verification, using existing tests and prior evidence first. Extensive regression runs and automatic rollback are deferred during accelerated development. Before authorized deployment confirm a prior backup or working release exists; deploy, smoke-verify and **fix in place** if needed. Include exact revision, commands attempted, observed results and unresolved blockers in the delivery summary. A successful command exit does not by itself prove feature acceptance.
