# R3 CONTROLLED SOURCE
# File: scripts/deployment/Deploy-R3.ps1
# Component: R3-MANIFEST-DEPLOY
# File Revision: 1.0.3
# Created: 2026-11-05 UTC (exact time not independently verified)
# Created By: ChatGPT GPT-6
# Purpose: Fail-closed manifest validation and deployment plan generator
# Execution Model: Windows PowerShell 7; local read-only validation
# Observability: Console, clipboard, explicit plan-only status
# Dependencies: PowerShell 7; JSON manifest; docs/runbooks/R3_MANIFEST_DEPLOYMENT.md
# Authority: Steward request for repository-owned deployment
# Changed: 2026-11-05 UTC | R3-MANIFEST-DEPLOY-003 | ChatGPT GPT-6 | Repair corrupted script; validate fields and refuse unverified activation
# Changed: 2026-11-05 UTC | R3-MANIFEST-DEPLOY-002 | ChatGPT GPT-6 | Dependency and test declarations
# Changed: 2026-11-05 UTC | R3-MANIFEST-DEPLOY-001 | ChatGPT GPT-6 | Initial plan-only runner
# Changed: 2026-11-04 UTC | R3-MANIFEST-DEPLOY-022 | ChatGPT GPT-6 | Explicitly return validator success exit status to calling bridge
# Supersedes: None (legacy scripts/Deploy-R3.ps1 retained)
# Superseded By: None
# Contracts: hints/file-provenance.md; docs/runbooks/R3_MANIFEST_DEPLOYMENT.md
# Tests: Not executed; must be validated in PowerShell 7 before production use
# History/Predecessor: Git blob 14ce83d42e001e29450c64403c0f5863a2974c38
[CmdletBinding()]
param(
    [Parameter(Position=0)]
    [string]$Manifest = (Join-Path $PSScriptRoot 'manifests/website.example.json'),
    [switch]$SkipClipboard
)
$ErrorActionPreference = 'Stop'
$lines = [System.Collections.Generic.List[string]]::new()
function Emit([string]$message) {
    Write-Host $message
    [void]$lines.Add($message)
}
$exitCode = 1
try {
    $manifestPath = (Resolve-Path -LiteralPath $Manifest -ErrorAction Stop).Path
    $cfg = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json -Depth 32
    if ($cfg.schemaVersion -ne 1) { throw 'Unsupported schemaVersion' }
    if ($cfg.source.type -notin @('github', 'local')) { throw 'source.type must be github or local' }
    if ($cfg.target.service -ne 'website') { throw 'Only website target is supported' }
    if ($cfg.target.sshAlias -cnotmatch '^[a-zA-Z0-9_.-]+$') { throw 'Invalid target.sshAlias' }
    if ($cfg.target.port -notmatch '^[0-9]+$' -or [int]$cfg.target.port -lt 1 -or [int]$cfg.target.port -gt 65535) {
        throw 'Invalid target.port'
    }
    if ($cfg.source.type -eq 'github') {
        if ($cfg.source.repositoryUrl -cne 'https://github.com/ppow1/R3.git') { throw 'Unapproved source.repositoryUrl' }
        if ($cfg.source.commit -cnotmatch '^[0-9a-fA-F]{40}$') { throw 'Supply exact 40-character source.commit' }
        $sourceDescription = "GitHub $($cfg.source.repositoryUrl) at $($cfg.source.commit)"
    } else {
        if (-not $cfg.source.path) { throw 'Local source requires source.path' }
        $local = (Resolve-Path -LiteralPath $cfg.source.path -ErrorAction Stop).Path
        if (-not (Test-Path -LiteralPath $local -PathType Container)) { throw 'Local source must be a directory' }
        $sourceDescription = "Local directory $local (not transferred)"
    }
    foreach ($key in @('releaseRoot', 'activeSymlink', 'venvPath', 'entrypoint', 'healthPath')) {
        if ([string]::IsNullOrWhiteSpace([string]$cfg.target.$key)) { throw "Missing target.$key" }
    }
    if (-not $cfg.dependencies -or $cfg.dependencies.manager -ne 'pip') { throw 'dependencies.manager must be pip' }
    if ($cfg.dependencies.installMode -ne 'locked') { throw 'dependencies.installMode must be locked' }
    $req = [string]$cfg.dependencies.requirementsFile
    if ($req -cnotmatch '^[a-zA-Z0-9_./-]+$' -or $req.StartsWith('/') -or $req.Split('/') -contains '..') {
        throw 'Invalid relative dependencies.requirementsFile'
    }
    if ([string]$cfg.dependencies.pythonVersion -notmatch '^3\.[0-9]+(\.[0-9]+)?$') {
        throw 'Specify Python major.minor or patch version'
    }
    if ($cfg.dependencies.hashesRequired -ne $true) { throw 'dependencies.hashesRequired must be true' }
    if (-not $cfg.tests -or $cfg.tests.profile -ne 'website') { throw 'tests.profile must be website' }
    if ($cfg.tests.timeoutSeconds -notmatch '^[0-9]+$' -or
        [int]$cfg.tests.timeoutSeconds -lt 1 -or [int]$cfg.tests.timeoutSeconds -gt 1800) {
        throw 'tests.timeoutSeconds must be 1..1800'
    }
    if ($cfg.tests.onFailure -ne 'abort-before-activation') { throw 'tests.onFailure must be abort-before-activation' }
    Emit 'R3_DEPLOYMENT_PLAN_ONLY=TRUE'
    Emit "MANIFEST=$manifestPath"
    Emit "SOURCE=$sourceDescription"
    Emit "HOST=$($cfg.target.sshAlias)"
    Emit "SERVICE=$($cfg.target.service)"
    Emit "PORT=$($cfg.target.port)"
    Emit "RELEASE_ROOT=$($cfg.target.releaseRoot) (unverified)"
    Emit "ACTIVE_LINK=$($cfg.target.activeSymlink) (unverified)"
    Emit "ENTRYPOINT=$($cfg.target.entrypoint)"
    Emit "DEPENDENCY_LOCKFILE=$req (existence unverified)"
    Emit "DEPENDENCY_PYTHON=$($cfg.dependencies.pythonVersion)"
    Emit "TEST_COMMAND=python -m unittest discover -s tests -p 'test_*.py' -v (candidate; not executed)"
    Emit "TEST_TIMEOUT_SECONDS=$($cfg.tests.timeoutSeconds)"
    Emit 'DEPENDENCY_INSTALL=NOT_RUN'
    Emit 'REGRESSION_PASS=NOT_RUN'
    Emit 'ACTIVATION=DISABLED'
    Emit 'DEPLOY_PASS=NOT_RUN'
    Emit 'ACCEPTANCE_PASS=NOT_RUN'
    $exitCode = 0
} catch {
    Emit "ERROR=$($_.Exception.Message)"
} finally {
    $report = $lines -join [Environment]::NewLine
    if (-not $SkipClipboard) {
        try { Set-Clipboard -Value $report } catch { Write-Warning "Clipboard unavailable: $($_.Exception.Message)" }
    }
}
exit $exitCode
