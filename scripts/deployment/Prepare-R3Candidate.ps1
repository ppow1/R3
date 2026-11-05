# R3 CONTROLLED SOURCE
# File: scripts/deployment/Prepare-R3Candidate.ps1
# Component: R3-MANIFEST-DEPLOY
# File Revision: 1.0.2
# Created: 2026-11-05 UTC (exact time not independently verified)
# Created By: ChatGPT GPT-6
# Purpose: Explicit build-only Windows to Camrui candidate preparation
# Execution Model: PowerShell 7, SSH stdin to bash, isolated Python candidate builder
# Observability: Console, clipboard, SSH exit code, candidate-local logs
# Dependencies: Deploy-R3.ps1 validator, ssh.exe, remote Git and Python
# Authority: Steward deployment-engine directive
# Changed: 2026-11-05 UTC | R3-MANIFEST-DEPLOY-011 | ChatGPT GPT-6 | Initial build-only bridge
# Changed: 2026-11-05 UTC | R3-MANIFEST-DEPLOY-012 | ChatGPT GPT-6 | Use literal remote here-string and validated substitution
# Changed: 2026-11-05 UTC | R3-MANIFEST-DEPLOY-013 | ChatGPT GPT-6 | Separate builder revision from release revision and fix SSH invocation
# Supersedes: None
# Superseded By: None
# Contracts: docs/runbooks/R3_MANIFEST_DEPLOYMENT.md
# Tests: Not yet executed on Windows or Camrui
# History/Predecessor: None
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Manifest,
    [Parameter(Mandatory=$true)][string]$CandidateRoot,
    [switch]$SkipClipboard
)
$ErrorActionPreference = 'Stop'
$log = [System.Collections.Generic.List[string]]::new()
$exitCode = 1
function Emit([string]$message) {
    Write-Host $message
    [void]$log.Add($message)
}
try {
    $manifestPath = (Resolve-Path -LiteralPath $Manifest -ErrorAction Stop).Path
    $validator = Join-Path $PSScriptRoot 'Deploy-R3.ps1'
    & $validator -Manifest $manifestPath -SkipClipboard
    if ($LASTEXITCODE -ne 0) { throw 'Manifest validator rejected the request' }
    $cfg = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json -Depth 32
    if ($cfg.source.type -cne 'github') { throw 'Build-only bridge requires exact GitHub source commit' }
    $commit = [string]$cfg.source.commit
    if ($commit -cnotmatch '^[a-fA-F0-9]{40}$') { throw 'Invalid source commit' }
    $alias = [string]$cfg.target.sshAlias
    if ($alias -cnotmatch '^[A-Za-z0-9_.-]+$') { throw 'Invalid SSH alias' }
    $req = [string]$cfg.dependencies.requirementsFile
    if ($req -cnotmatch '^[A-Za-z0-9_./-]+$' -or $req.StartsWith('/') -or
        $req.Split('/') -contains '..') { throw 'Unsafe requirements path' }
    $timeout = [int]$cfg.tests.timeoutSeconds
    if ($timeout -lt 1 -or $timeout -gt 1800) { throw 'Unsafe timeout' }
    if ($CandidateRoot -cnotmatch '^/home/admin1/[^\s\x27\x22;|&$\x60\\]+$' -or
        $CandidateRoot.Contains('..') -or $CandidateRoot.Contains('//')) {
        throw 'CandidateRoot must be a safe absolute path under /home/admin1'
    }
    if ($CandidateRoot -match '^/home/admin1/R3(?:/|$)' -or
        $CandidateRoot -match '^/home/admin1/\.config(?:/|$)') {
        throw 'CandidateRoot overlaps protected paths'
    }
    # Explicitly transmit only validated literals. Remote builder independently
    # checks real paths, Git identity, lockfile and non-overlap.
    $remote = @'
set -eu
cd /home/admin1/R3
git fetch origin main --quiet
tmp=$(mktemp -d /tmp/r3-builder-XXXXXXXX)
trap 'rm -rf "$tmp"' EXIT
git show origin/main:scripts/deployment/prepare_candidate.py > "$tmp/prepare_candidate.py"
echo '=== CANDIDATE BUILD ONLY ==='
echo 'SOURCE_COMMIT=__COMMIT__'
python3 "$tmp/prepare_candidate.py" --source /home/admin1/R3 --commit '__COMMIT__' --candidate-root '__TARGET__' --requirements '__REQUIREMENTS__' --timeout '__TIMEOUT__'
echo 'WEBSITE_ACTIVATION=NOT_RUN'
'@
    $remote = $remote.Replace('__COMMIT__', $commit).Replace('__TARGET__', $CandidateRoot).Replace('__REQUIREMENTS__', $req).Replace('__TIMEOUT__', [string]$timeout)
    Emit 'R3_CANDIDATE_BUILD_ONLY=TRUE'
    Emit "SOURCE_COMMIT=$commit"
    Emit "CANDIDATE_ROOT=$CandidateRoot"
    $result = @(($remote -replace "`r", "") | & ssh.exe -T $alias 'tr -d "\r" | bash -s' 2>&1)
    foreach ($line in $result) { Emit ([string]$line) }
    $sshExit = $LASTEXITCODE
    Emit "SSH_EXIT_CODE=$sshExit"
    if ($sshExit -ne 0) { throw 'Candidate build failed; see remote diagnostics' }
    Emit 'CANDIDATE_BRIDGE_PASS=TRUE'
    $exitCode = 0
} catch {
    Emit "ERROR=$($_.Exception.Message)"
} finally {
    Emit 'WEBSITE_ACTIVATION=NOT_RUN'
    if (-not $SkipClipboard) {
        try { Set-Clipboard -Value ($log -join [Environment]::NewLine) }
        catch { Write-Warning "Clipboard unavailable: $($_.Exception.Message)" }
    }
}
if ($exitCode -ne 0) { exit $exitCode }
