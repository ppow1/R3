# R3 CONTROLLED SOURCE
# File: scripts/deployment/Deploy-R3.ps1
# Component: R3-MANIFEST-DEPLOY
# File Revision: 1.0.1
# Created: 2026-11-05 UTC (exact time not independently verified)
# Created By: ChatGPT GPT-6
# Purpose: Safe phase-1 manifest validator and deployment plan generator
# Execution Model: Windows PowerShell 7, local read-only validation
# Observability: Console, clipboard, explicit plan-only status
# Dependencies: PowerShell 7; JSON manifest; docs/runbooks/R3_MANIFEST_DEPLOYMENT.md
# Authority: Steward request for R3 repository-owned manifest-driven deployment
# Changed: 2026-11-05 UTC | R3-MANIFEST-DEPLOY-002 | ChatGPT GPT-6 | Validate declared dependency and test profiles without executing them
# Changed: 2026-11-05 UTC | R3-MANIFEST-DEPLOY-001 | ChatGPT GPT-6 | Initial plan-only runner
# Supersedes: None (legacy scripts/Deploy-R3.ps1 retained)
# Superseded By: None
# Contracts: hints/file-provenance.md; docs/runbooks/R3_MANIFEST_DEPLOYMENT.md
# Tests: Not executed against live Camrui; activation intentionally disabled
# History/Predecessor: Git blob facdd3cd86bd49086106de8509dbd34901c0b510
[CmdletBinding()]
param(
    [Parameter(Position=0)]
    [string]$Manifest = (Join-Path $PSScriptRoot 'manifests/website.example.json'),
    [switch]$SkipClipboard
)
$ErrorActionPreference = 'Stop'
Clear-Host
$lines = [System.Collections.Generic.List[string]]::new()
function Emit([string]$s) { Write-Host $s; $lines.Add($s) }
try {
    $path = (Resolve-Path -LiteralPath $Manifest).Path
    $cfg = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json -Depth 32
    if ($cfg.schemaVersion -ne 1) { throw 'Unsupported schemaVersion' }
    if ($cfg.source.type -notin @('github','local')) { throw 'source.type must be github or local' }
    if ($cfg.target.service -ne 'website') { throw 'This first-phase validator only accepts website targets' }
    if ($cfg.target.sshAlias -notmatch '^[a-zA-Z0-9_.-]+$') { throw 'Invalid SSH alias' }
    if ($cfg.target.port -lt 1 -or $cfg.target.port -gt 65535) { throw 'Invalid port' }
    if ($cfg.source.type -eq 'github') {
        if ($cfg.source.repositoryUrl -ne 'https://github.com/ppow1/R3.git') { throw 'Repository URL is not approved' }
        if ($cfg.source.commit -cnotmatch '^[0-9a-fA-F]{40}$') { throw 'Supply an exact 40-character Git commit SHA' }
        $sourceDescription = "GitHub $($cfg.source.repositoryUrl) at $($cfg.source.commit)"
    } else {
        if (-not $cfg.source.path) { throw 'Local source requires source.path' }
        $local = (Resolve-Path -LiteralPath $cfg.source.path).Path
        if (-not (Test-Path -LiteralPath $local -PathType Container)) { throw 'Local source must be a directory' }
        $sourceDescription = "Local directory $local"
    }
    foreach ($key in @('releaseRoot','activeSymlink','venvPath','entrypoint','healthPath')) {
        if (-not $cfg.target.$key) { throw "Missing target.$key" }
    }
    if (-not $cfg.dependencies) { throw 'Missing dependencies section' }
    if ($cfg.dependencies.manager -ne 'pip') { throw 'Only pip dependency declarations are supported in phase 1' }
    if ($cfg.dependencies.installMode -ne 'locked') { throw 'Dependencies must use installMode=locked' }
    if ($cfg.dependencies.requirementsFile -notmatch '^[a-zA-Z0-9_./-]+
    Emit "MANIFEST=$path"
    Emit "SOURCE=$sourceDescription"
    Emit "HOST=$($cfg.target.sshAlias)"
    Emit "SERVICE=$($cfg.target.service)"
    Emit "PORT=$($cfg.target.port)"
    Emit "RELEASE_ROOT=$($cfg.target.releaseRoot)"
    Emit "ACTIVE_LINK=$($cfg.target.activeSymlink)"
    Emit "ENTRYPOINT=$($cfg.target.entrypoint)"
    Emit "HEALTH_PATH=$($cfg.target.healthPath)"
    Emit 'ACTIVATION=DISABLED_PENDING_LIVE_TOPOLOGY_VERIFICATION'
    Emit 'DEPLOY_PASS=NOT_RUN'
    Emit 'ACCEPTANCE_PASS=NOT_RUN'
    $exitCode = 0
} catch {
    Emit "ERROR=$($_.Exception.Message)"
    $exitCode = 1
} finally {
    $report = $lines -join [Environment]::NewLine
    if (-not $SkipClipboard) {
        try { Set-Clipboard -Value $report } catch { Write-Warning "Clipboard unavailable: $($_.Exception.Message)" }
    }
}
if ($exitCode -ne 0) { exit $exitCode }
 -or
        $cfg.dependencies.requirementsFile.StartsWith('/') -or
        $cfg.dependencies.requirementsFile.Contains('..')) { throw 'Invalid relative requirementsFile path' }
    if ($cfg.dependencies.pythonVersion -notmatch '^3\.[0-9]+(\.[0-9]+)?
    Emit "MANIFEST=$path"
    Emit "SOURCE=$sourceDescription"
    Emit "HOST=$($cfg.target.sshAlias)"
    Emit "SERVICE=$($cfg.target.service)"
    Emit "PORT=$($cfg.target.port)"
    Emit "RELEASE_ROOT=$($cfg.target.releaseRoot)"
    Emit "ACTIVE_LINK=$($cfg.target.activeSymlink)"
    Emit "ENTRYPOINT=$($cfg.target.entrypoint)"
    Emit "HEALTH_PATH=$($cfg.target.healthPath)"
    Emit 'ACTIVATION=DISABLED_PENDING_LIVE_TOPOLOGY_VERIFICATION'
    Emit 'DEPLOY_PASS=NOT_RUN'
    Emit 'ACCEPTANCE_PASS=NOT_RUN'
    $exitCode = 0
} catch {
    Emit "ERROR=$($_.Exception.Message)"
    $exitCode = 1
} finally {
    $report = $lines -join [Environment]::NewLine
    if (-not $SkipClipboard) {
        try { Set-Clipboard -Value $report } catch { Write-Warning "Clipboard unavailable: $($_.Exception.Message)" }
    }
}
if ($exitCode -ne 0) { exit $exitCode }
) { throw 'Declare an exact Python major.minor or patch version' }
    if ($cfg.dependencies.hashesRequired -ne $true) { throw 'Dependency hashes must be required' }
    if (-not $cfg.tests -or $cfg.tests.profile -ne 'website') { throw 'Missing or unsupported tests.profile' }
    if ($cfg.tests.timeoutSeconds -lt 1 -or $cfg.tests.timeoutSeconds -gt 1800) { throw 'tests.timeoutSeconds must be 1..1800' }
    if ($cfg.tests.onFailure -ne 'abort-before-activation') { throw 'Tests must abort before activation on failure' }
    Emit 'R3_DEPLOYMENT_PLAN_ONLY=TRUE'
    Emit "DEPENDENCY_MANAGER=$($cfg.dependencies.manager)"
    Emit "DEPENDENCY_PYTHON=$($cfg.dependencies.pythonVersion)"
    Emit "DEPENDENCY_LOCKFILE=$($cfg.dependencies.requirementsFile)"
    Emit "DEPENDENCY_HASHES_REQUIRED=$($cfg.dependencies.hashesRequired)"
    Emit "TEST_PROFILE=$($cfg.tests.profile)"
    Emit "TEST_TIMEOUT_SECONDS=$($cfg.tests.timeoutSeconds)"
    Emit 'DEPENDENCY_INSTALL=NOT_RUN'
    Emit 'REGRESSION_PASS=NOT_RUN'
    Emit "MANIFEST=$path"
    Emit "SOURCE=$sourceDescription"
    Emit "HOST=$($cfg.target.sshAlias)"
    Emit "SERVICE=$($cfg.target.service)"
    Emit "PORT=$($cfg.target.port)"
    Emit "RELEASE_ROOT=$($cfg.target.releaseRoot)"
    Emit "ACTIVE_LINK=$($cfg.target.activeSymlink)"
    Emit "ENTRYPOINT=$($cfg.target.entrypoint)"
    Emit "HEALTH_PATH=$($cfg.target.healthPath)"
    Emit 'ACTIVATION=DISABLED_PENDING_LIVE_TOPOLOGY_VERIFICATION'
    Emit 'DEPLOY_PASS=NOT_RUN'
    Emit 'ACCEPTANCE_PASS=NOT_RUN'
    $exitCode = 0
} catch {
    Emit "ERROR=$($_.Exception.Message)"
    $exitCode = 1
} finally {
    $report = $lines -join [Environment]::NewLine
    if (-not $SkipClipboard) {
        try { Set-Clipboard -Value $report } catch { Write-Warning "Clipboard unavailable: $($_.Exception.Message)" }
    }
}
if ($exitCode -ne 0) { exit $exitCode }
