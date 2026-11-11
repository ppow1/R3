<!--
R3 CONTROLLED DOCUMENT
File: hints/b2-development-bridge-startup.md
Component: EXTERNAL-B2-STARTUP
File Revision: 1.0.0
Created: 2026-11-11 UTC (date precision)
Created By: ChatGPT GPT-6, acting on Steward instruction
Purpose: Restart or verify the two required external B-2 Windows terminal windows at the beginning of a development session
Execution Model: Operator-initiated Windows PowerShell 7
Observability: Window titles, running bridge process, GitHub Issue #61 receipts
Dependencies: Existing installed B-2 script, GitHub CLI authentication, PowerShell 7, target JSON
Authority: Steward; external development tooling only
Changed: 2026-11-11 UTC | B2-STARTUP-001 | ChatGPT GPT-6 | Add session startup and safe duplicate checks
Supersedes: None
Contracts: docs/operations/development-bridge/B2_EXTERNAL_DEVELOPMENT_CONTROL_HANDOFF.md
Tests: Not executed on Windows host; operator must verify first startup
History/Predecessor: None
-->
# B-2 external development bridge — new-session startup

**This starts development tooling on the Windows workstation, not Riverview.** At the beginning of a new ChatGPT development session, check whether both required windows are already running before creating them:

1. **B-2 Administrator Coordinator** — a PowerShell 7 window titled `Riverview B2 Administrator Coordinator`, where B-2-delivered PowerShell commands execute.
2. **B-2 Multi-Target Bridge** — a separate PowerShell 7 window running `Riverview-GitHub-Bridge-B2-MultiTarget.ps1 -DispatchIssue 61 -PollSeconds 10 -Arm`, which polls GitHub and delivers assignments.

## One-shot Windows PowerShell 7 startup (paste in an existing PowerShell window)

This code checks for existing windows/processes and launches only missing components. It does **not** stop or restart existing windows, change dispatch state, or create new infrastructure. It requests UAC elevation for new windows (matching the previously observed Administrator bridge window); approve only if expected. The bridge startup uses the already-installed script and existing target JSON.

```powershell
$ErrorActionPreference = 'Stop'
$folder = Join-Path $env:USERPROFILE 'Downloads\Riverview-B2-Administrator-Package'
$bridgeScript = Join-Path $folder 'Riverview-GitHub-Bridge-B2-MultiTarget.ps1'
$targets = Join-Path $folder 'Riverview-B2-targets.json'
$pwsh = (Get-Command pwsh.exe -ErrorAction Stop).Source
if (-not (Test-Path -LiteralPath $bridgeScript)) { throw "Missing bridge: $bridgeScript" }
if (-not (Test-Path -LiteralPath $targets)) { throw "Missing target registry: $targets" }

$adminTitle = 'Riverview B2 Administrator Coordinator'
$adminWindows = @(Get-Process | Where-Object {
    $_.MainWindowHandle -ne 0 -and
    $_.MainWindowTitle -cin @($adminTitle, "Select $adminTitle")
})
if ($adminWindows.Count -eq 0) {
    $adminCommand = '$Host.UI.RawUI.WindowTitle = ''Riverview B2 Administrator Coordinator''; Write-Host ''B-2 Administrator Coordinator ready. Leave this window open.'''
    Start-Process -FilePath $pwsh -Verb RunAs -ArgumentList @('-NoExit', '-NoProfile', '-Command', $adminCommand)
    Write-Output 'ADMIN_COORDINATOR=START_REQUESTED'
} elseif ($adminWindows.Count -eq 1) {
    Write-Output "ADMIN_COORDINATOR=ALREADY_RUNNING PID=$($adminWindows[0].Id)"
} else {
    throw "Multiple Administrator Coordinator windows ($($adminWindows.Count)); inspect before continuing"
}

# Inspect actual command lines rather than assuming a generic Administrator: pwsh.exe title.
$bridgeProcesses = @(Get-CimInstance Win32_Process | Where-Object {
    $_.Name -in @('pwsh.exe', 'powershell.exe') -and
    $_.CommandLine -like '*Riverview-GitHub-Bridge-B2-MultiTarget.ps1*'
})
if ($bridgeProcesses.Count -eq 0) {
    $bridgeCommand = '& ''' + $bridgeScript.Replace("'", "''") + ''' -DispatchIssue 61 -PollSeconds 10 -Arm'
    Start-Process -FilePath $pwsh -Verb RunAs -ArgumentList @('-NoExit', '-NoProfile', '-Command', $bridgeCommand)
    Write-Output 'MULTI_TARGET_BRIDGE=START_REQUESTED'
} elseif ($bridgeProcesses.Count -eq 1) {
    Write-Output "MULTI_TARGET_BRIDGE=ALREADY_RUNNING PID=$($bridgeProcesses[0].ProcessId)"
} else {
    throw "Multiple matching bridge processes ($($bridgeProcesses.Count)); inspect before continuing"
}
Write-Output 'STARTUP_CHECK=FINISHED; verify both windows and GitHub Issue #61'
```

**Important:** The Administrator Coordinator window is an idle PowerShell command receiver, **not** another bridge polling process. The bridge process must be a separate window. If a bridge was started interactively using `& $Script ...`, its command line might show only `pwsh.exe` and not the script name; the process check above may then miss it. **Before starting a second bridge, visually check the existing Multi-Target Bridge window and its polling output.** Never launch two polling bridges against the same state.

## Manual fallback if process detection is ambiguous

Open **two separate elevated PowerShell 7 windows**. In the first, set the exact title:

```powershell
$Host.UI.RawUI.WindowTitle = 'Riverview B2 Administrator Coordinator'
Write-Output 'B-2 Administrator Coordinator ready'
```

In the second, start the existing bridge:

```powershell
Clear-Host
$Folder = Join-Path $env:USERPROFILE 'Downloads\Riverview-B2-Administrator-Package'
$Script = Join-Path $Folder 'Riverview-GitHub-Bridge-B2-MultiTarget.ps1'
& $Script -DispatchIssue 61 -PollSeconds 10 -Arm
```

Do not start a second bridge if the original is already polling. Expect `Mode: ARMED` and periodic GitHub polling; confirm a harmless authorized Issue #61 assignment and its **result**, not just a wake-up receipt. If elevation, authentication, path, or script execution fails, report the actual error instead of installing a replacement subsystem.

**Verification status:** These startup instructions are documented from known working launch parameters and title requirements; the combined startup script has not yet been exercised end-to-end on the workstation.
