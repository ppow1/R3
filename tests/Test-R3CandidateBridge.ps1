# R3 CONTROLLED SOURCE
# File: tests/Test-R3CandidateBridge.ps1
# Component: R3-MANIFEST-DEPLOY
# File Revision: 1.0.0
# Created: 2026-11-05 UTC (exact time not independently verified)
# Created By: ChatGPT GPT-6
# Purpose: Permanent PowerShell 7 offline bridge regression tests
# Execution Model: Local only; invokes bridge with invalid paths, no SSH permitted
# Observability: Assertions and nonzero exit on failure
# Dependencies: PowerShell 7, scripts/deployment/Prepare-R3Candidate.ps1
# Authority: Steward permanent regression policy
# Changed: 2026-11-05 UTC | R3-MANIFEST-DEPLOY-015 | ChatGPT GPT-6 | Initial bridge validation tests
# Supersedes: None
# Superseded By: None
# Contracts: docs/runbooks/R3_MANIFEST_DEPLOYMENT.md
# Tests: Not yet executed on Windows
# History/Predecessor: None
$ErrorActionPreference = 'Stop'
$bridge = Join-Path $PSScriptRoot '../scripts/deployment/Prepare-R3Candidate.ps1'
$validator = Join-Path $PSScriptRoot '../scripts/deployment/Deploy-R3.ps1'
$passed = 0
$failed = 0

function Assert-True([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}
function Test-Parser([string]$Path) {
    $tokens = $null
    $errors = $null
    [System.Management.Automation.Language.Parser]::ParseFile(
        (Resolve-Path $Path).Path, [ref]$tokens, [ref]$errors) | Out-Null
    Assert-True ($errors.Count -eq 0) "Parser errors in $Path : $($errors | Out-String)"
}
function Test-Case([string]$Name, [scriptblock]$Action) {
    try {
        & $Action
        $script:passed++
        Write-Host "PASS $Name"
    } catch {
        $script:failed++
        Write-Host "FAIL $Name : $($_.Exception.Message)"
    }
}
Test-Case 'bridge parses' { Test-Parser $bridge }
Test-Case 'validator parses' { Test-Parser $validator }

# This test runs each invalid request in its own PowerShell process. Even if
# the bridge calls exit 1, the test harness remains alive.
Test-Case 'unsafe paths fail before SSH' {
    $manifest = Join-Path ([IO.Path]::GetTempPath()) ("r3-bridge-" + [guid]::NewGuid().ToString('N') + '.json')
    try {
        $fixture = @{
            schemaVersion = 1
            source = @{ type='github'; repositoryUrl='https://github.com/ppow1/R3.git'; commit=('a'*40) }
            target = @{ service='website'; sshAlias='camrui'; port=18303; releaseRoot='/tmp/releases'; activeSymlink='/tmp/active'; venvPath='/tmp/venv'; entrypoint='r3_app:app'; healthPath='/health' }
            dependencies = @{ manager='pip'; installMode='locked'; requirementsFile='requirements-deploy.lock'; pythonVersion='3.12'; hashesRequired=$true }
            tests = @{ profile='website'; timeoutSeconds=30; onFailure='abort-before-activation' }
        }
        $fixture | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $manifest
        foreach ($unsafe in @('/home/admin1/R3/overwrite',
                              '/home/admin1/candidate$(touch /tmp/r3-pwned)',
                              '/home/admin1/candidate'';echo bad',
                              '/home/admin1/../tmp/candidate',
                              '/tmp/candidate')) {
            $output = & pwsh -NoProfile -NonInteractive -File $bridge -Manifest $manifest -CandidateRoot $unsafe -SkipClipboard 2>&1 | Out-String
            Assert-True ($LASTEXITCODE -ne 0) "Accepted unsafe path: $unsafe"
            Assert-True ($output -match 'ERROR=') "No failure diagnostics for: $unsafe"
            Assert-True ($output -notmatch 'R3_CANDIDATE_BUILD_ONLY=TRUE') "Attempted SSH for unsafe path: $unsafe"
        }
    } finally {
        Remove-Item -LiteralPath $manifest -ErrorAction SilentlyContinue
    }
}
Write-Host "BRIDGE_TESTS_PASS=$passed"
Write-Host "BRIDGE_TESTS_FAIL=$failed"
Write-Host 'WEBSITE_ACTIVATION=NOT_RUN'
if ($failed -gt 0) { exit 1 }
