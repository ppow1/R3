# Riverview Controlled Source
# File: scripts/operations/Invoke-RiverviewSsh.ps1
# Component: OPERATIONS-SSH-WRAPPER
# File Revision: 1.0.0
# Created: 2026-11-01 UTC (exact time unverified)
# Created By: ChatGPT GPT-6
# Purpose: Run a literal Bash file over an existing SSH alias.
# Execution Model: One remote Bash invocation.
# Observability: stdout, stderr, exit code, optional clipboard.
# Dependencies: PowerShell, ssh.exe, configured SSH aliases.
# Authority: Steward instruction; no host configuration changes.
# Changed: 2026-11-01 UTC | SSH-WRAPPER-001 | Initial implementation
# Supersedes: None
# Contracts: R3 hints/deployment.md; R2 machine-access index is read-only reference
# Tests: Pending Windows execution
# History/Predecessor: Adapted from read-only R2 reference branch engineering/canonical-shell-wrappers-20261101
param(
    [Parameter(Mandatory=$true)][string]$Alias,
    [Parameter(Mandatory=$true)][string]$ScriptPath,
    [switch]$CopyToClipboard
)
Clear-Host
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $ScriptPath -PathType Leaf)) {
    Write-Error "Script file not found: $ScriptPath"
    exit 2
}
$source = [IO.File]::ReadAllText((Resolve-Path -LiteralPath $ScriptPath).Path)
$lf = [string][char]10
$cr = [string][char]13
$source = $source.Replace($cr+$lf,$lf).Replace($cr,$lf).TrimEnd([char]10) + $lf
# A single-quoted source file preserves Bash variables and command substitutions.
$output = @($source | & ssh.exe -o BatchMode=yes -o ConnectTimeout=8 $Alias bash -s 2>&1)
$sshExitCode = $LASTEXITCODE
$report = (@("TARGET_ALIAS=$Alias") + @($output | ForEach-Object { [string]$_ }) + @("SSH_EXIT_CODE=$sshExitCode")) -join [Environment]::NewLine
Write-Output $report
if ($CopyToClipboard) {
    if (Get-Command Set-Clipboard -ErrorAction SilentlyContinue) {
        Set-Clipboard -Value $report
    } else {
        Write-Warning 'Clipboard utility unavailable.'
    }
}
exit $sshExitCode
